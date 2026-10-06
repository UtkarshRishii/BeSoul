from __future__ import annotations

from enum import Enum
from collections.abc import Callable

class State(str, Enum):
    STARTING = "starting"
    READY = "ready"
    PROCESSING = "processing"
    RETRIEVING_MEMORY = "retrieving memory"
    THINKING = "thinking"
    RESPONDING = "responding"
    GENERATING_VOICE = "generating voice"
    SPEAKING = "speaking"
    CALLING_TOOL = "calling tool"
    EXECUTING_TOOL = "executing tool"
    WAITING_FOR_TOOL = "waiting for confirmation"
    OBSERVING_SCREEN = "observing screen"
    IDENTIFYING_TARGET = "identifying target"
    EXECUTING_ACTION = "executing action"
    VERIFYING_ACTION = "verifying action"
    ERROR = "error"
    SHUTTING_DOWN = "shutting down"

class StateManager:
    def __init__(self, listener: Callable[[State], None] | None = None):
        self.current = State.STARTING
        self.listener = listener

    def set(self, state: State) -> None:
        if self.current == State.SHUTTING_DOWN and state != State.SHUTTING_DOWN:
            raise RuntimeError("Runtime already shutting down")
        self.current = state
        if self.listener:
            self.listener(state)
