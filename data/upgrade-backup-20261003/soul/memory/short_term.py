from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class Message:
    role: str
    text: str

class WorkingMemory:
    def __init__(self, max_turns: int = 12):
        self.max_turns = max_turns
        self.messages: list[Message] = []

    def commit(self, user: str, assistant: str) -> None:
        self.messages.extend([Message("user", user), Message("model", assistant)])
        self.messages = self.messages[-self.max_turns * 2:]

    def clear(self) -> None:
        self.messages.clear()
