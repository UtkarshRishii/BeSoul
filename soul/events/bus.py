from __future__ import annotations

import logging
import re
import threading
from collections import deque
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

_PRIVATE = {"image", "images", "audio", "screenshot", "clipboard", "password", "api_key", "token", "secret", "arguments"}
_CREDENTIAL = re.compile(r"AIza[\w-]{20,}|(?:sk-|ghp_)[\w-]{16,}|(?i:(?:password|api[_ -]?key|secret|token)\s*[:=]\s*)\S+")


def public_payload(value: Any, depth: int = 0) -> Any:
    """Never transport image bytes, tool arguments or known credential patterns."""
    if depth > 8:
        return None
    if isinstance(value, dict):
        return {str(k): public_payload(v, depth + 1) for k, v in value.items()
                if str(k).lower() not in _PRIVATE}
    if isinstance(value, (list, tuple)):
        return [public_payload(v, depth + 1) for v in value[:100]]
    if isinstance(value, bytes):
        return None
    if isinstance(value, str):
        return _CREDENTIAL.sub("[REDACTED]", value)[:16000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:1000]


class RuntimeEvent(BaseModel):
    type: str
    sequence: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EventBus:
    """Listeners must be fast; asynchronous bridges enqueue rather than block here."""

    def __init__(self, history_limit: int = 200):
        self.history: deque[RuntimeEvent] = deque(maxlen=history_limit)
        self._listeners: list[Callable[[RuntimeEvent], None]] = []
        self._sequence = 0
        self._lock = threading.RLock()

    def subscribe(self, callback: Callable[[RuntimeEvent], None]) -> Callable[[], None]:
        with self._lock:
            self._listeners.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._listeners:
                    self._listeners.remove(callback)
        return unsubscribe

    def publish(self, event_type: str, payload: dict | None = None, task_id: str | None = None) -> RuntimeEvent:
        with self._lock:
            self._sequence += 1
            safe_payload = public_payload(payload or {})
            # This is streamed prose, not an authentication token. Other token fields stay private.
            if event_type == "AssistantTokenReceived" and isinstance((payload or {}).get("token"), str):
                safe_payload["token"] = public_payload(payload["token"])
            event = RuntimeEvent(type=event_type, sequence=self._sequence,
                                 task_id=task_id, payload=safe_payload)
            self.history.append(event)
            listeners = tuple(self._listeners)
        for callback in listeners:
            try:
                callback(event)
            except Exception:
                logging.getLogger("soul").exception("event_listener_failed type=%s", event_type)
        return event
