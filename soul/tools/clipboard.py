from __future__ import annotations
from pydantic import Field
from soul.tools.models import Arguments


class ClipboardArguments(Arguments):
    text: str = Field(max_length=10000)
