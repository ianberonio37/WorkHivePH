#!/usr/bin/env python3
"""validate_truth_view_security_invoker.py — Arc G G4: every v_*_truth view must respect RLS.

THE FINDING (Arc G, 2026-06-20): the v_*_truth views are the platform's canonical READ API, granted to
anon+authenticated. A Postgres view that is NOT `security_invoker` runs as its OWNER and BYPASSES base-table
RLS — so reading `v_inventory_items_truth?hive_id=eq.<victim>` returned the victim's rows even though the
base table's RLS blocked the direct read. 37 of 38 truth views were owner-running → read-path tenant
isolation was off platform-wide. Fixed by `ALTER VIEW … SET (security_invoker = true)` (migration
20260620000012).

RULE: every `public.v_*_truth` view must be `security_invoker=true`, so base-table RLS actually applies to
the read path. A new owner-running truth view = a regression that re-opens cross-tenant reads. Baseline 0
non-invoker.

USAGE: python tools/validate_truth_view_security_invoker.py
"""
from __future__ import annotations
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
GREEN, RED = "\033[92m", "\033[91m"; RST = "\033[0m"


def query_non_invoker() -> list[str] | None:
    sql = r"""
    SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='v' AND c.relname LIKE 'v\_%truth'
      AND (c.reloptions IS NULL OR NOT c.reloptions::text ~* 'security_invoker=(on|true)')
    ORDER BY c.relname;"""
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if p.returncode != 0:
            return None
        return [l.strip() for l in p.stdout.splitlines() if l.strip()]
    except Exception:
        return None


def main() -> int:
    bad = query_non_invoker()
    if bad is None:
        print(f"  {RED}ERROR{RST}: could not introspect (is {DB} running?)")
        return 1
    print("=" * 70)
    print("  Arc G G4 — v_*_truth views must be security_invoker (respect base RLS)")
    print("=" * 70)
    if bad:
        for v in bad:
            print(f"  {RED}OWNER-RUNNING{RST} {v} — bypasses base-table RLS (cross-tenant read via the view)")
        print(f"\n  {RED}FAIL{RST}: {len(bad)} truth view(s) not security_invoker (baseline 0) — "
              f"add `ALTER VIEW … SET (security_invoker = true)`")
        return 1
    print(f"  {GREEN}PASS{RST} — every v_*_truth view is security_invoker; base-table RLS applies to the read path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
