from __future__ import annotations

import re
from dataclasses import dataclass

@dataclass(frozen=True)
class AudioBuffer:
    data: bytes
    sample_rate: int

class GeminiVoice:
    def __init__(self, client):
        self.client = client

    async def generate(self, text: str) -> AudioBuffer:
        data, mime = await self.client.audio(text)
        if not mime.lower().startswith("audio/l16"):
            raise ValueError(f"Unsupported Gemini PCM format: {mime}")
        match = re.search(r"rate=(\d+)", mime)
        rate = int(match.group(1)) if match else 24000
        if len(data) % 2 or rate < 8000 or rate > 96000:
            raise ValueError("Invalid PCM audio")
        return AudioBuffer(data, rate)
