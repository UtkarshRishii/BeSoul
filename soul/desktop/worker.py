"""Private fixed-operation OS worker. Not a shell, interpreter tool, or public API."""
from __future__ import annotations

import base64
import io
import json
import os
import platform
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
import psutil
from soul.desktop.windows import (enable_dpi_awareness, require_windows, visible_windows, foreground,
                                  focus, emergency_check, last_input_tick)
from soul.tools.models import ToolError


def matching_windows(name: str) -> list[dict]:
    from soul.desktop.resolver import ApplicationResolver
    app = ApplicationResolver().resolve(name)
    expected = str(app.executable).lower()
    found = [w for w in visible_windows() if w["executable"].lower() == expected]
    if not found:
        # Windows packaged apps can forward a system launcher to another executable location.
        candidates = [w for w in visible_windows() if Path(w["executable"]).name.lower() == app.executable.name.lower()]
        if len({w["executable"].lower() for w in candidates}) == 1:
            found = candidates
    if not found:
        raise ToolError("APP_NOT_RUNNING", "No visible window for that installed application is running.")
    return found


def application(operation: str, args: dict) -> dict:
    import win32gui
    import win32con
    from soul.desktop.resolver import ApplicationResolver
    if operation == "list_running_applications":
        return {"applications": [{k: w[k] for k in ("application", "title", "pid")} for w in visible_windows()][:60]}
    if operation == "open_application":
        app = ApplicationResolver().resolve(args["app_name"])
        os.startfile(str(app.shortcut or app.executable))
        expected = str(app.executable).lower()
        for _ in range(30):
            for process in psutil.process_iter(["pid", "exe", "name"]):
                if (process.info["exe"] or "").lower() == expected or (process.info["name"] or "").lower() == app.executable.name.lower():
                    windows = [w for w in visible_windows() if w["pid"] == process.pid]
                    return {"application": app.name, "pid": process.pid, "window": windows[0] if windows else None,
                            "action_dispatched": True, "desired_result_verified": bool(windows),
                            "observation_required": not bool(windows)}
            time.sleep(0.2)
        raise ToolError("LAUNCH_UNVERIFIED", "Launch was requested, but the expected process could not be verified.")
    windows = matching_windows(args["app_name"])
    if operation == "focus_application":
        if len(windows) != 1:
            raise ToolError("AMBIGUOUS_WINDOW", "Several application windows are open; select the desired window manually.")
        return {**focus(windows[0]["handle"]), "action_dispatched": True, "desired_result_verified": True}
    for window in windows:
        win32gui.PostMessage(window["handle"], win32con.WM_CLOSE, 0, 0)
    for _ in range(25):
        if not any(win32gui.IsWindow(w["handle"]) for w in windows):
            return {"application": args["app_name"], "closed_windows": len(windows),
                    "action_dispatched": True, "desired_result_verified": True}
        time.sleep(0.2)
    raise ToolError("CLOSE_PENDING", "Close requested, but a window remains open (possibly an unsaved-work dialog). No process was force terminated.")


