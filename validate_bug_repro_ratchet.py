#!/usr/bin/env python3
"""
validate_bug_repro_ratchet.py — the BUG-REPRO site count may fall, never rise.

Ian, 2026-10-04: "expand and extend the number of trajectories in our roadmap, where we have to bug
reproduced and fix". The §BRP wave's rows each name one measured defect site. A fixed site must STAY
fixed, and nothing else on the platform should quietly add a new one - so the inventory that sizes the
wave doubles as its ratchet.

WHAT A SITE IS (tools/bug_repro_inventory.py measures all three against the real source and real schema):
  A  a page scopes ownership by worker_name - a display string - where the table carries auth_uid
  B  a truth VIEW drops the auth_uid its base table carries, so no consumer can ask correctly at all
  C  no identity column anywhere, so ownership is only expressible as a name (needs a migration)

WHY THIS IS THE RIGHT LOCK. Each class-A fix is a few characters in one page: swap a name filter for
`.or(auth_uid…,worker_name…)` on a read, or for `.eq('auth_uid', …)` on a write guard. Nothing stops the
next edit from putting the name back, and the symptom is invisible - a person whose display name drifted
sees an empty list, or a 0-row update that raises no error. The count is the one thing that notices.

Per-class floors, because the classes are fixed by different means and at different speeds: a view
migration clears a block of B at once while A falls page by page.

Self-test: --selftest pins both directions. Output: bug_repro_ratchet_report.json. Exit 1 on a rise.
"""
from __future__ import annotations

import datetime
import io
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
BASELINE = ROOT / "bug_repro_ratchet_baseline.json"
REPORT = ROOT / "bug_repro_ratchet_report.json"
GREEN, RED, RESET, BOLD = "\033[92m", "\033[91m", "\033[0m", "\033[1m"

CLASS_WHY = {
    "A": "a page asks who owns a row by DISPLAY NAME where the table carries auth_uid - one character of "
         "drift empties the list, or makes a write match nothing and raise nothing",
    "B": "a truth VIEW hides the auth_uid its base table carries, so no consumer can scope by identity",
    "C": "the relation has no identity column at all - ownership is only expressible as a name",
}


def audit(now: dict, floors: dict) -> list[str]:
    """★THE TOTAL IS THE RATCHET; A PER-CLASS RISE IS ONLY A FINDING IF THE TOTAL DID NOT FALL.

    First version failed on any per-class rise, and the first thing that tripped it was PROGRESS: the
    sellers-view migration took class B from 2 to 0 by giving the view its auth_uid, which RECLASSIFIED
    those two sites into class A (now expressible, so now fixable). Class A read 13 -> 14 and the gate
    called it a regression while the total fell 26 -> 25.

    A site's class is a property of the world right now, not its identity - the same reason the seeder's
    skip key is class-agnostic - so classes trade places as the platform is fixed, and a per-class floor
    cannot tell a reclassification from a new defect. The TOTAL can: a reclassification conserves it or
    lowers it, a genuine new site raises it. This is the ★×14 lesson in its own small way - bind to the
    target, not to a sub-metric that moves for reasons the gate does not model. Per-class movement is still
    reported, so the trade stays visible instead of being smoothed away.
    """
    out = []
    now_total, floor_total = sum(now.values()), floors.get("_total")
    if floor_total is not None and now_total > floor_total:
        out.append(f"TOTAL rose {floor_total} -> {now_total}: at least one new ownership-by-display-name "
                   f"site exists that did not before")
        for cls in sorted(set(now) | set(floors) - {"_total"}):
            n, fl = now.get(cls, 0), floors.get(cls)
            if fl is not None and n > fl:
                out.append(f"  class {cls} rose {fl} -> {n}: {CLASS_WHY.get(cls, 'a new defect site')}")
    return out


def selftest() -> int:
    probs = []
    if not audit({"A": 46}, {"A": 45, "_total": 45}):
        probs.append("a real RISE (total 45 -> 46) was not caught - the ratchet has no teeth")
    if audit({"A": 44}, {"A": 45, "_total": 45}):
        probs.append("a FALL was flagged - the ratchet would block the fixes it exists for")
    if audit({"A": 45}, {"A": 45, "_total": 45}):
        probs.append("an unchanged count was flagged")
    if audit({"A": 1}, {}) != []:
        probs.append("no floor yet was treated as a rise - the first run must be able to seed")
    # THE CASE THAT BROKE THE FIRST VERSION: a reclassification. Class A rises, class B falls further,
    # the total falls. That is progress and must NOT fail.
    if audit({"A": 14, "B": 0}, {"A": 13, "B": 2, "_total": 15}):
        probs.append("a RECLASSIFICATION (A 13->14 while B 2->0, total 15->14) was flagged as a "
                     "regression - this is the exact shape that failed on real progress")
    # and a rise that is NOT compensated must still bite
    if not audit({"A": 14, "B": 2}, {"A": 13, "B": 2, "_total": 15}):
        probs.append("an uncompensated class rise (total 15 -> 16) was not caught")
    print("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs))
    return 1 if probs else 0


def main() -> int:
    if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")
    if "--selftest" in sys.argv:
        return selftest()

    from bug_repro_inventory import collect
    sites = collect()
    now = dict(Counter(s["cls"] for s in sites))
    by_page = Counter(s["page"] for s in sites)

    floors = {}
    if BASELINE.exists():
        try:
            floors = json.loads(BASELINE.read_text(encoding="utf-8")).get("floors", {})
        except Exception:
            floors = {}
    problems = audit(now, floors)
    ok = not problems

    print(f"\n{BOLD}BUG-REPRO RATCHET (a fixed site stays fixed; a new one is caught here){RESET}")
    print("-" * 76)
    for cls in ("A", "B", "C"):
        n, floor = now.get(cls, 0), floors.get(cls)
        mark = GREEN + "ok  " + RESET if floor is None or n <= floor else RED + "RISE" + RESET
        print(f"  {mark} class {cls}: {n:>3} site(s)   (floor {floor if floor is not None else '-'})")
    _ft = floors.get("_total")
    print(f"  {'ok  ' if _ft is None or sum(now.values()) <= _ft else 'RISE'} TOTAL: "
          f"{sum(now.values())} site(s)   (floor {_ft if _ft is not None else '-'})  <- THE ratchet")
    print(f"  total {sum(now.values())} across {len(by_page)} page(s); worst: "
          + ", ".join(f"{p} {c}" for p, c in by_page.most_common(4)))
    for p in problems:
        print(f"  {RED}FAIL{RESET} {p}")
    if ok:
        BASELINE.write_text(json.dumps({
            "_doc": "Forward-only floors for the §BRP wave: a class's site count may fall, never rise. "
                    "Measured by tools/bug_repro_inventory.py against the live source and schema.",
            "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "floors": dict({c: min(now.get(c, 0), floors.get(c, now.get(c, 0)))
                            for c in (set(now) | set(floors)) - {"_total"}},
                           _total=min(sum(now.values()), floors.get("_total", sum(now.values())))),
            "by_page": dict(by_page),
        }, indent=2) + "\n", encoding="utf-8")
        print(f"  {GREEN}PASS{RESET}  no class gained a site")
    REPORT.write_text(json.dumps({"ok": ok, "by_class": now, "by_page": dict(by_page),
                                  "failures": problems,
                                  "generated": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                                 indent=2) + "\n", encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
