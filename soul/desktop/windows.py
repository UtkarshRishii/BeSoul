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
        started = process.create_time()
    except (psutil.Error, OSError):
        executable, name = "", "unknown"
        started = None
    return {"handle": hwnd, "pid": pid, "application": name,
            "executable": executable, "title": win32gui.GetWindowText(hwnd),
            "bounds": list(win32gui.GetWindowRect(hwnd)), "process_started": started,
            "window_class": win32gui.GetClassName(hwnd), "application_id": Path(executable).stem.lower() if executable else name}


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
    import ctypes
    if not win32gui.IsWindow(hwnd):
        raise ToolError("WINDOW_GONE", "The target window has closed.")
    try:
        user32 = ctypes.windll.user32
        user32.AllowSetForegroundWindow(-1)
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        user32.keybd_event(0x12, 0, 0, 0)
        user32.SetForegroundWindow(hwnd)
        user32.keybd_event(0x12, 0, 2, 0)
        user32.BringWindowToTop(hwnd)
    except Exception:
        pass
    time.sleep(0.1)
    try:
        result = foreground()
        if result["handle"] == hwnd:
            return result
    except Exception:
        pass
    try:
        return window_info(hwnd)
    except Exception:
        return foreground()


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


def last_input_tick() -> int | None:
    """Session-local input freshness marker; no key values or typed contents are collected."""
    if os.name != "nt":
        return None

    class LastInputInfo(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    information = LastInputInfo()
    information.cbSize = ctypes.sizeof(information)
    if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(information)):
        return int(information.dwTime)
    return None
