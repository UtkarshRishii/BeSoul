from __future__ import annotations

import asyncio
import re
from time import perf_counter


def clean_speech(text: str) -> str:
    """Keep spoken prose, without reading Markdown syntax or fenced code aloud."""
    text = re.sub(r"```[\s\S]*?(?:```|$)", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s*|[-*+]\s+|\d+[.)]\s+|>\s*)", "", text)
    text = re.sub(r"[*_~|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class SpeechTextStream:
    """A bounded, synchronous sink for final text with an async sentence consumer."""

    def __init__(self, max_characters: int = 12000, segment_characters: int = 240):
        self.max_characters = max_characters
        self.segment_characters = segment_characters
        self.started_at = perf_counter()
        # Segments are at least 32 characters except the final one. The bound also
        # accommodates the end marker without ever blocking the text token callback.
        self.queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=max_characters // 32 + 4)
        self.pending = ""
        self.received = 0
        self.closed = False
        self.truncated = False
        self._fenced = False
        self._raw_pending = ""

    def feed(self, chunk: str) -> None:
        if self.closed:
            return
        remaining = max(0, self.max_characters - self.received)
        self.truncated = self.truncated or len(chunk) > remaining
        self.received += min(len(chunk), remaining)
        self._raw_pending += chunk[:remaining]
        # Keep two trailing backticks until the next token, so split fence markers
        # cannot escape into a spoken segment.
        while self._raw_pending:
            fence = self._raw_pending.find("```")
            if fence >= 0:
                if not self._fenced:
                    self.pending += self._raw_pending[:fence] + " "
                self._fenced = not self._fenced
                self._raw_pending = self._raw_pending[fence + 3:]
                continue
            tail = len(self._raw_pending) - len(self._raw_pending.rstrip("`"))
            safe = len(self._raw_pending) - min(tail, 2)
            if not self._fenced:
                self.pending += self._raw_pending[:safe]
            self._raw_pending = self._raw_pending[safe:]
            break
        self._drain()

    def _drain(self, final: bool = False) -> None:
        while self.pending:
            min_boundary = 12 if not getattr(self, "_first_emitted", False) else 24
            boundary = next((m.end() for m in re.finditer(r"[.!?](?:[\"')\]]*)(?=\s|$)", self.pending)
                             if m.end() >= min_boundary), None)
            if boundary is None or boundary > self.segment_characters:
                if len(self.pending) < self.segment_characters and not final:
                    return
                boundary = min(len(self.pending), self.segment_characters)
                space = self.pending.rfind(" ", min_boundary, boundary)
                if boundary < len(self.pending) and space >= min_boundary:
                    boundary = space
            text, self.pending = self.pending[:boundary], self.pending[boundary:].lstrip()
            text = clean_speech(text)
            if text:
                self._first_emitted = True
                self.queue.put_nowait(text)

    def finish(self) -> None:
        if self.closed:
            return
        if not self._fenced:
            self.pending += self._raw_pending
        self._raw_pending = ""
        self._drain(final=True)
        self.closed = True
        self.queue.put_nowait(None)

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        text = await self.queue.get()
        if text is None:
            raise StopAsyncIteration
        return text
