import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from soul.config.settings import Settings
from soul.core.assistant import Assistant
from soul.core.state import State, StateManager
from soul.events import EventBus
from soul.memory.short_term import WorkingMemory
from soul.ui_bridge.input import DesktopInputProvider
from soul.voice.recorder import SpeechActivityDetector


class FakeRecorder:
    instances = []

    def __init__(self, max_seconds, on_amplitude=None, silence_seconds=None):
        self.endpoint = asyncio.Event()
        self.speech_detected = True
        self.started = self.finished = False
        self.discarded = False
        self.continuous = silence_seconds is not None
        self.instances.append(self)

    async def start(self):
        self.started = True

    async def wait_for_endpoint(self):
        await self.endpoint.wait()

    async def finish(self, discard=False):
        self.finished = True
        self.discarded = discard
        self.endpoint.set()
        return b"" if discard else b"fake-wav"


class FakeUI:
    def __init__(self):
        self.messages = []

    @contextmanager
    def response(self):
        yield self.messages.append

    def notice(self, text):
        self.messages.append(text)

    error = notice


def assistant_fixture(monkeypatch):
    FakeRecorder.instances = []
    monkeypatch.setattr("soul.core.assistant.PushToTalkRecorder", FakeRecorder)
    settings = Settings(_env_file=None, gemini_api_key="unit-test", soul_tts_enabled=False,
                        soul_memory_enabled=False)
    events = EventBus()
    state = StateManager(events=events)
    state.set(State.READY)
    transcriptions = []

    async def transcribe(audio, mime):
        transcriptions.append(audio)
        return "Hello from the microphone"

    async def respond(working, text, memories, on_chunk, metrics):
        on_chunk("Here is the complete assistant reply.")
        return "Here is the complete assistant reply."

    brain = SimpleNamespace(client=SimpleNamespace(transcribe=transcribe, active_model="test"),
                            respond=respond)
    assistant = Assistant(settings, brain, None, WorkingMemory(12), None, state, FakeUI(), DesktopInputProvider())
    return assistant, transcriptions, events


async def until(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0.01)


def test_vad_requires_sustained_speech_and_trailing_silence():
    detector = SpeechActivityDetector(sample_rate=1000, silence_seconds=0.8)
    assert not detector.update(1200, 50)  # One click.
    assert not detector.update(30, 900)
    assert not detector.speech_detected
    assert not detector.update(1200, 250)
    assert detector.speech_detected
    assert not detector.update(50, 799)
    assert detector.update(50, 1)


def test_vad_does_not_treat_silence_as_speech():
    detector = SpeechActivityDetector(sample_rate=1000)
    for _ in range(100):
        assert not detector.update(100, 100)
    assert not detector.speech_detected


@pytest.mark.asyncio
async def test_continuous_capture_submits_once_and_resumes_after_turn(monkeypatch):
    assistant, transcriptions, events = assistant_fixture(monkeypatch)
    await assistant.set_continuous_listening(True)
    try:
        await until(lambda: assistant.microphone is not None)
        recorder = assistant.microphone
        assert recorder.continuous
        assert assistant.continuous_phase == "listening"
        recorder.endpoint.set()
        text = await asyncio.wait_for(assistant.input.get_input(), 1)
        assert text == "Hello from the microphone"
        assert transcriptions == [b"fake-wav"]
        assert assistant.microphone is None
        assert assistant.continuous_phase == "paused"
        await asyncio.sleep(0.12)
        assert assistant.microphone is None  # Pending transcript is not yet a turn.
        await assistant.turn(text)
        await until(lambda: assistant.microphone is not None)
        assert assistant.microphone is not recorder
        assert len(FakeRecorder.instances) == 2
    finally:
        await assistant.set_continuous_listening(False)
    assert assistant.microphone is None
    assert assistant.continuous_phase == "off"
    assert events.history[-1].type == "ContinuousListeningChanged"
    assert events.history[-1].payload == {"enabled": False, "phase": "off"}


@pytest.mark.asyncio
async def test_silent_capture_is_discarded_without_model_request(monkeypatch):
    assistant, transcriptions, _ = assistant_fixture(monkeypatch)
    await assistant.set_continuous_listening(True)
    try:
        await until(lambda: assistant.microphone is not None)
        recorder = assistant.microphone
        recorder.speech_detected = False
        recorder.endpoint.set()
        await until(lambda: assistant.microphone is not None and assistant.microphone is not recorder)
        assert recorder.discarded
        assert transcriptions == []
        assert assistant.input.queue.empty()
    finally:
        await assistant.set_continuous_listening(False)


@pytest.mark.asyncio
async def test_continuous_listening_waits_for_native_output(monkeypatch):
    assistant, _, _ = assistant_fixture(monkeypatch)
    release = asyncio.Event()
    assistant.voice_task = asyncio.create_task(release.wait())
    await assistant.set_continuous_listening(True)
    try:
        await asyncio.sleep(0.15)
        assert assistant.continuous_phase == "paused"
        assert assistant.microphone is None
        release.set()
        await until(lambda: assistant.microphone is not None)
    finally:
        await assistant.set_continuous_listening(False)
        await assistant.stop_voice()


@pytest.mark.asyncio
async def test_disable_cancels_transcription_and_never_submits_stale_audio(monkeypatch):
    assistant, _, _ = assistant_fixture(monkeypatch)
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def transcribe(audio, mime):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    assistant.brain.client.transcribe = transcribe
    await assistant.set_continuous_listening(True)
    await until(lambda: assistant.microphone is not None)
    assistant.microphone.endpoint.set()
    await asyncio.wait_for(started.wait(), 1)
    await asyncio.wait_for(assistant.set_continuous_listening(False), 1)
    assert cancelled.is_set()
    assert assistant.transcription_task is None
    assert assistant.input.queue.empty()
    assert assistant.continuous_task is None


@pytest.mark.asyncio
async def test_manual_microphone_disables_continuous_mode(monkeypatch):
    assistant, _, _ = assistant_fixture(monkeypatch)
    await assistant.set_continuous_listening(True)
    await until(lambda: assistant.microphone is not None)
    old_recorder = assistant.microphone
    assert await assistant.start_listening()
    assert not assistant.continuous_listening
    assert old_recorder.discarded
    assert not assistant.microphone.continuous
    await assistant.cancel_listening()


@pytest.mark.asyncio
async def test_microphone_permission_blocks_continuous_capture(monkeypatch):
    assistant, _, _ = assistant_fixture(monkeypatch)
    assistant.settings.soul_microphone_enabled = False
    with pytest.raises(ValueError, match="Enable the microphone"):
        await assistant.set_continuous_listening(True)
    assert FakeRecorder.instances == []
