import asyncio
from types import SimpleNamespace

import aiohttp
import pytest

from soul.config.settings import Settings
from soul.events import EventBus
from soul.ui_bridge.input import DesktopInputProvider
from soul.ui_bridge.server import DesktopServer


async def server_fixture(tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>Soul</html>")
    settings = Settings(_env_file=None, gemini_api_key="unit-test", soul_data_dir=tmp_path)
    events = EventBus()
    provider = DesktopInputProvider()
    server = DesktopServer(events, settings, provider, static_dir=static)
    actions = []
    assistant = SimpleNamespace(continuous_listening=False, continuous_phase="off", microphone=None,
                                voice=SimpleNamespace(speaking=False, last_wav_bytes=b"last", audio_segments={}))

    async def continuous(enabled):
        assistant.continuous_listening = enabled
        assistant.continuous_phase = "paused" if enabled else "off"
        actions.append(("continuous", enabled))
        events.publish("ContinuousListeningChanged", {"enabled": enabled, "phase": assistant.continuous_phase})
        return enabled

    async def cancel():
        actions.append(("cancel", None))

    async def stop_voice():
        assistant.voice.speaking = False
        actions.append(("voice", None))

    assistant.set_continuous_listening = continuous
    assistant.cancel_current = cancel
    assistant.stop_voice = stop_voice
    server.attach_assistant(assistant)
    await server.start()
    server.ready = True
    session = aiohttp.ClientSession(headers={"Authorization": "Bearer " + server.token})
    return server, assistant, provider, session, actions


@pytest.mark.asyncio
async def test_continuous_api_has_authenticated_explicit_boolean_contract(tmp_path):
    server, assistant, _, session, _ = await server_fixture(tmp_path)
    try:
        async with aiohttp.ClientSession() as unauthorized:
            response = await unauthorized.post(server.origin + "/api/microphone/continuous", json={"enabled": True})
            assert response.status == 401
        response = await session.post(server.origin + "/api/microphone/continuous", json={"enabled": "true"})
        assert response.status == 400
        response = await session.post(server.origin + "/api/microphone/continuous", json={"enabled": True})
        assert await response.json() == {"continuous_listening": True, "continuous_phase": "paused"}
        assert assistant.continuous_listening
        assistant.microphone = object()
        assistant.voice.speaking = True
        bootstrap = await (await session.get(server.origin + "/api/bootstrap")).json()
        assert bootstrap["continuous_listening"]
        assert bootstrap["microphone_active"]
        assert bootstrap["speaking_active"]
        assert "gemini_api_key" not in bootstrap["preferences"]
    finally:
        await session.close()
        await server.close()


@pytest.mark.asyncio
async def test_stop_turns_off_continuous_before_cancelling_actions(tmp_path):
    server, assistant, provider, session, actions = await server_fixture(tmp_path)
    try:
        assistant.continuous_listening = True
        provider.submit("stale pending transcript")
        response = await session.post(server.origin + "/api/stop", json={})
        assert response.status == 200
        assert actions == [("continuous", False), ("cancel", None)]
        assert provider.queue.empty()
        assert not assistant.continuous_listening
    finally:
        await session.close()
        await server.close()


@pytest.mark.asyncio
async def test_microphone_permission_and_confirmation_prevent_auto_capture(tmp_path):
    server, _, _, session, actions = await server_fixture(tmp_path)
    future = asyncio.get_running_loop().create_future()
    try:
        server.settings.soul_microphone_enabled = False
        response = await session.post(server.origin + "/api/microphone/continuous", json={"enabled": True})
        assert response.status == 409
        server.settings.soul_microphone_enabled = True
        server.confirmations["pending"] = (future, {})
        response = await session.post(server.origin + "/api/microphone/continuous", json={"enabled": True})
        assert response.status == 409
        assert actions == []
        response = await session.post(server.origin + "/api/microphone/continuous", json={"enabled": False})
        assert response.status == 200
    finally:
        await session.close()
        await server.close()


@pytest.mark.asyncio
async def test_voice_mute_and_engine_switch_stop_current_audio_live(tmp_path):
    server, assistant, _, session, actions = await server_fixture(tmp_path)
    try:
        assistant.voice.speaking = True
        response = await session.patch(server.origin + "/api/preferences", json={"soul_tts_enabled": False})
        assert response.status == 200
        assert not assistant.voice.speaking
        response = await session.patch(server.origin + "/api/preferences", json={"soul_voice_engine": "gemini"})
        result = await response.json()
        assert response.status == 200
        assert result["preferences"]["soul_voice_engine"] == "gemini"
        assert not result["restart_required"]
        assert actions.count(("voice", None)) == 2
    finally:
        await session.close()
        await server.close()


@pytest.mark.asyncio
async def test_immutable_audio_route_returns_exact_clip_or_expired(tmp_path):
    server, assistant, _, session, _ = await server_fixture(tmp_path)
    segment = "a" * 32
    try:
        assistant.voice.audio_segments[segment] = b"first-wav"
        response = await session.get(server.origin + "/api/audio/" + segment + ".wav")
        assert response.status == 200
        assert await response.read() == b"first-wav"
        assert response.headers["Cache-Control"] == "no-store"
        del assistant.voice.audio_segments[segment]
        response = await session.get(server.origin + "/api/audio/" + segment + ".wav")
        assert response.status == 404
    finally:
        await session.close()
        await server.close()


@pytest.mark.asyncio
async def test_stop_rejects_a_late_push_to_talk_transcript(tmp_path):
    server, assistant, provider, session, _ = await server_fixture(tmp_path)
    started, release = asyncio.Event(), asyncio.Event()

    async def finish():
        started.set()
        await release.wait()
        return "stale transcript"

    assistant.finish_listening = finish
    pending = asyncio.create_task(session.post(server.origin + "/api/microphone/finish", json={}))
    try:
        await asyncio.wait_for(started.wait(), 1)
        await session.post(server.origin + "/api/stop", json={})
        release.set()
        response = await asyncio.wait_for(pending, 1)
        assert await response.json() == {"transcript": "", "accepted": False}
        assert provider.queue.empty()
    finally:
        release.set()
        await asyncio.gather(pending, return_exceptions=True)
        await session.close()
        await server.close()
