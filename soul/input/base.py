from __future__ import annotations

from typing import Protocol

class InputProvider(Protocol):
    async def get_input(self) -> str: ...
