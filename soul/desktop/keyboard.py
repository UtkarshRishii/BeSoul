"""Fixed, bounded physical input. No clipboard, shell commands, or elevated injection."""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from soul.desktop.windows import emergency_check, foreground, require_windows, last_input_tick
from soul.tools.keyboard import KEY_CODES, restricted_input_window, validate_keyboard_request
from soul.tools.models import ToolError


def _send(events: list[tuple[int, int, int]]) -> None:
    # Include all INPUT union members so cbSize follows the native ABI on x86 and x64.
    pointer = ctypes.c_size_t

    class KeyInput(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", pointer)]

    class MouseInput(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", pointer)]

    class HardwareInput(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

    class InputUnion(ctypes.Union):
        _fields_ = [("ki", KeyInput), ("mi", MouseInput), ("hi", HardwareInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("value", InputUnion)]

    values = (Input * len(events))()
    for index, (key, scan, flags) in enumerate(events):
        values[index].type = 1
        values[index].value.ki = KeyInput(key, scan, flags, 0, 0)
    send = ctypes.windll.user32.SendInput
    send.argtypes = [wintypes.UINT, ctypes.POINTER(Input), ctypes.c_int]
    send.restype = wintypes.UINT
    inserted = send(len(values), values, ctypes.sizeof(Input))
    if inserted != len(values):
        # If Windows accepted only part of a chord, release our modifiers before reporting failure.
        import win32api
        for modifier in (0x10, 0x11, 0x12):
            win32api.keybd_event(modifier, 0, 0x0002, 0)
        error = ToolError("INPUT_BLOCKED", "Windows blocked some keyboard input. Inspect the application before retrying.")
        error.data = {"action_dispatched": inserted > 0, "desired_result_verified": False,
                      "observation_required": inserted > 0, "input_events_dispatched": inserted}
        raise error


def _guard(arguments: dict, *, check_input_tick: bool = True) -> None:
    import win32api
    emergency_check()
    current = foreground()
    if (current["handle"], current["pid"]) != (arguments["window_handle"], arguments["window_pid"]):
        raise ToolError("FOCUS_LOST", "The grounded application lost focus. Observe again before typing.")
    if current["bounds"] != arguments["window_bounds"]:
        raise ToolError("SCREEN_CHANGED", "Window geometry changed before keyboard input.")
    if restricted_input_window(current):
        raise ToolError("RESTRICTED_WINDOW", "Keyboard automation is disabled in command shells and interpreters.")
    x, y = win32api.GetCursorPos()
    cx, cy = arguments["cursor"]
    if abs(x-cx) > arguments.get("takeover_tolerance", 12) or abs(y-cy) > arguments.get("takeover_tolerance", 12):
        raise ToolError("USER_TAKEOVER", "The user moved the pointer. Automation stopped to yield control.")
    import win32con
    if win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000:
        raise ToolError("USER_TAKEOVER", "A physical key or mouse button is held. Automation yielded control.")
    if (check_input_tick and arguments.get("last_input_tick") is not None and
            last_input_tick() != arguments["last_input_tick"]):
        raise ToolError("USER_TAKEOVER", "New input arrived after grounding. Automation yielded control.")


def keyboard(arguments: dict) -> dict:
    require_windows()
    action = arguments.get("action")
    validate_keyboard_request(action, arguments)
    _guard(arguments)
    if action == "type_text":
        # A pair for every UTF-16 unit supports all languages, including supplementary characters.
        encoded = arguments["text"].encode("utf-16-le")
        units = [int.from_bytes(encoded[index:index+2], "little") for index in range(0, len(encoded), 2)]
        dispatched = 0
        try:
            for offset in range(0, len(units), 8):
                _guard(arguments, check_input_tick=False)
                batch = units[offset:offset+8]
                _send([(0, unit, flag) for unit in batch for flag in (0x0004, 0x0006)])
                dispatched += len(batch)
                time.sleep(0.01)
        except ToolError as error:
            if dispatched:
                characters_sent = len(encoded[:dispatched*2].decode("utf-16-le", errors="ignore"))
                error.data = {**getattr(error, "data", {}), "action_dispatched": True,
                              "desired_result_verified": False, "observation_required": True,
                              "utf16_units_dispatched": dispatched, "characters_dispatched": characters_sent}
                error.args = (f"{error} Sent input for {characters_sent} characters before stopping; "
                              "field contents remain unverified.",)
            raise
        return {"action": action, "characters": len(arguments["text"]), "action_dispatched": True,
                "executed": True, "desired_result_verified": False}
    names = arguments["key"].split("+") if action == "press_key" else arguments["shortcut"].split("+")
    codes = [KEY_CODES[name] for name in names]
    # Each chord is one native batch including releases, so cancellation cannot strand a held modifier.
    _send([(code, 0, 0) for code in codes] + [(code, 0, 0x0002) for code in reversed(codes)])
    return {"action": action, "key": arguments.get("key", arguments.get("shortcut")),
            "action_dispatched": True, "executed": True, "desired_result_verified": False}
