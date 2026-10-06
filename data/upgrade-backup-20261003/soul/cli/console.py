from __future__ import annotations

from rich.console import Console
from soul.cli.theme import THEME

def make_console():
    console = Console(theme=THEME, highlight=False)
    console.width = min(console.width, 96)
    return console
