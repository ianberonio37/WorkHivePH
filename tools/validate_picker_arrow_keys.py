#!/usr/bin/env python3
"""validate_picker_arrow_keys.py — T48's lock instrument: the logbook asset-picker is a keyboard combobox,
not a Tab-only list — ArrowDown/ArrowUp move focus through the options.

T48 measured the gap on the keyboard-only journey: a user at the picker search box reaches for ArrowDown
first, and ArrowDown+Enter selected nothing because the options were Tab-only. The fix wired the combobox
expectation: ArrowDown from search enters the list; ArrowDown/ArrowUp move focus between options. This gate
locks that wiring so a future edit cannot silently drop it back to Tab-only — the 'declared but never
wired' / keyboard-a11y-regression class.

Assertions on logbook.html (each refutable — see the self-test):
  1. ArrowDown is HANDLED (`e.key === 'ArrowDown'`).
  2. ArrowUp is HANDLED (`e.key === 'ArrowUp'`).
  3. An arrow branch MOVES FOCUS to an option (`.focus()` in the arrow-key handler region).

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "logbook.html"

CHECK_NAMES = ["picker-arrow-keys"]

_ARROWDOWN = re.compile(r"""e\.key\s*===\s*['"]ArrowDown['"]""")
_ARROWUP = re.compile(r"""e\.key\s*===\s*['"]ArrowUp['"]""")
# a focus move that sits in the same neighbourhood as the arrow handling (option navigation)
_ARROW_FOCUS = re.compile(r"""ArrowDown['"][^}]{0,160}\.focus\(\)|opts\[[^\]]+\]\.focus\(\)""", re.S)


def check(src: str) -> list[str]:
    problems: list[str] = []
    if not _ARROWDOWN.search(src):
        problems.append("ArrowDown is not handled — the picker is Tab-only, the exact gap T48 fixed.")
    if not _ARROWUP.search(src):
        problems.append("ArrowUp is not handled — arrow-key navigation is one-directional.")
    if not _ARROW_FOCUS.search(src):
        problems.append("no arrow branch moves focus to an option (.focus()) — arrows do not navigate.")
    return problems


def main() -> int:
    if not PAGE.exists():
        print("FAIL picker-arrow-keys: logbook.html not found"); return 1
    problems = check(PAGE.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL picker-arrow-keys — the asset-picker is not a keyboard combobox:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS picker-arrow-keys — the asset-picker handles ArrowDown/ArrowUp and arrows move focus "
          "through the options (a keyboard combobox, not Tab-only).")
    return 0


def self_test() -> int:
    fails = []
    good = "if (e.key === 'ArrowDown' && i < opts.length - 1) opts[i + 1].focus(); else if (e.key === 'ArrowUp') {"
    if check(good):
        fails.append("the real arrow-combobox wiring should PASS")
    if not any("ArrowDown" in p for p in check("if (e.key === 'ArrowUp') opts[i-1].focus();")):
        fails.append("missing ArrowDown should FAIL")
    if not any("ArrowUp" in p for p in check("if (e.key === 'ArrowDown') opts[i+1].focus();")):
        fails.append("missing ArrowUp should FAIL")
    if not any("focus" in p for p in check("if (e.key === 'ArrowDown') x; else if (e.key === 'ArrowUp') y;")):
        fails.append("arrows that do not move focus should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_picker_arrow_keys self-test (missing arrow / no-focus-move all redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
