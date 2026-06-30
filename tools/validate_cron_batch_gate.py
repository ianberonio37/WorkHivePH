#!/usr/bin/env python3
"""validate_cron_batch_gate.py — G0 gate: all-hives batch fns must be cron-only.

THE CLASS (2 instances found): an edge fn that builds a service-role client and
iterates EVERY hive (`from("v_hives_truth")` / `from("hives")` with no client
hive_id filter) is a daily cron batch. If it has no service-role gate, ANY
authenticated user can trigger the full all-hives compute = unauthorized
expensive batch / cost-abuse.
  · batch-risk-scoring — fixed 2026-06-08
  · parts-staging-recommender — fixed 2026-06-20 (caught by a live foreign-hive probe)

RULE: any fn that fetches the all-hives set must gate on the service-role bearer
(`bearer === SERVICE_KEY` / isService) before doing the batch. Baseline 0.

USAGE: python tools/validate_cron_batch_gate.py
"""
from __future__ import annotations
import re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FUNCS = ROOT / "supabase" / "functions"
ALL_HIVES = re.compile(r"""from\(\s*['"](v_hives_truth|hives)['"]\s*\)\s*\.select""")
# a service-role gate: compares the bearer to the service-role key, or an isService flag
SERVICE_GATE = re.compile(r"isService|bearer\s*===\s*SERVICE|===\s*SERVICE_KEY|requireServiceRole|SERVICE_ROLE_KEY\s*&&\s*bearer")


def main() -> int:
    violations = []
    for d in sorted(FUNCS.glob("*/index.ts")):
        src = d.read_text(encoding="utf-8", errors="replace")
        code = re.sub(r"//.*", "", re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL))
        if ALL_HIVES.search(code) and not SERVICE_GATE.search(code):
            violations.append(d.parent.name)

    print("=" * 60)
    print("  validate_cron_batch_gate — all-hives batch must be cron-only")
    print("=" * 60)
    if violations:
        for fn in violations:
            print(f"  X  {fn}: fetches all hives but no service-role gate")
        print(f"\n  FAIL: {len(violations)} ungated all-hives batch fn(s) (baseline 0)")
        return 1
    n = sum(1 for d in FUNCS.glob("*/index.ts") if ALL_HIVES.search(d.read_text(encoding='utf-8', errors='replace')))
    print(f"  OK  all {n} all-hives batch fn(s) gate on the service-role bearer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