def capture(args: dict) -> dict:
    import mss
    from PIL import Image
    active = foreground()
    with mss.mss() as screen:
        monitors = screen.monitors[1:]
        selected = int(args.get("monitor", 0))
        if selected:
            if selected > len(monitors) or selected < 1:
                raise ToolError("INVALID_MONITOR", "Selected monitor does not exist.")
            monitor = monitors[selected-1]
        else:
            left, top, right, bottom = active["bounds"]
            monitor = max(monitors, key=lambda m: max(0, min(right, m["left"]+m["width"])-max(left, m["left"])) *
                          max(0, min(bottom, m["top"]+m["height"])-max(top, m["top"])))
        mode = args.get("mode", "active_window")
        if mode not in {"active_window", "monitor"}:
            raise ToolError("INVALID_ARGUMENTS", "Capture mode must be active_window or monitor.")
        region = dict(monitor)
        if mode == "active_window":
            left, top, right, bottom = active["bounds"]
            left, top = max(left, monitor["left"]), max(top, monitor["top"])
            right, bottom = min(right, monitor["left"]+monitor["width"]), min(bottom, monitor["top"]+monitor["height"])
            if right <= left or bottom <= top:
                raise ToolError("INVALID_MONITOR", "Active application is not visible on the selected monitor.")
            region = {"left": left, "top": top, "width": right-left, "height": bottom-top}
        shot = screen.grab(region)
        image = Image.frombytes("RGB", shot.size, shot.rgb)
        maximum = args.get("max_dimension", 1600)
        if type(maximum) is not int or not 320 <= maximum <= 2400:
            raise ToolError("INVALID_ARGUMENTS", "Capture dimension must be from 320 to 2400.")
        image.thumbnail((maximum, maximum))
        buffer = io.BytesIO()
        image.save(buffer, "PNG")
        import win32api
        return {"png": base64.b64encode(buffer.getvalue()).decode(), "image_width": image.width,
                "image_height": image.height, "screen_width": region["width"], "screen_height": region["height"],
                "left": region["left"], "top": region["top"], "active_window": active,
                "monitor": {"index": monitors.index(monitor)+1, **monitor}, "capture_mode": mode,
                "cursor": list(win32api.GetCursorPos()), "last_input_tick": last_input_tick(),
                "timestamp": datetime.now().astimezone().isoformat()}


def mouse(args: dict) -> dict:
    import win32api
    import win32con
    emergency_check()
    active = foreground()
    if (active["handle"] != args["window_handle"] or
        ("window_pid" in args and active["pid"] != args["window_pid"])):
        raise ToolError("WINDOW_CHANGED", "Foreground window changed. Observe and locate again.")
    if "window_bounds" in args and active["bounds"] != args["window_bounds"]:
        raise ToolError("SCREEN_CHANGED", "Window geometry changed. Observe and locate again.")
    if "cursor" in args:
        current = win32api.GetCursorPos()
        if any(abs(a-b) > args.get("takeover_tolerance", 12) for a, b in zip(current, args["cursor"])):
            raise ToolError("USER_TAKEOVER", "The user moved the pointer. Automation yielded control.")
    if args.get("last_input_tick") is not None and last_input_tick() != args["last_input_tick"]:
        raise ToolError("USER_TAKEOVER", "New input arrived after observation. Automation yielded control.")
    if win32api.GetAsyncKeyState(win32con.VK_ESCAPE) & 0x8000:
        raise ToolError("EMERGENCY_STOP", "Escape emergency stop activated.")
    x, y = int(args["x"]), int(args["y"])
    if not any(left <= x < right and top <= y < bottom for _, _, (left, top, right, bottom) in win32api.EnumDisplayMonitors()):
        raise ToolError("INVALID_COORDINATES", "Mouse point is outside connected displays.")
    win32api.SetCursorPos((x, y))
    emergency_check()
    action = args["action"]
    if action == "scroll":
        amount = int(args["amount"])
        if not 1 <= amount <= 8 or args["direction"] not in {"up", "down"}:
            raise ToolError("INVALID_ARGUMENTS", "Invalid scroll amount or direction.")
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0, amount * 120 * (1 if args["direction"] == "up" else -1), 0)
    elif action != "move_mouse":
        if action not in {"click_mouse", "double_click", "right_click"}:
            raise ToolError("INVALID_ARGUMENTS", "Invalid mouse operation.")
        right = action == "right_click" or args.get("button") == "right"
        down, up = (win32con.MOUSEEVENTF_RIGHTDOWN, win32con.MOUSEEVENTF_RIGHTUP) if right else (win32con.MOUSEEVENTF_LEFTDOWN, win32con.MOUSEEVENTF_LEFTUP)
        dispatched = 0
        try:
            for _ in range(2 if action == "double_click" else 1):
                emergency_check()
                current = foreground()
                if ((current["handle"], current["pid"]) != (active["handle"], active["pid"]) or
                        current["bounds"] != active["bounds"]):
                    raise ToolError("FOCUS_LOST", "Application focus or geometry changed during input. Inspect before continuing.")
                pointer = win32api.GetCursorPos()
                if any(abs(a-b) > args.get("takeover_tolerance", 12) for a, b in zip(pointer, (x, y))):
                    raise ToolError("USER_TAKEOVER", "The user moved the pointer during input. Automation yielded control.")
                if any(win32api.GetAsyncKeyState(key) & 0x8000 for key in range(1, 255) if key != 0xE7):
                    raise ToolError("USER_TAKEOVER", "A physical input is held. Automation yielded control.")
                win32api.mouse_event(down, 0, 0, 0, 0)
                win32api.mouse_event(up, 0, 0, 0, 0)
                dispatched += 1
                time.sleep(0.07)
        except ToolError as error:
            if dispatched:
                error.data.update({"action_dispatched": True, "desired_result_verified": False,
                                   "observation_required": True, "clicks_dispatched": dispatched})
                error.args = (f"{error} Sent {dispatched} click(s) before stopping; "
                              "the desired outcome remains unverified.",)
            raise
    return {"action": action, "x": x, "y": y, "executed": True, "desired_result_verified": False}


