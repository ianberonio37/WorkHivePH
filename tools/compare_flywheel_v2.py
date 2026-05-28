#!/usr/bin/env python3
"""
compare_flywheel_v2.py
======================

Reads the 100-turn baseline (under `.tmp/v2/turn-*/`) and the V2 run
(under `.tmp/flywheel-turn-*/`) and prints a side-by-side delta.

Honest comparison only — same probe bank schema, same independent grader,
same hive. The probe bank's schema_version changed from 1 → 2 so a few
probe IDs differ (B02/B04/B05/B06 moved from specialist agents to
voice-journal) — those probes are noted but still counted.
"""
from __future__ import annotations
import io
import json
import statistics
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent


def load_reports(glob_dir: Path, prefix: str) -> list[dict]:
    out = []
    for p in sorted(glob_dir.glob(f"{prefix}*")):
        if not p.is_dir():
            continue
        rj = p / "report.json"
        if rj.exists():
            try:
                out.append(json.loads(rj.read_text(encoding="utf-8")))
            except Exception:
                pass
    return out


def summarise(label: str, reports: list[dict]) -> dict:
    if not reports:
        print(f"{label}: no reports found")
        return {}
    pass_pcts = [r["metrics"]["pass_pct"] for r in reports if r.get("metrics", {}).get("pass_pct") is not None]
    rl = [r["drift"]["rate_limited"] for r in reports if r.get("drift", {}).get("rate_limited") is not None]
    err = [r["metrics"]["error"] for r in reports if r.get("metrics", {}).get("error") is not None]
    safety = [r["metrics"]["safety_clean_pct"] for r in reports if r.get("metrics", {}).get("safety_clean_pct") is not None]
    routing = [r["metrics"]["routing_pct"] for r in reports if r.get("metrics", {}).get("routing_pct") is not None]
    adv = [r["metrics"]["adversarial_pct"] for r in reports if r.get("metrics", {}).get("adversarial_pct") is not None]
    p50 = [r["conventions"]["p50_latency_ms"] for r in reports if r.get("conventions", {}).get("p50_latency_ms") is not None]
    leaks = sum(r["drift"]["leak_count"] for r in reports if r.get("drift", {}).get("leak_count") is not None)

    def mean(arr):
        return statistics.mean(arr) if arr else None

    return {
        "label":       label,
        "n_turns":     len(reports),
        "pass_mean":   mean(pass_pcts),
        "pass_max":    max(pass_pcts) if pass_pcts else None,
        "rl_mean":     mean(rl),
        "err_mean":    mean(err),
        "safety_mean": mean(safety),
        "routing_mean": mean(routing),
        "adv_mean":    mean(adv),
        "p50_mean":    mean(p50),
        "leaks_total": leaks,
    }


def fmt(v, suffix="", width=8):
    if v is None:
        return f"{'n/a':>{width}}{suffix}"
    if isinstance(v, float):
        return f"{v:>{width}.1f}{suffix}"
    return f"{v:>{width}}{suffix}"


def delta(v2, base, suffix="", width=8):
    if v2 is None or base is None:
        return f"{'n/a':>{width}}"
    d = v2 - base
    sign = "+" if d >= 0 else ""
    return f"{sign}{d:>{width-1}.1f}{suffix}"


def main() -> int:
    # Find baselines and v2 reports
    base_dir = ROOT / ".tmp" / "v2"   # archived 100-turn baseline
    v2_dir = ROOT / ".tmp"            # active V2 run
    base = load_reports(base_dir, "turn-")
    v2 = load_reports(v2_dir, "flywheel-turn-")

    base_s = summarise("BASELINE (100t)", base)
    v2_s   = summarise("V2 (post-fixes)", v2)

    print(f"\n{'='*72}")
    print(f"  FLYWHEEL V2 vs BASELINE — delta after gateway fixes")
    print(f"{'='*72}\n")

    rows = [
        ("Turns analyzed",     "n_turns",     "",   8),
        ("Pass rate (mean)",   "pass_mean",   "%",  7),
        ("Pass rate (max)",    "pass_max",    "%",  7),
        ("Routing accuracy",   "routing_mean", "%", 7),
        ("Safety clean",       "safety_mean", "%",  7),
        ("Adversarial pass",   "adv_mean",    "%",  7),
        ("Errors / turn",      "err_mean",    "",   8),
        ("Rate-limited / turn", "rl_mean",    "",   8),
        ("p50 latency (ms)",   "p50_mean",    "",   8),
        ("Total leaks",        "leaks_total", "",   8),
    ]
    print(f"  {'Metric':<22s}  {'Baseline':>12s}  {'V2':>12s}  {'Delta':>12s}")
    print(f"  {'-'*22}  {'-'*12}  {'-'*12}  {'-'*12}")
    for label, key, suffix, w in rows:
        b = base_s.get(key)
        v = v2_s.get(key)
        if isinstance(b, (int, float)) and isinstance(v, (int, float)):
            print(f"  {label:<22s}  {fmt(b, suffix, 11)}  {fmt(v, suffix, 11)}  {delta(v, b, suffix, 11)}")
        else:
            print(f"  {label:<22s}  {fmt(b, suffix, 11)}  {fmt(v, suffix, 11)}  {'':>12}")

    # Per-turn pass-rate trajectory for V2
    print(f"\n  V2 turn-by-turn pass-rate:")
    for r in v2:
        m = r.get("metrics", {})
        rl = r.get("drift", {}).get("rate_limited", 0)
        rp = m.get("routing_pct")
        rp_s = f"{rp:5.1f}%" if isinstance(rp, (int, float)) else " n/a "
        print(f"    Turn {r.get('turn'):3d}:  pass={m.get('pass_pct',0):5.1f}%  routing={rp_s}  safety={m.get('safety_clean_pct',0):5.1f}%  errors={m.get('error',0):2d}  rate_lim={rl:2d}")

    # Top drift categories — V2
    from collections import Counter
    v2_drift = Counter()
    for r in v2:
        for cat, n in r.get("drift", {}).get("fails_by_category", {}).items():
            v2_drift[cat] += n
    base_drift = Counter()
    for r in base:
        for cat, n in r.get("drift", {}).get("fails_by_category", {}).items():
            base_drift[cat] += n

    print(f"\n  Top drift categories (failures across runs):")
    print(f"  {'Category':<30s}  {'Baseline (100t)':>16s}  {'V2 ('+str(len(v2))+'t)':>14s}  Per-turn-delta")
    print(f"  {'-'*30}  {'-'*16}  {'-'*14}  --------------")
    cats = set(v2_drift) | set(base_drift)
    for cat in sorted(cats, key=lambda c: -(v2_drift[c]+base_drift[c]))[:12]:
        bn = base_drift[cat]
        vn = v2_drift[cat]
        # per-turn
        b_per = bn / max(1, len(base))
        v_per = vn / max(1, len(v2))
        d = v_per - b_per
        sign = "+" if d >= 0 else ""
        print(f"  {cat:<30s}  {bn:>16d}  {vn:>14d}  {sign}{d:+.2f}/turn")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
