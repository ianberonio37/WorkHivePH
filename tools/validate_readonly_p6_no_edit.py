#!/usr/bin/env python3
"""validate_readonly_p6_no_edit.py — pages classified P6-covered-by-nature must stay edit-free.

Bug-hunt roadmap P6 (concurrent-edit): a page with NO client edit surface (`.update`/`.upsert` on a
shared row) has no concurrent-edit race — it is covered-by-nature. 11 pages were VERIFIED read-only
(2026-07-17 census) and their P6 cells ratcheted to 100 on that basis. This gate LOCKS the claim:
if any of them later gains a `.update(`/`.upsert(`, the "no concurrent-edit surface" basis is void —
FAIL, forcing a real P6 hunt + re-score for that page. Forward-only, static, fast.

Exit 0 pass / 1 a read-only page gained an edit surface. --selftest = deterministic.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
READONLY_P6 = [
    "analytics", "analytics-report", "ai-quality", "public-feed", "engineering-design",
    "assistant", "report-sender", "project-report", "ph-intelligence", "plant-connections", "audit-log",
    "achievements",  # 2026-07-18: verified 0 insert/update/upsert/delete — gamification is display-only (badges/XP/leaderboard from truth views)
]
EDIT_RE = re.compile(r"\.update\(|\.upsert\(")


def edits_in(text: str) -> int:
    return len(EDIT_RE.findall(text))


def main() -> int:
    regressed = []
    for name in READONLY_P6:
        p = REPO / f"{name}.html"
        if not p.exists():
            continue
        n = edits_in(p.read_text(encoding="utf-8", errors="ignore"))
        if n:
            regressed.append((name, n))
    print(f"read-only P6 lock: {len(READONLY_P6)} covered-by-nature pages checked.")
    for name, n in regressed:
        print(f"  ✗ {name}.html gained {n} .update/.upsert call(s) — it is NO LONGER read-only; "
              f"its P6=100 (covered-by-nature) basis is void. HUNT the concurrent-edit path + re-score.")
    if regressed:
        return 1
    print("  ✓ all covered-by-nature P6 pages remain edit-free.")
    return 0


def selftest() -> int:
    fails = []
    if edits_in("db.from('x').select('*')") != 0:
        fails.append("a select must count 0 edits")
    if edits_in("db.from('x').update({a:1})") != 1:
        fails.append("an .update must count 1")
    if edits_in("db.from('x').upsert(r); db.from('y').update(z)") != 2:
        fails.append("update+upsert must count 2")
    if not READONLY_P6 or len(set(READONLY_P6)) != len(READONLY_P6):
        fails.append("READONLY_P6 list must be non-empty + unique")
    if fails:
        print("✗ selftest FAILED: " + "; ".join(fails))
        return 1
    print("✓ validate_readonly_p6_no_edit selftest passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(selftest() if "--selftest" in sys.argv else main())
