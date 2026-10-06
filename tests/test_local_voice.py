import asyncio
import threading
from types import SimpleNamespace

import pytest

from soul.config.settings import Settings
from soul.ui_bridge.preferences import public_preferences, validate_fields
from soul.voice.gemini_voice import AudioBuffer
from soul.voice.local_voice import SelectableVoice, WindowsVoice


@pytest.mark.asyncio
async def test_windows_voice_removed_raises_runtime_error():
    generator = WindowsVoice()
    with pytest.raises(RuntimeError, match="Windows local TTS has been removed"):
        await generator.generate("Test text")


@pytest.mark.asyncio
async def test_selectable_voice_uses_gemini_exclusively():
    calls = []

    class FakeVoice:
        voice_name = "Gemini Live Voice"

        def __init__(self, name):
            self.name = name

        async def generate(self, text):
            calls.append(self.name)
            return AudioBuffer(b"\x01\x00", 16000)

    settings = SimpleNamespace(soul_voice_engine="gemini", gemini_voice_name="Kore")
    generator = SelectableVoice(settings, FakeVoice("gemini"))
    await generator.generate("First sentence.")
    assert calls == ["gemini"]
    assert generator.engine == "gemini"
    assert generator.voice_name == "Kore"


def test_engine_preference_is_public_validated_and_saved_without_credentials(tmp_path):
    settings = Settings(_env_file=None, gemini_api_key="unit-test", soul_data_dir=tmp_path)
    values = validate_fields({"soul_voice_engine": "gemini"})
    settings.save_preferences(values)
    assert public_preferences(settings)["soul_voice_engine"] == "gemini"
    assert "gemini_api_key" not in public_preferences(settings)
    assert "unit-test" not in (tmp_path / "preferences.json").read_text()
    # Legacy 'local' setting is automatically coerced to 'gemini'
    migrated = validate_fields({"soul_voice_engine": "local"})
    assert migrated["soul_voice_engine"] == "gemini"
    with pytest.raises(ValueError):
        validate_fields({"soul_voice_engine": "unsupported"})
