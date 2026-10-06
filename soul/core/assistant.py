from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from soul.voice.recorder import PushToTalkRecorder
from soul.voice.text_stream import SpeechTextStream
from soul.core.state import State
from soul.core.session import Session
from soul.utils.timing import TurnMetrics
from soul.utils.errors import friendly_error

HELP = """/help                 Show commands
/status               Runtime, history and last turn metrics
/models               Configured Gemini models
/mode fast|full        Fast Flash-Lite or full configured Gemini model
/tools                List capabilities and risk levels
/memory [list]        List persistent memories
/memory clear         Delete all memories after confirmation
/forget <id>          Delete one memory after confirmation
/reset                Clear working conversation
/voice on|off         Toggle voice for this session
/debug                Toggle diagnostic logging and metrics
/clear                Clear the terminal
/exit                 Shut down"""

class Assistant:
    def __init__(self, settings, brain, memory, working, voice, state, renderer, input_provider):
        self.settings, self.brain, self.memory = settings, brain, memory
        self.working, self.voice, self.state = working, voice, state
        self.ui, self.input = renderer, input_provider
        self.session = Session()
        self.logger = logging.getLogger("soul")
        self.desktop_context = None
        self.voice_task = None
        self.memory_task = None
        self.memory_queue = asyncio.Queue(maxsize=20)
        self.events = getattr(state, "events", None)
        self.active_turn: asyncio.Task | None = None
        self.microphone: PushToTalkRecorder | None = None
        self.microphone_timeout: asyncio.Task | None = None
        self.transcription_task: asyncio.Task | None = None
        self.continuous_task: asyncio.Task | None = None
        self.continuous_listening = False
        self.continuous_phase = "off"
        self._turn_in_progress = False
        self._continuous_pending = False
        self._closing = False
        self.confirm_callback = None

    async def cancel_current(self) -> None:
        """Cancel future actions while retaining receipts for anything already dispatched."""
        await self._pause_continuous_capture()
        if hasattr(self.brain, "cancel"):
            self.brain.cancel()
        elif getattr(self.brain, "executor", None):
            self.brain.executor.stopped = True
        if self.active_turn and not self.active_turn.done():
            self.active_turn.cancel()
            await asyncio.gather(self.active_turn, return_exceptions=True)
        await self.cancel_listening()
        if self.transcription_task and not self.transcription_task.done():
            self.transcription_task.cancel()
            await asyncio.gather(self.transcription_task, return_exceptions=True)
        self.transcription_task = None
        await self.stop_voice()
        if getattr(self.brain, "vision", None):
            self.brain.vision.clear()
        if self.state.current != State.SHUTTING_DOWN:
            self.state.set(State.INTERRUPTED)
        self._continuous_pending = False
        self._ensure_continuous_task()

    def _continuous_status(self, phase: str) -> None:
        if phase == self.continuous_phase:
            return
        self.continuous_phase = phase
        if self.events:
            self.events.publish("ContinuousListeningChanged", {"enabled": self.continuous_listening, "phase": phase})

    async def _pause_continuous_capture(self) -> None:
        task, self.continuous_task = self.continuous_task, None
        if task and task is not asyncio.current_task():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self.continuous_listening:
            self._continuous_status("paused")

    def _ensure_continuous_task(self) -> None:
        if self.continuous_listening and not self._closing and (self.continuous_task is None or self.continuous_task.done()):
            self.continuous_task = asyncio.create_task(self._continuous_loop())

    async def set_continuous_listening(self, enabled: bool) -> bool:
        if enabled and (not self.settings.soul_microphone_enabled or self._closing):
            raise ValueError("Enable the microphone in Voice settings first.")
        if enabled and not hasattr(self.input, "replace_pending"):
            raise ValueError("Continuous listening requires the desktop input interface.")
        if enabled == self.continuous_listening:
            return enabled
        self.continuous_listening = enabled
        if not enabled:
            await self._pause_continuous_capture()
            await self.cancel_listening()
            self._continuous_pending = False
        elif self.microphone is not None:
            await self.cancel_listening()
        self._continuous_status("paused" if enabled else "off")
        self._ensure_continuous_task()
        return enabled

    def _continuous_busy(self) -> bool:
        pending_input = getattr(getattr(self.input, "queue", None), "empty", lambda: True)() is False
        return bool(self._turn_in_progress or self._continuous_pending or pending_input
                    or (self.active_turn and not self.active_turn.done())
                    or (self.voice_task and not self.voice_task.done())
                    or (self.transcription_task and not self.transcription_task.done())
                    or self.state.current == State.WAITING_CONFIRMATION)

    async def _continuous_loop(self) -> None:
        try:
            while self.continuous_listening and not self._closing:
                if self._continuous_busy():
                    self._continuous_status("paused")
                    await asyncio.sleep(0.1)
                    continue
                await self._open_microphone(continuous=True)
                recorder = self.microphone
                if recorder is None:
                    continue
                self._continuous_status("listening")
                await recorder.wait_for_endpoint()
                if self.microphone is not recorder:
                    continue
                self._continuous_status("paused")
                if not recorder.speech_detected:
                    await self.cancel_listening()
                    continue
                transcript = await self.finish_listening()
                if transcript and self.continuous_listening:
                    self._continuous_pending = True
                    self.input.replace_pending(transcript)
                elif self.state.current != State.SHUTTING_DOWN:
                    self.state.set(State.READY)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.continuous_listening = False
            self._continuous_status("off")
            self.state.set(State.ERROR)
            self.logger.exception("continuous_listening_failed")
            self.ui.error("Continuous listening stopped. " + friendly_error(exc))
        finally:
            await self.cancel_listening()

    async def start_listening(self) -> bool:
        if not self.settings.soul_microphone_enabled:
            self.ui.error("Microphone input is disabled in Settings.")
            return False
        if self.microphone is not None and not self.continuous_listening:
            return False
        await self.set_continuous_listening(False)
        await self.cancel_current()
        await self._open_microphone()
        return True

    async def _open_microphone(self, continuous: bool = False) -> None:
        if self.microphone is not None:
            return
        loop = asyncio.get_running_loop()
        def amplitude(level):
            if self.events:
                loop.call_soon_threadsafe(self.events.publish, "MicrophoneAmplitude", {"amplitude": level})
        self.microphone = PushToTalkRecorder(self.settings.soul_microphone_max_seconds, on_amplitude=amplitude,
            silence_seconds=getattr(self.settings, "soul_microphone_silence_seconds", 0.8) if continuous else None)
        try:
            await self.microphone.start()
        except BaseException:
            await self.cancel_listening()
            if not asyncio.current_task().cancelling():
                self.state.set(State.ERROR)
            raise
        self.state.set(State.LISTENING)
        if self.events:
            self.events.publish("MicrophoneStarted", {"max_seconds": self.settings.soul_microphone_max_seconds,
                                                      "continuous": continuous})
        if continuous:
            return
        async def limit_capture():
            await asyncio.sleep(self.settings.soul_microphone_max_seconds)
            await self.cancel_listening()
            self.ui.notice("Microphone stopped at the recording limit. Hold the microphone button to try again.")
        self.microphone_timeout = asyncio.create_task(limit_capture())

    async def cancel_listening(self) -> None:
        timer, self.microphone_timeout = self.microphone_timeout, None
        if timer and timer is not asyncio.current_task():
            timer.cancel()
            await asyncio.gather(timer, return_exceptions=True)
        recorder, self.microphone = self.microphone, None
        if recorder:
            await recorder.finish(discard=True)
            if self.events:
                self.events.publish("MicrophoneStopped", {})
            if self.state.current == State.LISTENING:
                self.state.set(State.IDLE)

    async def finish_listening(self) -> str:
        timer, self.microphone_timeout = self.microphone_timeout, None
        if timer:
            timer.cancel()
            await asyncio.gather(timer, return_exceptions=True)
        recorder, self.microphone = self.microphone, None
        if recorder is None:
            return ""
        audio = await recorder.finish()
        if self.events:
            self.events.publish("MicrophoneStopped", {})
        if not audio:
            self.state.set(State.IDLE)
            return ""
        self.state.set(State.THINKING)
        try:
            async with asyncio.timeout(self.settings.soul_request_timeout + 1):
                self.transcription_task = asyncio.create_task(self.brain.client.transcribe(audio, "audio/wav"))
                transcript = await self.transcription_task
            return transcript.strip()[:8000]
        except asyncio.CancelledError:
            self.state.set(State.INTERRUPTED)
            raise
        except Exception:
            self.state.set(State.ERROR)
            raise
        finally:
            self.transcription_task = None
            audio = b""

    async def stop_voice(self):
        if self.voice_task and not self.voice_task.done():
            self.voice_task.cancel()
            await asyncio.gather(self.voice_task, return_exceptions=True)
        self.voice_task = None

    async def save_memories(self):
        while True:
            text, context, metrics = await self.memory_queue.get()
            start = perf_counter()
            try:
                count = await self.memory.extract(text, context=context) if self.settings.soul_memory_enabled else 0
                if count:
                    self.ui.notice(f"  Memory saved · {count} fact(s)")
            except Exception:
                self.logger.exception("memory_extraction_failed")
                self.ui.error("  Memory could not be saved for the last turn.")
            finally:
                metrics.extraction_seconds = perf_counter() - start
                self.memory_queue.task_done()

    async def flush_memory(self):
        if self.memory_task:
            await self.memory_queue.join()

    async def speak(self, answer, metrics):
        try:
            await self.voice.speak(answer, self.state, metrics)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.logger.exception("voice_failed")
            self.ui.error("  Voice unavailable; text preserved. " + friendly_error(exc))
        finally:
            if not self._turn_in_progress and self.state.current != State.SHUTTING_DOWN:
                self.state.set(State.READY)

    async def speak_stream(self, stream, metrics):
        try:
            await self.voice.speak_stream(stream, self.state, metrics)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.logger.exception("voice_failed")
            self.ui.error("Voice unavailable; text preserved. " + friendly_error(exc))
        finally:
            if self.events:
                self.events.publish("VoiceMetrics", {
                    "first_audio_seconds": metrics.first_audio_seconds,
                    "tts_seconds": metrics.tts_seconds,
                    "playback_seconds": metrics.playback_seconds,
                    "engine": getattr(getattr(self.voice, "generator", None), "engine", ""),
                    "voice": getattr(getattr(self.voice, "generator", None), "voice_name", ""),
                })
            if not self._turn_in_progress and self.state.current != State.SHUTTING_DOWN:
                self.state.set(State.READY)

    async def close(self):
        self._closing = True
        await self.set_continuous_listening(False)
        await self.cancel_current()
        await self.stop_voice()
        if self.memory_task:
            try:
                async with asyncio.timeout(self.settings.soul_request_timeout + 2):
                    await self.flush_memory()
            except TimeoutError:
                self.ui.notice("Some memory updates could not finish before shutdown.")
            self.memory_task.cancel()
            await asyncio.gather(self.memory_task, return_exceptions=True)

    async def run(self):
        self.ui.startup(self.settings, self.memory is not None)
        self.state.set(State.READY)
        while True:
            try:
                text = (await self.input.get_input()).strip()
                self._continuous_pending = False
                if not text:
                    continue
                if text.startswith("/"):
                    self._turn_in_progress = True
                    try:
                        if not await self.command(text):
                            break
                    finally:
                        self._turn_in_progress = False
                else:
                    self.active_turn = asyncio.create_task(self.turn(text))
                    try:
                        await self.active_turn
                    except asyncio.CancelledError:
                        if self._closing:
                            raise
                    finally:
                        self.active_turn = None
            except EOFError:
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.state.set(State.ERROR)
                self.logger.exception("runtime_error")
                self.ui.error(friendly_error(exc))
                self.state.set(State.READY)

    async def turn(self, text):
        self._turn_in_progress = True
        self._continuous_pending = False
        await self.stop_voice()
        await self.cancel_listening()
        start = perf_counter()
        metrics = TurnMetrics()
        speech_stream = None
        if self.settings.soul_tts_enabled and hasattr(self.voice, "speak_stream"):
            speech_stream = SpeechTextStream(getattr(self.settings, "soul_tts_max_characters", 12000))
            self.voice_task = asyncio.create_task(self.speak_stream(speech_stream, metrics))
        if self.events:
            self.events.publish("UserMessageReceived", {"text": text})
        self.state.set(State.PROCESSING)
        try:
            memories = []
            if self.memory and self.settings.soul_memory_enabled:
                self.state.set(State.RETRIEVING_MEMORY)
                timer = perf_counter()
                try:
                    # Include the most recent user topic for short follow-ups.
                    previous = next((m.text for m in reversed(self.working.messages) if m.role == "user"), "")
                    memories = self.memory.retrieve(text + " " + previous)
                except Exception:
                    self.logger.exception("memory_retrieval_failed")
                    self.ui.error("Memory retrieval failed; continuing with conversation context.")
                finally:
                    metrics.retrieval_seconds = perf_counter() - timer
            self.state.set(State.THINKING)
            timer = perf_counter()
            try:
                with self.ui.response() as append:
                    def on_chunk(chunk):
                        if metrics.first_token_seconds is None:
                            metrics.first_token_seconds = perf_counter() - start
                        self.state.set(State.RESPONDING)
                        append(chunk)
                        if speech_stream and self.settings.soul_tts_enabled and self.voice_task and not self.voice_task.done():
                            speech_stream.feed(chunk)
                    answer = await self.brain.respond(self.working, text, memories, on_chunk, metrics)
            finally:
                if metrics.gemini_seconds is None:
                    metrics.gemini_seconds = perf_counter() - timer
                executor = getattr(self.brain, "executor", None)
                if executor:
                    metrics.tool_seconds = sum(record["seconds"] for record in executor.records)
                    metrics.tool_calls = len(executor.records)
            self.working.commit(text, answer)
            if speech_stream:
                speech_stream.finish()
                if speech_stream.truncated:
                    self.ui.notice(f"Voice reached the {speech_stream.max_characters:,}-character limit; the full response is available as text.")
            self.session.turns += 1
            if self.events:
                self.events.publish("TurnCompleted", {
                    "input_tokens": metrics.input_tokens or 0,
                    "output_tokens": metrics.output_tokens or 0,
                    "gemini_seconds": round(metrics.gemini_seconds or 0, 2),
                    "tool_seconds": round(metrics.tool_seconds or 0, 2),
                    "model": metrics.model_used or self.settings.gemini_text_model,
                    "first_token_seconds": round(metrics.first_token_seconds or 0, 2) if metrics.first_token_seconds else 0,
                    "turns": self.session.turns,
                })
            if self.memory and self.settings.soul_memory_enabled:
                if self.memory_task is None:
                    self.memory_task = asyncio.create_task(self.save_memories())
                context = self.brain.memory_context() if hasattr(self.brain, "memory_context") else {}
                await self.memory_queue.put((text, dict(context), metrics))
            if self.settings.soul_tts_enabled:
                if speech_stream is None:
                    self.voice_task = asyncio.create_task(self.speak(answer, metrics))
                if not self.settings.soul_background_voice:
                    await self.voice_task
        except asyncio.CancelledError:
            await self.stop_voice()
            self.state.set(State.INTERRUPTED)
            executor = getattr(self.brain, "executor", None)
            records = executor.records if executor else []
            report = "Task stopped. " + ("Tool receipts: " + "; ".join(
                f"{r['name']}: {r['message']}" for r in records) if records else "No completed tool receipts.")
            self.ui.notice(report)
            if records:
                self.working.commit(text, report)
            raise
        except Exception as exc:
            await self.stop_voice()
            self.state.set(State.ERROR)
            self.logger.exception("turn_failed")
            self.ui.error(friendly_error(exc) + " Any partial response was not saved to conversation history.")
            executor = getattr(self.brain, "executor", None)
            if executor and executor.records:
                report = "Request interrupted. Actual tool receipts: " + "; ".join(
                    f"{r['name']}: {r['message']} (desired UI result verified: {r.get('desired_result_verified')})"
                    for r in executor.records)
                self.ui.notice(report)
                self.working.commit(text, report)
        finally:
            self._turn_in_progress = False
            self._continuous_pending = False
            if self.desktop_context and self.desktop_context.console_handle:
                try:
                    await self.desktop_context.bridge.call("focus_window", handle=self.desktop_context.console_handle)
                except Exception:
                    self.ui.notice("Select the Soul terminal to enter your next command.")
            metrics.total_seconds = perf_counter() - start
            metrics.model_used = getattr(self.brain.client, "active_model", None)
            task = getattr(self.brain, "last_task", None)
            if task:
                metrics.task_id = task.task_id
                metrics.retry_count = sum(getattr(task, "retries", {}).values())
            vision = getattr(self.brain, "vision", None)
            if vision:
                timings = getattr(vision, "metrics", {})
                for field, value in timings.items():
                    if hasattr(metrics, field):
                        setattr(metrics, field, value)
            self.session.last_metrics = metrics
            self.logger.info("turn_metrics %s", metrics.values())
            if self.settings.soul_debug:
                self.ui.notice(str(metrics.values()))
            if self.events:
                self.events.publish("TurnMetrics", metrics.values(), task_id=metrics.task_id)
            if not (self.voice_task and not self.voice_task.done()) and self.state.current not in {State.SUCCESS, State.INTERRUPTED, State.ERROR, State.SHUTTING_DOWN}:
                self.state.set(State.READY)

    async def confirm(self, description):
        if self.confirm_callback:
            return await self.confirm_callback(description)
        self.ui.notice(description + " Type DELETE to confirm; anything else cancels.")
        return (await self.input.get_input()).strip() == "DELETE"

    async def command(self, text):
        words = text.split()
        command, args = words[0].lower(), words[1:]
        if command in {"/memory", "/forget", "/reset"}:
            await self.flush_memory()
        if command == "/exit" and not args:
            return False
        if command == "/help" and not args:
            self.ui.notice(HELP)
        elif command == "/status" and not args:
            self.ui.notice(f"State: {self.state.current.value} | Gemini: {'verified' if self.brain.client.verified else 'unverified'} | Voice: {'on' if self.settings.soul_tts_enabled else 'off'}")
            self.ui.notice(f"Memory: {'enabled' if self.memory else 'disabled/unavailable'} | Working turns: {len(self.working.messages)//2} | Session turns: {self.session.turns}")
            metrics = self.session.last_metrics
            parts = []
            if metrics.first_token_seconds is not None:
                parts.append(f"First text {metrics.first_token_seconds:.2f}s")
            if metrics.total_seconds is not None:
                parts.append(f"Reply {metrics.total_seconds:.2f}s")
            if metrics.tool_calls is not None:
                parts.append(f"{metrics.tool_calls} actions")
            if metrics.tts_seconds is not None:
                parts.append(f"Voice generation {metrics.tts_seconds:.2f}s")
            self.ui.notice(" · ".join(parts) if parts else "No conversation yet.")
        elif command == "/models" and not args:
            self.ui.notice(f"Text: {self.settings.gemini_text_model}\nVoice: {self.settings.gemini_voice_model} ({self.settings.gemini_voice_name})\nThese are configured identifiers; access is verified only when used.")
            self.ui.notice(f"Fallback: {self.settings.gemini_fallback_model or 'disabled'} | Active: {getattr(self.brain.client, 'active_model', self.settings.gemini_text_model)}")
        elif command == "/mode" and args in (["fast"], ["full"]):
            self.settings.soul_response_mode = args[0]
            self.brain.client.primary_cooldown = 0.0
            self.ui.notice("Response mode: " + args[0])
        elif command == "/tools" and not args:
            executor = getattr(self.brain, "executor", None)
            if executor:
                for tool in executor.registry.tools.values():
                    self.ui.notice(f"{tool.name} · {tool.risk.value}")
            else:
                self.ui.notice("Tools are disabled.")
        elif command in ("/memory", "/forget"):
            if not self.memory:
                self.ui.notice("Persistent memory is disabled or unavailable.")
            elif command == "/memory" and args in ([], ["list"]):
                self.ui.memories(self.memory.store.list())
            elif command == "/memory" and args == ["clear"]:
                if await self.confirm("Delete ALL persistent memories and clear working context?"):
                    self.memory.store.clear()
                    self.working.clear()
                    if hasattr(self.brain, "clear_context"):
                        self.brain.clear_context()
                    self.ui.notice("Persistent and working memory cleared.")
                else:
                    self.ui.notice("Cancelled.")
            elif command == "/forget" and len(args) == 1 and args[0].isdigit():
                memory_id = int(args[0])
                match = next((m for m in self.memory.store.list() if m.id == memory_id), None)
                if match is None:
                    self.ui.notice("No memory with that ID.")
                elif await self.confirm(f"Delete memory {memory_id}: {match.content} and clear working context?"):
                    self.memory.store.delete(memory_id)
                    self.working.clear()
                    if hasattr(self.brain, "clear_context"):
                        self.brain.clear_context()
                    self.ui.notice("Memory deleted; working context cleared.")
                else:
                    self.ui.notice("Cancelled.")
            else:
                self.ui.notice("Usage: /memory [list|clear] or /forget <id>")
        elif command == "/reset" and not args:
            self.working.clear()
            if hasattr(self.brain, "clear_context"):
                self.brain.clear_context()
            self.ui.notice("Working conversation cleared. Persistent memories retained.")
        elif command == "/voice" and args in (["on"], ["off"]):
            self.settings.soul_tts_enabled = args[0] == "on"
            if args == ["off"]:
                await self.stop_voice()
            self.ui.notice("Voice " + args[0])
        elif command == "/debug" and not args:
            self.settings.soul_debug = not self.settings.soul_debug
            self.logger.setLevel(logging.DEBUG if self.settings.soul_debug else logging.INFO)
            self.ui.notice(f"Debug {'on' if self.settings.soul_debug else 'off'}")
        elif command == "/clear" and not args:
            self.ui.console.clear()
        else:
            self.ui.notice("Unknown command or arguments. Use /help.")
        return True
