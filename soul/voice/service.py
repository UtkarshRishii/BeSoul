from __future__ import annotations

import asyncio
import io
import wave
from collections import OrderedDict
from time import perf_counter
from uuid import uuid4
from soul.core.state import State
from soul.voice.text_stream import SpeechTextStream

class VoiceService:
    def __init__(self, generator, player):
        self.generator, self.player = generator, player
        self.last_wav_bytes: bytes = b""
        self.audio_segments: OrderedDict[str, bytes] = OrderedDict()
        self.speaking = False

    async def speak(self, text, state, metrics):
        stream = SpeechTextStream()
        stream.feed(text)
        stream.finish()
        await self.speak_stream(stream, state, metrics)

    def _store_audio(self, audio) -> str:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(audio.sample_rate)
            wf.writeframes(audio.data)
        self.last_wav_bytes = buf.getvalue()
        segment_id = uuid4().hex
        self.audio_segments[segment_id] = self.last_wav_bytes
        # RAM-only immutable clips; old URLs expire rather than returning a newer clip.
        while len(self.audio_segments) > 8:
            self.audio_segments.popitem(last=False)
        return "/api/audio/" + segment_id + ".wav"

    async def speak_stream(self, text_stream, state, metrics):
        """Generate the next sentence while the current one plays, in strict order."""
        events = getattr(state, "events", None)
        audio_queue: asyncio.Queue = asyncio.Queue(maxsize=3)
        started = False

        async def generate():
            try:
                async for text in text_stream:
                    timer = perf_counter()
                    if not started:
                        state.set(State.GENERATING_VOICE)
                    try:
                        audio = await self.generator.generate(text)
                    finally:
                        metrics.tts_seconds = (metrics.tts_seconds or 0) + perf_counter() - timer
                    await audio_queue.put(audio)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                await audio_queue.put(exc)
            await audio_queue.put(None)

        producer = asyncio.create_task(generate())
        try:
            while True:
                audio = await audio_queue.get()
                if audio is None:
                    break
                if isinstance(audio, Exception):
                    raise audio
                audio_url = self._store_audio(audio)
                if not started:
                    started = True
                    self.speaking = True
                    metrics.first_audio_seconds = perf_counter() - text_stream.started_at
                    state.set(State.SPEAKING)
                    if events:
                        events.publish("SpeechStarted", {
                            "sample_rate": audio.sample_rate,
                            "duration": round(len(audio.data) / (audio.sample_rate * 2), 2),
                            "audio_url": audio_url,
                            "playback": "native",
                            "engine": getattr(self.generator, "engine", "gemini"),
                            "voice": getattr(self.generator, "voice_name", ""),
                        })
                        self.player.on_amplitude = lambda level: events.publish("SpeechAmplitude", {"amplitude": level})
                timer = perf_counter()
                try:
                    await self.player.play(audio)
                finally:
                    metrics.playback_seconds = (metrics.playback_seconds or 0) + perf_counter() - timer
        finally:
            self.speaking = False
            producer.cancel()
            await asyncio.gather(producer, return_exceptions=True)
            if events and started:
                events.publish("SpeechAmplitude", {"amplitude": 0.0})
                events.publish("SpeechEnded", {"playback": "native"})
            self.player.on_amplitude = None
