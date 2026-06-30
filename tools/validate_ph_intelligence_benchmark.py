#!/usr/bin/env python3
"""validate_ph_intelligence_benchmark.py — §13 P-engine: ph-intelligence value-correctness.
================================================================================
ph-intelligence renders the CROSS-HIVE BENCHMARK NETWORK (MTBF/MTTR per equipment
category + anonymized network percentiles), served by the `intelligence-api` edge
fn over data produced by `benchmark-compute`. Prior sweeps marked this cell
"external" (needs many hives + monthly cron). That was an UNTESTED assumption:
`benchmark-compute` is PURE SQL, no AI, deterministic, free, and INVOKABLE LOCALLY
(anon for the cron fan-out; service-role for the single-hive path). There are
exactly 3 local hives — the precise minimum `computeNetwork` needs.

So we prove the value-derivation LOCALLY, deterministically, the same rigor as the
calc/ai-quality oracles — by exercising the REAL edge fn (never a reimplementation)
against a hand-derived fixture, then asserting the numbers:

  Proof A — per-hive MTBF/MTTR (computeForHive, single-hive service-role path):
    seed ONE sentinel hive with a known breakdown sequence → invoke → assert
    hive_benchmarks.{mtbf_days,mttr_hours,failure_count,sample_machines}.

  Proof B — network percentile aggregation (computeNetwork, cron fan-out path):
    direct-insert 3 sentinel hive_benchmarks in a category extractCategory() can
    NEVER produce ("VX Test Category" → zero real collision) → invoke the fan-out
    → assert network_benchmarks.{avg,p25,p75,sample_hives}.

Both are isolated (sentinel hive_ids / sentinel category), deterministic, and
cleaned up. Exit 0 = both oracles matched; 1 = a value mismatch; 2 = edge down.
"""
from __future__ import annotations
import io
import json
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB_CONTAINER = "supabase_db_workhive"
EDGE = "http://127.0.0.1:54321/functions/v1"
ANON = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"
SERVICE_ROLE = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
                "eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0."
                "EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU")

WORKER = "__phbench__"
HA  = "00000000-0000-4000-8000-0000000000a1"   # Proof A sentinel hive
HB  = ["00000000-0000-4000-8000-0000000000b1",
       "00000000-0000-4000-8000-0000000000b2",
       "00000000-0000-4000-8000-0000000000b3"]  # Proof B sentinel hives
ZCAT = "VX Test Category"                        # never produced by extractCategory()

GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def psql(sql: str) -> list[list[str]]:
    out = subprocess.run(
        ["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
         "-t", "-A", "-F", "|", "-c", sql], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"psql failed: {out.stderr.strip() or out.stdout.strip()}")
    return [ln.split("|") for ln in out.stdout.splitlines() if ln.strip()]


def scalar(sql: str):
    r = psql(sql)
    return r[0][0] if r and r[0] else None


def edge(path: str, body: dict, bearer: str):
    data = json.dumps(body).encode()
    req = urllib.request.Request(f"{EDGE}/{path}", data=data, method="POST",
                                 headers={"Content-Type": "application/json",
                                          "Authorization": f"Bearer {bearer}", "apikey": ANON})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception:
        return None, ""


def cleanup():
    """Remove every sentinel artifact. Children (logbook, hive_benchmarks) BEFORE the
    hives rows — logbook's hive FK is NO-ACTION. ZCAT network row too."""
    hives = "','".join([HA] + HB)
    for sql in (
        f"DELETE FROM logbook WHERE worker_name='{WORKER}';",
        f"DELETE FROM hive_benchmarks WHERE hive_id IN ('{hives}') OR equipment_category='{ZCAT}';",
        f"DELETE FROM network_benchmarks WHERE equipment_category='{ZCAT}';",
        f"DELETE FROM hives WHERE created_by='{WORKER}';",
    ):
        try:
            psql(sql)
        except Exception:
            pass


