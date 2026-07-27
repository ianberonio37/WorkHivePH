#!/usr/bin/env python3
"""
validate_corrective_definition_parity.py — LG2: one derived semantic, one definition.

THE CLASS: a derived semantic ("corrective", "open", a downtime window) that is re-expressed
independently by each consumer will drift the moment the vocabulary grows, and it drifts SILENTLY
because every consumer still returns a plausible number.

"Corrective" is defined THREE ways on this platform, measured 2026-07-12 and re-measured 2026-07-28:

  1. v_logbook_truth.is_corrective    -> a REGEX:  maintenance_type ~* '(corrective|breakdown)'
  2. v_asset_truth.last_failure_at and the five analytics RPCs (get_mtbf / get_mttr /
     failure_frequency / downtime_pareto / repeat_failures) -> the EXACT string
     'Breakdown / Corrective'
  3. trigger-ml-retrain -> ILIKE '%Corrective%' / '%Breakdown%'

They agree today only because every corrective row happens to use the exact string: 1,146 = 1,146 =
1,146. That is luck of vocabulary, not a guarantee. Add one entry typed 'Emergency Breakdown' and
is_corrective counts it while last_failure_at and EVERY MTBF/MTTR/failure-frequency KPI silently
miss it — the asset looks more reliable than it is, which is the direction that gets someone hurt.

WHY THIS GATE RATHER THAN CANONICALISING NOW: collapsing the three into one definition means
editing a view, five RPCs and an edge function at once, and every one of them feeds a KPI a plant
would act on. The disposition that ends a drift class without that blast radius is the middle tier:
allow the duplicate representations, but make divergence IMPOSSIBLE-THEN-DETECTABLE. This asserts
the three populations are identical, as a fix-to-ZERO ratchet, so the drift is caught at CI on the
first divergent row instead of being discovered in a wrong MTBF months later.

Live-tier; SKIPS cleanly (exit 0) when the local DB is down. Self-test: --selftest.
"""
from __future__ import annotations
import io, json, subprocess, sys

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c"]

# Rows each definition claims, and the symmetric difference between them.
PARITY_SQL = """
WITH regex_set AS (
  SELECT id FROM public.logbook WHERE maintenance_type ~* '(corrective|breakdown)'
), exact_set AS (
  SELECT id FROM public.logbook WHERE maintenance_type = 'Breakdown / Corrective'
), ilike_set AS (
  SELECT id FROM public.logbook
   WHERE maintenance_type ILIKE '%corrective%' OR maintenance_type ILIKE '%breakdown%'
)
SELECT
  (SELECT count(*) FROM regex_set),
  (SELECT count(*) FROM exact_set),
  (SELECT count(*) FROM ilike_set),
  (SELECT count(*) FROM ((SELECT id FROM regex_set EXCEPT SELECT id FROM exact_set)
                          UNION ALL
                         (SELECT id FROM exact_set EXCEPT SELECT id FROM regex_set)) d),
  (SELECT count(*) FROM ((SELECT id FROM ilike_set EXCEPT SELECT id FROM exact_set)
                          UNION ALL
                         (SELECT id FROM exact_set EXCEPT SELECT id FROM ilike_set)) d);
"""

# The offending vocabulary, so a failure names what to fix rather than just counting.
OFFENDERS_SQL = """
SELECT DISTINCT maintenance_type
FROM public.logbook
WHERE (maintenance_type ~* '(corrective|breakdown)' OR maintenance_type ILIKE '%corrective%'
       OR maintenance_type ILIKE '%breakdown%')
  AND maintenance_type <> 'Breakdown / Corrective'
LIMIT 8;
"""


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=45)
        return None if r.returncode != 0 else (r.stdout or "").strip()
    except Exception:
        return None


def analyze():
    out = psql(PARITY_SQL)
    if out is None:
        return {"skipped": True, "reason": "local DB unreachable (docker supabase_db_workhive)"}
    parts = (out.splitlines()[0] if out else "").split("|")
    if len(parts) < 5:
        return {"skipped": True, "reason": f"unexpected psql output: {out[:80]!r}"}
    try:
        rx, ex, il, d_rx, d_il = (int(x) for x in parts[:5])
    except ValueError:
        return {"skipped": True, "reason": f"unparseable counts: {parts[:5]!r}"}
    offenders = []
    if d_rx or d_il:
        offenders = [ln.strip() for ln in (psql(OFFENDERS_SQL) or "").splitlines() if ln.strip()]
    return {"skipped": False, "regex": rx, "exact": ex, "ilike": il,
            "divergent_regex_vs_exact": d_rx, "divergent_ilike_vs_exact": d_il,
            "offending_vocabulary": offenders}


def run_selftest():
    problems = []
    for frag in ("EXCEPT", "~*", "ILIKE", "Breakdown / Corrective"):
        if frag not in PARITY_SQL:
            problems.append(f"PARITY_SQL must exercise {frag!r} — otherwise it is not comparing the "
                            f"three real definitions and would false-PASS")
    live = analyze()
    if not live.get("skipped"):
        if live["divergent_regex_vs_exact"] or live["divergent_ilike_vs_exact"]:
            problems.append("live divergence is non-zero — the fix-to-zero ratchet is breached")
    return problems


def main():
    as_json = "--json" in sys.argv
    if "--selftest" in sys.argv:
        probs = run_selftest()
        print(json.dumps({"selftest_problems": probs}, indent=2) if as_json
              else ("SELFTEST PASS" if not probs else "SELFTEST FAIL:\n  " + "\n  ".join(probs)))
        return 1 if probs else 0

    res = analyze()
    if as_json:
        print(json.dumps(res, indent=2))
        return 0 if (res.get("skipped") or not (res["divergent_regex_vs_exact"] or res["divergent_ilike_vs_exact"])) else 1

    print("LG2 corrective-definition parity (one derived semantic must not have three definitions)")
    if res.get("skipped"):
        print(f"  SKIP -- {res['reason']}")
        return 0
    total_div = res["divergent_regex_vs_exact"] + res["divergent_ilike_vs_exact"]
    if total_div == 0:
        print(f"  PASS: all three definitions select the same {res['exact']} rows "
              f"(regex {res['regex']} / exact {res['exact']} / ilike {res['ilike']})")
        return 0
    print(f"  FAIL: {total_div} rows are claimed by one definition of 'corrective' and not another "
          f"(regex {res['regex']} / exact {res['exact']} / ilike {res['ilike']}).")
    if res["offending_vocabulary"]:
        print(f"  Offending maintenance_type values: {', '.join(res['offending_vocabulary'])}")
    print("  Why it matters: v_logbook_truth.is_corrective would count these, while "
          "v_asset_truth.last_failure_at and every MTBF / MTTR / failure-frequency RPC would miss "
          "them - the asset reads as MORE reliable than it is.")
    print("  Fix: use the canonical 'Breakdown / Corrective' value, or canonicalise all consumers "
          "onto one definition in a single change.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
