from __future__ import annotations

from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    gemini_api_key: SecretStr = SecretStr("")
    gemini_text_model: str = Field("gemini-3.5-flash", min_length=1)
    gemini_voice_model: str = Field("gemini-2.5-flash-preview-tts", min_length=1)
    gemini_voice_name: str = "Kore"
    soul_name: str = "Soul"
    soul_tts_enabled: bool = True
    soul_streaming: bool = True
    soul_memory_enabled: bool = True
    soul_debug: bool = False
    soul_request_timeout: float = Field(20, gt=0)
    gemini_fallback_model: str = "gemini-3.5-flash-lite"
    soul_background_voice: bool = True
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
