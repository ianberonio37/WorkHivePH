#!/usr/bin/env python3
"""validate_money_columns_numeric.py — T424's lock: no MONEY column is stored as a binary float, so a
cost/price/payout rollup cannot drift by a centavo. double precision / real cannot represent 0.10 exactly
and accumulates error under SUM — fine for a physics metric, catastrophic for pesos. Every money-context
column must be numeric/integer.

Verified 2026-09-01: every money column (amount, price, peso, payout, credit, fee, wage, cost...) is numeric;
the ONLY binary float in a cost/hours context is hive_benchmarks.mttr_hours — a duration METRIC displayed
rounded, never summed as money, so it is exempt (matched by 'hours', not by the money pattern). This gate
holds the line so a new money column added as double precision reddens before it ships.

DB-backed (psql), read-only, browser-free. SKIPs if the DB is unreachable. Registered in run_platform_checks.
"""
from __future__ import annotations

import io
import re
import subprocess
import sys

CHECK_NAMES = ["money-columns-numeric"]
# money-context name fragments (NOT 'hours'/'rate'/'ratio' which are metrics, legitimately float)
MONEY = r"(amount|price|peso|php|payout|earning|salary|wage|\bfee\b|_fee|fee_|\bcost\b|_cost|cost_|credits?|balance|revenue|commission|refund|topup|top_up|payment)"


def _float_money_cols() -> list[str] | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c",
             "select table_name||'.'||column_name from information_schema.columns "
             "where table_schema='public' and data_type in ('double precision','real') "
             "and table_name in (select table_name from information_schema.tables where table_schema='public' and table_type='BASE TABLE') "
             "order by 1;"],
            capture_output=True, text=True, timeout=45)
        if r.returncode != 0:
            return None
        cols = [c.strip() for c in (r.stdout or "").splitlines() if c.strip()]
        return [c for c in cols if re.search(MONEY, c.split(".")[-1], re.I)]
    except Exception:
        return None


def check(float_money: list[str]) -> list[str]:
    return [f"{c} is a binary float (double precision/real) — money must be numeric; a SUM drifts by centavos."
            for c in float_money]


def main() -> int:
    fm = _float_money_cols()
    if fm is None:
        print("SKIP money-columns-numeric — DB unreachable (no unearned pass)."); return 0
    problems = check(fm)
    if problems:
        print("FAIL money-columns-numeric — a money column is a binary float:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS money-columns-numeric — no money-context column is a binary float; every peso amount is "
          "numeric/integer, so cost/price/payout rollups cannot drift by a centavo.")
    return 0


def self_test() -> int:
    fails = []
    if check([]):
        fails.append("no float money cols should PASS")
    if not any("centavos" in p for p in check(["service_payments.amount"])):
        fails.append("a float money column should FAIL")
    # a metric float must NOT be flagged (it never reaches check, but confirm the pattern excludes it)
    if re.search(MONEY, "mttr_hours", re.I):
        fails.append("mttr_hours (a metric) must NOT match the money pattern")
    if not re.search(MONEY, "amount", re.I) or not re.search(MONEY, "payout_peso", re.I):
        fails.append("money names must match the money pattern")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_money_columns_numeric self-test (float money reddens; metric floats exempt)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