def setup_hives():
    """Sentinel hives (FK target for logbook + hive_benchmarks). v_hives_truth = SELECT FROM
    hives, so these join the fan-out — HB1-3 carry no logbook (skipped); HA is cleared before
    Proof B so it cannot contribute to any real category's network aggregate."""
    psql(f"""INSERT INTO hives (id, name, invite_code, created_by) VALUES
             ('{HA}','VX PHBench A','VXBN00','{WORKER}'),
             ('{HB[0]}','VX PHBench B1','VXBN01','{WORKER}'),
             ('{HB[1]}','VX PHBench B2','VXBN02','{WORKER}'),
             ('{HB[2]}','VX PHBench B3','VXBN03','{WORKER}')
             ON CONFLICT (id) DO NOTHING;""")


def approx(a, b, tol=0.05):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def main() -> int:
    print(f"{BOLD}\nPH-INTELLIGENCE BENCHMARK — value-correctness (live edge, deterministic){RESET}")
    print("=" * 74)
    # reachability
    st, _ = edge("benchmark-compute", {}, ANON)
    if st is None:
        print(f"{YEL}SKIP (exit 2){RESET}: local edge unreachable — start it to validate.")
        return 2

    cleanup()
    setup_hives()
    fails: list[str] = []
    results: dict = {}
    try:
        # ── Proof A: per-hive MTBF/MTTR via the REAL computeForHive ──────────
        # 4 breakdowns @ −60/−50/−30/−0 d → intervals 10,20,30 → MTBF mean 20.0
        # downtimes 4,6,8,2 → MTTR mean 5.0 · failure_count 4 · 1 machine
        psql(f"""INSERT INTO logbook (id, worker_name, hive_id, machine, category,
                 maintenance_type, downtime_hours, status, problem, action, date, created_at) VALUES
                 ('__phb_a1','{WORKER}','{HA}','VX-PUMP-A','Breakdown','Breakdown / Corrective',4,'Closed','phb A1','x', now()-interval '60 days', now()-interval '60 days'),
                 ('__phb_a2','{WORKER}','{HA}','VX-PUMP-A','Breakdown','Breakdown / Corrective',6,'Closed','phb A2','x', now()-interval '50 days', now()-interval '50 days'),
                 ('__phb_a3','{WORKER}','{HA}','VX-PUMP-A','Breakdown','Breakdown / Corrective',8,'Closed','phb A3','x', now()-interval '30 days', now()-interval '30 days'),
                 ('__phb_a4','{WORKER}','{HA}','VX-PUMP-A','Breakdown','Breakdown / Corrective',2,'Closed','phb A4','x', now(), now());""")
        sta, ba = edge("benchmark-compute", {"hive_id": HA}, SERVICE_ROLE)
        row = psql(f"""SELECT equipment_category, mtbf_days, mttr_hours, failure_count, sample_machines
                       FROM hive_benchmarks WHERE hive_id='{HA}';""")
        if not row:
            fails.append(f"Proof A: benchmark-compute produced no hive_benchmarks row (HTTP {sta}: {ba[:80]})")
        else:
            cat, mtbf, mttr, fc, sm = row[0]
            oracle = {"category": "Centrifugal Pump", "mtbf": 20.0, "mttr": 5.0, "fc": 4, "sm": 1}
            okA = (cat == oracle["category"] and approx(mtbf, oracle["mtbf"]) and approx(mttr, oracle["mttr"])
                   and int(fc) == oracle["fc"] and int(sm) == oracle["sm"])
            results["proofA"] = {"category": cat, "mtbf_days": mtbf, "mttr_hours": mttr,
                                 "failure_count": fc, "sample_machines": sm, "oracle": oracle, "ok": okA}
            mark = f"{GREEN}✓{RESET}" if okA else f"{RED}✗{RESET}"
            print(f"  {mark} Proof A (per-hive MTBF/MTTR): cat={cat} mtbf={mtbf}(=20.0) "
                  f"mttr={mttr}(=5.0) count={fc}(=4) machines={sm}(=1)")
            if not okA:
                fails.append(f"Proof A mismatch: {results['proofA']}")

        # Clear HA entirely so the Proof-B fan-out (which recomputes ALL hives,
        # HA included) cannot add HA's "Centrifugal Pump" benchmark to any real
        # network aggregate — Proof B's network must derive ONLY from the ZCAT trio.
        psql(f"DELETE FROM logbook WHERE hive_id='{HA}'; DELETE FROM hive_benchmarks WHERE hive_id='{HA}';")

        # ── Proof B: network avg/p25/p75 via the REAL computeNetwork ─────────
        # 3 hives, mtbf 10/20/30 in an isolated category → avg 20.0, p25 10, p75 30
        for h, v in zip(HB, (10, 20, 30)):
            psql(f"""INSERT INTO hive_benchmarks (hive_id, equipment_category, mtbf_days, mttr_hours,
                     failure_count, sample_machines, period_days, computed_at)
                     VALUES ('{h}','{ZCAT}',{v},5,3,1,90, now());""")
        stb, bb = edge("benchmark-compute", {}, ANON)   # cron fan-out → computeNetwork
        nrow = psql(f"""SELECT avg_mtbf_days, p25_mtbf_days, p75_mtbf_days, sample_hives
                        FROM network_benchmarks WHERE equipment_category='{ZCAT}';""")
        if not nrow:
            fails.append(f"Proof B: computeNetwork published no network row (HTTP {stb}: {bb[:80]})")
        else:
            avg, p25, p75, sh = nrow[0]
            oracleB = {"avg": 20.0, "p25": 10.0, "p75": 30.0, "sample_hives": 3}
            okB = (approx(avg, 20.0) and approx(p25, 10.0) and approx(p75, 30.0) and int(sh) == 3)
            results["proofB"] = {"avg_mtbf_days": avg, "p25_mtbf_days": p25, "p75_mtbf_days": p75,
                                 "sample_hives": sh, "oracle": oracleB, "ok": okB}
            mark = f"{GREEN}✓{RESET}" if okB else f"{RED}✗{RESET}"
            print(f"  {mark} Proof B (network percentiles): avg={avg}(=20.0) p25={p25}(=10.0) "
                  f"p75={p75}(=30.0) hives={sh}(=3)")
            if not okB:
                fails.append(f"Proof B mismatch: {results['proofB']}")
    finally:
        cleanup()

    passed = not fails
    (ROOT / "ph_intelligence_benchmark_proof.json").write_text(json.dumps({
        "tool": "tools/validate_ph_intelligence_benchmark.py",
        "subject": "ph-intelligence cross-hive benchmark network (benchmark-compute + intelligence-api)",
        "method": "live local edge fn vs hand-derived deterministic oracle; sentinel-isolated; cleaned up",
        "results": results, "result": "PASS" if passed else "FAIL",
    }, indent=2), encoding="utf-8")

    print("-" * 74)
    if passed:
        print(f"{GREEN}{BOLD}  PH-INTELLIGENCE BENCHMARK: PASS{RESET} — value-derivation proven LOCALLY "
              f"(per-hive MTBF + network percentiles), deterministic, via the real edge fn.")
        return 0
    print(f"{RED}{BOLD}  PH-INTELLIGENCE BENCHMARK: FAIL{RESET}")
    for f in fails:
        print(f"      • {f}")
    return 1


def validate_ph_intelligence_benchmark(blind: bool = False) -> bool:
    """Importable entry for the value-validator registry (tools/mine_lineage_map.py).
    Returns True iff BOTH oracles pass live this run; edge down → False (honest, not credited).
    `blind` accepted for signature parity with the other value validators."""
    return main() == 0


if __name__ == "__main__":
    sys.exit(main())
