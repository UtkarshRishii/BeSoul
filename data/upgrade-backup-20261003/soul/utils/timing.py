from __future__ import annotations

from dataclasses import dataclass, asdict

@dataclass
class TurnMetrics:
    gemini_seconds: float | None = None
    first_token_seconds: float | None = None
    retrieval_seconds: float | None = None
    extraction_seconds: float | None = None
    tts_seconds: float | None = None
    playback_seconds: float | None = None
    total_seconds: float | None = None
    tool_seconds: float | None = None
    tool_calls: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def values(self):
        return {k: v for k, v in asdict(self).items() if v is not None}