def volume(operation: str, args: dict) -> dict:
    from pycaw.pycaw import AudioUtilities
    endpoint = AudioUtilities.GetSpeakers().EndpointVolume
    if operation == "set_volume":
        level = args["level"]
        if type(level) is not int or not 0 <= level <= 100:
            raise ToolError("INVALID_ARGUMENTS", "Volume must be an integer from 0 to 100.")
        endpoint.SetMasterVolumeLevelScalar(level / 100, None)
    elif operation in {"mute_audio", "unmute_audio"}:
        endpoint.SetMute(operation == "mute_audio", None)
    level, muted = round(endpoint.GetMasterVolumeLevelScalar() * 100), bool(endpoint.GetMute())
    result = {"level": level, "muted": muted}
    if operation != "get_volume":
        result.update({"action_dispatched": True,
                       "desired_result_verified": level == args["level"] if operation == "set_volume" else
                       muted == (operation == "mute_audio")})
    return result


def clipboard(operation: str, args: dict) -> dict:
    import win32clipboard
    import win32con
    for attempt in range(5):
        try:
            win32clipboard.OpenClipboard()
            break
        except Exception:
            if attempt == 4:
                raise ToolError("CLIPBOARD_BUSY", "Clipboard is currently locked by another application.") from None
            time.sleep(0.05)
    try:
        if operation == "write_clipboard":
            text = args["text"]
            if len(text) > 10000:
                raise ToolError("INVALID_ARGUMENTS", "Clipboard text is too large.")
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
            return {"characters": len(text), "action_dispatched": True,
                    "desired_result_verified": win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT) == text}
        if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return {"text": "", "format": "empty or non-text"}
        text = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return {"text": text[:10000], "truncated": len(text) > 10000}
    finally:
        win32clipboard.CloseClipboard()


def find_youtube(args: dict) -> dict:
    import re
    import yt_dlp
    class QuietLogger:
        def debug(self, *_): pass
        def warning(self, *_): pass
        def error(self, *_): pass
    options = {"quiet": True, "no_warnings": True, "logger": QuietLogger(), "skip_download": True,
               "extract_flat": True, "socket_timeout": 8, "retries": 0, "noplaylist": True}
    with yt_dlp.YoutubeDL(options) as downloader:
        try:
            result = downloader.extract_info("ytsearch1:" + args["query"], download=False)
            item = next(iter(result.get("entries", [])), None)
        except Exception:
            raise ToolError("MEDIA_SEARCH_FAILED", "YouTube search failed; use search_youtube to open results instead.") from None
    if not item or not re.fullmatch(r"[A-Za-z0-9_-]{11}", item.get("id", "")):
        raise ToolError("MEDIA_NOT_FOUND", "No playable YouTube result found.")
    return {"title": item.get("title", "YouTube video"), "url": "https://www.youtube.com/watch?v=" + item["id"] + "&autoplay=1"}


