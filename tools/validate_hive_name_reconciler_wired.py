#!/usr/bin/env python3
"""validate_hive_name_reconciler_wired.py — C11's lock: the stale-identity-cache reconciler is
wired PLATFORM-WIDE, not built-and-barely-called.

Walked receipt (critic deepwalk): wh_hive_name renders directly on ~24 pages and never followed
wh_active_hive_id — Bryan (Baguio) saw 'Lucena Pharmaceutical' chrome over his own correctly-scoped
data after a shared-device divergence. The cure existed (whReconcileHiveName: read v_hives_truth,
correct the cache, repaint) but ONLY hive.html called it — the built-but-never-called class.
Fixed 2026-09-02: utils.js auto-wires the reconciler once for every page (retry loop until the
page's getDb singleton exists; best-effort, never page-breaking). Proven live: staged
wh_hive_name='Baguio Textile Mills' against the Manila id on dayplanner (a page with NO call site)
→ reconciled to 'Manila Electronics Assembly' within seconds.

Legs: (1) the helper exists and reads the truth view; (2) the auto-wire exists (attempt loop
calling whReconcileHiveName off the singleton); (3) hive.html keeps its richer call (board title +
switch-button repaint). Self-test: each leg's removal reddens.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["hive-name-reconciler-wired"]

LEGS = [
    ("helper-reads-truth", "utils.js",
     re.compile(r"function whReconcileHiveName[\s\S]{0,900}?v_hives_truth"),
     "whReconcileHiveName no longer reads v_hives_truth - the reconciler lost its truth source"),
    ("auto-wire", "utils.js",
     re.compile(r"_whAutoReconcileHiveName[\s\S]{0,900}?whReconcileHiveName\(window\._whSupabaseClient\)"),
     "the platform-wide auto-wire is gone - only pages with a hand-written call reconcile (the built-but-never-called hole reopens)"),
    ("hive-board-call", "hive.html",
     re.compile(r"whReconcileHiveName\(db\)"),
     "hive.html dropped its reconcile call - the board title/switch-button repaint no longer refreshes"),
]


def check() -> list[str]:
    problems = []
    cache: dict[str, str] = {}
    for name, fname, rx, msg in LEGS:
        if fname not in cache:
            cache[fname] = io.open(ROOT / fname, encoding="utf-8", errors="replace").read()
        if not rx.search(cache[fname]):
            problems.append(msg)
    return problems


def main() -> int:
    problems = check()
    if problems:
        print("FAIL hive-name-reconciler-wired - the stale-identity-cache cure lost a leg:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS hive-name-reconciler-wired - whReconcileHiveName reads v_hives_truth, utils "
          "auto-wires it on every page off the getDb singleton, and hive.html keeps its richer "
          "board repaint (staged Baguio-name-over-Manila-id corrected live on dayplanner).")
    return 0


def self_test() -> int:
    fails = []
    if check():
        fails.append("HEAD must PASS: " + "; ".join(check()))
    for name, fname, rx, _ in LEGS:
        src = io.open(ROOT / fname, encoding="utf-8", errors="replace").read()
        if rx.search(src) is None:
            fails.append(f"leg '{name}' not present at HEAD")
            continue
        broken = rx.sub("/* leg removed */", src, count=1)
        import unittest.mock as _m
        real_open = io.open
        def fake_open(p, *a, **k):
            if str(p).endswith(fname):
                return io.StringIO(broken)
            return real_open(p, *a, **k)
        with _m.patch("io.open", side_effect=fake_open):
            if not check():
                fails.append(f"removing leg '{name}' must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_hive_name_reconciler_wired self-test (each leg's removal reddens; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
