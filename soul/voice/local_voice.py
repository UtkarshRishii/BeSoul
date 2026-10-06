from __future__ import annotations

import asyncio
import sys
import threading
import logging
from time import perf_counter

from soul.voice.gemini_voice import AudioBuffer
from soul.voice.text_stream import clean_speech


class WindowsVoice:
    """Legacy placeholder; local TTS has been removed in favor of Gemini Live 3.5 TTS."""

    engine = "gemini-3.1-flash-live-preview"

    def __init__(self):
        self.voice_name = "gemini-3.1-flash-live-preview"

    def prepare(self) -> None:
        pass

    async def generate(self, text: str) -> AudioBuffer:
        raise RuntimeError("Windows local TTS has been removed. Soul uses Gemini Live 3.5 TTS exclusively.")


class SelectableVoice:
    """Pure Gemini Live 3.5 TTS voice generator."""

    def __init__(self, settings, gemini):
        self.settings, self.gemini = settings, gemini
        self.engine = "gemini-3.1-flash-live-preview"
        self.voice_name = getattr(settings, "gemini_voice_name", "Kore")

    async def generate(self, text: str) -> AudioBuffer:
        self.engine = "gemini-3.1-flash-live-preview"
        self.voice_name = getattr(self.settings, "gemini_voice_name", "Kore")
        return await self.gemini.generate(text)

    def prepare(self) -> None:
        if hasattr(self.gemini, "prepare"):
            self.gemini.prepare()

