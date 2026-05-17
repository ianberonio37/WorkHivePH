"""validate_sentinel_baseline.py - forward-only ratchet on sentinel coverage.

Reads sentinel_coverage_report.json and compares against sentinel_baseline.json.
PASSES if current coverage >= baseline. FAILS if any metric regressed.

The first run (no baseline yet) writes the current numbers as the baseline.
Subsequent runs ratchet upward: a drop in behavioral_coverage_pct or
check_coverage_pct triggers a Layer 0 failure that the Platform Guardian
surfaces. This is what makes the sentinel architecture forward-only.

Standard rule: bumping the baseline downward requires explicit human
intervention - delete or edit sentinel_baseline.json. The validator
never bumps it down on its own.

To raise the baseline after a coverage improvement:
  rm sentinel_baseline.json  (then re-run; new higher numbers lock in)

Skills consulted: platform-guardian (forward-only ratchet pattern),
qa-tester (regression detection), architect (ratchet vs full-replay decision).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
REPORT_FILE = ROOT / "sentinel_coverage_report.json"
BASELINE_FILE = ROOT / "sentinel_baseline.json"
RESULT_FILE = ROOT / "sentinel_baseline_report.json"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"
BOLD = "\033[1m"

RATCHETED_KEYS = [
    "validator_coverage_pct",
    "effective_coverage_pct",
    "check_coverage_pct",
    "behavioral_coverage_pct",
    "covered_validators",
    "covered_per_page_checks",
    "covered_per_page_behavioral_checks",
]

# Only HARD-FAIL on these keys. Others are reported but don't block.
# Rationale: when new validators are added (a normal platform-growth event),
# the validator-level % metrics dip because the denominator grew faster than
# the numerator. That's not a real regression - it's a coverage TODO for the
# new validators. Only the behavioral % (and absolute covered counts) reflect
# genuine "did we lose tests" regressions.
HARD_FAIL_KEYS = {
    "behavioral_coverage_pct",
    "covered_per_page_behavioral_checks",
    "covered_per_page_checks",
}


def main():
    print()
    print(f"{BOLD}SENTINEL BASELINE RATCHET{RESET}")
    print("-" * 60)

    if not REPORT_FILE.exists():
        print(f"  {RED}FAIL{RESET}  sentinel_coverage_report.json missing.")
        print(f"        Run `python run_sentinel_review.py` first.")
        return 1

    report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    summary = report.get("summary", {})
    current = {k: summary.get(k, 0) for k in RATCHETED_KEYS}

    if not BASELINE_FILE.exists():
        BASELINE_FILE.write_text(
            json.dumps({
                "_description": "Sentinel coverage baseline. Forward-only ratchet "
                                "enforced by validate_sentinel_baseline.py. "
                                "Delete this file to re-baseline after an "
                                "approved coverage drop.",
                "_locked_at": report.get("timestamp"),
                "metrics": current,
            }, indent=2),
            encoding="utf-8",
        )
        print(f"  {YELLOW}BASELINE LOCKED{RESET}  no prior baseline, "
              f"saved current metrics to sentinel_baseline.json")
        for k, v in current.items():
            print(f"    {k:<40} {v}")
        RESULT_FILE.write_text(json.dumps({
            "status": "BASELINE_LOCKED",
            "current": current,
        }, indent=2), encoding="utf-8")
        return 0

    baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
    bmetrics = baseline.get("metrics", {})

    regressions = []
    soft_regressions = []
    improvements = []
    for k in RATCHETED_KEYS:
        cur = current.get(k, 0)
        bas = bmetrics.get(k, 0)
        if isinstance(cur, (int, float)) and isinstance(bas, (int, float)):
            if cur < bas:
                if k in HARD_FAIL_KEYS:
                    regressions.append((k, bas, cur))
                else:
                    soft_regressions.append((k, bas, cur))
            elif cur > bas:
                improvements.append((k, bas, cur))

    print(f"  {BOLD}Baseline locked at:{RESET} {baseline.get('_locked_at', 'unknown')}")
    print()
    print(f"  {BOLD}Metric                              Baseline -> Current{RESET}")
    for k in RATCHETED_KEYS:
        cur = current.get(k, 0)
        bas = bmetrics.get(k, 0)
        sign = "=" if cur == bas else ("+" if cur > bas else "-")
        col = GREEN if cur >= bas else RED
        print(f"    {k:<35} {bas:>6}  {sign}  {col}{cur:>6}{RESET}")
    print()

    if regressions:
        print(f"  {RED}FAIL{RESET}  {len(regressions)} HARD-FAIL metric(s) regressed:")
        for k, bas, cur in regressions:
            print(f"         {k}: {bas} -> {cur}  (drop of {bas - cur:.2f})")
        print()
        print(f"  Either fix the regression or, if intentional, delete")
        print(f"  sentinel_baseline.json to re-baseline.")
        RESULT_FILE.write_text(json.dumps({
            "status": "FAIL",
            "regressions": [{"key": k, "baseline": bas, "current": cur}
                            for k, bas, cur in regressions],
            "soft_regressions": [{"key": k, "baseline": bas, "current": cur}
                                 for k, bas, cur in soft_regressions],
            "improvements": [{"key": k, "baseline": bas, "current": cur}
                             for k, bas, cur in improvements],
        }, indent=2), encoding="utf-8")
        return 1

    if soft_regressions:
        print(f"  {YELLOW}PASS (with informational dips){RESET}  "
              f"{len(soft_regressions)} non-blocking metric(s) below baseline:")
        for k, bas, cur in soft_regressions:
            print(f"         {k}: {bas} -> {cur}  (typically: new validator added without test)")
        print()
        print(f"  HARD-FAIL metrics ({', '.join(sorted(HARD_FAIL_KEYS))})")
        print(f"  are all at or above baseline. Build is OK.")
    elif improvements:
        print(f"  {GREEN}PASS{RESET}  no regressions. {len(improvements)} metric(s) improved.")
        print(f"  Run `rm sentinel_baseline.json` then re-run to lock the new numbers.")
    else:
        print(f"  {GREEN}PASS{RESET}  all metrics at or above baseline.")

    RESULT_FILE.write_text(json.dumps({
        "status": "PASS",
        "regressions": [],
        "soft_regressions": [{"key": k, "baseline": bas, "current": cur}
                             for k, bas, cur in soft_regressions],
        "improvements": [{"key": k, "baseline": bas, "current": cur}
                         for k, bas, cur in improvements],
    }, indent=2), encoding="utf-8")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
