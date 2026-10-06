from __future__ import annotations

from dataclasses import dataclass, field
from soul.utils.timing import TurnMetrics

@dataclass
class Session:
    turns: int = 0
    last_metrics: TurnMetrics = field(default_factory=TurnMetrics)
