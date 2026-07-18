#!/usr/bin/env python3
# DEEPWALK-CELL: analytics D2
# DEEPWALK-CELL: analytics-report D2
"""validate_reliability_kpi_faithfulness.py -- LOCK for the reliability-KPI temporal seesaw.

ARC DI §10.5 anti-seesaw (2026-07-08). Reliability KPIs (MTBF/risk) are ONE truth in TWO
representations: the LIVE canonical engine `get_mtbf_by_machine` (computed from logbook on
read) vs the PRECOMPUTED cache `asset_risk_scores.mtbf_days` (written by the batch-risk-scoring
cron + the on-demand "Recompute now" path, stamped `generated_at`). A precomputed cache lags
its source between refreshes -> a *temporal/staleness* seesaw.

The dangerous form of this seesaw is a METHODOLOGY FORK: the cache silently computing MTBF a
DIFFERENT way than the live path, so the two diverge even with no staleness. That is NOT the
case here -- batch-risk-scoring pulls mtbf from the SAME `get_mtbf_by_machine` RPC (index.ts
~L323), so the cache is a time-stamped SNAPSHOT of the canonical engine. The only legitimate
divergence is BOUNDED STALENESS: a logbook event written AFTER a score's `generated_at` that
the next cron run will fold in.

This gate encodes exactly that invariant (measured live 2026-07-08: 90 machines joined across
3 hives, 1 divergence, 0 unexplained):
  For every machine, compare the newest cached `mtbf_days` to the LIVE `get_mtbf_by_machine`.
  A divergence is ALLOWED only if the machine has a logbook event with `created_at >
  generated_at` (i.e. the source changed after the snapshot -> the cache is legitimately
  pending the next refresh). A divergence with NO newer source event is an UNEXPLAINED
  divergence == a real methodology/computation fork == the seesaw. -> fix-to-ZERO.

Staleness-explained divergences are reported (bounded lag, monitored separately by
validate_cron_health, which locks that the refresh cron actually runs). Env-independent
(reads the same DB the live path does); SKIPS cleanly (exit 0) if the local DB is down.

Usage:  python tools/validate_reliability_kpi_faithfulness.py [--json] [--selftest]
Exit 0 = clean / skipped, 1 = >0 unexplained divergences (or self-test failure).
"""
import sys, json, subprocess, os

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c"]

# Newest cached mtbf per (hive, machine) vs the LIVE canonical RPC; a divergence counts as
# UNEXPLAINED only when NO logbook event postdates the score (so staleness can't excuse it).
COUNT_SQL = """
WITH hh AS (SELECT DISTINCT hive_id FROM asset_risk_scores WHERE hive_id IS NOT NULL),
cached AS (
  SELECT DISTINCT ON (hive_id, asset_name) hive_id, asset_name, mtbf_days, generated_at
  FROM asset_risk_scores WHERE mtbf_days IS NOT NULL
  ORDER BY hive_id, asset_name, generated_at DESC
),
live AS (
  SELECT h.hive_id, m.machine, m.mtbf_days
  FROM hh h CROSS JOIN LATERAL get_mtbf_by_machine(h.hive_id, NULL, 365) m
)
SELECT count(*) AS joined,
  count(*) FILTER (WHERE round(l.mtbf_days::numeric,0) <> round(c.mtbf_days::numeric,0)) AS total_divergence,
  count(*) FILTER (WHERE round(l.mtbf_days::numeric,0) <> round(c.mtbf_days::numeric,0)
        AND NOT EXISTS (SELECT 1 FROM logbook lg
                        WHERE lower(lg.machine)=lower(c.asset_name)
                          AND lg.hive_id=c.hive_id AND lg.created_at > c.generated_at)) AS unexplained
FROM live l JOIN cached c ON c.hive_id=l.hive_id AND lower(c.asset_name)=lower(l.machine);
"""

