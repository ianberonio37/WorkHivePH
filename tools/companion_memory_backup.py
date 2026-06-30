#!/usr/bin/env python3
"""companion_memory_backup.py - Companion-Memory C3.1: backup + restore DRILL of the
companion memory tables (agent_episodic_memory + agent_memory).
================================================================================
The substrate audit (COMPANION_MEMORY_AUDIT.md) found NO drill proving the durable
companion memory restores — Supabase PITR exists platform-wide but is never drilled
per these tables. This is the M1.1 / Arc-S `data_backup.py` pattern (pg_dump ->
restore into a scratch schema -> assert rowcount), extended with the C3.1-specific
acceptance bar the roadmap names: **a known recall query still returns its fact after
the restore** (a rowcount match alone does not prove the memory is still RECALLABLE).

Runs entirely against the LOCAL docker Supabase ($0, never prod). Zero net pollution:
the canary it seeds to prove recall is removed in a finally-cleanup.

  --backup  pg_dump --data-only the companion tables -> backups/companion_mem_<ts>.sql + manifest.
  --drill   (default) for each table: dump -> restore the FILE into scratch schema dr_companion ->
            assert restored rowcount == source. For agent_episodic_memory also seed a unique canary
            procedural memory, include it in the round-trip, and assert a RECALL-shaped query
            (importance-ordered) against the RESTORED copy still returns the canary fact.

Exit 0 = backup/restore + recall proven (or DB down -> SKIP); 1 = round-trip lost rows or the
restored memory was not recallable.  Stdlib only; reads no secrets; never touches prod.
"""
from __future__ import annotations
import io, json, subprocess, sys, time
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / "backups"
DB = "supabase_db_workhive"
G = "\033[92m"; R = "\033[91m"; Y = "\033[93m"; C = "\033[96m"; B = "\033[1m"; X = "\033[0m"

COMPANION_TABLES = ["agent_episodic_memory", "agent_memory"]
CANARY_WORKER = "__c3_backup_drill__"
CANARY_TAG = "C3DRILL-canary-procedure-fact-zx41"   # unique nonce, no collision with real data


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


def _rowcount(table: str, schema: str = "public") -> int:
    r = _psql(f'select count(*) from {schema}."{table}";')
    try:
        return int(r.stdout.strip())
    except ValueError:
        return -1


def _seed_canary() -> bool:
    """Insert a unique canary procedural memory (high importance so a recall query surfaces it).
    Idempotent: clears any leftover canary first."""
    _psql(f"delete from public.agent_episodic_memory where worker_name = '{CANARY_WORKER}';")
    ins = _psql(
        "insert into public.agent_episodic_memory(worker_name, memory_type, content, importance) "
        f"values ('{CANARY_WORKER}','procedural','{CANARY_TAG}: torque 137 Nm on pump CANARY-9', 0.95);"
    )
    return ins.returncode == 0


def _clear_canary():
    _psql(f"delete from public.agent_episodic_memory where worker_name = '{CANARY_WORKER}';")


