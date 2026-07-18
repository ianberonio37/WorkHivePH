#!/usr/bin/env python3
"""land_ops_artifacts.py — Operator-Console → Grafana arc (P1, 2026-07-18).

Lands the two FILE-ARTIFACT observability metrics (that founder-console read as JSON)
into public.ops_artifact_metrics so Grafana (Postgres-only datasource) can show them:
  - memento_health.json          → artifact='memento_health'
  - companion_eval_scorecard.json → artifact='companion_eval'

Append-only snapshot per run (the Founder-Ops dashboard reads the latest). Writes via
`docker exec psql` as postgres (bypasses RLS, like the seeders). Idempotent-safe to
re-run (each run adds a fresh snapshot). Wire it into the Stop hook / a cron later so
the Grafana panels stay fresh the way the JSON artifacts did.

Usage:  python tools/land_ops_artifacts.py
"""
from __future__ import annotations
import io
import json
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"


def _q(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def _land(artifact, status, headline, metrics) -> bool:
    sql = (
        "INSERT INTO public.ops_artifact_metrics (artifact, status, headline, metrics) "
        f"VALUES ({_q(artifact)}, {_q(status)}, {_q(headline)}, {_q(json.dumps(metrics))}::jsonb);"
    )
    p = subprocess.run(
        ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-c", sql],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    ok = p.returncode == 0
    print(f"  {'ok ' if ok else 'FAIL'} {artifact}: {headline}")
    if not ok:
        print("     " + (p.stdout + p.stderr).strip()[:200])
    return ok


def land_memento() -> bool:
    f = ROOT / "memento_health.json"
    if not f.exists():
        print("  skip memento_health.json (not present)")
        return True
    d = json.loads(f.read_text(encoding="utf-8"))
    summ = d.get("summary", {}) or {}
    metrics = dict(d.get("metrics", {}) or {})
    # keep the derived precision/honesty blocks too if present (small)
    for k in ("precision", "honesty", "context"):
        if isinstance(d.get(k), dict):
            metrics[k] = d[k]
    return _land("memento_health", summ.get("status"), summ.get("headline"), metrics)


def land_companion() -> bool:
    f = ROOT / "companion_eval_scorecard.json"
    if not f.exists():
        print("  skip companion_eval_scorecard.json (not present)")
        return True
    d = json.loads(f.read_text(encoding="utf-8"))
    dims = d.get("dimensions")
    ndim = len(dims) if isinstance(dims, (dict, list)) else 0
    metrics = {
        "phase": d.get("phase"),
        "axis": d.get("axis"),
        "pass_score": d.get("pass_score"),
        "dimensions": ndim,
        "coverage": d.get("coverage"),
    }
    headline = f"{ndim} eval dimensions · pass≥{d.get('pass_score')}"
    return _land("companion_eval", "registry", headline, metrics)


def _prune(keep_per_artifact: int = 50) -> None:
    """Keep the table bounded when this runs on a schedule: retain the newest N
    snapshots per artifact (panels read `order by captured_at desc limit 1`)."""
    sql = (
        "DELETE FROM public.ops_artifact_metrics o USING ("
        "  SELECT id, row_number() OVER (PARTITION BY artifact ORDER BY captured_at DESC) AS rn"
        "  FROM public.ops_artifact_metrics) r "
        f"WHERE o.id = r.id AND r.rn > {int(keep_per_artifact)};"
    )
    try:
        subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-c", sql],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    except Exception:
        pass


def main() -> int:
    print("Landing operator-console file artifacts -> ops_artifact_metrics")
    ok = land_memento() and land_companion()
    _prune()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
