from __future__ import annotations

from typing import Any


# An explicit boundary: API keys, filesystem paths and system prompt fields never
# appear in browser-visible settings, even if future Settings fields are added.
PUBLIC_FIELDS = frozenset({
    "soul_name", "gemini_text_model", "soul_response_mode", "soul_tts_enabled",
    "gemini_voice_name", "soul_memory_enabled", "soul_tools_enabled", "soul_vision_enabled",
    "soul_debug", "soul_reduced_motion", "soul_visual_quality", "soul_onboarding_complete",
    "soul_microphone_enabled", "soul_voice_engine",
})
RESTART_FIELDS = frozenset({"soul_memory_enabled", "soul_tools_enabled", "soul_vision_enabled"})


def public_preferences(settings: Any) -> dict[str, Any]:
    if hasattr(settings, "public_preferences"):
        values = settings.public_preferences()
        return {key: value for key, value in values.items() if key in PUBLIC_FIELDS}
    return {key: getattr(settings, key) for key in PUBLIC_FIELDS if hasattr(settings, key)}


def validate_fields(values: Any) -> dict[str, Any]:
    if not isinstance(values, dict) or not values or len(values) > len(PUBLIC_FIELDS):
        raise ValueError("Choose at least one supported setting.")
    if any(key not in PUBLIC_FIELDS for key in values):
        raise ValueError("This setting is not available in the desktop interface.")
    if any(isinstance(value, (dict, list)) for value in values.values()):
        raise ValueError("Settings must be simple values.")
    for key, value in values.items():
        if key in {"soul_name", "gemini_text_model", "gemini_voice_name"}:
            limit = 40 if key == "soul_name" else 120 if key == "gemini_text_model" else 60
            if not isinstance(value, str) or not value.strip() or len(value) > limit:
                raise ValueError("Choose a supported name or model identifier.")
        elif key == "soul_response_mode":
            if value not in {"fast", "full"}:
                raise ValueError("Choose fast or full response mode.")
        elif key == "soul_visual_quality":
            if value not in {"auto", "low", "high"}:
                raise ValueError("Choose auto, low or high visual quality.")
        elif key == "soul_voice_engine":
            if value == "local":
                values[key] = "gemini"
            elif value != "gemini":
                raise ValueError("Choose Gemini voice.")
        elif type(value) is not bool:
            raise ValueError("Feature preferences must be true or false.")
    return values
