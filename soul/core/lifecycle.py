from __future__ import annotations

import asyncio
import logging
import inspect
from soul.events import EventBus
from soul.config.settings import Settings
from soul.ai.prompts import DEFAULT_SYSTEM_PROMPT, TOOL_SYSTEM_PROMPT
from soul.ai.gemini_client import GeminiClient
from soul.core.assistant import Assistant
from soul.core.brain import Brain
from soul.core.state import State, StateManager
from soul.memory.long_term import SQLiteMemoryStore
from soul.memory.manager import MemoryManager
from soul.memory.short_term import WorkingMemory
from soul.input.terminal import TerminalInputProvider
from soul.voice.gemini_voice import GeminiVoice
from soul.voice.local_voice import SelectableVoice
from soul.voice.player import AudioPlayer
from soul.voice.service import VoiceService
from soul.cli.renderer import Renderer
from soul.utils.logger import setup_logging
from soul.desktop.bridge import DesktopBridge
from soul.desktop.context import DesktopContext
from soul.desktop.vision import VisionService
from soul.tools.setup import build_registry
from soul.tools.executor import ToolExecutor

async def run(console, *, renderer=None, input_provider=None, confirm_callback=None,
              events=None, on_ready=None, settings=None):
    settings = settings or Settings.load()
    ui = renderer or Renderer(console, settings.soul_name)
    if not settings.gemini_api_key.get_secret_value().strip():
        ui.error("GEMINI_API_KEY is missing. Add your key to .env, then restart SOUL.")
        return 1
    logger = setup_logging(settings.soul_data_dir, settings.soul_debug, settings.gemini_api_key.get_secret_value())
    state = StateManager(ui.state_changed, events=events or EventBus())
    client = store = desktop_context = bridge = assistant = None
    try:
        client = GeminiClient(settings)
        client.on_model_change = ui.model_changed
        voice_generator = GeminiVoice(client)
        if settings.soul_tts_enabled:
            voice_generator.prepare()
        memory = None
        if settings.soul_memory_enabled:
            try:
                store = SQLiteMemoryStore(settings.soul_data_dir / "memories.sqlite3")
                memory = MemoryManager(store, client, settings.soul_memory_limit, (settings.gemini_api_key.get_secret_value(),))
            except Exception:
                logger.exception("memory_startup_failed")
                ui.error("Memory database unavailable. Conversation can continue without persistent memory.")
        prompt = settings.soul_system_prompt_file.read_text(encoding="utf-8") if settings.soul_system_prompt_file else DEFAULT_SYSTEM_PROMPT
        prompt += f"\nYour configured name is {settings.soul_name}."
        input_provider = input_provider or TerminalInputProvider(console)
        executor = vision = browser = None
        if settings.soul_tools_enabled:
            bridge = DesktopBridge()
            try:
                async with asyncio.timeout(8):
                    await bridge.call("ping")
                desktop_context = DesktopContext(bridge)
                desktop_context.start()
            except Exception:
                logger.exception("desktop_startup_failed")
                ui.error("Windows automation is unavailable. Conversation, memory and voice can continue.")
                await bridge.close()
                bridge = None
            async def confirm_action(description):
                if confirm_callback:
                    return await confirm_callback(description)
                if desktop_context.console_handle:
                    try:
                        await bridge.call("focus_window", handle=desktop_context.console_handle)
                    except Exception:
                        pass
                with ui.pause_live():
                    ui.notice(description + " Type CONFIRM to allow; anything else cancels.")
                    return (await input_provider.get_input()).strip() == "CONFIRM"
            if bridge and settings.soul_vision_enabled:
                vision = VisionService(bridge, desktop_context, client, settings, state, confirm_action)
            if bridge:
                registry, browser = build_registry(bridge, settings, vision)
                executor = ToolExecutor(registry, state, confirm_action, ui, settings.soul_max_tool_calls, desktop=vision)
                executor.settings = settings
                if vision:
                    vision.receipt_lookup = lambda execution_id: next((receipt for receipt in
                        getattr(executor.task, "tool_receipts", []) if receipt.get("execution_id") == execution_id), None)
                prompt += TOOL_SYSTEM_PROMPT
        assistant = Assistant(settings, Brain(client, prompt, executor, vision, browser), memory,
            WorkingMemory(settings.soul_history_turns), VoiceService(voice_generator, AudioPlayer()),
            state, ui, input_provider)
        assistant.desktop_context = desktop_context
        assistant.brain.engine.events = state.events
        assistant.brain.engine.state = state
        assistant.confirm_callback = confirm_callback
        if renderer is not None and desktop_context:
            desktop_context.console_handle = 0
        if on_ready:
            ready = on_ready(assistant)
            if inspect.isawaitable(ready):
                await ready
        await assistant.run()
        return 0
    finally:
        if assistant:
            await assistant.close()
        state.set(State.SHUTTING_DOWN)
        if desktop_context:
            desktop_context.close()
        if bridge:
            await bridge.close()
        if store:
            try:
                store.close()
            except Exception:
                logger.exception("memory_close_failed")
        if client:
            try:
                await client.close()
            except Exception:
                logger.exception("client_close_failed")
        ui.notice("Soul offline. Session closed.")
