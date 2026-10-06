from __future__ import annotations

import asyncio
from time import perf_counter

class AudioPlayer:
    def __init__(self):
        self.on_amplitude = None

    async def play(self, audio):
        import numpy as np
        import sounddevice as sd
        samples = np.frombuffer(audio.data, dtype="<i2")
        try:
            sd.play(samples, samplerate=audio.sample_rate, blocking=False)
            start = perf_counter()
            while sd.get_stream().active:
                if self.on_amplitude:
                    offset = max(0, int((perf_counter() - start - sd.get_stream().latency) * audio.sample_rate))
                    block = samples[offset:offset + max(1, audio.sample_rate // 20)].astype(np.float32)
                    level = min(1.0, float(np.sqrt(np.mean(block ** 2))) / 12000) if len(block) else 0.0
                    self.on_amplitude(level)
                await asyncio.sleep(0.05)
        finally:
            sd.stop()
            if self.on_amplitude:
                self.on_amplitude(0.0)
