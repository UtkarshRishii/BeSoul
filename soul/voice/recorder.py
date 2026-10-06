from __future__ import annotations

import asyncio
import io
import threading
import wave
from collections.abc import Callable


class SpeechActivityDetector:
    """Local energy VAD with sustained-speech and trailing-silence requirements."""

    def __init__(self, sample_rate: int = 16000, silence_seconds: float = 0.8):
        self.sample_rate = sample_rate
        self.silence_samples = int(silence_seconds * sample_rate)
        self.minimum_speech_samples = int(0.2 * sample_rate)
        self.elapsed_samples = 0
        self.voice_samples = 0
        self.last_voice_sample = 0
        self.noise_floor = 80.0
        self.speech_detected = False

    def update(self, rms: float, samples: int) -> bool:
        self.elapsed_samples += samples
        threshold = max(350.0, self.noise_floor * 3.0)
        if rms >= threshold:
            self.voice_samples += samples
            self.last_voice_sample = self.elapsed_samples
            self.speech_detected = self.voice_samples >= self.minimum_speech_samples
        elif not self.speech_detected:
            # An isolated click is not an utterance. Adapt only to quiet samples,
            # so sustained speech cannot raise its own detection threshold.
            self.voice_samples = 0
            self.noise_floor = self.noise_floor * 0.95 + min(rms, 300.0) * 0.05
        return self.speech_detected and self.elapsed_samples - self.last_voice_sample >= self.silence_samples


class PushToTalkRecorder:
    """Explicit, bounded microphone capture. WAV bytes never leave memory until transcription."""

    def __init__(self, max_seconds: int = 30, sample_rate: int = 16000,
                 on_amplitude: Callable[[float], None] | None = None,
                 silence_seconds: float | None = None):
        self.sample_rate = sample_rate
        self.max_samples = max_seconds * sample_rate
        self.on_amplitude = on_amplitude
        self._stream = None
        self._blocks: list[bytes] = []
        self._samples = 0
        self._lock = threading.Lock()
        self.detector = SpeechActivityDetector(sample_rate, silence_seconds) if silence_seconds is not None else None
        self._endpoint = asyncio.Event()

    @property
    def speech_detected(self) -> bool:
        return bool(self.detector and self.detector.speech_detected)

    async def wait_for_endpoint(self) -> None:
        await self._endpoint.wait()

    @property
    def active(self) -> bool:
        return self._stream is not None and bool(self._stream.active)

    async def start(self) -> None:
        if self._stream is not None:
            raise RuntimeError("Microphone is already active")
        import numpy as np
        import sounddevice as sd
        self._blocks.clear()
        self._samples = 0
        self._endpoint.clear()
        loop = asyncio.get_running_loop()

        def callback(data, frames, timing, status):
            with self._lock:
                remaining = self.max_samples - self._samples
                count = min(frames, remaining)
                if count:
                    samples = data[:count].copy()
                    self._blocks.append(samples.tobytes())
                    self._samples += count
                    rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
                    if self.on_amplitude:
                        self.on_amplitude(min(1.0, rms / 6000))
                    endpoint = self.detector.update(rms, count) if self.detector else False
                else:
                    endpoint = False
                # Limit silent cycles as well; continuous mode discards them and
                # reopens without sending silence to the transcription model.
                silent_limit = bool(self.detector and not self.speech_detected and self._samples >= 10 * self.sample_rate)
                if endpoint or silent_limit or self._samples >= self.max_samples:
                    loop.call_soon_threadsafe(self._endpoint.set)
                    raise sd.CallbackStop()

        def open_stream():
            stream = sd.InputStream(samplerate=self.sample_rate, channels=1, dtype="int16", callback=callback)
            try:
                stream.start()
            except BaseException:
                stream.close()
                raise
            return stream
        opening = asyncio.create_task(asyncio.to_thread(open_stream))
        try:
            self._stream = await asyncio.shield(opening)
        except asyncio.CancelledError:
            # A native open cannot be cancelled in the worker thread; collect and close it.
            self._stream = await opening
            await self.finish(discard=True)
            raise

    async def finish(self, discard: bool = False) -> bytes:
        stream, self._stream = self._stream, None
        if stream is not None:
            def close_stream():
                try:
                    stream.stop()
                finally:
                    stream.close()
            await asyncio.to_thread(close_stream)
        with self._lock:
            pcm = b"".join(self._blocks) if not discard else b""
            self._blocks.clear()
            self._samples = 0
        self._endpoint.set()
        if self.on_amplitude:
            self.on_amplitude(0.0)
        if not pcm:
            return b""
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(self.sample_rate)
            output.writeframes(pcm)
        return buffer.getvalue()
