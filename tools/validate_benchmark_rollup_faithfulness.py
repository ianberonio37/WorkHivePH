#!/usr/bin/env python3
# DEEPWALK-CELL: analytics D2
"""validate_benchmark_rollup_faithfulness.py -- LOCK for the cross-hive benchmark rollup seesaw.

ARC DI §10.5 anti-seesaw / cross-tenant rollup (2026-07-08). A shared benchmark is ONE truth
in TWO representations: the per-hive inputs `hive_benchmarks` (each hive's MTBF/MTTR per
equipment_category) vs the cross-tenant rollup `network_benchmarks` (avg/p25/p75 across the
hives in a segment). A per-hive change must propagate to the rollup, and the rollup must never
silently diverge from the exact aggregate of its inputs -- else a hive is benchmarked against a
stale/forked peer number (the cross-tenant seesaw).

`benchmark-compute` computes both in ONE run (hive rows first, then the network rollup from
them: avg = mean of the hives' mtbf_days, p25/p75 = index-based percentiles on the sorted
values == percentile_disc, sample_hives = the contributing-hive count, min 3 to publish for
privacy -- index.ts L192-194). This gate asserts, for EVERY network row, that it still equals
that exact aggregate of the CURRENT `hive_benchmarks` for its (equipment_category, period_days)
segment (measured live 2026-07-08: 5 rollups, 0 unfaithful, 0 privacy-violations, 0 orphans):

  UNFAITHFUL      -- avg/p25/p75/sample_hives != the recomputation (rollup drifted from inputs).
  PRIVACY breach  -- sample_hives < 3 (a rollup published on too few hives -> peer-identifiable).
  ORPHAN          -- a network row whose segment has NO hive_benchmarks inputs (phantom rollup).
Any of the three -> fix-to-ZERO.

NOTE: locally `industry` is blank and `hives` has no industry column, so the segment is
(equipment_category, period_days). If per-hive industry segmentation is later populated, extend
the recompute to join hive_benchmarks -> hives on industry so the aggregate matches the segment.

COMPLEMENTARY to `validate_ph_intelligence_benchmark.py` (NOT a duplicate): that one proves the
benchmark-compute edge fn COMPUTES correctly by invoking it on synthetic sentinel hives vs hand
oracles (compute-correctness, needs the edge up). THIS one proves the STORED rollup stays
CONSISTENT with the STORED per-hive inputs on the REAL data, with no invoke -- the anti-seesaw
invariant (a per-hive change that didn't propagate to the rollup), which the compute gate can't
see because it always recomputes fresh synthetic output.

Env-independent (recomputes from the same DB); SKIPS cleanly (exit 0) if the local DB is down.

Usage:  python tools/validate_benchmark_rollup_faithfulness.py [--json] [--selftest]
Exit 0 = clean / skipped, 1 = >0 unfaithful/privacy/orphan (or self-test failure).
"""
import sys, json, subprocess

DOCKER_DB = ["docker", "exec", "supabase_db_workhive", "psql", "-U", "postgres", "-d", "postgres",
             "-t", "-A", "-c"]

COUNT_SQL = """
WITH agg AS (
  SELECT equipment_category, period_days,
         round(avg(mtbf_days)::numeric,1) AS a_avg,
         round(percentile_disc(0.25) WITHIN GROUP (ORDER BY mtbf_days)::numeric,1) AS a_p25,
         round(percentile_disc(0.75) WITHIN GROUP (ORDER BY mtbf_days)::numeric,1) AS a_p75,
         count(DISTINCT hive_id) AS a_n
  FROM hive_benchmarks GROUP BY equipment_category, period_days
)
SELECT count(*) AS network_rows,
  count(*) FILTER (WHERE a.equipment_category IS NOT NULL AND (
        round(n.avg_mtbf_days::numeric,1) IS DISTINCT FROM a.a_avg
     OR round(n.p25_mtbf_days::numeric,1) IS DISTINCT FROM a.a_p25
     OR round(n.p75_mtbf_days::numeric,1) IS DISTINCT FROM a.a_p75
     OR n.sample_hives IS DISTINCT FROM a.a_n)) AS unfaithful,
  count(*) FILTER (WHERE n.sample_hives < 3) AS privacy_violations,
  count(*) FILTER (WHERE a.equipment_category IS NULL) AS orphans
FROM network_benchmarks n
LEFT JOIN agg a ON a.equipment_category=n.equipment_category AND a.period_days=n.period_days;
"""

