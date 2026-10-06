from __future__ import annotations

import asyncio
import hmac
import json
import logging
import math
import re
import secrets
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from soul.ui_bridge.input import DesktopInputProvider
from soul.ui_bridge.preferences import RESTART_FIELDS, public_preferences, validate_fields


BLOCKED_KEYS = frozenset({
    "api_key", "gemini_api_key", "password", "authorization", "access_token", "refresh_token",
    "image", "screenshot", "image_bytes", "arguments", "system_prompt", "system_prompt_file",
})
SECRET_PATTERN = re.compile(r"(?:AIza[0-9A-Za-z_-]{30,}|(?:sk-|ghp_)[0-9A-Za-z_-]{16,})")


def sanitize(value: Any, *, secret: str = "", depth: int = 0) -> Any:
    """Bound event payloads and remove credentials/images before browser IPC."""
    if depth > 8:
        return None
    if isinstance(value, str):
        text = value.replace(secret, "[redacted]") if secret else value
        return SECRET_PATTERN.sub("[redacted]", text)[:16_384]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, dict):
        return {
            str(key)[:128]: sanitize(item, secret=secret, depth=depth + 1)
            for key, item in list(value.items())[:80]
            if str(key).lower() not in BLOCKED_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item, secret=secret, depth=depth + 1) for item in value[:100]]
    if hasattr(value, "model_dump"):
        return sanitize(value.model_dump(mode="json"), secret=secret, depth=depth + 1)
    return None


