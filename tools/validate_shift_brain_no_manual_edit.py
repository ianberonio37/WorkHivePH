#!/usr/bin/env python3
"""validate_shift_brain_no_manual_edit.py — T76's lock: shift-brain has NO manual-edit surface, so the
"regeneration silently discards a supervisor's hand-tuning" failure cannot occur.

T76 worries that regenerating the AI shift brief could throw away edits a supervisor made by hand,
without saying so. Measured 2026-08-28: shift-brain.html has ZERO editable controls on the brief —
no input, no textarea, no contenteditable, no edit/reassign button — so the brief is a generated,
read-only artifact and there is nothing to discard on regen. The edit-then-regen-honesty question is
structurally moot.

This gate is a RATCHET: it holds shift-brain.html to that no-edit posture. If a manual-edit control
is ever added, the gate reddens — a deliberate signal that whoever adds editing MUST now also handle
"which of your edits survived this regen, and say so on the glass" before it can pass again.

Static (file read), browser-free. Registered in run_platform_checks (Platform)."""
from __future__ import annotations

import io
import re
import sys

CHECK_NAMES = ["shift-brain-no-manual-edit"]
PAGE = "shift-brain.html"


def _read() -> str | None:
    try:
        return io.open(PAGE, encoding="utf-8").read()
    except Exception:
        return None


def check(html: str) -> list[str]:
    problems: list[str] = []
    if "<input" in html:
        problems.append("an <input> appeared on shift-brain — if it edits the brief, regen must now prove which edits survive")
    if "<textarea" in html:
        problems.append("a <textarea> appeared on shift-brain — regen-honesty must be handled before this passes")
    if "contenteditable" in html:
        problems.append("a contenteditable region appeared — the brief is now hand-tunable; regen must say what it discarded")
    if re.search(r'onclick\s*=\s*"[^"]*(reassign|editBrief|editTask)', html, re.I):
        problems.append("an edit/reassign control appeared — regen must reconcile hand-tuning honestly")
    return problems


def main() -> int:
    html = _read()
    if html is None:
        print(f"FAIL shift-brain-no-manual-edit — {PAGE} not found or unreadable."); return 1
    problems = check(html)
    if problems:
        print("FAIL shift-brain-no-manual-edit — a manual-edit surface exists; edit-then-regen honesty is now REQUIRED:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS shift-brain-no-manual-edit — the brief is a generated, read-only artifact (no input/textarea/"
          "contenteditable/edit control): regeneration has no hand-tuning to silently discard.")
    return 0


def self_test() -> int:
    fails = []
    if check("<div>read-only brief</div>"):
        fails.append("a no-edit page should PASS")
    if not any("input" in p for p in check('<input type="text">')):
        fails.append("an input should FAIL")
    if not any("textarea" in p for p in check("<textarea></textarea>")):
        fails.append("a textarea should FAIL")
    if not any("contenteditable" in p for p in check('<div contenteditable="true">')):
        fails.append("contenteditable should FAIL")
    if not any("reassign" in p for p in check('<button onclick="reassignTask(1)">x</button>')):
        fails.append("an edit control should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_shift_brain_no_manual_edit self-test (input/textarea/contenteditable/edit-control redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
