from __future__ import annotations

from contextlib import contextmanager
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich.padding import Padding
from rich.rule import Rule
from soul.cli.components import banner

class Renderer:
    def __init__(self, console, name):
        self.console, self.name = console, name
        self.status = None
        self.live = None
        self.content = ""
        self.actions = []
        self.phase = "Thinking"

    def render_turn(self):
        parts = [Text("SOUL", style="bold accent")]
        for name, message, success, elapsed in self.actions:
            row = Text("  " + ("·" if success is None else "✓" if success else "!") + " ", style="muted" if success is None else "accent" if success else "warning")
            row.append(name.replace("_", " "), style="muted")
            if elapsed is not None:
                row.append(f"  {elapsed:.1f}s", style="muted")
            if name == "model fallback":
                row.append("  " + message, style="muted")
            if success is False:
                row.append("\n    " + message, style="warning")
            parts.append(row)
        if self.content:
            parts.append(Padding(Markdown(self.content), (0, 0, 0, 2)))
        else:
            parts.append(Text("  " + self.phase + "…", style="muted"))
        return Group(*parts)

    def state_changed(self, state):
        import logging
        logging.getLogger("soul").debug("state_transition state=%s", state.value)
        if self.status:
            self.status.update(f"[muted]{state.value.capitalize()}…[/]")
        elif self.live:
            self.phase = state.value.capitalize()
            self.live.update(self.render_turn())

    def startup(self, settings, memory_ready):
        self.console.print()
        self.console.print(Text("  " + settings.soul_name.upper(), style="bold accent"))
        self.console.print(Text("  PERSONAL INTELLIGENCE  /  SOUL V2", style="muted"))
        self.console.print()
        table = Table.grid(padding=(0, 3))
        model = settings.gemini_fallback_model if settings.soul_response_mode == "fast" and settings.gemini_fallback_model else settings.gemini_text_model
        table.add_row(Text("  MODEL", style="muted"), Text(model + " · " + settings.soul_response_mode))
        enabled = ["memory" if memory_ready else "session only", "tools" if settings.soul_tools_enabled else "chat",
                   "vision" if settings.soul_tools_enabled and settings.soul_vision_enabled else "text",
                   "voice on" if settings.soul_tts_enabled else "voice off"]
        table.add_row(Text("  READY", style="accent"), Text(" · ".join(enabled), style="muted"))
        self.console.print(table)
        self.console.print()
        self.console.print(Rule(style="muted"))
        self.notice("  /help commands   /voice off quiet mode   Ctrl+C exit")
        if settings.soul_tools_enabled and settings.soul_vision_enabled:
            self.notice("  Mouse stop: hold Esc or move to a screen corner")
        self.console.print()

    @contextmanager
    def activity(self):
        with self.console.status("[muted]Processing…[/]", spinner="dots") as status:
            self.status = status
            try:
                yield
            finally:
                self.status = None

    @contextmanager
    def response(self):
        self.content, self.actions, self.phase = "", [], "Thinking"
        with Live(self.render_turn(), console=self.console, refresh_per_second=16) as live:
            self.live = live
            def append(chunk):
                self.content += chunk
                live.update(self.render_turn())
            try:
                yield append
            finally:
                self.live = None
        self.console.print()

    @contextmanager
    def pause_live(self):
        live = self.live
        if live:
            live.stop()
        try:
            yield
        finally:
            if live:
                live.start()

    def tool_started(self, name):
        self.actions.append((name, "", None, None))
        if self.live:
            self.live.update(self.render_turn())

    def tool_finished(self, name, result, elapsed):
        for index in range(len(self.actions)-1, -1, -1):
            if self.actions[index][0] == name and self.actions[index][2] is None:
                self.actions[index] = (name, result.message, result.success, elapsed)
                break
        if self.live:
            self.live.update(self.render_turn())

    def model_changed(self, message):
        if self.live:
            self.actions.append(("model fallback", message, None, None))
            self.phase = message
            self.live.update(self.render_turn())
        else:
            self.notice(message)

    def notice(self, text):
        self.console.print(Text(text, style="muted"))

    def error(self, text):
        self.console.print(Text(text, style="error"))

    def memories(self, memories):
        table = Table("ID", "Category", "Memory", border_style="muted", expand=True)
        for m in memories:
            table.add_row(str(m.id), m.category, Text(m.content))
        self.console.print(table)
        if not memories:
            self.notice("No stored memories.")
