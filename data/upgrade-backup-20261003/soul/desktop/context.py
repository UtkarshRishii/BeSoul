from __future__ import annotations

import os
import threading
from soul.desktop.windows import foreground, enable_dpi_awareness
from soul.tools.models import ToolError


class DesktopContext:
    """Remember only foreground-window metadata while the user types in Soul."""
    TERMINALS = {"windowsterminal.exe", "powershell.exe", "pwsh.exe", "cmd.exe", "conhost.exe", "openconsole.exe"}

    def __init__(self, bridge):
        self.bridge = bridge
        self.last_window: dict | None = None
        self.console_handle: int | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

    def is_console(self, window):
        return window["handle"] == self.console_handle or window["application"].lower() in self.TERMINALS

    def start(self):
        if os.name != "nt":
            return
        enable_dpi_awareness()
        initial = foreground()
        if initial["application"].lower() in self.TERMINALS:
            self.console_handle = initial["handle"]
        def watch():
            while not self.stop_event.wait(0.2):
                try:
                    current = foreground()
                    if not self.is_console(current):
                        self.last_window = current
                except Exception:
                    continue
        self.thread = threading.Thread(target=watch, name="soul-window-context", daemon=True)
        self.thread.start()

    async def prepare(self, expected: dict | None = None):
        current = await self.bridge.call("get_active_window")
        if self.is_console(current):
            target = expected or self.last_window
            if not target:
                raise ToolError("NO_TARGET_WINDOW", "Select the application you want to control, then return to Soul and try again.")
            current = await self.bridge.call("focus_window", handle=target["handle"])
        if expected and (current["handle"], current["pid"]) != (expected["handle"], expected["pid"]):
            raise ToolError("WINDOW_CHANGED", "A different application is active. Locate the target again.")
        self.last_window = current
        return current

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)
