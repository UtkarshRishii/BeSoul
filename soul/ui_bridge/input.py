from __future__ import annotations

import asyncio


class DesktopInputProvider:
    """A bounded user-only channel, separate from confirmation responses."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=8)

    async def get_input(self) -> str:
        value = await self.queue.get()
        self.queue.task_done()
        if value is None:
            raise EOFError
        return value

    def submit(self, text: str) -> None:
        self.queue.put_nowait(text)

    def clear_pending(self) -> None:
        while not self.queue.empty():
            self.queue.get_nowait()
            self.queue.task_done()

    def replace_pending(self, text: str) -> None:
        self.clear_pending()
        self.submit(text)

    def close(self) -> None:
        self.clear_pending()
        self.queue.put_nowait(None)

