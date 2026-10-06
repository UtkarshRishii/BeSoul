from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from rich.align import Align

def banner(name):
    title = Text("  ".join(name.upper()), style="bold accent", justify="center")
    title.append("\n\nPERSONAL INTELLIGENCE SYSTEM", style="muted")
    return Panel(Align.center(title), border_style="accent", padding=(1, 4), subtitle="EPISODE 01 · FOUNDATION")
