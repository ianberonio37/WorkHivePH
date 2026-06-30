#!/usr/bin/env python3
"""dataloss_monitor.py - Arc S (Resilience/DR) R-lens: silent row-deletion detector.
================================================================================
RTO_RPO_DECLARATION.md leans on Supabase PITR (7-day window) for data recovery, but
NOTHING detects a silent loss (a rogue DELETE, a bad migration, a broken backfill)
INSIDE that window. By the time a user reports "my data is gone" the PITR window may
have expired = unrecoverable. This tool snapshots per-table row counts each run and
alerts when a critical table drops by more than a threshold vs the prior snapshot —
so a deletion is caught in hours, while PITR can still restore it.

  --snapshot   record current per-table counts to dataloss_snapshots.json (history-capped)
  (default)    compare current counts to the LAST snapshot; FAIL on a > -DROP_PCT drop;
               first run records a baseline and PASSes (nothing to compare yet).

Exit 0 = no anomalous drop (or baseline taken); 1 = a critical table dropped sharply.
Stdlib only; reads no secrets; LOCAL docker Supabase; $0.
"""
from __future__ import annotations
import io, json, subprocess, sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "dataloss_snapshots.json"
DB = "supabase_db_workhive"
DROP_PCT = 20.0          # a critical table losing >20% of its rows between runs is suspicious
MIN_ROWS = 20            # ignore tiny tables (noise); a drop from 3->1 isn't a data-loss event
HISTORY = 30             # keep the last N snapshots
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

CRITICAL_TABLES = [
    "worker_profiles", "hive_members", "logbook", "pm_completions",
    "inventory_items", "inventory_transactions", "assets", "asset_nodes",
    "projects", "project_items", "hive_audit_log",
]


def _psql(sql: str, timeout: int = 30):
    return subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                           "-tA", "-c", sql], capture_output=True, text=True, timeout=timeout)


def _db_up() -> bool:
    try:
        r = _psql("select 1;", timeout=10)
        return r.returncode == 0 and r.stdout.strip().startswith("1")
    except Exception:
        return False


def _counts() -> dict[str, int]:
    out = {}
    r = _psql("select table_name from information_schema.tables where table_schema='public';")
    present = set(x.strip() for x in r.stdout.splitlines() if x.strip())
    for t in CRITICAL_TABLES:
        if t not in present:
            continue
        c = _psql(f'select count(*) from public."{t}";')
        try:
            out[t] = int(c.stdout.strip())
        except ValueError:
            pass
    return out


def _load() -> list[dict]:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def main() -> int:
    print(f"{B}Arc S - silent data-loss monitor (R-lens){X}")
    print("=" * 56)
    if not _db_up():
        print(f"  {Y}SKIP{X} local Supabase DB not reachable — nothing to snapshot.")
        return 0

    now = _counts()
    hist = _load()

    if "--snapshot" in sys.argv or not hist:
        # NOTE: timestamp comes from the DB, not Python (deterministic, no host clock dep).
        ts = _psql("select to_char(now() at time zone 'UTC','YYYY-MM-DD\"T\"HH24:MI:SS');").stdout.strip()
        hist.append({"at": ts, "counts": now})
        STORE.write_text(json.dumps(hist[-HISTORY:], indent=2), encoding="utf-8")
        print(f"  {G}snapshot{X} recorded {len(now)} tables ({sum(now.values())} rows) at {ts}")
        if "--snapshot" not in sys.argv:
            print(f"  {Y}(baseline — no prior snapshot to compare; PASS){X}")
        return 0

    prev = hist[-1]["counts"]
    alerts = []
    for t, cur in now.items():
        was = prev.get(t)
        if was is None or was < MIN_ROWS:
            continue
        if cur < was * (1 - DROP_PCT / 100.0):
            drop = 100.0 * (was - cur) / was
            alerts.append((t, was, cur, drop))

    for t, was, cur, drop in alerts:
        print(f"  {R}DROP{X} {t}: {was} -> {cur}  (-{drop:.0f}%)  ← restore via PITR before the window expires")
    for t in sorted(now):
        if not any(a[0] == t for a in alerts):
            print(f"  {G}ok{X}   {t}: {prev.get(t,'?')} -> {now[t]}")

    if alerts:
        print(f"\n{R}{B}  DATA-LOSS MONITOR: ALERT{X} - {len(alerts)} critical table(s) dropped sharply.")
        return 1
    print(f"\n{G}{B}  DATA-LOSS MONITOR: PASS{X} - no anomalous row drop since the last snapshot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
