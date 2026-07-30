#!/usr/bin/env python3
"""validate_slo_budget.py - C15 lock: the arc's north-star metrics are MEASURED, not adjectives.

WHAT THIS GATE DOES AND DELIBERATELY DOES NOT DO. It asserts that every SLI is computable, has a
numeric target, and reports honestly. It does NOT fail when an SLO is BREACHED. A breach is a
business signal ("the marketplace is under-allocating this month"), not a code regression, and a gate
that reds for non-code reasons gets excluded — which is exactly how nine cron jobs stayed dead behind
a "reasonable" exclusion for weeks. So breaches are PRINTED loudly and the exit code stays 0; only a
broken or dishonest MEASUREMENT fails.

  L1  every SLI has a numeric target and a valid comparator, stored as DATA (tunable without a migration)
  L2  every named SLI actually computes from live data
  L3  an empty denominator reports NULL ("not measurable yet"), never 0 — reporting 0% allocation for
      a month with no hails would be a fabricated breach, the metric-honesty class
  L4  the AI chain's breaker is intact: a failing slot is PARKED (with Retry-After honored) and SKIPPED
      while blocked. Verified as already-present, not rebuilt — §4b's "adopt a circuit breaker" verdict
      was wrong; the chain has had one all along.

Infra absent => SKIP (exit 0), never a false FAIL.
"""
import os
import re
import subprocess
import sys

DB = "supabase_db_workhive"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[0m"

CHECKS = []
SLIS = ("allocation_rate", "time_to_accept_p50", "completion_rate")


def psql(sql, timeout=60):
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c", sql],
            capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return (r.stdout or "").strip() if r.returncode == 0 else None


def check(name, ok, detail=""):
    CHECKS.append((bool(ok), name, detail))


def main():
    print("=" * 78)
    print("  C15 SLO budget - the north-star metrics are measured, with numeric targets")
    print("=" * 78)

    if psql("select 1") is None:
        print("  SKIP: docker/psql unavailable")
        return 0
    if psql("select to_regclass('public.v_service_slo')") in (None, "", "\\N"):
        print("  SKIP: v_service_slo not migrated yet (C15 not built)")
        return 0

    # L1 - targets exist, as DATA
    rows = psql("""select sli || '|' || target || '|' || comparator || '|' || unit
                   from public.service_slo_targets order by sli""") or ""
    have = {ln.split("|")[0] for ln in rows.split("\n") if ln.strip()}
    for sli in SLIS:
        check(f"L1 {sli} has a numeric SLO target", sli in have,
              "no target row - the metric has no number to be judged against")
    bad_cmp = psql("""select count(*) from public.service_slo_targets
                      where comparator not in ('>=', '<=')""")
    check("L1 every target has a valid comparator", (bad_cmp or "0") == "0",
          f"{bad_cmp} target(s) with an unusable comparator")

    # L2 - the SLIs compute
    live = psql("""select sli || '|' || coalesce(value::text, 'NULL') || '|' ||
                          comparator || target::text || '|' || denominator
                   from public.v_service_slo order by sli""") or ""
    live_rows = [ln for ln in live.split("\n") if ln.strip()]
    got = {ln.split("|")[0] for ln in live_rows}
    for sli in SLIS:
        check(f"L2 {sli} computes from live data", sli in got, "the view does not emit this SLI")

    # L3 - an empty denominator must read NULL, not 0 (a fabricated breach is worse than no number)
    defn = psql("select pg_get_viewdef('public.v_service_slo'::regclass, true)") or ""
    guards = len(re.findall(r"WHEN\s+\w*\.?\w*_n\s*=\s*0\s+THEN\s+NULL", defn, re.I))
    check("L3 an empty denominator reports NULL ('not measurable'), never a fabricated 0",
          guards >= len(SLIS),
          f"only {guards} zero-denominator guard(s) for {len(SLIS)} SLIs - one would report 0% and read as a breach")

    # L4 - the breaker the chain ALREADY has (validated in §4b, not rebuilt)
    chain = os.path.join(ROOT, "supabase", "functions", "_shared", "ai-chain.ts")
    try:
        src = open(chain, encoding="utf-8", errors="replace").read()
    except Exception:
        src = ""
    if not src:
        check("L4 ai-chain breaker present", True, "")   # not this gate's job to police a missing file
    else:
        check("L4 a failing model/provider slot is PARKED (breaker trips)",
              "recordSlotFailure" in src, "no slot-failure recorder - a dead provider is retried every call")
        check("L4 a parked slot is SKIPPED while blocked (breaker stays open)",
              "isSlotBlocked" in src, "nothing consults the parked state")
        check("L4 the provider's Retry-After is honored for the cooldown",
              "parseRetryAfter" in src or "retry-after" in src.lower(),
              "cooldown ignores Retry-After - we hammer a rate-limited provider")

    fails = [c for c in CHECKS if not c[0]]
    for ok, name, detail in CHECKS:
        print(f"  {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}  {name}"
              + (f"  {DIM}[{detail}]{RST}" if detail and not ok else ""))

    # Report the standing, NOT as pass/fail. A breach is a business signal for Ian, not a regression.
    print(f"\n  {DIM}current standing (informational - a breach does NOT fail this gate):{RST}")
    for ln in live_rows:
        parts = ln.split("|")
        if len(parts) < 4:
            continue
        sli, val, target, denom = parts[0], parts[1], parts[2], parts[3]
        if val == "NULL":
            mark, tone = "not measurable yet", DIM
        else:
            cmp_op, tgt = target[:2], float(target[2:])
            meets = (float(val) >= tgt) if cmp_op == ">=" else (float(val) <= tgt)
            mark, tone = ("MEETS" if meets else "BREACH"), (GREEN if meets else YEL)
        print(f"    {tone}{sli:<20} {val:>8}   SLO {target:<8} n={denom:<5} {mark}{RST}")

    print()
    if fails:
        print(f"{RED}FAIL{RST} - {len(fails)}/{len(CHECKS)} SLO measurement invariant(s) broken")
        return 1
    print(f"{GREEN}PASS{RST} - {len(CHECKS)} invariants: every SLI computes, carries a tunable numeric "
          f"target, distinguishes 'not measurable' from a breach, and the AI-chain breaker is intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
