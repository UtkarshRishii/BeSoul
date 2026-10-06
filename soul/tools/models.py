from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable
from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    message: str = ""
    tool_name: str | None = None
    execution_id: str | None = None
    summary: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    duration_ms: float | None = None
    action_dispatched: bool = False
    desired_result_verified: bool | None = None
    observation_required: bool = False
    image: bytes | None = None

    @model_validator(mode="after")
    def compatible_receipt(self):
        # Existing tool handlers can continue returning message and data metadata.
        self.message = self.message or self.summary
        self.summary = self.summary or self.message
        if not self.success and self.error_message is None:
            self.error_message = self.message
        for name in ("action_dispatched", "desired_result_verified", "observation_required"):
            if name in self.data and name not in self.model_fields_set:
                setattr(self, name, self.data[name])
        return self

    def payload(self) -> dict:
        return self.model_dump(exclude={"image"})

    @classmethod
    def fail(cls, code: str, message: str, **data):
        return cls(success=False, message=message, error_code=code, data=data)


class ToolError(Exception):
    def __init__(self, code: str, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.data = dict(data or {})


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    arguments: type[Arguments]
    risk: Risk
    handler: Callable[[Arguments], Awaitable[ToolResult]]
    timeout: float = 20
    # Opt in only when both the handler and its resources support concurrent reads.
    parallel_safe: bool = False
