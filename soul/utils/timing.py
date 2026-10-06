from __future__ import annotations

from dataclasses import dataclass, asdict

@dataclass
class TurnMetrics:
    gemini_seconds: float | None = None
    first_token_seconds: float | None = None
    first_audio_seconds: float | None = None
    retrieval_seconds: float | None = None
    extraction_seconds: float | None = None
    tts_seconds: float | None = None
    playback_seconds: float | None = None
    total_seconds: float | None = None
    tool_seconds: float | None = None
    tool_calls: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    task_id: str | None = None
    tool_selection_seconds: float | None = None
    vision_capture_seconds: float | None = None
    vision_analysis_seconds: float | None = None
    localization_seconds: float | None = None
    verification_seconds: float | None = None
    frame_upload_bytes: int = 0
    retry_count: int = 0
    model_used: str | None = None

    def values(self):
        return {k: v for k, v in asdict(self).items() if v is not None}
