from __future__ import annotations

from pathlib import Path
from typing import Literal
import json
import os
import sys
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
PREFERENCE_FIELDS = frozenset({
    "soul_name", "gemini_text_model", "soul_response_mode", "soul_tts_enabled", "gemini_voice_name",
    "soul_memory_enabled", "soul_tools_enabled", "soul_vision_enabled", "soul_debug",
    "soul_reduced_motion", "soul_visual_quality", "soul_onboarding_complete", "soul_microphone_enabled", "soul_voice_engine",
})

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    gemini_api_key: SecretStr = SecretStr("")
    gemini_text_model: str = Field("gemini-3.5-flash", min_length=1)
    gemini_voice_model: str = Field("gemini-3.1-flash-live-preview", min_length=1)
    gemini_voice_name: str = "Kore"
    gemini_transcription_model: str = ""  # Empty preserves the selected conversation model.
    soul_name: str = "Soul"
    soul_tts_enabled: bool = True
    soul_voice_engine: Literal["gemini"] = "gemini"
    soul_streaming: bool = True
    soul_memory_enabled: bool = True
    soul_debug: bool = False
    soul_request_timeout: float = Field(20, gt=0)
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    soul_background_voice: bool = True
    soul_tts_max_characters: int = Field(12000, ge=200, le=50000)
    soul_fast_responses: bool = True
    soul_response_mode: Literal["fast", "full"] = "fast"
    soul_history_turns: int = Field(12, ge=1, le=100)
    soul_memory_limit: int = Field(6, ge=1, le=30)
    soul_data_dir: Path = ROOT / "data"
    soul_system_prompt_file: Path | None = None
    soul_tools_enabled: bool = True
    soul_vision_enabled: bool = True
    gemini_vision_model: str = ""  # Empty means use the configured multimodal text model.
    soul_max_tool_iterations: int = Field(10, ge=1, le=20)
    soul_max_tool_calls: int = Field(24, ge=1, le=50)
    soul_tool_timeout: float = Field(25, ge=1, le=120)
    soul_turn_timeout: float = Field(240, ge=10, le=600)
    soul_monitor: int = Field(0, ge=0, le=16)  # 0 selects the active window's display.
    soul_target_confidence: float = Field(0.85, ge=0.7, le=1)
    soul_target_ttl: float = Field(90, ge=5, le=180)
    soul_max_clicks: int = Field(6, ge=1, le=12)
    soul_max_scrolls: int = Field(5, ge=1, le=10)
    soul_action_interval: float = Field(0.5, ge=0.2, le=5)
    soul_vision_max_dimension: int = Field(1600, ge=320, le=2400)
    soul_visual_context_ttl: float = Field(30, ge=2, le=120)
    soul_uia_enabled: bool = True
    soul_max_keyboard_actions: int = Field(8, ge=1, le=20)
    soul_max_typed_characters: int = Field(4000, ge=100, le=10000)
    soul_takeover_tolerance: int = Field(12, ge=3, le=100)
    soul_max_retries: int = Field(2, ge=0, le=5)
    soul_max_parallel_reads: int = Field(4, ge=1, le=8)
    soul_microphone_enabled: bool = True
    soul_microphone_max_seconds: int = Field(30, ge=3, le=120)
    soul_microphone_silence_seconds: float = Field(0.8, ge=0.3, le=3)
    soul_reduced_motion: bool = False
    soul_visual_quality: Literal["auto", "low", "high"] = "auto"
    soul_onboarding_complete: bool = False

    @classmethod
    def load(cls) -> "Settings":
        base = cls()
        path = base.soul_data_dir / "preferences.json"
        if not path.is_file():
            return base
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or set(data) - PREFERENCE_FIELDS:
                raise ValueError("Unknown preference fields")
            # Revalidate the complete object without environment coercion overriding preferences.
            return cls.model_validate({**base.model_dump(), **data})
        except (ValueError, OSError):
            import logging
            logging.getLogger("soul").warning("preferences_invalid_using_environment_defaults")
            return base

    def public_preferences(self) -> dict:
        return self.model_dump(mode="json", include=PREFERENCE_FIELDS)

    def save_preferences(self, values: dict) -> None:
        if not isinstance(values, dict) or set(values) - PREFERENCE_FIELDS:
            raise ValueError("Only public settings may be changed")
        candidate = type(self).model_validate({**self.model_dump(), **values})
        self.soul_data_dir.mkdir(parents=True, exist_ok=True)
        destination = self.soul_data_dir / "preferences.json"
        temporary = destination.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(candidate.public_preferences(), indent=2), encoding="utf-8")
        os.replace(temporary, destination)
        for field in PREFERENCE_FIELDS:
            setattr(self, field, getattr(candidate, field))
