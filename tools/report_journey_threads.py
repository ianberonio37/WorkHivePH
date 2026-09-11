#!/usr/bin/env python3
"""report_journey_threads.py — what the journey walks have measured about the threads BETWEEN pages.

Each walked hop is classified three ways: the page carries the next page in its OWN body (`own`), it is
reachable only through the shared nav hub (`hub-only`), or there is no way onward at all (`none`). The last
is a finding; the middle is a design observation worth a number - a journey where every hop needs the drawer
is a set of tools, not a path.

Only hops whose page ARRIVED and finished rendering are counted: a thread read on a page that bounced, or one
still loading, says nothing about the page it was supposed to be.

  python tools/report_journey_threads.py
"""
from __future__ import annotations

import glob
import json
from collections import Counter
from pathlib import Path


def main() -> int:
    hops = []
    for f in sorted(glob.glob(".tmp/full_journeys_*.json")):
        try:
            doc = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        for r in doc.get("results", []):
            for s in r.get("steps", []):
                if not s.get("next") or s.get("loadError"):
                    continue
                if s.get("landed") and s.get("landed") != s.get("page"):
                    continue                     # a bounced step is not evidence about its page
                if (s.get("chars") or 0) < 900 and s.get("settledBy") == "cap":
                    continue                     # never finished rendering: unreadable
                own, hub = s.get("own") or 0, s.get("hub") or 0
                hops.append((s["page"], s["next"], "own" if own else ("hub-only" if hub else "none")))

    if not hops:
        print("no readable hops yet - walk an archetype first")
        return 0
    kinds = Counter(k for _p, _n, k in hops)
    total = len(hops)
    print(f"readable hops walked: {total}")
    for k in ("own", "hub-only", "none"):
        n = kinds.get(k, 0)
        print(f"   {k:9} {n:4}  {100.0 * n / total:5.1f}%")

    # ★A COUNT ACROSS A FIX IS TWO COUNTS. Walks taken BEFORE the nav-mode repair (2026-09-08) were taken
    # while a supervisor's hub was missing Analytics, the Alert Hub and Reports, so every hop toward those
    # three read `none` for a reason that no longer exists. Results files walked after the repair are the
    # ones to trust for those pairs; the mix below is honest only about the walks it contains.
    print("\nhops with NO way onward (the finding — see the note on walks taken before the nav-mode repair):")
    none = Counter((p, n) for p, n, k in hops if k == "none")
    for (p, n), c in none.most_common(12):
        print(f"   {c:3}x  {p:28} -> {n}")

    print("\npages that never carry their own onward link (every hop from them needs the drawer):")
    by_page = {}
    for p, _n, k in hops:
        d = by_page.setdefault(p, Counter())
        d[k] += 1
    for p, d in sorted(by_page.items(), key=lambda kv: -sum(kv[1].values())):
        if d.get("own", 0) == 0 and sum(d.values()) >= 2:
            print(f"   {p:28} {sum(d.values()):3} hop(s), all hub-only or none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