def dispatch(operation: str, args: dict) -> dict:
    if operation == "ping":
        return {"ready": True, "platform": platform.system()}
    if operation == "get_system_info":
        memory = psutil.virtual_memory()
        return {"os": platform.system(), "release": platform.release(), "cpu_cores": psutil.cpu_count(),
                "ram_gb": round(memory.total / 1024**3, 1), "ram_used_percent": memory.percent}
    if operation in {"get_current_time", "get_current_date"}:
        now = datetime.now().astimezone()
        return {"value": now.isoformat() if operation == "get_current_time" else now.date().isoformat(), "timezone": str(now.tzinfo)}
    if operation == "get_battery_status":
        battery = psutil.sensors_battery()
        return {"present": battery is not None, "percent": battery.percent if battery else None,
                "plugged_in": battery.power_plugged if battery else None}
    if operation == "find_youtube":
        return find_youtube(args)
    require_windows()
    if operation in {"open_application", "close_application", "list_running_applications", "focus_application"}:
        return application(operation, args)
    if operation == "get_active_window":
        return foreground()
    if operation == "focus_window":
        return focus(int(args["handle"]))
    if operation == "capture":
        return capture(args)
    if operation == "mouse":
        return mouse(args)
    if operation == "keyboard":
        from soul.desktop.keyboard import keyboard
        return keyboard(args)
    if operation == "accessibility":
        # Some application providers block indefinitely. Contain them in a disposable process.
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            probe = subprocess.run([sys.executable, "-m", "soul.desktop.accessibility", str(int(args["handle"]))],
                                   capture_output=True, timeout=1.5, creationflags=flags, check=False)
            if len(probe.stdout) > 128000:
                return {"available": False, "elements": [], "reason": "metadata_limit"}
            return json.loads(probe.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {"available": False, "elements": [], "reason": "provider_unavailable"}
    if operation in {"get_volume", "set_volume", "mute_audio", "unmute_audio"}:
        return volume(operation, args)
    if operation in {"read_clipboard", "write_clipboard"}:
        return clipboard(operation, args)
    if operation == "open_url":
        from soul.tools.browser import normalize_url
        try:
            os.startfile(normalize_url(args["url"]))
        except OSError:
            raise ToolError("BROWSER_UNAVAILABLE", "No browser could open the URL.") from None
        return {"dispatched": True}
    if operation == "open_file_or_folder":
        path = Path(args["path"]).expanduser().resolve()
        if not path.exists():
            raise ToolError("PATH_NOT_FOUND", "The local path does not exist.")
        # File opening cannot serve as an executable/script/protocol backdoor.
        if not path.is_dir() and path.suffix.lower() not in {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".wav", ".mp3", ".mp4", ".csv"}:
            raise ToolError("RESTRICTED_FILE_TYPE", "Only folders and supported document/media files may be opened.")
        os.startfile(str(path))
        return {"path": str(path), "dispatched": True}
    raise ToolError("UNKNOWN_OPERATION", "Desktop operation is not registered.")


def main():
    enable_dpi_awareness()
    def handle(operation, args):
        try:
            return {"success": True, "data": dispatch(operation, args)}
        except ToolError as exc:
            return {"success": False, "error_code": exc.code, "message": str(exc), "data": getattr(exc, "data", {})}
        except Exception as exc:
            import traceback
            traceback.print_exc(file=sys.stderr)
            return {"success": False, "error_code": "OS_ERROR", "message": f"OS operation failed ({type(exc).__name__})."}
    if sys.argv[1] == "--serve":
        for line in sys.stdin.buffer:
            try:
                request = json.loads(line)
                result = handle(request["operation"], request["arguments"])
            except Exception:
                result = {"success": False, "error_code": "INVALID_REQUEST", "message": "Malformed worker request."}
            sys.stdout.buffer.write(json.dumps(result).encode() + b"\n")
            sys.stdout.buffer.flush()
    else:
        result = handle(sys.argv[1], json.loads(sys.stdin.buffer.read()))
        sys.stdout.buffer.write(json.dumps(result).encode())


if __name__ == "__main__":
    main()
