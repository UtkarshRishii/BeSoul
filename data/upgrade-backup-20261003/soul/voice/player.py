from __future__ import annotations

import asyncio

class AudioPlayer:
    async def play(self, audio):
        import numpy as np
        import sounddevice as sd
        samples = np.frombuffer(audio.data, dtype="<i2")
        try:
            sd.play(samples, samplerate=audio.sample_rate, blocking=False)
            while sd.get_stream().active:
                await asyncio.sleep(0.05)
        finally:
            sd.stop()
