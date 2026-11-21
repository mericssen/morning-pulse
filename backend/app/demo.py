"""Demo mode: inject believable faults so the stage demo always has something to fix.

Faults are simulated (nothing on the machine is broken). A check that has an
active fault reports it; applying the matching fix clears the fault.
"""
from __future__ import annotations

DEFAULT_FAULTS = {"disk", "dns", "cpu_hog", "uptime"}

_state = {"enabled": False, "faults": set()}


def enable(faults: set[str] | None = None) -> None:
    _state["enabled"] = True
    _state["faults"] = set(faults or DEFAULT_FAULTS)


def disable() -> None:
    _state["enabled"] = False
    _state["faults"] = set()


def enabled() -> bool:
    return _state["enabled"]


def has(fault: str) -> bool:
    return _state["enabled"] and fault in _state["faults"]


def clear(fault: str) -> None:
    _state["faults"].discard(fault)


def status() -> dict:
    return {"enabled": _state["enabled"], "faults": sorted(_state["faults"])}