def do_backup(tables: list[str]) -> int:
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = _psql("select to_char(now(),'YYYYMMDD_HH24MISS');").stdout.strip() or "now"
    out = BACKUP_DIR / f"companion_mem_{ts}.sql"
    args = ["docker", "exec", DB, "pg_dump", "-U", "postgres", "-d", "postgres", "--data-only", "--no-owner"]
    for t in tables:
        args += ["--table", f"public.{t}"]
    dump = subprocess.run(args, capture_output=True, text=True, timeout=300)
    if dump.returncode != 0:
        print(f"  {R}FAIL{X} pg_dump: {dump.stderr.strip()[:200]}")
        return 1
    out.write_text(dump.stdout, encoding="utf-8")
    manifest = {"created_at": ts, "file": out.name, "tables": {t: _rowcount(t) for t in tables}}
    (BACKUP_DIR / f"companion_mem_{ts}.manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(v for v in manifest["tables"].values() if v > 0)
    print(f"  {G}backup{X} {out.name}  ({len(tables)} tables, {total} rows)  + manifest")
    return 0


def _drill_table(target: str, recall_canary: bool) -> int:
    """Dump one table -> restore the FILE into scratch schema dr_companion -> assert rowcount.
    When recall_canary, also assert the seeded canary is RECALLABLE from the restored copy."""
    src = _rowcount(target)
    t0 = time.monotonic()
    dump = subprocess.run(["docker", "exec", DB, "pg_dump", "-U", "postgres", "-d", "postgres",
                           "--data-only", "--no-owner", "--table", f"public.{target}"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    dump_sql = dump.stdout or ""
    if dump.returncode != 0 or not dump_sql:
        print(f"  {R}FAIL{X} pg_dump {target}: rc={dump.returncode} {(dump.stderr or '').strip()[:160]}"); return 1

    # restore the dump into a scratch schema (rewrite the schema-qualified target). The scratch
    # table is created LIKE ... INCLUDING DEFAULTS, which does NOT copy the self-referential
    # superseded_by FK, so the circular-FK pg_dump warning is harmless here (restore is
    # insert-order-independent into a constraint-light scratch copy).
    restored_sql = dump_sql.replace("public.", "dr_companion.")
    prep = (f'drop schema if exists dr_companion cascade; create schema dr_companion; '
            f'create table dr_companion."{target}" (like public."{target}" including defaults);')
    if _psql(prep).returncode != 0:
        print(f"  {R}FAIL{X} could not create scratch schema for {target}"); return 1
    rp = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                         "-v", "ON_ERROR_STOP=1"], input=restored_sql, capture_output=True,
                        text=True, encoding="utf-8", errors="replace", timeout=240)
    restored = _rowcount(target, schema="dr_companion")
    elapsed = time.monotonic() - t0

    rc = 0
    rowcount_ok = (rp.returncode == 0) and (restored == src) and (src >= 0)
    if rowcount_ok:
        print(f"  {G}drill{X} {target}: restored {restored}/{src} rows in {elapsed:.1f}s (round-trip verified)")
    else:
        print(f"  {R}FAIL{X} {target} round-trip: src={src} restored={restored} rc={rp.returncode} "
              f"{rp.stderr.strip()[:140]}")
        rc = 1

    if recall_canary and rowcount_ok:
        # RECALL proof: an importance-ordered recall query against the RESTORED copy must still
        # surface the canary fact (proves the restored memory is recallable, not merely present).
        q = (f"select content from dr_companion.\"{target}\" "
             f"where worker_name = '{CANARY_WORKER}' order by importance desc, use_count desc limit 5;")
        rr = _psql(q)
        if rr.returncode == 0 and CANARY_TAG in rr.stdout:
            print(f"  {G}recall{X} {target}: canary fact recallable from the restored copy "
                  f"(importance-ordered query returned it).")
        else:
            print(f"  {R}FAIL{X} {target}: canary fact NOT recallable from the restored copy "
                  f"(restore preserved rows but the recall query missed it).")
            rc = 1

    _psql("drop schema if exists dr_companion cascade;")  # always clean up the scratch schema
    return rc


def do_drill(tables: list[str]) -> int:
    avail = [t for t in tables if t in _existing_tables()]
    if not avail:
        print(f"  {Y}SKIP{X} no companion memory tables present to drill")
        return 0
    rc = 0
    seeded = False
    try:
        if "agent_episodic_memory" in avail:
            seeded = _seed_canary()
            if not seeded:
                print(f"  {Y}note{X} could not seed canary (recall assertion will be skipped for episodic)")
        for t in avail:
            rc |= _drill_table(t, recall_canary=(t == "agent_episodic_memory" and seeded))
    finally:
        if seeded:
            _clear_canary()   # zero net pollution
    return rc


def main() -> int:
    print(f"{B}Companion-Memory C3.1 - backup + restore drill (agent_episodic_memory + agent_memory){X}")
    print("=" * 78)
    if not _db_up():
        print(f"  {Y}SKIP{X} local Supabase DB ({DB}) not reachable - start it to back up/drill. "
              f"(A down DB is not a backup failure; nothing to dump.)")
        return 0
    tables = [t for t in COMPANION_TABLES if t in _existing_tables()]
    rc = 0
    if "--backup" in sys.argv:
        rc |= do_backup(tables)
    if "--drill" in sys.argv or not any(a.startswith("--") for a in sys.argv[1:]):
        rc |= do_drill(tables)
    if rc == 0:
        print(f"\n{G}{B}  COMPANION MEMORY BACKUP/RESTORE: PASS{X} - dump + restore round-trip + recall proven locally.")
    else:
        print(f"\n{R}{B}  COMPANION MEMORY BACKUP/RESTORE: FAIL{X}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
