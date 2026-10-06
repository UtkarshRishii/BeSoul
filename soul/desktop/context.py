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
        self.assistant_handles: set[int] = set()
        self.assistant_pids: set[int] = {os.getpid()}
        self._lock = threading.RLock()
        self.generation = 0

    def register_assistant_window(self, handle: int) -> None:
        """Exclude a native SOUL UI window from remembered application focus."""
        with self._lock:
            self.assistant_handles.add(int(handle))
            if self.last_window and self.is_console(self.last_window):
                self.last_window = None
                self.generation += 1

    register_self_window = register_assistant_window

    def unregister_assistant_window(self, handle: int) -> None:
        with self._lock:
            self.assistant_handles.discard(int(handle))

    def _remember(self, window: dict) -> None:
        identity = lambda item: (item["handle"], item["pid"], item.get("title"), item.get("bounds"))
        with self._lock:
            if self.is_console(window):
                return
            if self.last_window is not None and identity(self.last_window) != identity(window):
                self.generation += 1
            self.last_window = window

    def is_console(self, window):
        return (window["handle"] == self.console_handle or window["handle"] in self.assistant_handles
                or window.get("pid") in self.assistant_pids or window["application"].lower() in self.TERMINALS)

    def start(self):
        if os.name != "nt":
            return
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        enable_dpi_awareness()
        try:
            initial = foreground()
            if initial["application"].lower() in self.TERMINALS:
                self.console_handle = initial["handle"]
            elif not self.is_console(initial):
                self._remember(initial)
        except ToolError:
            pass  # Locked/secure desktops can become available later; nonvisual tools still work.
        def watch():
            while not self.stop_event.wait(0.2):
                try:
                    current = foreground()
                    if not self.is_console(current):
                        self._remember(current)
                except Exception:
                    continue
        self.thread = threading.Thread(target=watch, name="soul-window-context", daemon=True)
        self.thread.start()

    async def prepare(self, expected: dict | None = None):
        current = await self.bridge.call("get_active_window")
        if self.is_console(current):
            target = expected or self.last_window
            if target and not self.is_console(target):
                try:
                    current = await self.bridge.call("focus_window", handle=target["handle"])
                except Exception:
                    pass
        if expected and (current["handle"], current["pid"]) != (expected["handle"], expected["pid"]):
            try:
                current = await self.bridge.call("focus_window", handle=expected["handle"])
            except Exception:
                pass
        self._remember(current)
        return current

    def close(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1)
