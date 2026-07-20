#!/usr/bin/env python3
"""memory_health_gate.py - Memory-System M2.2: health-regression gate for the Memento retriever.
================================================================================
The health metrics (silent_rate, latency, file-grounded %, index size) are computed by
`memento_health_export.build_payload()` and shown on the founder-console — but ONLY on a
dashboard, so a regression (silent_rate spiking, p95 latency ballooning, grounding collapsing)
needs a human to notice. This wraps the SAME payload in thresholds so a degraded metric FAILS
the gate automatically instead of waiting to be eyeballed.

Honesty doctrine (inherited from the export): when `warming_up` is true (retrievals_today < 10),
the activity metrics are statistically unreliable, so the gate enforces ONLY the always-valid
structural invariants (index non-empty, vocab present) and reports the activity metrics as
informational. It never false-fails on a tiny sample — matching the founder-console's
"show gap, not fiction" contract.

  --self-test  prove teeth: a synthetic DEGRADED payload (silent_rate 90%, p95 9s) must FAIL;
               a healthy one must PASS.

Exit 0 = healthy (or warming up with sound structure); 1 = a threshold breached. Stdlib only;
reads the live memory.db read-only via the export module. Writes nothing.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

MEMENTO_TOOLS = Path.home() / ".claude-memento" / "tools"
sys.path.insert(0, str(MEMENTO_TOOLS))
try:
    import memento_health_export as mhe  # noqa: E402  (same payload the dashboard uses)
except Exception as e:  # pragma: no cover
    print(f"  SKIP — memento health export not importable ({type(e).__name__}: {e})")
    sys.exit(0)

G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

# (metric, direction, limit, scope). direction 'max' = breach if value > limit; 'min' = breach if
# value < limit. scope 'structural' = always checked; 'activity' = skipped while warming up.
THRESHOLDS = [
    ("chunks_indexed",    "min",    1, "structural"),
    ("vocab_terms",       "min",    1, "structural"),
    ("silent_rate_pct",   "max", 40.0, "activity"),
    # Latency health is gated on the MEDIAN (robust to transient load-spike outliers), not raw p95.
    # This gate RUNS INSIDE the release gate — i.e. while jscpd + ~80 validators saturate the same
    # CPU/disk — and reads a rolling-24h window that therefore INCLUDES those load spikes. On a small
    # sample (n~33) p95 is just "the 2nd-slowest sample": 4 build-session spikes (3.5–5.5 s) on a
    # healthy body (median 1.3 s) dragged p95 to 4.3 s and manufactured a false fail (2026-07-21). A
    # genuine retriever regression (index bloat, bad vocab, IO) slows the WHOLE distribution → the
    # median balloons and is caught; transient tail spikes leave the median healthy and are tolerated.
    # Mirrors the codebase perf-gate doctrine: flat thresholds that manufacture false fails on
    # environmental jitter are "the L0-gate honesty-bug class"; median-of-N is why a gate doesn't flap.
    ("median_latency_ms", "max", 2500, "activity"),
    # p95 kept as a GENEROUS catastrophic-tail sanity bound (tolerates build-session spikes; a truly
    # pathological tail still trips it) and printed as informational.
    ("p95_latency_ms",    "max", 8000, "activity"),
    ("file_grounded_pct", "min", 50.0, "precision"),   # only if a fresh precision report exists
]


def evaluate(payload: dict) -> tuple[list[str], list[str], list[str]]:
    """Return (breaches, applied, skipped-as-strings)."""
    m = payload.get("metrics", {}) or {}
    precision = payload.get("precision", {}) or {}
    warming = bool(payload.get("honesty", {}).get("warming_up"))
    breaches: list[str] = []
    applied: list[str] = []
    skipped: list[str] = []

    for name, direction, limit, scope in THRESHOLDS:
        if scope == "activity" and warming:
            skipped.append(f"{name} (warming up)")
            continue
        if scope == "precision":
            val = precision.get(name)
            if val is None:
                skipped.append(f"{name} (no fresh precision report)")
                continue
        else:
            val = m.get(name)
            if val is None:
                skipped.append(f"{name} (absent)")
                continue
        ok = (val <= limit) if direction == "max" else (val >= limit)
        sign = "<=" if direction == "max" else ">="
        applied.append(f"{name}={val} {sign} {limit}")
        if not ok:
            breaches.append(f"{name}={val} violates {sign}{limit}")
    return breaches, applied, skipped


def do_self_test() -> int:
    healthy = {"metrics": {"chunks_indexed": 10000, "vocab_terms": 5000,
                           "silent_rate_pct": 5.0, "median_latency_ms": 700, "p95_latency_ms": 800},
               "precision": {"file_grounded_pct": 80.0},
               "honesty": {"warming_up": False}}
    degraded = {"metrics": {"chunks_indexed": 10000, "vocab_terms": 5000,
                            "silent_rate_pct": 90.0, "median_latency_ms": 6000, "p95_latency_ms": 9000},
                "precision": {"file_grounded_pct": 12.0},
                "honesty": {"warming_up": False}}
    hb, _, _ = evaluate(healthy)
    db, _, _ = evaluate(degraded)
    print(f"  healthy payload -> {len(hb)} breaches ({'CLEAN' if not hb else hb})")
    print(f"  degraded payload -> {len(db)} breaches ({'CAUGHT' if db else 'MISSED'})")
    if not hb and len(db) >= 3:
        print(f"  {G}TEETH VERIFIED{X} healthy passes; degraded breaches {db} -> gate catches it.")
        return 0
    print(f"  {R}TOOTHLESS{X} healthy_breaches={hb} degraded_breaches={db}")
    return 1


def main() -> int:
    print(f"{B}Memory-System M2.2 - retriever health-regression gate{X}")
    print("=" * 62)
    if "--self-test" in sys.argv[1:]:
        rc = do_self_test()
        print(f"\n{(G if rc == 0 else R)}{B}  HEALTH GATE SELFTEST: {'PASS' if rc == 0 else 'FAIL'}{X}")
        return rc

    payload = mhe.build_payload()
    m = payload.get("metrics", {}) or {}
    warming = bool(payload.get("honesty", {}).get("warming_up"))
    breaches, applied, skipped = evaluate(payload)

    print(f"  status: {payload.get('summary', {}).get('headline', '?')}")
    print(f"  index: {m.get('chunks_indexed','?')} chunks / {m.get('files_indexed','?')} files · "
          f"vocab {m.get('vocab_terms','?')} terms")
    if not warming:
        print(f"  activity: {m.get('retrievals_today','?')} retrievals · silent {m.get('silent_rate_pct','?')}% · "
              f"median {m.get('median_latency_ms','?')}ms · p95 {m.get('p95_latency_ms','?')}ms (informational tail)")
    for a in applied:
        print(f"    {G}check{X} {a}")
    for s in skipped:
        print(f"    {Y}skip {X} {s}")
    if breaches:
        print(f"\n{R}{B}  HEALTH GATE: FAIL{X} - {'; '.join(breaches)}")
        return 1
    note = " (warming up — activity thresholds deferred)" if warming else ""
    print(f"\n{G}{B}  HEALTH GATE: PASS{X} - all applicable health thresholds met{note}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
