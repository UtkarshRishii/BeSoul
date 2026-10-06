from __future__ import annotations

import ctypes
import os
import time
from pathlib import Path
import psutil
from soul.tools.models import ToolError


def require_windows():
    if os.name != "nt":
        raise ToolError("UNSUPPORTED_OS", "This desktop capability currently requires Windows.")


def enable_dpi_awareness():
    if os.name == "nt":
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()


def window_info(hwnd: int) -> dict:
    import win32gui
    import win32process
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    try:
        process = psutil.Process(pid)
        executable = process.exe()
        name = process.name()
    except (psutil.Error, OSError):
        executable, name = "", "unknown"
    return {"handle": hwnd, "pid": pid, "application": name,
            "executable": executable, "title": win32gui.GetWindowText(hwnd),
            "bounds": list(win32gui.GetWindowRect(hwnd))}


def visible_windows() -> list[dict]:
    require_windows()
    import win32gui
    result = []
    def collect(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            try:
                result.append(window_info(hwnd))
            except Exception:
                pass  # Windows may disappear during enumeration.
    win32gui.EnumWindows(collect, None)
    return result


def foreground() -> dict:
    require_windows()
    import win32gui
    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        raise ToolError("NO_ACTIVE_WINDOW", "No foreground window is available.")
    return window_info(hwnd)


def focus(hwnd: int) -> dict:
    require_windows()
    import win32gui
    import win32con
    if not win32gui.IsWindow(hwnd):
        raise ToolError("WINDOW_GONE", "The target window has closed.")
    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        raise ToolError("FOCUS_DENIED", "Windows blocked focus. Select the target window manually and try again.") from None
    time.sleep(0.15)
    result = foreground()
    if result["handle"] != hwnd:
        raise ToolError("FOCUS_DENIED", "Target window did not become active.")
    return result


def emergency_check():
    require_windows()
    import win32api
    import win32con
    x, y = win32api.GetCursorPos()
    if win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000:
        raise ToolError("EMERGENCY_STOP", "Escape emergency stop activated.")
    for monitor, _, _ in win32api.EnumDisplayMonitors():
        left, top, right, bottom = win32api.GetMonitorInfo(monitor)["Monitor"]
        if any(abs(x-cx) <= 3 and abs(y-cy) <= 3 for cx, cy in
               [(left, top), (right-1, top), (left, bottom-1), (right-1, bottom-1)]):
            raise ToolError("EMERGENCY_STOP", "Mouse corner failsafe activated.")
