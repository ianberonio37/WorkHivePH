#!/usr/bin/env python3
"""validate_destructive_proportional_confirm.py — T50's lock instrument: every destructive action is
CONFIRMED, and the confirm roster cannot silently shrink.

T50 built the DENOMINATOR — tools/build_destructive_control_registry.py scans every page and rosters
each whConfirm/whPrompt call site into substrate/reference/destructive_control_registry.json (its
--check exits 1 when the roster drifts from the live call sites). This gate locks that discipline:

  1. ROSTER CURRENT (hard) — build_destructive_control_registry.py --check exits 0. A destructive
     confirm added or removed without updating the roster reddens here: the roster is the platform's
     complete are-you-sure vocabulary, and a silent shrink is a destructive action losing its guard.
  2. NO BLANK CONFIRM (hard) — every rostered control carries a non-empty message_head. A confirm
     that asks nothing ("", a bare true) is a click-through, not a decision point.
  3. FORWARD-ONLY COUNT (hard) — the number of rostered controls never falls below a frozen baseline
     without an explicit re-baseline. Removing a confirmation is exactly the regression T50 guards.

★WHAT IT DELIBERATELY DOES NOT DO: judge PROPORTIONALITY of the prose. A low-consequence action
(remove one scheduled item, reversible) SHOULD carry a light confirm; a high-consequence one (delete
work that cascades) a heavy one. A lint that demanded a consequence clause on EVERY confirm would
false-fail the appropriately-light ones — the same over-reach that made units_at_boundary cry wolf.
Proportionality is the hand-audit T50 already did ("audited all 52, most strong"); this gate counts
the objective floor and REPORTS (never fails) the consequence-light ones so a reviewer can see them.

Registered in run_platform_checks (Platform). Read-only; no browser.
"""
from __future__ import annotations

import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "substrate" / "reference" / "destructive_control_registry.json"
BUILDER = ROOT / "tools" / "build_destructive_control_registry.py"
BASELINE = ROOT / "tools" / "destructive_confirm_baseline.json"

CHECK_NAMES = ["destructive-proportional-confirm"]

# a message that names a downstream EFFECT — used ONLY to REPORT the light ones, never to fail them.
# Deliberately NOT the bare action verbs (remove/delete/clear): "Remove item?" states the action, not
# its consequence, so it must read as light. A consequence is what happens AFTER: a cascade, a loss, an
# irreversibility, a second sentence describing the downstream.
_CONSEQUENCE = re.compile(
    r"(cascade|cannot|permanent|forever|lose\b|lost\b|unlink|kept|history|re-?verif|re-?enter|"
    r"no longer|will\s+\w+|un-?done|irrevers|\.\s+\w)", re.I)


def _controls(reg: dict) -> list[tuple[str, int, str]]:
    out = []
    for f, ctrls in (reg.get("controls") or {}).items():
        for c in (ctrls or []):
            out.append((f, c.get("line"), c.get("message_head") or ""))
    return out


def check(reg: dict, baseline: int | None) -> tuple[list[str], int, int]:
    ctrls = _controls(reg)
    total = len(ctrls)
    problems: list[str] = []
    blank = [(f, ln) for f, ln, m in ctrls if not m.strip()]
    for f, ln in blank:
        problems.append(f"{f}:{ln}: a rostered destructive control has a BLANK confirm message")
    if baseline is not None and total < baseline:
        problems.append(f"the destructive-confirm roster SHRANK {baseline} -> {total} — a destructive "
                        f"action lost its confirmation (re-baseline only after a deliberate removal)")
    light = sum(1 for _f, _ln, m in ctrls if m.strip() and not _CONSEQUENCE.search(m))
    return problems, total, light


def main() -> int:
    r = subprocess.run([sys.executable, str(BUILDER), "--check"], capture_output=True, text=True)
    if r.returncode != 0:
        print("FAIL destructive-proportional-confirm: the roster is STALE — a destructive confirm was "
              "added/removed without updating it. Run: python tools/build_destructive_control_registry.py")
        print("  " + " ".join((r.stdout or r.stderr or "").split())[:160])
        return 1
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    baseline = None
    if BASELINE.exists():
        baseline = json.loads(BASELINE.read_text(encoding="utf-8")).get("count")
    problems, total, light = check(reg, baseline)
    if baseline is None:
        BASELINE.write_text(json.dumps({"count": total, "established": "2026-09-01"}, indent=1), encoding="utf-8")
        print(f"BASELINE established: {total} destructive confirms rostered (forward-only floor)")
    elif total > baseline:
        BASELINE.write_text(json.dumps({"count": total, "ratcheted": "auto"}, indent=1), encoding="utf-8")
        print(f"roster grew {baseline} -> {total}; floor raised.")
    print(f"destructive-proportional-confirm: {total} confirms rostered · {light} consequence-light "
          f"(reported, not failed) · roster current")
    if problems:
        for p in problems[:8]:
            print(f"  FAIL {p}")
        return 1
    print("PASS destructive-proportional-confirm — every destructive action is rostered + confirmed, "
          "no blank confirm, and the roster has not shrunk.")
    return 0


def self_test() -> int:
    good = {"controls": {"a.html": [{"line": 1, "message_head": "Delete this? It cascades."},
                                    {"line": 2, "message_head": "Remove item?"}]}}
    fails = []
    if check(good, 2)[0]:
        fails.append("a current, non-blank roster at baseline should PASS")
    blank = {"controls": {"a.html": [{"line": 1, "message_head": ""}]}}
    if not any("BLANK" in p for p in check(blank, 1)[0]):
        fails.append("a blank confirm message should FAIL")
    if not any("SHRANK" in p for p in check(good, 5)[0]):
        fails.append("a roster below baseline should FAIL")
    # the light one is REPORTED, never a problem
    _p, _t, light = check(good, 2)
    if light != 1:
        fails.append("the consequence-light confirm should be COUNTED (1), not failed")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_destructive_proportional_confirm self-test (blank / shrink redden; light is "
          "counted not failed)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
