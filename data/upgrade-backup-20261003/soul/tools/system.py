from __future__ import annotations
from pydantic import Field
from soul.tools.models import Arguments, ToolResult


class VolumeArguments(Arguments):
    level: int = Field(ge=0, le=100, strict=True)


class PathArguments(Arguments):
    path: str = Field(min_length=1, max_length=2048)


class SystemTools:
    def __init__(self, bridge):
        self.bridge = bridge

    def handler(self, operation):
        async def run(args):
            return ToolResult(success=True, message="Operation completed.", data=await self.bridge.call(operation, **args.model_dump()))
        return run
