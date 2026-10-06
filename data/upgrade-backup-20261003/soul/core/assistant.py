from __future__ import annotations

import asyncio
import logging
from time import perf_counter
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
                count = await self.memory.extract(text, context=context)
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
            if self.state.current != State.SHUTTING_DOWN:
                self.state.set(State.READY)

    async def close(self):
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
                if not text:
                    continue
                if text.startswith("/"):
                    if not await self.command(text):
                        break
                else:
                    await self.turn(text)
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
        await self.stop_voice()
        start = perf_counter()
        metrics = TurnMetrics()
        self.state.set(State.PROCESSING)
        try:
            memories = []
            if self.memory:
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
                    answer = await self.brain.respond(self.working, text, memories, on_chunk, metrics)
            finally:
                if metrics.gemini_seconds is None:
                    metrics.gemini_seconds = perf_counter() - timer
                executor = getattr(self.brain, "executor", None)
                if executor:
                    metrics.tool_seconds = sum(record["seconds"] for record in executor.records)
                    metrics.tool_calls = len(executor.records)
            self.working.commit(text, answer)
            self.session.turns += 1
            if self.memory:
                if self.memory_task is None:
                    self.memory_task = asyncio.create_task(self.save_memories())
                context = self.brain.memory_context() if hasattr(self.brain, "memory_context") else {}
                await self.memory_queue.put((text, dict(context), metrics))
            if self.settings.soul_tts_enabled:
                self.voice_task = asyncio.create_task(self.speak(answer, metrics))
                if not self.settings.soul_background_voice:
                    await self.voice_task
        except asyncio.CancelledError:
            raise
        except Exception as exc:
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
            if self.desktop_context and self.desktop_context.console_handle:
                try:
                    await self.desktop_context.bridge.call("focus_window", handle=self.desktop_context.console_handle)
                except Exception:
                    self.ui.notice("Select the Soul terminal to enter your next command.")
            metrics.total_seconds = perf_counter() - start
            self.session.last_metrics = metrics
            self.logger.info("turn_metrics %s", metrics.values())
            if self.settings.soul_debug:
                self.ui.notice(str(metrics.values()))
            self.state.set(State.READY)

    async def confirm(self, description):
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
