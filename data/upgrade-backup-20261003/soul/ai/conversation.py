from __future__ import annotations

from soul.memory.short_term import Message

def build_context(working, user_text):
    return [*working.messages, Message("user", user_text)]
