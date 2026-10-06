from __future__ import annotations

import asyncio
import logging
from time import perf_counter
from google import genai
from google.genai import types

class GeminiClient:
    """The only module that calls Google's SDK. Tool execution is always explicit."""
    def __init__(self, settings):
        self.settings = settings
        self.client = genai.Client(api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=int(settings.soul_request_timeout * 1000),
                                          retry_options=types.HttpRetryOptions(attempts=1)))
        self.verified = False
        self.primary_cooldown = 0.0
        self.active_model = settings.gemini_text_model
        self.on_model_change = None

    def fast_config(self, config, model):
        if not self.settings.soul_fast_responses:
            return config
        if model.startswith("gemini-3"):
            config.thinking_config = types.ThinkingConfig(thinking_level="MINIMAL")
        elif model.startswith("gemini-2.5-flash"):
            config.thinking_config = types.ThinkingConfig(thinking_budget=0)
        return config

    def selected_model(self):
        if self.settings.soul_response_mode == "fast" and self.settings.gemini_fallback_model:
            return self.settings.gemini_fallback_model
        if perf_counter() < getattr(self, "primary_cooldown", 0) and self.settings.gemini_fallback_model:
            return self.settings.gemini_fallback_model
        return self.settings.gemini_text_model

    def fallback(self, exc, model):
        fallback = self.settings.gemini_fallback_model
        if fallback and model != fallback and (isinstance(exc, TimeoutError) or getattr(exc, "code", None) in {500, 502, 503, 504}):
            self.primary_cooldown = perf_counter() + 120
            if getattr(self, "on_model_change", None):
                self.on_model_change(f"{model} unavailable · using {fallback}")
            return fallback
        return None

    async def tool_conversation(self, messages, system, on_chunk, metrics, executor):
        contents = [types.Content(role=m.role, parts=[types.Part.from_text(text=m.text)]) for m in messages]
        declarations = [types.FunctionDeclaration(**item) for item in executor.registry.declarations()]
        executor.reset()
        model = self.selected_model()
        request_seconds = 0.0
        async with asyncio.timeout(self.settings.soul_turn_timeout):
            for iteration in range(self.settings.soul_max_tool_iterations + 1):
                final_only = iteration == self.settings.soul_max_tool_iterations or executor.stopped
                config = types.GenerateContentConfig(
                    system_instruction=system + ("\nAction budget ended. Give an honest final report; perform no further actions." if final_only else ""),
                    tools=[types.Tool(function_declarations=declarations)],
                    tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="NONE" if final_only else "AUTO")),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
                start = perf_counter()
                emitted = False
                def emit(text):
                    nonlocal emitted
                    emitted = True
                    on_chunk(text)
                try:
                    content, usage, request_id = await self._tool_response(contents, self.fast_config(config, model), emit, model)
                except Exception as exc:
                    alternate = self.fallback(exc, model) if iteration == 0 and not emitted else None
                    if not alternate:
                        raise
                    model = alternate
                    content, usage, request_id = await self._tool_response(contents, self.fast_config(config, model), emit, model)
                self.active_model = model
                request_seconds += perf_counter()-start
                metrics.gemini_seconds = request_seconds
                if usage:
                    if usage.prompt_token_count is not None:
                        metrics.input_tokens = (metrics.input_tokens or 0) + usage.prompt_token_count
                    if usage.candidates_token_count is not None:
                        metrics.output_tokens = (metrics.output_tokens or 0) + usage.candidates_token_count
                logging.getLogger("soul").debug("gemini_response id=%s iteration=%s", request_id, iteration)
                self.verified = True
                calls = [p.function_call for p in content.parts or [] if p.function_call]
                if not calls:
                    text = "".join(p.text for p in content.parts or [] if p.text and not p.thought).strip()
                    if not text:
                        raise ValueError("Gemini returned no final text")
                    # Only the final response is rendered/spoken. Planning prose isn't a completed action.
                    if not self.settings.soul_streaming:
                        on_chunk(text)
                    return text
                if final_only:
                    raise RuntimeError("Gemini requested tools after the execution budget ended")
                # Preserve the exact model parts, including thought signatures and function IDs.
                contents.append(content)
                responses = []
                for call in calls:
                    result = await executor.execute(call.name, call.args or {})
                    response = types.FunctionResponse(name=call.name, id=call.id, response=result.payload())
                    if result.image:
                        response.parts = [types.FunctionResponsePart(inline_data=types.FunctionResponseBlob(
                            mime_type="image/png", data=result.image))]
                    responses.append(types.Part(function_response=response))
                # Retain metadata but only the most recent image-bearing tool batch in request history.
                for item in contents:
                    for part in item.parts or []:
                        if part.function_response:
                            part.function_response.parts = None
                contents.append(types.Content(role="user", parts=responses))
        raise RuntimeError("Tool loop ended without a response")

    async def _tool_response(self, contents, config, on_chunk, model=None):
        model = model or self.settings.gemini_text_model
        async with asyncio.timeout(self.settings.soul_request_timeout):
            if self.settings.soul_streaming:
                parts, usage, request_id = [], None, None
                stream = await self.client.aio.models.generate_content_stream(
                    model=model, contents=contents, config=config)
                try:
                    async for chunk in stream:
                        if chunk.candidates and chunk.candidates[0].content:
                            for part in chunk.candidates[0].content.parts or []:
                                parts.append(part)  # Preserve thought signatures, even on empty text parts.
                                if part.text and not part.thought:
                                    on_chunk(part.text)
                        if chunk.usage_metadata:
                            usage = chunk.usage_metadata
                        if chunk.response_id:
                            request_id = chunk.response_id
                finally:
                    await stream.aclose()
                return types.Content(role="model", parts=parts), usage, request_id
            response = await self.client.aio.models.generate_content(
                model=model, contents=contents, config=config)
        if not response.candidates or not response.candidates[0].content:
            raise ValueError("Gemini returned no candidate content")
        return response.candidates[0].content, response.usage_metadata, response.response_id

    async def vision(self, prompt, images, schema):
        model = self.settings.gemini_vision_model or self.selected_model()
        async def request(model):
            async with asyncio.timeout(self.settings.soul_request_timeout):
                return await self.client.aio.models.generate_content(
                    model=model,
                    contents=types.Content(role="user", parts=[types.Part.from_text(text=prompt)] +
                                          [types.Part.from_bytes(data=image, mime_type="image/png") for image in images]),
                    config=self.fast_config(types.GenerateContentConfig(response_mime_type="application/json", response_schema=schema), model))
        try:
            response = await request(model)
        except Exception as exc:
            alternate = self.fallback(exc, model)
            if not alternate:
                raise
            response = await request(alternate)
        return schema.model_validate_json(response.text or "")

    async def respond(self, messages, system, on_chunk, metrics, tools=None):
        config = types.GenerateContentConfig(system_instruction=system, tools=tools or None,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
        contents = [types.Content(role=m.role, parts=[types.Part.from_text(text=m.text)]) for m in messages]
        model = self.selected_model()
        emitted = False
        def emit(text):
            nonlocal emitted
            emitted = True
            on_chunk(text)
        try:
            content, usage, _ = await self._tool_response(contents, self.fast_config(config, model), emit, model)
        except Exception as exc:
            alternate = self.fallback(exc, model) if not emitted else None
            if not alternate:
                raise
            model = alternate
            content, usage, _ = await self._tool_response(contents, self.fast_config(config, model), emit, model)
        if any(part.function_call for part in content.parts or []):
            raise RuntimeError("No tool executor is installed for this request")
        text = "".join(part.text for part in content.parts or [] if part.text and not part.thought).strip()
        if not text:
            raise ValueError("Gemini returned no text")
        if not self.settings.soul_streaming:
            on_chunk(text)
        if usage:
            metrics.input_tokens = usage.prompt_token_count
            metrics.output_tokens = usage.candidates_token_count
        self.verified, self.active_model = True, model
        return text

    @staticmethod
    def _collect(response, chunks, on_chunk, metrics):
        if response.function_calls:
            raise RuntimeError("Function call requested but no tool executor is installed")
        if response.text:
            chunks.append(response.text)
            on_chunk(response.text)
        usage = response.usage_metadata
        if usage:
            metrics.input_tokens = usage.prompt_token_count
            metrics.output_tokens = usage.candidates_token_count

    async def extract(self, text, prompt, schema):
        # A small structured extraction does not need the main reasoning model.
        model = self.settings.gemini_fallback_model or self.selected_model()
        async with asyncio.timeout(self.settings.soul_request_timeout):
            response = await self.client.aio.models.generate_content(
                model=model, contents=text,
                config=self.fast_config(types.GenerateContentConfig(system_instruction=prompt,
                    response_mime_type="application/json", response_schema=schema), model))
        return schema.model_validate_json(response.text or "")

    async def audio(self, text):
        async with asyncio.timeout(self.settings.soul_request_timeout):
            response = await self.client.aio.models.generate_content(
                model=self.settings.gemini_voice_model,
                contents="Read aloud calmly and naturally, verbatim:\n" + text,
                config=types.GenerateContentConfig(response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=self.settings.gemini_voice_name)))))
        parts = [p.inline_data for c in response.candidates or [] for p in (c.content.parts if c.content else []) or [] if p.inline_data]
        if not parts or not all(p.data for p in parts):
            raise ValueError("Gemini returned no audio")
        mime = parts[0].mime_type or ""
        if any(p.mime_type != mime for p in parts):
            raise ValueError("Inconsistent audio formats")
        return b"".join(p.data for p in parts), mime

    async def close(self):
        await self.client.aio.aclose()
        self.client.close()
