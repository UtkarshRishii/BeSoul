from types import SimpleNamespace

import pytest
from google.genai import types

from soul.ai.gemini_client import GeminiClient
from soul.config.settings import Settings
from soul.core.brain import Brain
from soul.tools.models import ToolResult
from soul.utils.timing import TurnMetrics


def client_fixture():
    client = GeminiClient.__new__(GeminiClient)
    client.settings = Settings(_env_file=None, gemini_api_key="unit-test", gemini_text_model="gemini-3.5-flash",
                               gemini_fallback_model="gemini-3.5-flash-lite", soul_response_mode="full")
    client.verified = False
    client.primary_cooldown = 0.0
    client.active_model = client.settings.gemini_text_model
    client.on_model_change = None
    return client


@pytest.mark.asyncio
async def test_ordinary_answer_requires_one_model_request_and_no_executor_actions():
    client = client_fixture()
    requests, chunks = [], []
    executor = SimpleNamespace(registry=SimpleNamespace(declarations=lambda: []), reset=lambda: None,
                               stopped=False, request_final_report=False, task=None)

    async def response(contents, config, emit, model):
        requests.append(model)
        emit("A direct conversational answer.")
        return types.Content(role="model", parts=[types.Part.from_text(text="A direct conversational answer.")]), None, None

    client._tool_response = response
    answer = await client.tool_conversation([SimpleNamespace(role="user", text="Hello")], "system", chunks.append,
                                            TurnMetrics(), executor)
    assert answer == "A direct conversational answer."
    assert chunks == [answer]
    assert requests == ["gemini-3.5-flash"]


@pytest.mark.asyncio
async def test_prose_before_tool_calls_is_never_rendered_or_spoken():
    client = client_fixture()
    chunks, requests = [], []
    executor = SimpleNamespace(registry=SimpleNamespace(declarations=lambda: []), reset=lambda: None,
                               stopped=False, request_final_report=False, task=None)

    async def execute_many(calls):
        assert calls == [("finalize_task", {})]
        executor.request_final_report = True
        return [ToolResult(success=True, message="Final report requested")]

    executor.execute_many = execute_many

    async def response(contents, config, emit, model):
        requests.append(config.tool_config.function_calling_config.mode)
        if len(requests) == 1:
            emit("This unverified plan must remain private.")
            return types.Content(role="model", parts=[types.Part.from_text(text="This unverified plan must remain private."),
                types.Part(function_call=types.FunctionCall(name="finalize_task", args={}, id="call-1"))]), None, None
        emit("Here is the honest final report.")
        assert chunks == ["Here is the honest final report."]
        return types.Content(role="model", parts=[types.Part.from_text(text=chunks[0])]), None, None

    client._tool_response = response
    await client.tool_conversation([SimpleNamespace(role="user", text="Perform an action")], "system", chunks.append,
                                   TurnMetrics(), executor)
    assert requests == ["AUTO", "NONE"]
    assert chunks == ["Here is the honest final report."]


@pytest.mark.asyncio
async def test_audio_keeps_full_supplied_segment_including_later_sentences():
    client = client_fixture()
    requests = []

    async def generate_content(**request):
        requests.append(request)
        return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[
            SimpleNamespace(inline_data=SimpleNamespace(data=b"\x01\x00", mime_type="audio/L16;rate=24000"))]))])

    client.client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    text = "First spoken sentence. " + "Every later sentence must be preserved too. " * 10
    data, mime = await client.audio(text)
    assert requests[0]["contents"] == "Read this aloud naturally:\n" + text.strip()
    assert data == b"\x01\x00"


@pytest.mark.asyncio
async def test_prompt_skips_finalization_for_conversation_but_retains_receipt_verification():
    brain = Brain(None, "system", executor=SimpleNamespace())
    captured = []

    async def run(text, messages, system, on_chunk, metrics):
        captured.append(system)
        return "reply"

    brain.engine.run = run
    await brain.respond(SimpleNamespace(messages=[]), "Hello", [], lambda _: None, TurnMetrics())
    assert "answer directly without calling finalize_task" in captured[0]
    assert "After using tools" in captured[0]
    assert "Verify meaningful UI transitions" in captured[0]
