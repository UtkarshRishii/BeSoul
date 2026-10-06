from __future__ import annotations

from enum import Enum
from collections.abc import Callable

class State(str, Enum):
    STARTING = "starting"
    IDLE = "idle"
    READY = "idle"
    LISTENING = "listening"
    SEEING = "seeing"
    ACTING = "acting"
    VERIFYING = "verifying"
    WAITING_CONFIRMATION = "waiting_confirmation"
    SUCCESS = "success"
    INTERRUPTED = "interrupted"
    PROCESSING = "processing"
    RETRIEVING_MEMORY = "retrieving memory"
    THINKING = "thinking"
    RESPONDING = "responding"
    GENERATING_VOICE = "generating voice"
    SPEAKING = "speaking"
    CALLING_TOOL = "calling tool"
    EXECUTING_TOOL = "executing tool"
    WAITING_FOR_TOOL = "waiting_confirmation"
    OBSERVING_SCREEN = "seeing"
    IDENTIFYING_TARGET = "seeing"
    EXECUTING_ACTION = "acting"
    VERIFYING_ACTION = "verifying"
    ERROR = "error"
    SHUTTING_DOWN = "shutting down"

class StateManager:
    def __init__(self, listener: Callable[[State], None] | None = None, events=None):
        self.current = State.STARTING
        self.listener = listener
        self.events = events

    def set(self, state: State) -> None:
        if self.current == State.SHUTTING_DOWN and state != State.SHUTTING_DOWN:
            raise RuntimeError("Runtime already shutting down")
        if self.current == state:
            return
        previous = self.current
        self.current = state
        if self.events:
            self.events.publish("StateChanged", {"state": state.value, "previous": previous.value})
        if self.listener:
            self.listener(state)
