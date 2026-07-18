#!/usr/bin/env python3
"""validate_rls_coverage.py — Arc G G1: non-RLS tenant/personal-scoped table detector (RLS-disabled gap).

The G2 work (validate_rls_no_permissive_bypass) covered tables that have RLS ON but a legacy `USING(true)`
policy defeating it. THIS covers the other half: tables with a tenant-scope column but RLS entirely DISABLED —
no policy is even evaluated, so anon/authenticated can read+write every owner's rows directly via PostgREST.
Same deferred-auth-migration root (project_rls_decision): RLS was a no-op in the anon-key era, so many
tables never had it enabled. Enabling it (+ a scoped policy) is the auth-migration enforcement.

TWO scope classes are detected (per-object, both ratcheted) — the second was added 2026-06-20 after a
per-OBJECT sweep found `worker_achievements` (personal gamification, anon-readable platform-wide) that the
hive-only scan structurally MISSED:
  • HIVE     — a `hive_id` column, RLS off (cross-tenant read+write of every hive's rows)
  • PERSONAL — an `auth_uid` column and NO `hive_id`, RLS off (cross-user read of every worker's private rows)

This MEASURES the gap precisely and is a forward-only DOWN ratchet — the count can only shrink as tables are
enabled (each enable verified per G2's method: confirm no anon-key reader, add a scoped policy, ROLLBACK-test
owner-reads-own + cross-scope-0 + anon-0). BY_DESIGN tables (cross-scope on purpose, evidence-curated) excluded.

USAGE:  python tools/validate_rls_coverage.py   [--update-baseline]
"""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
BASELINE = ROOT / "rls_coverage_baseline.json"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

# Cross-scope BY DESIGN (a tenant/personal column but intentionally not isolated) — evidence-curated.
# 2026-07-06 (deep-walk C8): the marketplace tables were REMOVED from this exemption. The old rationale
# ("public cross-hive catalogue → no RLS needed, scoped at the app layer") was WRONG — it conflated
# "public READ" with "no row security". Reads are public, but WRITES were never app-scoped (real
# cross-seller IDOR) and orders/inquiries/disputes/seller-PII are NOT public. They now have proper RLS
# (public-read + owner/party-write + admin-allow) via migration 20260706000001_marketplace_rls.sql, so
# they no longer register as non-RLS here. Keeping them OUT of BY_DESIGN means a future RLS-disable
# re-surfaces as a GAP regression instead of being silently re-hidden. This is the C8 lock.
BY_DESIGN = {}


def _query(sql: str) -> list[str] | None:
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if p.returncode != 0:
            return None
        return [l.strip() for l in p.stdout.splitlines() if l.strip()]
    except Exception:
        return None


def query() -> tuple[list[str], list[str], list[str]] | None:
    # class HIVE: a hive_id column, RLS off (cross-tenant)
    hive = _query("""
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity
      AND EXISTS (SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id')
    ORDER BY c.relname;""")
    # class PERSONAL: an auth_uid column and NO hive_id, RLS off (cross-user) — the class the hive-only scan missed
    personal = _query("""
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity
      AND EXISTS (SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='auth_uid')
      AND NOT EXISTS (SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id')
    ORDER BY c.relname;""")
    # class WORKER: a worker_name column and NO hive_id AND NO auth_uid, RLS off (cross-user by owner-name).
    # 2026-07-07 blind-spot fix: the PERSONAL class requires auth_uid, so worker_name-ONLY tables slipped
    # through RLS-off — exactly how marketplace_watchlist / marketplace_saved_searches (email PII!) /
    # achievement_xp_log were exposed. This class catches them.
    worker = _query("""
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r' AND NOT c.relrowsecurity
      AND EXISTS (SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='worker_name')
      AND NOT EXISTS (SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id')
      AND NOT EXISTS (SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='auth_uid')
    ORDER BY c.relname;""")
    if hive is None or personal is None or worker is None:
        return None
    return hive, personal, worker


def main() -> int:
    update = "--update-baseline" in sys.argv[1:]
    q = query()
    if q is None:
        print(f"  {RED}ERROR{RST}: could not introspect (is {DB} running?)")
        return 1
    hive_tables, personal_tables, worker_tables = q
    hive_gaps = [t for t in hive_tables if t not in BY_DESIGN]
    personal_gaps = [t for t in personal_tables if t not in BY_DESIGN]
    worker_gaps = [t for t in worker_tables if t not in BY_DESIGN]
    gaps = sorted(hive_gaps + personal_gaps + worker_gaps)
    bydesign = [t for t in (hive_tables + personal_tables + worker_tables) if t in BY_DESIGN]

    print("=" * 74)
    print("  Arc G G1 — non-RLS tenant/personal table detector (RLS entirely disabled)")
    print("=" * 74)
    print(f"  HIVE class:     {len(hive_tables)} non-RLS hive_id tables ({len([t for t in hive_tables if t in BY_DESIGN])} by-design, {len(hive_gaps)} gaps)")
    print(f"  PERSONAL class: {len(personal_tables)} non-RLS auth_uid tables ({len(personal_gaps)} gaps)")
    print(f"  WORKER class:   {len(worker_tables)} non-RLS worker_name-only tables ({len(worker_gaps)} gaps)")
    for t in bydesign:
        print(f"    {YEL}by-design{RST} {t} — {BY_DESIGN[t]}")
    for t in hive_gaps:
        print(f"    {RED}GAP{RST}  {t} — hive data, RLS off (anon/authenticated read+write any hive directly)")
    for t in personal_gaps:
        print(f"    {RED}GAP{RST}  {t} — personal data, RLS off (anon/authenticated read every worker's rows cross-user)")
    for t in worker_gaps:
        print(f"    {RED}GAP{RST}  {t} — worker_name-scoped, RLS off (anon/authenticated read every worker's rows by name)")

    base = {}
    if BASELINE.exists():
        try: base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception: base = {}
    baseline_n = base.get("gap_count")

    if update or baseline_n is None:
        BASELINE.write_text(json.dumps({"gap_count": len(gaps), "gaps": gaps}, indent=2), encoding="utf-8")
        print(f"\n  baseline set: {len(gaps)} non-RLS hive-table gaps (forward-only DOWN ratchet)")
        print(f"  {YEL}auth-migration enforcement{RST} — enable RLS + a hive-scoped policy per table once its")
        print(f"  anon-key readers are confirmed gone (Ian-gated; project_rls_decision). NOT a blind enable.")
        return 0

    print(f"\n  baseline {baseline_n} gaps · now {len(gaps)}")
    if len(gaps) > baseline_n:
        new = sorted(set(gaps) - set(base.get("gaps", [])))
        print(f"  {RED}REGRESSION{RST}: {len(gaps)-baseline_n} NEW non-RLS tenant/personal table(s): {', '.join(new)}")
        return 1
    if len(gaps) < baseline_n:
        print(f"  {GREEN}PROGRESS{RST}: {baseline_n-len(gaps)} table(s) enabled since baseline — run --update-baseline to lock")
        return 0
    print(f"  {GREEN}HELD{RST} — no regression (still {len(gaps)} known gaps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
