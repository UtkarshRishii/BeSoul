from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field

class MemoryFact(BaseModel):
    key: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    content: str = Field(min_length=1, max_length=500)
    category: Literal["preference", "project", "configuration", "fact"]
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.8, ge=0, le=1)
    tags: list[str] = Field(default_factory=list, max_length=10)

class Extraction(BaseModel):
    memories: list[MemoryFact] = Field(default_factory=list, max_length=3)

class Memory(MemoryFact):
    id: int
    created_at: str
    updated_at: str
    last_accessed_at: str | None = None
    source: str = "user_explicit"
