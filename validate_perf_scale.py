#!/usr/bin/env python3
"""validate_perf_scale.py — Arc L L-Accept gate: the Performance & Scale ratchet.

Forward-only: every lens's pass-count in perf_scale_results.json must stay AT OR ABOVE
the locked perf_scale_baseline.json (a regression = a real perf/scale loss). Also reports
the per-lens floor status (S 90 / E 85 / R 85 / B 95). Fast JSON read — no live probe, no
network; CI-safe and never flaky. Re-measure with the perf_l3/l5 tools + sweep, then
`--update-baseline` to ratchet UP after a verified gain.

USAGE: python validate_perf_scale.py                  # gate (exit 1 on regression)
       python validate_perf_scale.py --update-baseline  # ratchet baseline to current (forward-only)
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(ROOT, "perf_scale_results.json")
BASELINE = os.path.join(ROOT, "perf_scale_baseline.json")
FLOORS = {"S": 90, "E": 85, "R": 85, "B": 95}
UPDATE = "--update-baseline" in sys.argv


def main():
    if not (os.path.exists(RESULTS) and os.path.exists(BASELINE)):
        print("  ! missing perf_scale_results.json or perf_scale_baseline.json (run the Arc-L scorers first)")
        return 1
    res = json.load(open(RESULTS, encoding="utf-8"))
    base = json.load(open(BASELINE, encoding="utf-8"))
    lp = res.get("lens_pass", {})
    pct = res.get("lens_pct", {})

    print("=" * 66)
    print("ARC L L-Accept - Performance & Scale ratchet (forward-only)")
    print("=" * 66)
    print("  lens  pass  baseline  floor%  now%   status")
    regressions, below_floor = [], []
    for L in ("S", "E", "R", "B"):
        now = lp.get(L, 0)
        b = base.get(f"{L}_pass", 0)
        fl = FLOORS[L]
        p = pct.get(L, 0)
        ratchet_ok = now >= b
        floor_ok = p >= fl
        tag = "OK" if (ratchet_ok and floor_ok) else ("REGRESSION" if not ratchet_ok else "below-floor")
        if not ratchet_ok:
            regressions.append((L, now, b))
        if not floor_ok:
            below_floor.append((L, p, fl))
        print(f"   {L}    {now:4}   {b:4}     {fl:3}   {p:5}%  {tag}")

    if UPDATE:
        for L in ("S", "E", "R", "B"):
            base[f"{L}_pass"] = max(base.get(f"{L}_pass", 0), lp.get(L, 0))
        json.dump(base, open(BASELINE, "w", encoding="utf-8"), indent=2)
        print("\n  -> baseline ratcheted UP to current pass-counts (forward-only).")
        return 0

    if regressions:
        print("\n  FAIL - perf/scale REGRESSION (a lens dropped below its locked baseline):")
        for L, now, b in regressions:
            print(f"    {L}: {now} < baseline {b}")
        return 1
    floors_met = sum(1 for L in FLOORS if pct.get(L, 0) >= FLOORS[L])
    print(f"\n  PASS - no regression. Floors met: {floors_met}/4" +
          ("  (ALL FLOORS MET)" if floors_met == 4 else f"  (below floor: {', '.join(L for L, _, _ in below_floor)})"))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
