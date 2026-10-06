from __future__ import annotations

import re
from dataclasses import dataclass

@dataclass(frozen=True)
class AudioBuffer:
    data: bytes
    sample_rate: int

class GeminiVoice:
    engine = "gemini-3.1-flash-live-preview"

    def __init__(self, client):
        self.client = client

    @property
    def voice_name(self) -> str:
        return getattr(getattr(self.client, "settings", None), "gemini_voice_name", "Kore")

    def prepare(self) -> None:
        """Gemini Live TTS is cloud-ready and does not require local COM thread warmup."""
        pass

    async def generate(self, text: str) -> AudioBuffer:
        data, mime = await self.client.audio(text)
        mime_lower = mime.lower()
        if mime_lower.startswith("audio/wav") or mime_lower.startswith("audio/x-wav"):
            import io, wave
            with wave.open(io.BytesIO(data), "rb") as wf:
                rate = wf.getframerate()
                data = wf.readframes(wf.getnframes())
        elif mime_lower.startswith("audio/l16") or mime_lower.startswith("audio/pcm"):
            match = re.search(r"rate=(\d+)", mime)
            rate = int(match.group(1)) if match else 24000
        else:
            raise ValueError(f"Unsupported Gemini audio format: {mime}")
        if len(data) % 2 or rate < 8000 or rate > 96000:
            raise ValueError("Invalid PCM audio")
        return AudioBuffer(data, rate)