SAMPLE_SQL = """
WITH hh AS (SELECT DISTINCT hive_id FROM asset_risk_scores WHERE hive_id IS NOT NULL),
cached AS (
  SELECT DISTINCT ON (hive_id, asset_name) hive_id, asset_name, mtbf_days, generated_at
  FROM asset_risk_scores WHERE mtbf_days IS NOT NULL
  ORDER BY hive_id, asset_name, generated_at DESC
),
live AS (
  SELECT h.hive_id, m.machine, m.mtbf_days
  FROM hh h CROSS JOIN LATERAL get_mtbf_by_machine(h.hive_id, NULL, 365) m
)
SELECT c.asset_name, l.mtbf_days AS live, c.mtbf_days AS cached
FROM live l JOIN cached c ON c.hive_id=l.hive_id AND lower(c.asset_name)=lower(l.machine)
WHERE round(l.mtbf_days::numeric,0) <> round(c.mtbf_days::numeric,0)
  AND NOT EXISTS (SELECT 1 FROM logbook lg WHERE lower(lg.machine)=lower(c.asset_name)
                  AND lg.hive_id=c.hive_id AND lg.created_at > c.generated_at)
LIMIT 8;
"""

# Structural methodology-unity guard: the cache MUST source mtbf from the canonical RPC, not a
# re-implemented formula, or the "cache is a snapshot of the same engine" premise breaks.
FUNC = os.path.join(os.path.dirname(__file__), "..", "supabase", "functions",
                    "batch-risk-scoring", "index.ts")


def psql(sql):
    try:
        r = subprocess.run(DOCKER_DB + [sql], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        if r.returncode != 0:
            return None
        return (r.stdout or "").strip()
    except Exception:
        return None


def analyze():
    out = psql(COUNT_SQL)
    if out is None:
        return {"skipped": True, "reason": "local DB unreachable (docker supabase_db_workhive)"}
    try:
        joined, total_div, unexplained = (int(x) for x in out.splitlines()[0].split("|"))
    except (ValueError, IndexError):
        return {"skipped": True, "reason": f"unexpected psql output: {out[:80]!r}"}
    samples = []
    if unexplained > 0:
        s = psql(SAMPLE_SQL) or ""
        for line in s.splitlines():
            p = [x.strip() for x in line.split("|")]
            if len(p) >= 3:
                samples.append(f"{p[0]} live={p[1]} cached={p[2]}")
    return {"skipped": False, "joined": joined, "stale_pending": total_div - unexplained,
            "unexplained": unexplained, "samples": samples}


def _func_sources_canonical_rpc():
    try:
        with open(os.path.abspath(FUNC), encoding="utf-8") as f:
            return "get_mtbf_by_machine" in f.read()
    except OSError:
        return None  # can't read -> don't assert (avoid a false structural failure)


def run_selftest():
    problems = []
    if "get_mtbf_by_machine" not in COUNT_SQL or "created_at > c.generated_at" not in COUNT_SQL:
        problems.append("COUNT_SQL must compare cached mtbf to the live RPC and excuse only post-generated_at staleness")
    src = _func_sources_canonical_rpc()
    if src is False:
        problems.append("batch-risk-scoring no longer references get_mtbf_by_machine -- methodology-unity broken (cache may fork from the live engine)")
    live = analyze()
    if not live.get("skipped") and live.get("unexplained", 0) != 0:
        problems.append(f"live unexplained divergence is {live['unexplained']} (expected 0) -- reliability-KPI seesaw breached")
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
    else:
        print("reliability-KPI faithfulness (precomputed asset_risk_scores.mtbf_days must mirror the live get_mtbf_by_machine; divergence allowed ONLY as bounded post-generated_at staleness)")
        if res.get("skipped"):
            print(f"  SKIP -- {res['reason']}")
        elif res["unexplained"] == 0:
            print(f"  PASS: 0 unexplained divergences across {res['joined']} machines "
                  f"({res['stale_pending']} bounded-stale, pending the next refresh cron -- monitored by cron-health)")
        else:
            print(f"  FAIL: {res['unexplained']} machines whose cached mtbf_days diverges from the live engine "
                  f"with NO newer logbook event (methodology fork / stale-beyond-source). Top: {', '.join(res['samples'])}")
            print("  Fix: ensure batch-risk-scoring sources mtbf from get_mtbf_by_machine (no re-implemented formula); "
                  "re-run the scoring cron / Recompute-now to refresh asset_risk_scores.")
    if res.get("skipped"):
        return 0
    return 1 if res["unexplained"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
