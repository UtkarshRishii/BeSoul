from __future__ import annotations

import asyncio
import logging
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
from soul.voice.player import AudioPlayer
from soul.voice.service import VoiceService
from soul.cli.renderer import Renderer
from soul.utils.logger import setup_logging
from soul.desktop.bridge import DesktopBridge
from soul.desktop.context import DesktopContext
from soul.desktop.vision import VisionService
from soul.tools.setup import build_registry
from soul.tools.executor import ToolExecutor

async def run(console):
    settings = Settings()
    if not settings.gemini_api_key.get_secret_value().strip():
        console.print("[error]GEMINI_API_KEY is missing. Copy .env.example to .env and add your key.[/]")
        return 1
    logger = setup_logging(settings.soul_data_dir, settings.soul_debug, settings.gemini_api_key.get_secret_value())
    ui = Renderer(console, settings.soul_name)
    state = StateManager(ui.state_changed)
    client = store = desktop_context = bridge = assistant = None
    try:
        client = GeminiClient(settings)
        client.on_model_change = ui.model_changed
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
        input_provider = TerminalInputProvider(console)
        executor = vision = browser = None
        if settings.soul_tools_enabled:
            bridge = DesktopBridge()
            async with asyncio.timeout(8):
                await bridge.call("ping")
            desktop_context = DesktopContext(bridge)
            desktop_context.start()
            async def confirm_action(description):
                if desktop_context.console_handle:
                    try:
                        await bridge.call("focus_window", handle=desktop_context.console_handle)
                    except Exception:
                        pass
                with ui.pause_live():
                    ui.notice(description + " Type CONFIRM to allow; anything else cancels.")
                    return (await input_provider.get_input()).strip() == "CONFIRM"
            if settings.soul_vision_enabled:
                vision = VisionService(bridge, desktop_context, client, settings, state, confirm_action)
            registry, browser = build_registry(bridge, settings, vision)
            executor = ToolExecutor(registry, state, confirm_action, ui, settings.soul_max_tool_calls, desktop=vision)
            prompt += TOOL_SYSTEM_PROMPT
        assistant = Assistant(settings, Brain(client, prompt, executor, vision, browser), memory,
            WorkingMemory(settings.soul_history_turns), VoiceService(GeminiVoice(client), AudioPlayer()),
            state, ui, input_provider)
        assistant.desktop_context = desktop_context
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
