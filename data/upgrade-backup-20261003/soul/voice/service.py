from __future__ import annotations

from time import perf_counter
from soul.core.state import State

class VoiceService:
    def __init__(self, generator, player):
        self.generator, self.player = generator, player

    async def speak(self, text, state, metrics):
        state.set(State.GENERATING_VOICE)
        start = perf_counter()
        try:
            audio = await self.generator.generate(text)
        finally:
            metrics.tts_seconds = perf_counter() - start
        state.set(State.SPEAKING)
        start = perf_counter()
        try:
            await self.player.play(audio)
        finally:
            metrics.playback_seconds = perf_counter() - start