class DesktopServer:
    """Authenticated loopback bridge. No shell, file browser, or Python RPC surface."""

    def __init__(self, events: Any, settings: Any, input_provider: DesktopInputProvider,
                 *, static_dir: Path | None = None, preview: bool = False) -> None:
        self.events, self.settings, self.input = events, settings, input_provider
        self.static_dir = (static_dir or Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()
        self.preview = preview
        self.token = secrets.token_urlsafe(32)
        self.port = 0
        self.assistant: Any = None
        self.ready = False
        self.state = "IDLE"
        self.loop: asyncio.AbstractEventLoop | None = None
        self.runner: web.AppRunner | None = None
        self.clients: set[asyncio.Queue[dict[str, Any] | None]] = set()
        self.history: deque[dict[str, Any]] = deque(maxlen=300)
        self.messages: deque[dict[str, Any]] = deque(maxlen=100)
        self.confirmations: dict[str, tuple[asyncio.Future[bool], dict[str, Any]]] = {}
        self.sequence = 0
        self._mutations = asyncio.Lock()
        self._input_generation = 0
        self.unsubscribe = events.subscribe(self._receive_event)
        self.logger = logging.getLogger("soul.ui")
        key = getattr(settings, "gemini_api_key", None)
        self._secret = key.get_secret_value() if key is not None else ""
        self.app = web.Application(client_max_size=32_768, middlewares=[self._security])
        self.app.add_routes([
            web.get("/api/bootstrap", self._bootstrap),
            web.get("/api/events", self._websocket),
            web.post("/api/message", self._message),
            web.post("/api/stop", self._stop),
            web.post("/api/confirmation", self._confirmation),
            web.post("/api/microphone/start", self._microphone_start),
            web.post("/api/microphone/finish", self._microphone_finish),
            web.post("/api/microphone/cancel", self._microphone_cancel),
            web.post("/api/microphone/continuous", self._microphone_continuous),
            web.patch("/api/preferences", self._preferences),
            web.get("/api/memories", self._memories),
            web.get("/api/audio/last.wav", self._last_audio),
            web.get("/api/audio/{segment}.wav", self._segment_audio),
            web.get("/api/system/stats", self._system_stats),
            web.post("/api/screen/observe", self._screen_observe),
            web.get("/{path:.*}", self._static),
        ])
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def origin(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def url(self) -> str:
        return self.origin + "/#token=" + self.token

    @web.middleware
    async def _security(self, request: web.Request, handler: Any) -> web.StreamResponse:
        expected_host = f"127.0.0.1:{self.port}"
        if request.host != expected_host or request.remote not in {"127.0.0.1", "::1"}:
            return web.json_response({"error": "Loopback access required."}, status=403)
        origin = request.headers.get("Origin")
        if origin and origin != self.origin:
            return web.json_response({"error": "Origin is not allowed."}, status=403)
        if request.path.startswith("/api/"):
            credentials = request.headers.get("Authorization", "")
            protocols = request.headers.get("Sec-WebSocket-Protocol", "").split(",")
            valid = hmac.compare_digest(credentials.encode("utf-8"), ("Bearer " + self.token).encode("ascii"))
            valid = valid or any(hmac.compare_digest(part.strip().encode("utf-8"), ("soul." + self.token).encode("ascii")) for part in protocols)
            if not valid:
                return web.json_response({"error": "Authentication required."}, status=401)
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = web.json_response({"error": exc.text or exc.reason}, status=exc.status)
        except (ValueError, TypeError, json.JSONDecodeError):
            response = web.json_response({"error": "The request contains invalid values."}, status=400)
        except Exception:
            self.logger.exception("desktop_request_failed path=%s", request.path)
            response = web.json_response({"error": "SOUL could not complete this request."}, status=500)
        if not response.prepared:
            response.headers.update({
                "Cache-Control": "no-store" if request.path.startswith("/api/") or request.path in {"/", "/index.html"} else "private, max-age=3600",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": (
                    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data:; font-src 'self'; connect-src 'self' "
                    f"ws://127.0.0.1:{self.port}; object-src 'none'; base-uri 'none'; "
                    "form-action 'none'; frame-ancestors 'none'; media-src 'self'; frame-src 'none'"
                ),
            })
        return response

    async def start(self) -> str:
        if not (self.static_dir / "index.html").is_file():
            raise FileNotFoundError("Desktop assets are missing. Run npm.cmd install and npm.cmd run build in frontend.")
        self.loop = asyncio.get_running_loop()
        self.runner = web.AppRunner(self.app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await site.start()
        assert site._server is not None
        self.port = site._server.sockets[0].getsockname()[1]
        return self.url

    def attach_assistant(self, assistant: Any) -> None:
        self.assistant = assistant

    def _receive_event(self, event: Any) -> None:
        if not self.loop or self.loop.is_closed():
            return
        value = event.model_dump(mode="json") if hasattr(event, "model_dump") else dict(event)
        safe = sanitize(value, secret=self._secret)
        if len(json.dumps(safe, ensure_ascii=False).encode("utf-8")) > 65_536:
            payload = safe.get("payload", {})
            allowed = {
                "message", "summary", "token", "state", "tool_name", "execution_id", "success",
                "action_dispatched", "desired_result_verified", "duration_ms", "error_code",
                "input_tokens", "output_tokens", "gemini_seconds", "tool_seconds", "model",
                "amplitude", "level", "audio_url", "sample_rate", "duration", "turns",
            }
            safe["payload"] = {key: item[:4096] if isinstance(item, str) else item
                               for key, item in payload.items() if key in allowed
                               and (item is None or isinstance(item, (str, bool, int, float)))}
            safe["payload"]["details_truncated"] = True
        self.loop.call_soon_threadsafe(self._broadcast, safe)

    def _broadcast(self, event: dict[str, Any]) -> None:
        self.sequence = max(self.sequence, int(event.get("sequence", self.sequence + 1)))
        self.history.append(event)
        kind, payload = event.get("type"), event.get("payload") or {}
        if kind == "StateChanged":
            self.state = str(payload.get("state", payload.get("current", "IDLE"))).upper()
        elif kind == "RuntimeReady":
            self.ready = True
        elif kind in {"RuntimeError", "StartupFailed"}:
            self.ready = False
        elif kind == "UserMessageReceived":
            self.messages.append({"id": str(event["sequence"]), "role": "user",
                                  "text": payload.get("text", payload.get("message", "")),
                                  "task_id": event.get("task_id"), "streaming": False})
        elif kind == "AssistantResponseStarted":
            self.messages.append({"id": str(event["sequence"]), "role": "assistant", "text": "",
                                  "task_id": event.get("task_id"), "streaming": True})
        elif kind == "AssistantTokenReceived":
            if not self.messages or self.messages[-1]["role"] != "assistant":
                self.messages.append({"id": str(event["sequence"]), "role": "assistant", "text": "",
                                      "task_id": event.get("task_id"), "streaming": True})
            self.messages[-1]["text"] = (self.messages[-1]["text"] + str(payload.get("token", "")))[-120_000:]
        elif kind == "AssistantResponseEnded" and self.messages and self.messages[-1]["role"] == "assistant":
            self.messages[-1]["streaming"] = False
        elif kind == "ConversationCleared":
            self.messages.clear()
        elif kind == "TurnCompleted":
            self.total_input_tokens += int(payload.get("input_tokens", 0))
            self.total_output_tokens += int(payload.get("output_tokens", 0))
        for queue in tuple(self.clients):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Close slow consumers; their next bootstrap receives a snapshot.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(None)

    async def _bootstrap(self, request: web.Request) -> web.Response:
        return web.json_response({
            "preview": self.preview, "ready": self.ready, "state": self.state,
            "preferences": public_preferences(self.settings), "sequence": self.sequence,
            "messages": list(self.messages),
            "events": [event for event in self.history if event.get("type") != "AssistantTokenReceived"],
            "confirmations": [payload for _, payload in self.confirmations.values()],
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "model": getattr(self.settings, "gemini_text_model", "gemini-3.5-flash"),
            "voice_model": getattr(self.settings, "gemini_voice_model", "gemini-2.5-flash-preview-tts"),
            "continuous_listening": bool(getattr(self.assistant, "continuous_listening", False)),
            "continuous_phase": getattr(self.assistant, "continuous_phase", "off"),
            "microphone_active": getattr(self.assistant, "microphone", None) is not None,
            "speaking_active": bool(getattr(getattr(self.assistant, "voice", None), "speaking", False)),
        })

    async def _websocket(self, request: web.Request) -> web.WebSocketResponse:
        if len(self.clients) >= 8:
            raise web.HTTPServiceUnavailable(text="Too many desktop connections.")
        since = int(request.query.get("since", "0"))
        ws = web.WebSocketResponse(protocols=["soul." + self.token], max_msg_size=1024, heartbeat=20)
        await ws.prepare(request)
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=256)
        self.clients.add(queue)
        for event in list(self.history)[-256:]:
            if int(event.get("sequence", 0)) > since:
                queue.put_nowait(event)

        async def send() -> None:
            while True:
                event = await queue.get()
                if event is None:
                    await ws.close(code=1013, message=b"Refresh runtime snapshot")
                    return
                await ws.send_json(event)

        sender = asyncio.create_task(send())
        try:
            async for message in ws:
                if message.type in {WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR}:
                    break
                # Browser->runtime commands are authenticated HTTP operations only.
        finally:
            self.clients.discard(queue)
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
        return ws

    def _require_ready(self) -> None:
        if self.preview or not self.ready or self.assistant is None:
            raise web.HTTPServiceUnavailable(text="The assistant is not connected yet.")

    async def _message(self, request: web.Request) -> web.Response:
        self._require_ready()
        body = await request.json()
        text = body.get("text") if isinstance(body, dict) else None
        if not isinstance(text, str) or not text.strip() or len(text) > 12_000:
            return web.json_response({"error": "Enter a request up to 12,000 characters."}, status=400)
        if self.confirmations:
            return web.json_response({"error": "Allow or cancel the pending action first."}, status=409)
        async with self._mutations:
            self._input_generation += 1
            self.input.clear_pending()
            await self.assistant.cancel_current()
            self.input.replace_pending(text.strip())
        return web.json_response({"accepted": True}, status=202)

    async def _stop(self, request: web.Request) -> web.Response:
        self._require_ready()
        async with self._mutations:
            self._input_generation += 1
            self.input.clear_pending()
            for future, _ in tuple(self.confirmations.values()):
                if not future.done():
                    future.set_result(False)
            if hasattr(self.assistant, "set_continuous_listening"):
                await self.assistant.set_continuous_listening(False)
            await self.assistant.cancel_current()
            self.input.clear_pending()
        return web.json_response({"stopped": True})

    async def confirm(self, description: str, **context: Any) -> bool:
        if self.preview:
            return False
        confirmation_id = secrets.token_urlsafe(16)
        future = asyncio.get_running_loop().create_future()
        payload = {
            "confirmation_id": confirmation_id, "description": description,
            "reason": context.get("reason", "This action needs your explicit permission."),
            "consequence": context.get("consequence", "Only this action will be allowed."),
            "expires_at": datetime.now(timezone.utc).timestamp() + 120,
        }
        self.confirmations[confirmation_id] = (future, payload)
        self.events.publish("ConfirmationRequested", payload)
        try:
            async with asyncio.timeout(120):
                return await future
        except TimeoutError:
            return False
        finally:
            self.confirmations.pop(confirmation_id, None)
            self.events.publish("ConfirmationResolved", {"confirmation_id": confirmation_id})

    async def _confirmation(self, request: web.Request) -> web.Response:
        body = await request.json()
        if not isinstance(body, dict) or not isinstance(body.get("allow"), bool):
            return web.json_response({"error": "Choose Allow or Cancel."}, status=400)
        pending = self.confirmations.get(str(body.get("confirmation_id", "")))
        if not pending or pending[0].done():
            return web.json_response({"error": "This confirmation has expired."}, status=409)
        pending[0].set_result(body["allow"])
        return web.json_response({"accepted": True})

    async def _microphone_start(self, request: web.Request) -> web.Response:
        self._require_ready()
        if not getattr(self.settings, "soul_microphone_enabled", True):
            return web.json_response({"error": "Enable push-to-talk in Voice settings first."}, status=409)
        if self.confirmations:
            return web.json_response({"error": "Resolve the pending action first."}, status=409)
        async with self._mutations:
            self._input_generation += 1
            self.input.clear_pending()
            listening = bool(await self.assistant.start_listening())
        return web.json_response({"listening": listening})

    async def _microphone_finish(self, request: web.Request) -> web.Response:
        self._require_ready()
        generation = self._input_generation
        try:
            # Transcription remains interruptible; Stop must never wait for this lock.
            transcript = await self.assistant.finish_listening()
        except asyncio.CancelledError:
            return web.json_response({"transcript": "", "accepted": False, "cancelled": True})
        async with self._mutations:
            if generation != self._input_generation or not self.settings.soul_microphone_enabled:
                transcript = ""
            if transcript and not self.confirmations:
                self.input.replace_pending(transcript)
        return web.json_response({"transcript": transcript, "accepted": bool(transcript)})

    async def _microphone_cancel(self, request: web.Request) -> web.Response:
        self._require_ready()
        async with self._mutations:
            self._input_generation += 1
            await self.assistant.cancel_listening()
        return web.json_response({"cancelled": True})

    async def _microphone_continuous(self, request: web.Request) -> web.Response:
        self._require_ready()
        body = await request.json()
        if not isinstance(body, dict) or type(body.get("enabled")) is not bool:
            return web.json_response({"error": "Choose whether continuous listening is enabled."}, status=400)
        if body["enabled"] and not self.settings.soul_microphone_enabled:
            return web.json_response({"error": "Enable the microphone in Voice settings first."}, status=409)
        if body["enabled"] and self.confirmations:
            return web.json_response({"error": "Resolve the pending action first."}, status=409)
        async with self._mutations:
            if not body["enabled"]:
                self._input_generation += 1
            enabled = await self.assistant.set_continuous_listening(body["enabled"])
        return web.json_response({"continuous_listening": enabled,
                                  "continuous_phase": self.assistant.continuous_phase})

    async def _preferences(self, request: web.Request) -> web.Response:
        values = validate_fields(await request.json())
        if not hasattr(self.settings, "save_preferences"):
            return web.json_response({"error": "Preferences are unavailable in this runtime."}, status=503)
        changed = [key for key in RESTART_FIELDS if key in values and values[key] != getattr(self.settings, key, None)]
        async with self._mutations:
            if self.preview:
                candidate = type(self.settings).model_validate({**self.settings.model_dump(), **values})
                for key in values:
                    setattr(self.settings, key, getattr(candidate, key))
            else:
                self.settings.save_preferences(values)
            if self.assistant and any(values.get(key) is False for key in ("soul_tools_enabled", "soul_vision_enabled", "soul_memory_enabled")):
                self._input_generation += 1
                self.input.clear_pending()
                await self.assistant.cancel_current()
                self.input.clear_pending()
            if self.assistant and values.get("soul_tts_enabled") is False:
                await self.assistant.stop_voice()
            if self.assistant and any(key in values for key in ("soul_voice_engine", "gemini_voice_name")):
                await self.assistant.stop_voice()
            if self.assistant and values.get("soul_microphone_enabled") is False:
                self._input_generation += 1
                self.input.clear_pending()
                await self.assistant.set_continuous_listening(False)
                # Also cancels any active transcription, not only a live recorder.
                await self.assistant.cancel_current()
                self.input.clear_pending()
        result = {"preferences": public_preferences(self.settings), "restart_required": bool(changed)}
        self.events.publish("PreferencesChanged", result)
        return web.json_response(result)

    async def _memories(self, request: web.Request) -> web.Response:
        self._require_ready()
        memory = getattr(self.assistant, "memory", None)
        if not memory:
            return web.json_response({"memories": [], "available": False})
        return web.json_response({"memories": sanitize(memory.store.list(), secret=self._secret), "available": True})

    async def _last_audio(self, request: web.Request) -> web.Response:
        voice = getattr(self.assistant, "voice", None)
        wav = getattr(voice, "last_wav_bytes", b"")
        if not wav:
            return web.Response(status=404, text="No audio generated yet.")
        return web.Response(body=wav, content_type="audio/wav")

    async def _segment_audio(self, request: web.Request) -> web.Response:
        segment = request.match_info["segment"]
        if not re.fullmatch(r"[a-f0-9]{32}", segment):
            raise web.HTTPNotFound(text="Audio clip not found.")
        voice = getattr(self.assistant, "voice", None)
        wav = getattr(voice, "audio_segments", {}).get(segment)
        if not wav:
            raise web.HTTPNotFound(text="Audio clip has expired.")
        return web.Response(body=wav, content_type="audio/wav")

    async def _system_stats(self, request: web.Request) -> web.Response:
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            proc = psutil.Process()
            proc_mb = proc.memory_info().rss / (1024 * 1024)
            return web.json_response({
                "cpu": round(cpu, 1),
                "ram": round(mem.percent, 1),
                "ram_used_gb": round((mem.total - mem.available) / (1024**3), 2),
                "ram_total_gb": round(mem.total / (1024**3), 1),
                "process_mb": round(proc_mb, 1),
                "status": "nominal"
            })
        except Exception:
            return web.json_response({"error": "System metrics are unavailable."}, status=503)

    async def _screen_observe(self, request: web.Request) -> web.Response:
        summary = "Screen observed. Desktop window grounded."
        if self.assistant:
            vision = getattr(self.assistant.brain, "vision", None)
            if vision:
                try:
                    obs = await vision.capture(mode="monitor")
                    active = obs.metadata.get("active_window", {})
                    app = active.get("application", "Desktop")
                    title = active.get("title", "")
                    summary = f"Active window: {title} ({app})" if title else f"Active window: {app}"
                except Exception:
                    pass
        return web.json_response({"success": True, "summary": summary})

    async def _static(self, request: web.Request) -> web.StreamResponse:
        relative = request.match_info["path"] or "index.html"
        if relative.startswith("api/"):
            raise web.HTTPNotFound()
        path = (self.static_dir / relative).resolve()
        if not path.is_relative_to(self.static_dir) or not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def close(self) -> None:
        self.unsubscribe()
        for future, _ in tuple(self.confirmations.values()):
            if not future.done():
                future.set_result(False)
        for queue in tuple(self.clients):
            while not queue.empty():
                queue.get_nowait()
            queue.put_nowait(None)
        if self.runner:
            await self.runner.cleanup()
