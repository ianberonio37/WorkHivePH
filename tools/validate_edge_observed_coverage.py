#!/usr/bin/env python3
# DEEPWALK-CELL: ai:* D21
"""validate_edge_observed_coverage.py — fix-to-ZERO: every AI edge fn is serveObserved-wrapped.

Arc T banked the observability net: `serveObserved()` wraps each edge fn so an unhandled throw
lands a `wh_traces` error row (visibility + aggregation + a clean 500 envelope). That win is only
durable if a NEW AI fn can't ship WITHOUT the wrapper. This gate statically asserts every AI fn in
`ai_seams_catalog.json.ai_fns` has `serveObserved` in its `index.ts` — fix-to-ZERO unwrapped.

Pairs the LIVE proof (`observability_fault_walk.py`, which injects a fault and asserts the row
lands): that walk proves the net FIRES; this gate proves the net COVERS every AI surface. Fast
(static scan), so it binds the deep-walk flywheel's D21 (observability) row for the AI sub-grid.

DEEPWALK-CELL tag (top): ai:* D21 — observability/SLO across every AI edge fn.

Usage:  python tools/validate_edge_observed_coverage.py [--json]
Exit 0 = every AI fn wrapped, 1 = an AI fn missing serveObserved (regression).
"""
import json
import os
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEAMS = os.path.join(ROOT, "ai_seams_catalog.json")
FUNCS = os.path.join(ROOT, "supabase", "functions")


def main():
    as_json = "--json" in sys.argv
    if not os.path.isfile(SEAMS):
        print("SKIP — ai_seams_catalog.json absent")
        return 0
    ai_fns = json.load(open(SEAMS, encoding="utf-8")).get("ai_fns", [])
    wrapped, unwrapped = [], []
    for fn in ai_fns:
        idx = os.path.join(FUNCS, fn, "index.ts")
        if not os.path.isfile(idx):
            unwrapped.append({"fn": fn, "reason": "no index.ts"})
            continue
        src = open(idx, encoding="utf-8", errors="replace").read()
        if "serveObserved" in src:
            wrapped.append(fn)
        else:
            unwrapped.append({"fn": fn, "reason": "no serveObserved wrapper"})

    result = {"ai_fns": len(ai_fns), "wrapped": len(wrapped),
              "unwrapped": unwrapped, "unwrapped_count": len(unwrapped)}
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if unwrapped:
            print(f"FAIL — {len(unwrapped)}/{len(ai_fns)} AI edge fn(s) NOT serveObserved-wrapped "
                  f"(observability hole — an unhandled throw would vanish):")
            for u in unwrapped[:20]:
                print(f"  {u['fn']:32} {u['reason']}")
        else:
            print(f"PASS — {len(wrapped)}/{len(ai_fns)} AI edge fns serveObserved-wrapped "
                  f"(D21 observability coverage, fix-to-zero).")
    return 1 if unwrapped else 0


if __name__ == "__main__":
    sys.exit(main())
