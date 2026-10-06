from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Iterator


class DesktopConsole:
    """Console compatibility without sending Rich markup or tracebacks to the UI."""

    def __init__(self, renderer: DesktopRenderer) -> None:
        self.renderer = renderer

    def print(self, value: Any = "", **_: Any) -> None:
        import re

        text = re.sub(r"\[/?(?:error|muted|warning|accent|bold)[^\]]*\]", "", str(value)).strip()
        if text:
            self.renderer.notice(text)

    def clear(self) -> None:
        self.renderer.events.publish("ConversationCleared", {})


class DesktopRenderer:
    """Rendering adapter; orchestration, tasks and state still belong to Python."""

    def __init__(self, events: Any) -> None:
        self.events = events
        self.console = DesktopConsole(self)
        self.name = "Soul"

    def startup(self, settings: Any, memory_ready: bool) -> None:
        self.name = settings.soul_name
        self.events.publish("RuntimeReady", {
            "name": self.name,
            "model": settings.gemini_text_model,
            "memory_ready": memory_ready,
            "voice_enabled": settings.soul_tts_enabled,
            "vision_enabled": settings.soul_vision_enabled and settings.soul_tools_enabled,
            "automation_enabled": settings.soul_tools_enabled,
        })

    def state_changed(self, state: Any) -> None:
        # StateManager publishes the authoritative StateChanged event.
        pass

    @contextmanager
    def response(self) -> Iterator[Callable[[str], None]]:
        self.events.publish("AssistantResponseStarted", {})
        content: list[str] = []

        def append(chunk: str) -> None:
            content.append(chunk)
            self.events.publish("AssistantTokenReceived", {"token": chunk})

        try:
            yield append
        finally:
            self.events.publish("AssistantResponseEnded", {"text": "".join(content)})

    @contextmanager
    def activity(self) -> Iterator[None]:
        yield

    @contextmanager
    def pause_live(self) -> Iterator[None]:
        yield

    def tool_started(self, name: str) -> None:
        # ToolExecutor publishes complete, authoritative receipts.
        pass

    def tool_finished(self, name: str, result: Any, elapsed: float) -> None:
        pass

    def model_changed(self, message: str) -> None:
        self.events.publish("ModelChanged", {"message": message})

    def notice(self, text: str) -> None:
        self.events.publish("Notice", {"message": text.strip()})

    def error(self, text: str) -> None:
        self.events.publish("Error", {"message": text.strip()})

    def memories(self, memories: list[Any]) -> None:
        self.events.publish("MemoriesListed", {"memories": [m.model_dump(mode="json") for m in memories]})

