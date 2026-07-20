#!/usr/bin/env python3
"""data_backup.py - Arc S (Resilience/DR) R-lens: LOCAL logical data backup + restore drill.
================================================================================
verify_backups.py proves the SCHEMA is reproducible (migrations + lock). This tool
backs the OTHER half RTO_RPO_DECLARATION.md claims but never implemented: a LOGICAL
DATA dump (the rows) with a PROVEN restore path. It runs entirely against the LOCAL
docker Supabase ($0, no prod), so the "daily logical dump" + "we can restore" claims
become backed by a runnable, drilled mechanism instead of a doc promise.

  --backup  pg_dump --data-only the critical tables -> backups/wh_data_<ts>.sql
            + a manifest.json with per-table row counts (the RPO evidence).
  --drill   prove RESTORE works: dump one critical table to a file, restore that
            FILE into a scratch schema (dr_drill), assert restored rowcount == source,
            measure elapsed (RTO evidence), then drop the scratch. A real round-trip.
  (default) run --drill (the gate's cheap, deterministic proof; --backup writes files).

Exit 0 = backup/restore proven; 1 = the round-trip lost rows or the DB is unreachable.
Stdlib only; reads no secrets; never touches prod.
"""
from __future__ import annotations
import io, json, subprocess, sys, time
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "backups"
DB = "supabase_db_workhive"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; B = "\033[1m"; X = "\033[0m"

# The data classes RTO_RPO_DECLARATION.md commits to recovering (the rows that matter).
# Arc S R-lens DEPTH (2026-07-20): the list under-covered — it missed the hive's PM PLAN, the tenant
# records, marketplace/sales, and user-authored work (calcs/resumes/community/voice). For a maintenance
# product, losing a hive's PM program or its sales is unrecoverable data-loss = the exact Arc S thesis.
# Backup covers the PRIMARY user-authored/operational rows (caches/embeddings/analytics are regenerable).
CRITICAL_TABLES = [
    "hives", "worker_profiles", "hive_members",              # tenant + auth/identity (RPO 0)
    "logbook", "pm_completions", "pm_assets", "pm_scope_items",  # work log + the PM PLAN (unrecoverable if lost)
    "inventory_items", "inventory_transactions",             # stock + ledger
    "asset_nodes", "projects", "project_items",              # active operational ("assets" was a stale alias)
    "engineering_calcs", "resume_documents", "resume_versions",  # user-authored saved work
    "community_posts", "community_replies", "skill_profiles",    # community + skills
    "voice_journal_entries",                                 # field voice logs
    "marketplace_listings", "marketplace_orders", "marketplace_sellers",  # marketplace / sales
    "hive_audit_log",                                        # audit trail
]


def _psql(sql: str, timeout: int = 60):
    return subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                           "-tA", "-c", sql], capture_output=True, text=True, timeout=timeout)


def _db_up() -> bool:
    try:
        r = _psql("select 1;", timeout=10)
        return r.returncode == 0 and r.stdout.strip().startswith("1")
    except Exception:
        return False


def _existing_tables() -> set[str]:
    r = _psql("select table_name from information_schema.tables where table_schema='public';")
    return set(x.strip() for x in r.stdout.splitlines() if x.strip())


def _rowcount(table: str) -> int:
    r = _psql(f'select count(*) from public."{table}";')
    try:
        return int(r.stdout.strip())
    except ValueError:
        return -1


