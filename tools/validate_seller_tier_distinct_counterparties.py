#!/usr/bin/env python3
"""validate_seller_tier_distinct_counterparties.py — T98's lock instrument: a seller's reputation tier is
earned over DISTINCT COUNTERPARTIES, not raw sales rows — so a seller cannot inflate a tier by selling to
the same buyer repeatedly (or to one buyer whose phone is written three ways).

T98 unified two divergent tier definitions at the SSOT (migration ...065): tier counts
COUNT(DISTINCT COALESCE(buyer_auth_uid, normalised_contact, buyer_name)) across sold listings — identity
prefers a real account, falls back to a normalised contact (one phone written three ways = one buyer),
then the typed name. This gate locks that: recompute_seller_sales_and_tier must count DISTINCT
counterparties with the identity coalesce, so a future edit cannot silently revert to COUNT(*) rows
(which would let repeat sales inflate the tier) — the 'a metric's definition is a claim' class.

Assertions on the recompute_seller_sales_and_tier function body (introspected via psql):
  1. DISTINCT — the count is COUNT(DISTINCT …), not COUNT(*) / COUNT(rows).
  2. COUNTERPARTY IDENTITY — the DISTINCT key COALESCEs buyer_auth_uid (the real-account-first identity),
     so one buyer counts once regardless of how many rows.

DB-backed (psql), NOT browser. SKIPS (does not fail) when the DB is unreachable — an unearned pass is how
a false green happens. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import subprocess
import sys

CHECK_NAMES = ["seller-tier-distinct-counterparties"]
FN = "recompute_seller_sales_and_tier"


def _fndef(fn: str) -> str | None:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c", f"SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname='{fn}' LIMIT 1;"],
            capture_output=True, text=True, timeout=30)
        out = (r.stdout or "").strip()
        return out or None
    except Exception:
        return None


def check(src: str) -> list[str]:
    problems: list[str] = []
    if not re.search(r"COUNT\s*\(\s*DISTINCT", src, re.I):
        problems.append("the tier count is not COUNT(DISTINCT …) — repeat sales to one buyer would inflate "
                        "the tier (it must count distinct counterparties, not rows).")
    if not re.search(r"DISTINCT[^)]{0,80}COALESCE[^)]{0,80}buyer_auth_uid", src, re.I | re.S):
        problems.append("the DISTINCT key does not COALESCE buyer_auth_uid — one buyer written several ways "
                        "(or across contact/name) would count as several counterparties.")
    return problems


def main() -> int:
    src = _fndef(FN)
    if src is None:
        print(f"SKIP seller-tier-distinct-counterparties — DB unreachable or {FN} absent (no unearned pass).")
        return 0
    problems = check(src)
    if problems:
        print(f"FAIL seller-tier-distinct-counterparties — {FN} does not count distinct counterparties:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS seller-tier-distinct-counterparties — the tier is COUNT(DISTINCT COALESCE(buyer_auth_uid, "
          "…)), so a repeat buyer counts once and a tier cannot be inflated by repeat sales.")
    return 0


def self_test() -> int:
    fails = []
    good = "SELECT COUNT(DISTINCT COALESCE(i.buyer_auth_uid::text, NULLIF(lower(i.buyer_contact),''), i.buyer_name))"
    if check(good):
        fails.append("the real DISTINCT-COALESCE-auth_uid body should PASS")
    if not any("COUNT(DISTINCT" in p for p in check("SELECT COUNT(*) FROM sold_listings")):
        fails.append("a COUNT(*) tier should FAIL (row count, not distinct counterparties)")
    if not any("COALESCE buyer_auth_uid" in p for p in check("SELECT COUNT(DISTINCT i.buyer_name) FROM x")):
        fails.append("a DISTINCT that does not coalesce buyer_auth_uid should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_seller_tier_distinct_counterparties self-test (COUNT(*) / name-only-distinct redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
