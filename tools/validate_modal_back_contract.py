#!/usr/bin/env python3
"""validate_modal_back_contract.py — T42's lock: modals trap the hardware-Back gesture.

Walked live 2026-09-02 (critic T42): opening inventory's Add-Part modal pushed NO history entry,
so the phone Back gesture — a constant on Android — navigated away from the WHOLE page mid-form
(inventory → logbook; task and typed input gone). No page implemented modal-back-to-close.

The fix lives in the ONE shared primitive every hand-rolled modal already opts into
(whModalA11y / whSheetA11y): activate() pushes a history entry, a shared popstate handler closes
the top open modal via its OWN close path (the same logic Escape uses), and deactivate() consumes
the entry with a suppressed back when the modal closed any other way (X, backdrop, save). Proven
live on the exact walked defect: Back dismissed the modal and stayed on inventory; after an
X-close the stack drained so the next Back exits the page.

This gate asserts the contract's three legs exist in utils.js — the push on activate, the shared
popstate closer, and the suppressed-back consumption on deactivate. Self-test: each leg's removal
reddens (resurrection).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["modal-back-contract"]

LEGS = [
    ("push-on-activate",
     re.compile(r"history\.pushState\(\s*\{\s*whModalBack:\s*true\s*\}"),
     "activate() no longer pushes the modal's history entry - hardware Back exits the page mid-form again"),
    ("popstate-closer",
     re.compile(r"addEventListener\(\s*['\"]popstate['\"][\s\S]{0,400}?__whModalBackStack"),
     "the shared popstate handler is gone - Back no longer closes the top open modal"),
    ("suppressed-back-on-deactivate",
     re.compile(r"__whModalBackSuppress\s*=\s*true;\s*\n?\s*history\.back\(\)"),
     "deactivate() no longer consumes the entry on X/backdrop close - a ghost history state accumulates per open"),
]


def check(src: str) -> list[str]:
    return [msg for _, rx, msg in LEGS if not rx.search(src)]


def main() -> int:
    src = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    problems = check(src)
    if problems:
        print("FAIL modal-back-contract - the Back-traps-modals contract lost a leg:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS modal-back-contract - whModalA11y pushes a history entry per activation, popstate "
          "closes the top modal via its own close path, and non-Back closes consume the entry "
          "(every whModalA11y/whSheetA11y modal platform-wide inherits it).")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "utils.js", encoding="utf-8", errors="replace").read()
    fails = []
    if check(src):
        fails.append("HEAD must PASS: " + "; ".join(check(src)))
    for name, rx, _ in LEGS:
        broken = rx.sub("/* leg removed */", src, count=1)
        if not check(broken):
            fails.append(f"removing leg '{name}' must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_modal_back_contract self-test (each leg's removal reddens; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
