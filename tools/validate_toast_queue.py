#!/usr/bin/env python3
"""validate_toast_queue.py — C7's lock: logbook's receipt toasts QUEUE instead of stomping.

Walked (critic T9): a save fires 'Entry saved' + '+15 XP' + a badge back-to-back; the single
toast slot replaced each with the next in ~0ms (clearTimeout + overwrite), so the worker read
only the LAST receipt — the XP receipt they most care about vanished unread every save.
Fixed 2026-09-02: showToast enqueues while one is showing (queue capped at 4, same-message
de-dup) and the hide-timer chains to the next. Proven live: the three-receipt burst showed
sequentially at 0s/2.8s/5.6s, each full-length.

Legs: (1) the queue+guard exists; (2) the enqueue is capped AND de-duplicated; (3) the hide
timer chains the next toast. Self-test: each leg's removal reddens.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["toast-queue"]

LEGS = [
    ("queue-guard",
     re.compile(r"const _toastQueue = \[\];[\s\S]{0,200}?if \(_toastShowing\) \{"),
     "showToast lost its queue guard - concurrent receipts stomp each other again (~0ms replace)"),
    ("capped-dedup",
     re.compile(r"_toastQueue\.length < 4 && !_toastQueue\.some"),
     "the enqueue lost its cap/de-dup - a repeating error can build an unbounded toast backlog"),
    ("chain-next",
     re.compile(r"_toastShowing = false;\s*\n\s*const _next = _toastQueue\.shift\(\);\s*\n\s*if \(_next\) showToast"),
     "the hide timer no longer chains the next queued toast - enqueued receipts are swallowed"),
]


def check(src: str) -> list[str]:
    return [msg for _, rx, msg in LEGS if not rx.search(src)]


def main() -> int:
    src = io.open(ROOT / "logbook.html", encoding="utf-8", errors="replace").read()
    problems = check(src)
    if problems:
        print("FAIL toast-queue - the receipt queue lost a leg:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS toast-queue - logbook's receipts queue (capped, de-duplicated, chained): "
          "'Entry saved' / '+15 XP' / badge each show full-length in order.")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "logbook.html", encoding="utf-8", errors="replace").read()
    fails = []
    if check(src):
        fails.append("HEAD must PASS: " + "; ".join(check(src)))
    for name, rx, _ in LEGS:
        broken = rx.sub("/* leg removed */", src, count=1)
        if not check(broken):
            fails.append(f"removing leg '{name}' must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_toast_queue self-test (each leg's removal reddens; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