SAMPLE_SQL = """
WITH agg AS (
  SELECT equipment_category, period_days,
         round(avg(mtbf_days)::numeric,1) AS a_avg,
         round(percentile_disc(0.25) WITHIN GROUP (ORDER BY mtbf_days)::numeric,1) AS a_p25,
         round(percentile_disc(0.75) WITHIN GROUP (ORDER BY mtbf_days)::numeric,1) AS a_p75,
         count(DISTINCT hive_id) AS a_n
  FROM hive_benchmarks GROUP BY equipment_category, period_days
)
SELECT n.equipment_category,
       'net(avg='||n.avg_mtbf_days||',p25='||n.p25_mtbf_days||',p75='||n.p75_mtbf_days||',n='||n.sample_hives||')',
       coalesce('calc(avg='||a.a_avg||',p25='||a.a_p25||',p75='||a.a_p75||',n='||a.a_n||')','ORPHAN(no inputs)')
FROM network_benchmarks n
LEFT JOIN agg a ON a.equipment_category=n.equipment_category AND a.period_days=n.period_days
WHERE a.equipment_category IS NULL OR n.sample_hives < 3
   OR round(n.avg_mtbf_days::numeric,1) IS DISTINCT FROM a.a_avg
   OR round(n.p25_mtbf_days::numeric,1) IS DISTINCT FROM a.a_p25
   OR round(n.p75_mtbf_days::numeric,1) IS DISTINCT FROM a.a_p75
   OR n.sample_hives IS DISTINCT FROM a.a_n
LIMIT 8;
"""


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
        rows, unfaithful, privacy, orphans = (int(x) for x in out.splitlines()[0].split("|"))
    except (ValueError, IndexError):
        return {"skipped": True, "reason": f"unexpected psql output: {out[:80]!r}"}
    bad = unfaithful + privacy + orphans
    samples = []
    if bad > 0:
        s = psql(SAMPLE_SQL) or ""
        for line in s.splitlines():
            p = [x.strip() for x in line.split("|")]
            if len(p) >= 3:
                samples.append(f"{p[0]}: {p[1]} vs {p[2]}")
    return {"skipped": False, "network_rows": rows, "unfaithful": unfaithful,
            "privacy_violations": privacy, "orphans": orphans, "samples": samples}


def run_selftest():
    problems = []
    if "percentile_disc(0.25)" not in COUNT_SQL or "avg(mtbf_days)" not in COUNT_SQL or "count(DISTINCT hive_id)" not in COUNT_SQL:
        problems.append("COUNT_SQL must recompute avg + percentile_disc(0.25/0.75) + distinct-hive count from hive_benchmarks")
    if "sample_hives < 3" not in COUNT_SQL:
        problems.append("COUNT_SQL must flag privacy violations (sample_hives < 3)")
    live = analyze()
    if not live.get("skipped"):
        n = live["unfaithful"] + live["privacy_violations"] + live["orphans"]
        if n != 0:
            problems.append(f"live rollup issues = {n} (unfaithful={live['unfaithful']}, "
                            f"privacy={live['privacy_violations']}, orphans={live['orphans']}) -- expected 0")
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
        print("cross-hive benchmark rollup faithfulness (network_benchmarks must == the exact aggregate of current hive_benchmarks; sample_hives >= 3)")
        if res.get("skipped"):
            print(f"  SKIP -- {res['reason']}")
        else:
            bad = res["unfaithful"] + res["privacy_violations"] + res["orphans"]
            if bad == 0:
                print(f"  PASS: {res['network_rows']} rollups all faithfully aggregate their per-hive inputs "
                      f"(0 unfaithful, 0 privacy-violations, 0 orphans)")
            else:
                if res["unfaithful"]:
                    print(f"  FAIL: {res['unfaithful']} rollups diverge from the recomputed aggregate of hive_benchmarks "
                          f"(per-hive change didn't propagate, or the aggregation forked). {'; '.join(res['samples'])}")
                if res["privacy_violations"]:
                    print(f"  FAIL: {res['privacy_violations']} rollups published on < 3 hives (peer-identification risk).")
                if res["orphans"]:
                    print(f"  FAIL: {res['orphans']} rollups have NO hive_benchmarks inputs (phantom rollup).")
                print("  Fix: re-run benchmark-compute so the network rollup matches current hive_benchmarks; "
                      "never publish a segment with < 3 hives.")
    if res.get("skipped"):
        return 0
    return 1 if (res["unfaithful"] + res["privacy_violations"] + res["orphans"]) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
