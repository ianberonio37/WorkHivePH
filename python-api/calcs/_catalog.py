"""Picking a standard size from a catalog list - and saying so when the duty is bigger than the list.

★A DUTY ABOVE THE CATALOG WAS HANDED THE LARGEST SIZE AS IF IT WERE ENOUGH (2026-11-02, Wave ED). 46 selections in 26
engines were written `next((s for s in SIZES if s >= need), SIZES[-1])`: when the need exceeds the largest entry, the
answer is the largest entry - undersized - and nothing says so. The cooling tower's condenser pump, computed in watts and
printed as kW, ran off its list and was "recommended" at 90 kW. tools/census_selection_ceiling.py drove every served case
x10 and x1000 and found 30 such selections answering silently: a 1,000 m2 office given one 10 kW split unit, a 19,000
L/min fire pump given the largest pump, a vessel wall given the thickest plate in the table.

pick_at_least() keeps the old answer (the largest size, so a multi-unit or catalog-selected design still reads) and
records what ran past its list; @discloses on an engine's calculate() returns those records as `exceeds_catalog`, which the
page states above the report. Contextvars keep each calculation's records its own.
"""
from __future__ import annotations

import functools
from contextvars import ContextVar
from typing import Any, Callable, Sequence

_EXCEEDS: ContextVar[list | None] = ContextVar("wh_exceeds_catalog", default=None)


def pick_at_least(sizes: Sequence[Any], need: float, what: str, key: str | None = None,
                  value: Callable[[Any], float] | None = None) -> Any:
    """The first size whose value (s, s[key] or value(s)) is at least `need`; past the end of the list, the largest -
    recorded."""
    val = value or ((lambda s: s[key]) if key else (lambda s: s))
    for s in sizes:
        if val(s) >= need:
            return s
    largest = sizes[-1]
    rec = _EXCEEDS.get()
    if rec is not None:
        top = val(largest)
        rec.append({"what": what, "needed": round(float(need), 3), "largest": top,
                    "note": f"{what}: the duty needs {float(need):.4g}, above the largest size this calculator lists "
                            f"({top}). The size shown is NOT enough - split the duty across units or select from a "
                            f"manufacturer's catalog."})
    return largest


def record_limit(what: str, needed: float, largest: Any, note: str) -> None:
    """Record a pick the list could not meet that is not a plain 'at least' (a size that must sit inside a window)."""
    rec = _EXCEEDS.get()
    if rec is not None:
        rec.append({"what": what, "needed": round(float(needed), 3), "largest": largest, "note": note})


def discloses(fn: Callable[..., dict]) -> Callable[..., dict]:
    """Wrap an engine's calculate(): its answer carries `exceeds_catalog` when any pick ran past its list."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        token = _EXCEEDS.set([])
        try:
            out = fn(*args, **kwargs)
            rec = _EXCEEDS.get()
            if rec and isinstance(out, dict):
                out["exceeds_catalog"] = rec
            return out
        finally:
            _EXCEEDS.reset(token)
    return wrapper