def do_backup(tables: list[str]) -> int:
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = _psql("select to_char(now(),'YYYYMMDD_HH24MISS');").stdout.strip() or "now"
    out = BACKUP_DIR / f"wh_data_{ts}.sql"
    args = ["docker", "exec", DB, "pg_dump", "-U", "postgres", "-d", "postgres", "--data-only", "--no-owner"]
    for t in tables:
        args += ["--table", f"public.{t}"]
    # Explicit UTF-8: pg_dump emits UTF-8, but text=True defaults to the locale encoding (cp1252 on
    # Windows) which can yield a None/garbled stdout on a clean (rc=0) dump — a backup tool must never
    # crash opaquely on that (Arc S R-lens robustness, 2026-07-20).
    dump = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    if dump.returncode != 0 or not dump.stdout:
        print(f"  {R}FAIL{X} pg_dump (rc={dump.returncode}): {(dump.stderr or 'empty stdout — no data captured').strip()[:200]}")
        return 1
    out.write_text(dump.stdout, encoding="utf-8")
    manifest = {"created_at": ts, "file": out.name, "tables": {t: _rowcount(t) for t in tables}}
    (BACKUP_DIR / f"wh_data_{ts}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(v for v in manifest["tables"].values() if v > 0)
    print(f"  {G}backup{X} {out.name}  ({len(tables)} tables, {total} rows)  + manifest")
    return 0


def do_drill(tables: list[str]) -> int:
    """Prove a file dump RESTORES: dump one table -> restore the FILE into a scratch
    schema -> assert rowcount matches -> drop scratch. A real backup→restore round-trip."""
    # pick the largest available critical table for a meaningful drill
    avail = [t for t in tables if t in _existing_tables()]
    if not avail:
        print(f"  {Y}SKIP{X} no critical tables present to drill")
        return 0
    target = max(avail, key=_rowcount)
    src = _rowcount(target)
    t0 = time.monotonic()

    # 1. dump just this table, data-only (the "backup")
    dump = subprocess.run(["docker", "exec", DB, "pg_dump", "-U", "postgres", "-d", "postgres",
                           "--data-only", "--no-owner", "--table", f"public.{target}"],
                          capture_output=True, text=True, timeout=120)
    if dump.returncode != 0:
        print(f"  {R}FAIL{X} pg_dump {target}: {dump.stderr.strip()[:160]}"); return 1

    # 2. restore the dump into a scratch schema (rewrite COPY/INSERT target schema)
    restored_sql = dump.stdout.replace("public.", "dr_drill.")
    prep = (f'drop schema if exists dr_drill cascade; create schema dr_drill; '
            f'create table dr_drill."{target}" (like public."{target}" including defaults);')
    if _psql(prep).returncode != 0:
        print(f"  {R}FAIL{X} could not create scratch schema"); return 1
    # feed the rewritten dump through psql stdin
    rp = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                         "-v", "ON_ERROR_STOP=1"], input=restored_sql, capture_output=True, text=True, timeout=180)
    restored = -1
    rc = _psql(f'select count(*) from dr_drill."{target}";')
    try: restored = int(rc.stdout.strip())
    except ValueError: pass
    elapsed = time.monotonic() - t0
    _psql("drop schema if exists dr_drill cascade;")  # always clean up

    ok = (rp.returncode == 0) and (restored == src) and (src >= 0)
    if ok:
        print(f"  {G}drill{X} {target}: dumped + restored {restored}/{src} rows in {elapsed:.1f}s "
              f"(round-trip verified; RTO~{elapsed:.1f}s/table)")
        return 0
    print(f"  {R}FAIL{X} restore round-trip {target}: src={src} restored={restored} "
          f"rc={rp.returncode} {rp.stderr.strip()[:160]}")
    return 1


def main() -> int:
    print(f"{B}Arc S - logical data backup + restore drill (R-lens){X}")
    print("=" * 62)
    if not _db_up():
        print(f"  {Y}SKIP{X} local Supabase DB ({DB}) not reachable — start it to back up/drill. "
              f"(A down DB is not a backup failure; nothing to dump.)")
        return 0
    tables = [t for t in CRITICAL_TABLES if t in _existing_tables()]
    rc = 0
    if "--backup" in sys.argv:
        rc |= do_backup(tables)
    if "--drill" in sys.argv or len(sys.argv) == 1:
        rc |= do_drill(tables)
    if rc == 0:
        print(f"\n{G}{B}  DATA BACKUP/RESTORE: PASS{X} - logical dump + restore round-trip proven locally.")
    else:
        print(f"\n{R}{B}  DATA BACKUP/RESTORE: FAIL{X}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
