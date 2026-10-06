import asyncio
from types import SimpleNamespace

import pytest

from soul.core.state import StateManager
from soul.events import EventBus
from soul.utils.timing import TurnMetrics
from soul.voice.gemini_voice import AudioBuffer
from soul.voice.service import VoiceService
from soul.voice.text_stream import SpeechTextStream


def test_sentence_stream_preserves_entire_reply_and_skips_split_code_fences():
    stream = SpeechTextStream()
    first = "This first sentence is ready to speak now. "
    last = "The last sentence must also be spoken completely."
    stream.feed(first + "``")
    stream.feed("`python\nsecret_code()\n``")
    stream.feed("`\n" + last)
    stream.finish()
    values = []
    while not stream.queue.empty():
        value = stream.queue.get_nowait()
        if value is not None:
            values.append(value)
    assert " ".join(values) == first.strip() + " " + last
    assert all(len(value) <= 240 for value in values)


def test_long_speech_is_explicitly_bounded_and_retains_numbers():
    stream = SpeechTextStream(max_characters=300)
    stream.feed("The price is 12.50 and the version is 3.1. " * 50)
    stream.finish()
    assert stream.truncated
    assert stream.received == 300
    assert stream.queue.qsize() <= stream.queue.maxsize
    assert "12.50" in stream.queue.get_nowait()


@pytest.mark.asyncio
async def test_voice_starts_before_text_finishes_prefetches_and_plays_once_in_order():
    generated, played = [], []
    playback_started = asyncio.Event()
    second_generated = asyncio.Event()
    release_playback = asyncio.Event()

    class Generator:
        async def generate(self, text):
            generated.append(text)
            if len(generated) == 2:
                second_generated.set()
            return AudioBuffer(bytes([len(generated), 0]) * 64, 16000)

    class Player:
        on_amplitude = None

        async def play(self, audio):
            played.append(audio.data[0])
            if len(played) == 1:
                playback_started.set()
                await release_playback.wait()

    events = EventBus()
    state = StateManager(events=events)
    voice = VoiceService(Generator(), Player())
    stream = SpeechTextStream()
    metrics = TurnMetrics()
    task = asyncio.create_task(voice.speak_stream(stream, state, metrics))
    stream.feed("This first sentence can already start playing. ")
    await asyncio.wait_for(playback_started.wait(), 1)
    assert not stream.closed
    stream.feed("This next sentence generates while the first one plays. ")
    await asyncio.wait_for(second_generated.wait(), 1)
    stream.finish()
    release_playback.set()
    await asyncio.wait_for(task, 1)
    assert played == [1, 2]
    kinds = [event.type for event in events.history]
    assert kinds.count("SpeechStarted") == kinds.count("SpeechEnded") == 1
    speech = next(event for event in events.history if event.type == "SpeechStarted")
    assert speech.payload["playback"] == "native"
    assert speech.payload["audio_url"] != "/api/audio/last.wav"
    assert not voice.speaking
    assert metrics.first_audio_seconds is not None


@pytest.mark.asyncio
async def test_cancel_stops_playback_and_prefetch_without_deadlocking():
    started = asyncio.Event()
    generated = asyncio.Event()
    stopped = asyncio.Event()
    calls = 0

    class Generator:
        async def generate(self, text):
            nonlocal calls
            calls += 1
            if calls == 3:
                generated.set()
            return AudioBuffer(b"\x01\x00" * 64, 16000)

    class Player:
        on_amplitude = None

        async def play(self, audio):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

    events = EventBus()
    voice = VoiceService(Generator(), Player())
    stream = SpeechTextStream()
    stream.feed("This first sentence is long enough to generate. "
                "This second sentence should be prefetched next. "
                "This third sentence waits in the bounded audio queue.")
    stream.finish()
    task = asyncio.create_task(voice.speak_stream(stream, StateManager(events=events), TurnMetrics()))
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.wait_for(generated.wait(), 1)
    task.cancel()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 1)
    assert stopped.is_set()
    assert not voice.speaking
    assert [event.type for event in events.history].count("SpeechEnded") == 1


@pytest.mark.asyncio
async def test_generation_error_is_propagated_and_native_error_is_not_hidden():
    class Generator:
        async def generate(self, text):
            raise RuntimeError("TTS failed")

    voice = VoiceService(Generator(), SimpleNamespace(on_amplitude=None))
    with pytest.raises(RuntimeError, match="TTS failed"):
        await voice.speak("This text should report an actual audio error.", StateManager(), TurnMetrics())
    assert not voice.speaking


def test_audio_urls_remain_immutable_and_storage_is_bounded():
    voice = VoiceService(None, None)
    first_url = voice._store_audio(AudioBuffer(b"\x01\x00" * 8, 16000))
    first_id = first_url.rsplit("/", 1)[-1][:-4]
    first_clip = voice.audio_segments[first_id]
    voice._store_audio(AudioBuffer(b"\x02\x00" * 8, 16000))
    assert voice.audio_segments[first_id] == first_clip
    for number in range(10):
        voice._store_audio(AudioBuffer(bytes([number, 0]) * 8, 16000))
    assert len(voice.audio_segments) == 8
    assert first_id not in voice.audio_segments
