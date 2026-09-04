#!/usr/bin/env python3
"""validate_year_walk_capstone.py — T196's lock: "the complete story: one hive, one year" holds as a
COMPOSITION — the material to compress a year exists, and every invariant that must survive that year
is protected by a built gate.

T196 is a meta-trajectory: it composes everything before it into a single longitudinal walk (grow a
hive's roster, age its logbook, run a multi-year history, and re-validate the platform's invariants at
each stage). Its capstone therefore has two halves, both checkable without a slow live re-run:
  1. THE YEAR-COMPRESSION MATERIAL EXISTS — the three fixtures the execution plan names:
     grow_hive_fixture.py (roster growth), age_hive_fixture.py (a 2-year logbook), and
     seed_5y_synthetic_history.py (five-year synthetic history). Without these, no year can be walked.
  2. EVERY CROSS-YEAR INVARIANT IS GATED — the properties that must hold after a year of growth,
     aging, PM cycles and shutdowns are each protected by a registered gate: the ledger reconciles,
     no hive-FK orphans, soft-deletes never aggregate, the analytics cache tracks freshness, a removed
     member loses access, tenant isolation holds, the shift window is server-validated, a deferral is
     never a completion, and a shutdown reads as skips not a false cliff.
If any fixture is missing, OR any cross-year invariant loses its gate, this capstone reddens — the
"one hive, one year" story would no longer be provable end to end.

Static (file + registry reads), browser-free, no DB mutation. Registered in run_platform_checks."""
from __future__ import annotations

import io
import os
import sys

CHECK_NAMES = ["year-walk-capstone"]
FIXTURES = ["tools/grow_hive_fixture.py", "tools/age_hive_fixture.py", "tools/seed_5y_synthetic_history.py"]
CROSS_YEAR_INVARIANTS = [
    "inventory-ledger-reconciled", "hive-fk-integrity", "soft-delete-not-aggregated",
    "analytics-cache-freshness", "stale-membership-no-access", "rls_tenant_isolation",
    "shift-window-server-validated", "a-deferral-is-not-a-completion", "pm-shutdown-skip-honesty",
]
CHECKS_FILE = "run_platform_checks.py"


def check(missing_fixtures: list[str], unregistered: list[str]) -> list[str]:
    problems: list[str] = []
    for f in missing_fixtures:
        problems.append(f"year-compression fixture missing: {f} — a year cannot be walked without it")
    for g in unregistered:
        problems.append(f"cross-year invariant '{g}' has no registered gate — it would not survive a simulated year unprotected")
    return problems


def _gather() -> tuple[list[str], list[str]]:
    missing = [f for f in FIXTURES if not os.path.exists(f)]
    try:
        checks = io.open(CHECKS_FILE, encoding="utf-8").read()
    except Exception:
        checks = ""
    unreg = [g for g in CROSS_YEAR_INVARIANTS if f'"{g}"' not in checks]
    return missing, unreg


def main() -> int:
    missing, unreg = _gather()
    problems = check(missing, unreg)
    if problems:
        print("FAIL year-walk-capstone — the one-hive-one-year story is not provable end to end:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"PASS year-walk-capstone — all {len(FIXTURES)} year-compression fixtures exist and all "
          f"{len(CROSS_YEAR_INVARIANTS)} cross-year invariants (ledger, FK, soft-delete, cache-freshness, "
          "membership, RLS, shift-window, deferral, shutdown-skip) are gated: the complete one-hive-one-year "
          "story composes and holds.")
    return 0


def self_test() -> int:
    fails = []
    if check([], []):
        fails.append("all present should PASS")
    if not any("fixture missing" in p for p in check(["tools/grow_hive_fixture.py"], [])):
        fails.append("a missing fixture should FAIL")
    if not any("no registered gate" in p for p in check([], ["hive-fk-integrity"])):
        fails.append("an unregistered invariant should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_year_walk_capstone self-test (missing-fixture / unregistered-invariant redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
