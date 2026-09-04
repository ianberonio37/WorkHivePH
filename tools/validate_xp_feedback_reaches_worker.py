#!/usr/bin/env python3
"""validate_xp_feedback_reaches_worker.py — T17's lock: when a worker EARNS XP, they are told,
at the earning moment, and the message is not displaced by a competing toast.

Walked live (T17): a worker earned 140 XP in 11 minutes and was never told at any earning moment —
(a) logbook's earn toast existed but a single-slot toast let the tasklist-ack toast DISPLACE it
(probed 1.8s post-save, XP toast absent), and (b) pm-scheduler granted 60+20 XP with NO feedback
path at all (grep: zero XP toast calls). Fixed and verified live 2026-09-02:
  - logbook has a TOAST QUEUE (_toastQueue + _toastShowing): a second toast queues and drains
    rather than being dropped — proved live: 'tasklist' toast then '✓ ... +60 XP' both shown.
  - logbook appends the earned XP to the save toast (_xpNote from achievement_xp_log).
  - pm-scheduler appends _xpNoteFor(completion.id) to its completion toast (lines ~2453/2470).

This gate locks all three so the earning moment can never go silent again. Static, fast; teeth
plant each pre-fix shape.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["xp-feedback-reaches-worker"]

QUEUE_RE = re.compile(r"_toastQueue\b[\s\S]{0,400}?_toastShowing[\s\S]{0,1600}?_toastQueue\.shift\(\)")
LB_XPNOTE_RE = re.compile(r"_xpNote[\s\S]{0,200}?showToast\(")
PM_XPNOTE_RE = re.compile(r"_xpNoteFor\(\s*compData\.id\s*\)")


def problems_for(logbook_src: str, pm_src: str) -> list[str]:
    out = []
    if not QUEUE_RE.search(logbook_src):
        out.append("logbook.html: the toast QUEUE is gone (single-slot toast) — a competing toast "
                   "can displace the XP earn toast again (the T17 contention)")
    if not LB_XPNOTE_RE.search(logbook_src):
        out.append("logbook.html: the save toast no longer appends the earned XP (_xpNote) — the "
                   "earning moment goes silent")
    if not PM_XPNOTE_RE.search(pm_src):
        out.append("pm-scheduler.html: PM completion no longer appends _xpNoteFor(compData.id) — a "
                   "60+20 XP grant tells the worker nothing")
    return out


def main() -> int:
    lb = io.open(ROOT / "logbook.html", encoding="utf-8", errors="replace").read()
    pm = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(lb, pm)
    if bad:
        print("FAIL xp-feedback-reaches-worker:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS xp-feedback-reaches-worker — logbook queues toasts (no XP-toast displacement) and "
          "appends earned XP; pm-scheduler tells the worker the XP on completion.")
    return 0


def self_test() -> int:
    lb = io.open(ROOT / "logbook.html", encoding="utf-8", errors="replace").read()
    pm = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(lb, pm):
        fails.append("HEAD should PASS")
    pre_queue = lb.replace("_toastQueue.shift()", "/*removed*/null")
    if not any("toast QUEUE is gone" in p for p in problems_for(pre_queue, pm)):
        fails.append("removing the queue drain must redden")
    pre_pm = re.sub(r"_xpNoteFor\(\s*compData\.id\s*\)", "''", pm)
    if not any("pm-scheduler" in p for p in problems_for(lb, pre_pm)):
        fails.append("removing the pm XP note must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_xp_feedback_reaches_worker self-test (missing queue + missing pm-note both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
