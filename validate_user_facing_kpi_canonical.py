"""
User-Facing KPI Canonical Gate (L0).
=====================================
Forward-only ratchet over `canonical_drift_platform_report.json`. The L-1.5
miner ranks every page by:

  TIER A  — page renders a hero KPI AND reads a raw table that has a
            v_*_truth view (or reimplements truth-math locally).
  TIER B  — drift on a non-KPI page or shared JS.

This gate locks the baseline TIER A footprint in
`canonical_drift_baseline.json`. New commits can only REDUCE the counts.
A regression FAILs:

  - A page that wasn't TIER A becomes TIER A.
  - A TIER A page gains MORE drift reads than baseline.
  - A TIER A page introduces local truth-math (FREQ_DAYS / calcNextDue /
    computeOEE / ...) when baseline had none.

Usage:
  python validate_user_facing_kpi_canonical.py
  python validate_user_facing_kpi_canonical.py --update-baseline  (only
       after a deliberate reduction — locks the lower count in)

Output:
  user_facing_kpi_canonical_report.json
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent
MINER_REPORT = ROOT / "canonical_drift_platform_report.json"
BASELINE     = ROOT / "canonical_drift_baseline.json"
REPORT_OUT   = ROOT / "user_facing_kpi_canonical_report.json"

GREEN = "\033[92m"
RED   = "\033[91m"
YEL   = "\033[93m"
END   = "\033[0m"
BOLD  = "\033[1m"


def _miner_report() -> dict:
    if not MINER_REPORT.exists():
        print(f"{RED}FAIL{END}  Miner report missing: {MINER_REPORT}")
        print("        Run `python tools/mine_canonical_drift_platform.py` first.")
        sys.exit(2)
    return json.loads(MINER_REPORT.read_text(encoding="utf-8"))


def _baseline() -> dict:
    if not BASELINE.exists():
        return {"tier_a_pages": {}, "_doc": "Initial baseline — created on first ratchet run."}
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def _build_tier_a_index(report: dict) -> dict[str, dict]:
    """{file_path: {drift_count, has_truth_math, truth_math_patterns, drift_tables}}"""
    idx = {}
    for p in report.get("tier_a_pages", []):
        idx[p["file"]] = {
            "drift_count":         len(p["drift"]),
            "has_truth_math":      bool(p["truth_math"]),
            "truth_math_patterns": sorted(t["pattern"] for t in p["truth_math"]),
            "drift_tables":        sorted({d["table"] for d in p["drift"]}),
        }
    return idx


def _build_gap_index(report: dict) -> dict[str, int]:
    """{table_name: read_count_across_platform}. Captures the "no wrapper yet" footprint.

    A growing gap_table_counts means new code is reading raw tables that
    should have a v_*_truth view. The ratchet locks the baseline; pull-requests
    that add new gap reads must EXPLICITLY ratchet up via --update-baseline."""
    return dict(report.get("gap_table_counts", {}))


def main(argv: list[str]) -> int:
    update_baseline = "--update-baseline" in argv

    report = _miner_report()
    current = _build_tier_a_index(report)
    current_gap = _build_gap_index(report)
    baseline = _baseline()
    base_idx = baseline.get("tier_a_pages", {})
    base_gap = baseline.get("gap_table_counts", {})

    issues: list[str] = []
    delta: dict[str, dict] = {}
    gap_regressions: list[str] = []

    # New TIER A pages
    for path, cur in current.items():
        if path not in base_idx:
            delta[path] = {"kind": "NEW", "current": cur}
            issues.append(
                f"NEW TIER A page (user-facing KPI + canonical drift): {path}\n"
                f"     drift on tables: {cur['drift_tables']}\n"
                f"     truth-math: {cur['truth_math_patterns'] or 'none'}\n"
                f"     fix: migrate the .from('T').select(...) calls to the matching v_*_truth view"
            )
            continue
        base = base_idx[path]
        # Drift count regression
        if cur["drift_count"] > base.get("drift_count", 0):
            delta[path] = {"kind": "DRIFT_UP", "current": cur, "baseline": base}
            issues.append(
                f"Drift COUNT REGRESSION on {path}: "
                f"{base.get('drift_count', 0)} -> {cur['drift_count']}"
            )
        # Truth-math introduced where baseline had none
        if cur["has_truth_math"] and not base.get("has_truth_math", False):
            delta[path] = {"kind": "TRUTH_MATH_INTRODUCED", "current": cur, "baseline": base}
            issues.append(
                f"Local truth-math INTRODUCED on {path}: {cur['truth_math_patterns']}\n"
                f"     fix: remove the local constant/function; use the canonical view columns instead"
            )

    # TIER C — gap-table footprint. Forward-only ratchet: if a table has more
    # raw reads now than at baseline, the gate FAILs. New tables in the gap
    # set (no baseline entry, > 0 current reads) also FAIL — they're either
    # a new dependency that needs a v_*_truth wrapper, or the developer
    # forgot to annotate with canonical-allow.
    for tbl, cnt in current_gap.items():
        base_cnt = base_gap.get(tbl, 0)
        if cnt > base_cnt:
            kind = "NEW_GAP" if base_cnt == 0 else "GAP_UP"
            gap_regressions.append(
                f"Gap-table read COUNT REGRESSION on `{tbl}`: {base_cnt} -> {cnt}\n"
                f"     options: (1) add `// canonical-allow: <reason>` near the new .from('{tbl}') call,\n"
                f"              (2) build v_{tbl}_truth wrapper if this table will be read by 2+ surfaces,\n"
                f"              (3) ratchet up via --update-baseline if this is a deliberate one-off"
            )

    issues.extend(gap_regressions)

    # Forward-only ratchet: pages that dropped off (i.e. were fixed) are FINE.
    fixed = [p for p in base_idx if p not in current]
    gap_fixed = [t for t in base_gap if base_gap.get(t, 0) > current_gap.get(t, 0)]

    summary = {
        "current_tier_a_pages":      len(current),
        "baseline_tier_a_pages":     len(base_idx),
        "tier_a_regressions":        len([i for i in issues if i not in gap_regressions]),
        "tier_a_fixed_since_baseline": len(fixed),
        "tier_a_fixed_pages":        sorted(fixed),
        "current_gap_tables":        len(current_gap),
        "baseline_gap_tables":       len(base_gap),
        "current_gap_reads":         sum(current_gap.values()),
        "baseline_gap_reads":        sum(base_gap.values()) if base_gap else 0,
        "gap_regressions":           len(gap_regressions),
        "gap_fixed":                 sorted(gap_fixed),
    }

    out = {
        "summary":          summary,
        "deltas":           delta,
        "current":          current,
        "current_gap":      current_gap,
        "gap_regressions":  gap_regressions,
        "issues":           issues,
    }
    REPORT_OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"{BOLD}User-Facing KPI Canonical Gate{END}")
    print(f"  TIER A pages:      {len(current)} (baseline {len(base_idx)}, fixed {len(fixed)})")
    print(f"  TIER C gap tables: {len(current_gap)} ({sum(current_gap.values())} raw reads, baseline {sum(base_gap.values()) if base_gap else 0})")
    print(f"  regressions:       {len(issues)}")
    if issues:
        print()
        for i in issues:
            print(f"  {RED}FAIL{END}  {i}")

    if update_baseline:
        new_base = {
            "_doc":              "Forward-only ratchet baseline. Updated only via --update-baseline after a deliberate reduction.",
            "tier_a_pages":      current,
            "gap_table_counts":  current_gap,
        }
        BASELINE.write_text(json.dumps(new_base, indent=2), encoding="utf-8")
        print(f"\n{GREEN}Baseline updated{END}: {len(current)} TIER A page(s), {sum(current_gap.values())} gap reads across {len(current_gap)} table(s).")
        return 0

    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({
            "_doc":              "Forward-only ratchet baseline. Updated only via --update-baseline after a deliberate reduction.",
            "tier_a_pages":      current,
            "gap_table_counts":  current_gap,
        }, indent=2), encoding="utf-8")
        print(f"\n{YEL}Baseline seeded{END}: {len(current)} TIER A page(s), {sum(current_gap.values())} gap reads. Re-run to enforce.")
        return 0

    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
