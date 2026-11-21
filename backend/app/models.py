"""Shared data shapes for checks, fixes and the morning report."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal, Optional

Status = Literal["ok", "warn", "crit"]


@dataclass
class CheckResult:
    id: str                      # stable id, e.g. "disk"
    title: str                   # short human title
    status: Status
    detail: str                  # one-line plain-language explanation
    metric: dict = field(default_factory=dict)   # raw numbers for the agent / UI
    fix_id: Optional[str] = None                 # whitelisted fix that addresses it
    fix_args: dict = field(default_factory=dict)
    minutes_per_week: float = 0.0                # estimated time lost if left as is

    def to_dict(self) -> dict:
        return asdict(self)


PENALTY = {"ok": 0, "warn": 8, "crit": 20}


def score(results: list[CheckResult]) -> int:
    return max(0, 100 - sum(PENALTY[r.status] for r in results))
