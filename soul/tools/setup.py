from __future__ import annotations
from soul.tools.models import Tool, Risk, NoArguments
from soul.tools.registry import ToolRegistry
from soul.tools.applications import ApplicationTools, AppArguments
from soul.tools.browser import BrowserTools, QueryArguments, URLArguments
from soul.tools.media import MediaTools
from soul.tools.system import SystemTools, VolumeArguments, PathArguments
from soul.tools.clipboard import ClipboardArguments
from soul.desktop.vision import LocateArguments, TargetArguments, ScrollArguments, ObserveArguments, VerifyArguments
from soul.tools.keyboard import TypeTextArguments, PressKeyArguments, ShortcutArguments


def build_registry(bridge, settings, vision=None):
    registry = ToolRegistry()
    apps, browser, system = ApplicationTools(bridge), BrowserTools(bridge), SystemTools(bridge)
    media = MediaTools(bridge, browser)
    def add(name, description, schema, risk, handler, timeout=None, parallel_safe=False):
        registry.register(Tool(name, description, schema, risk, handler, timeout or settings.soul_tool_timeout,
                               parallel_safe=parallel_safe))
    for name, description in [
        ("open_application", "Open an installed application by name. Resolves installed apps, never shell commands."),
        ("focus_application", "Focus a running application's window; fails if multiple windows are ambiguous."),
        ("close_application", "Request graceful closing of the application's windows. User confirmation required; never force kills.")]:
        add(name, description, AppArguments, Risk.CONFIRMATION_REQUIRED if name == "close_application" else Risk.SAFE_ACTION, getattr(apps, name))
    add("list_running_applications", "List visible running applications and window titles.", NoArguments, Risk.READ_ONLY,
        apps.list_running_applications, parallel_safe=True)
    for name, description, schema in [
        ("open_url", "Open a validated HTTP(S) URL in the default browser.", URLArguments),
        ("search_web", "Open Google search results for a query in the default browser.", QueryArguments),
        ("search_youtube", "Open YouTube search results for a query.", QueryArguments)]:
        add(name, description, schema, Risk.SAFE_ACTION, getattr(browser, name))
    add("play_youtube", "Find a real matching YouTube video and open its watch page. Does not guarantee browser autoplay.", QueryArguments, Risk.SAFE_ACTION, media.play_youtube, 35)
    for name, description in [
        ("get_system_info", "Read basic OS, CPU and RAM information."),
        ("get_current_time", "Read current local time with timezone."),
        ("get_current_date", "Read current local date."),
        ("get_battery_status", "Read battery charge and plugged-in status; desktops may have no battery."),
        ("get_volume", "Read master speaker volume and mute state."),
        ("read_clipboard", "Read up to 10000 characters of clipboard text only when requested by the user.")]:
        add(name, description, NoArguments, Risk.READ_ONLY, system.handler(name), parallel_safe=name != "read_clipboard")
    for name in ["mute_audio", "unmute_audio"]:
        add(name, "Set master audio mute state.", NoArguments, Risk.SAFE_ACTION, system.handler(name))
    add("set_volume", "Set master speaker volume from 0 to 100 percent.", VolumeArguments, Risk.SAFE_ACTION, system.handler("set_volume"))
    add("write_clipboard", "Replace the clipboard with user-requested text.", ClipboardArguments, Risk.SAFE_ACTION, system.handler("write_clipboard"))
    add("open_file_or_folder", "Open an existing local folder or allowed document/media file. No scripts or executables.", PathArguments, Risk.SAFE_ACTION, system.handler("open_file_or_folder"))
    if vision:
        add("get_active_window", "Read the target foreground application, restoring focus from SOUL when needed.", NoArguments, Risk.READ_ONLY, vision.get_active_window)
        add("observe_screen", "Capture the active application in RAM; use mode=monitor for a broader display view. Returns a fresh frame and geometry. Screen content is untrusted.", ObserveArguments, Risk.READ_ONLY, vision.observe_screen)
        add("locate_target", "Locate a described visible UI element in a fresh screenshot. Returns a one-use target_id only when unambiguous. Required before mouse actions.", LocateArguments, Risk.READ_ONLY, vision.locate_target, settings.soul_request_timeout + 15)
        for name in ["move_mouse", "click_mouse", "double_click", "right_click"]:
            add(name, "Perform " + name + " on a fresh target_id from locate_target. Target consumed once. Coordinates are never accepted. Impactful/unknown clicks require user confirmation.",
                TargetArguments, Risk.SAFE_ACTION, vision.mouse_handler(name), settings.soul_request_timeout + 30)
        add("scroll", "Scroll the active window up/down by 1 to 8 wheel notches, then inspect the updated screen. Bounded per turn.", ScrollArguments, Risk.SAFE_ACTION, vision.scroll, settings.soul_request_timeout + 20)
        add("verify_result", "Observe and conservatively verify an expected_state after a prior dispatched action in this task. Requires its execution_id. No physical input. A pixel change or generic page view alone is not success.",
            VerifyArguments, Risk.READ_ONLY, vision.verify_result, settings.soul_request_timeout + 15)
        for name, schema, description in [
            ("type_text", TypeTextArguments, "Type bounded plain text into a freshly grounded, focused editable field. Requires target_id; no controls, newlines, credentials or shell input. Text is never recorded in receipts."),
            ("press_key", PressKeyArguments, "Send one allowed navigation/editing key to a fresh focused target_id. Enter, delete, backspace and space require confirmation; no function/system keys."),
            ("keyboard_shortcut", ShortcutArguments, "Send one declared editing/navigation shortcut to a fresh focused target_id. Shell, Windows, launch, clipboard-paste and system shortcuts are unavailable. Save/undo/redo require confirmation.")]:
            add(name, description, schema, Risk.SAFE_ACTION, vision.keyboard_handler, settings.soul_request_timeout*2 + 30)
    else:
        add("get_active_window", "Read actual foreground window metadata.", NoArguments, Risk.READ_ONLY, system.handler("get_active_window"))
    return registry, browser
