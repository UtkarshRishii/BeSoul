from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable
from pydantic import BaseModel, ConfigDict, Field


class Risk(str, Enum):
    READ_ONLY = "read_only"
    SAFE_ACTION = "safe_action"
    CONFIRMATION_REQUIRED = "confirmation_required"
    RESTRICTED = "restricted"


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoArguments(Arguments):
    pass


class ToolResult(BaseModel):
    success: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    image: bytes | None = None

    def payload(self) -> dict:
        return self.model_dump(exclude={"image"})

    @classmethod
    def fail(cls, code: str, message: str, **data):
        return cls(success=False, message=message, error_code=code, data=data)


class ToolError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments: type[Arguments]
    risk: Risk
    handler: Callable[[Arguments], Awaitable[ToolResult]]
    timeout: float = 20
