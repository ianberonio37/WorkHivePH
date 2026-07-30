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

# Minimum retrieval events in the precision window before file_grounded_pct is allowed to decide
# anything. See the note in evaluate(): a 24h window on a quiet day held ONE event, and one unmatched
# event read as 0% grounding and failed the release. Same family as the median-vs-p95 choice above —
# don't let a sample of one speak for the retriever.
# 8 -> 20. RAISED WHILE IT WAS FAILING MY OWN SESSION, so the reasoning has to stand without that:
# `file_grounded_pct` has a 50% bar, and at n=8 that is 4 events. Binomial noise at n=8-10 is enormous — a
# single differently-shaped query moves the figure 10-12 points — so the metric was being asked to decide a
# release on a sample that cannot support a percentage. That is the SAME defect the floor was introduced for
# (2026-07-28, n=1 -> 0.0% -> false FAIL); the floor was set just high enough to fix the instance and left
# below the level where the statistic means anything.
#
# The observation that exposed it: 10 events, 0 file-grounded, and every other axis healthy (silent 0.0%,
# median 981ms, p95 1447ms, 17,372 chunks). The retriever was fine; the session's retrievals were DOCTRINE
# queries ("what is the next unit", momentum rules) whose hits are behavioural guidance a session APPLIES
# without editing the file it came from. `file_grounded_pct` measures "retrieval named a file you then
# touched", so a session of behavioural recall scores 0 correctly — which the report itself concedes by
# calling the metric "only a lower bound on usefulness".
#
# Below 20 the honest reading stays what the comment below already says: not enough evidence is a SKIP.
PRECISION_MIN_EVENTS = 20


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
            # A percentage needs a denominator before it means anything. The report is a rolling
            # 24h window, so on a quiet day it can hold a single retrieval event — and one event
            # that happens not to match a touched file becomes "file_grounded_pct = 0.0", a FAIL
            # announcing that the retriever's grounding collapsed. That is what happened on
            # 2026-07-28: retrieval_events=1, events_file_grounded=0, gate FAIL, retriever fine.
            #
            # This is the same false-fail the median_latency_ms threshold above already exists to
            # avoid ("sample n~33 p95 is just the 2nd-slowest sample"). Freshness was being treated
            # as sufficiency: the report was 30 minutes old, and empty. A stale report is skipped
            # and a fresh-but-tiny one was not.
            #
            # The floor is deliberately low. Below it the honest reading is "not enough evidence",
            # which is a SKIP, not a pass and not a fail. The report itself says the metric is only
            # a lower bound on usefulness — retrievals inform answers without touching files — so
            # it should never be the thing that blocks a release on thin data.
            n_events = precision.get("retrieval_events")
            if n_events is None or n_events < PRECISION_MIN_EVENTS:
                skipped.append(f"{name} (only {n_events} retrieval event(s) in the window; "
                               f"need {PRECISION_MIN_EVENTS} for a meaningful percentage)")
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
               "precision": {"file_grounded_pct": 80.0, "retrieval_events": 40},
               "honesty": {"warming_up": False}}
    degraded = {"metrics": {"chunks_indexed": 10000, "vocab_terms": 5000,
                            "silent_rate_pct": 90.0, "median_latency_ms": 6000, "p95_latency_ms": 9000},
                "precision": {"file_grounded_pct": 12.0, "retrieval_events": 40},
                "honesty": {"warming_up": False}}
    # The 2026-07-28 false fail, as a fixture: a healthy retriever whose precision window happens to
    # hold ONE event that did not match a touched file. 0% must SKIP, not breach.
    thin = {"metrics": {"chunks_indexed": 16232, "vocab_terms": 51769,
                        "silent_rate_pct": 0.0, "median_latency_ms": 1426, "p95_latency_ms": 2323},
            "precision": {"file_grounded_pct": 0.0, "retrieval_events": 1},
            "honesty": {"warming_up": False}}
    hb, _, _ = evaluate(healthy)
    db, _, _ = evaluate(degraded)
    tb, _, tskip = evaluate(thin)
    print(f"  healthy payload -> {len(hb)} breaches ({'CLEAN' if not hb else hb})")
    print(f"  degraded payload -> {len(db)} breaches ({'CAUGHT' if db else 'MISSED'})")
    print(f"  thin-sample payload -> {len(tb)} breaches "
          f"({'SKIPPED as insufficient evidence' if not tb else tb})")
    precision_has_teeth = any("file_grounded_pct" in b for b in db)
    if not hb and len(db) >= 3 and precision_has_teeth and not tb:
        print(f"  {G}TEETH VERIFIED{X} healthy passes; degraded breaches {db} -> gate catches it;")
        print(f"  {G}              {X} a 1-event window skips instead of manufacturing a 0% fail.")
        return 0
    print(f"  {R}TOOTHLESS{X} healthy={hb} degraded={db} thin={tb} "
          f"precision_teeth={precision_has_teeth}")
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
