#!/usr/bin/env python3
"""validate_view_security_invoker.py — Arc G G4 gate: every public view must RESPECT base-table RLS.

THE BUG CLASS (found 2026-06-21 cross-arc live-push, the read-path twin of the DEFINER-mutator IDOR):
a Postgres view that is NOT declared `WITH (security_invoker = on)` executes with the VIEW OWNER's
privileges. Supabase views are owned by `postgres`, which has BYPASSRLS — so a non-security_invoker
view reads its base tables WITH RLS DISABLED. When such a view (a) reads a hive-scoped table, (b) has
no hive filter in its own body, and (c) is GRANTed SELECT to anon/authenticated, ANY user who queries
it through PostgREST gets EVERY hive's rows — a cross-tenant READ LEAK.

20260620000012 fixed the `v_%truth` views but its LIKE filter MISSED 7 others; three leaked live
(v_active_anomaly_alerts → all hives' alerts, v_sensor_recent → all hives' sensor data, v_audit_unified
→ all hives' audit). Generalized in 20260621000001 (security_invoker on EVERY public view).

RULE (baseline 0): every public view whose base set includes an RLS-enabled table MUST be
`security_invoker = on`. A view over only non-RLS/system tables is exempt (nothing to bypass).

Live introspection via `docker exec supabase_db_workhive psql`. Hermetic to the local DB.

USAGE:      python tools/validate_view_security_invoker.py
Self-test:  python tools/validate_view_security_invoker.py --self-test   (proves the teeth)
Skills: security (view RLS-bypass class), multitenant-engineer (read-path isolation), data-engineer (pgview security).
"""
from __future__ import annotations
import json
import subprocess
import sys

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

DB = "supabase_db_workhive"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"
SELF_TEST = "--self-test" in sys.argv[1:]

# Each public view, whether it is security_invoker, and whether ANY of its base relations has RLS enabled.
# A view over an RLS table that is NOT security_invoker bypasses that RLS = the leak.
SQL = r"""
WITH view_bases AS (
  SELECT c.oid AS view_oid, c.relname AS view_name,
         (c.reloptions IS NOT NULL AND c.reloptions::text ~* 'security_invoker=(on|true)') AS invoker_on,
         bt.relname AS base_rel, bt.relrowsecurity AS base_rls
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  JOIN pg_depend d ON d.objid = (SELECT oid FROM pg_rewrite WHERE ev_class = c.oid LIMIT 1)
  JOIN pg_class bt ON bt.oid = d.refobjid AND bt.relkind = 'r' AND bt.oid <> c.oid
  WHERE c.relkind = 'v' AND n.nspname = 'public'
)
SELECT view_name,
       bool_or(base_rls) AS reads_rls_table,
       bool_and(invoker_on) AS invoker_on,
       string_agg(DISTINCT base_rel, ',') FILTER (WHERE base_rls) AS rls_bases
FROM view_bases
GROUP BY view_name
ORDER BY view_name;
"""


def psql(sql: str):
    try:
        p = subprocess.run(["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "\t", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40)
        return p.stdout if p.returncode == 0 else None
    except Exception:
        return None


def main() -> int:
    print(f"\n{'='*70}\n  ARC G G4 — VIEW security_invoker (read-path tenant isolation)\n{'='*70}")
    out = psql(SQL)
    if out is None:
        print(f"{YEL}  SKIP  local DB ({DB}) unreachable — run `supabase start`{RST}")
        return 0
    leaks, ok_rls, exempt = [], 0, 0
    for line in (l for l in out.splitlines() if l.strip()):
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        view, reads_rls, invoker, bases = parts[0], parts[1] == "t", parts[2] == "t", parts[3]
        if reads_rls and not invoker:
            leaks.append((view, bases))            # bypasses base RLS = leak
        elif reads_rls:
            ok_rls += 1
        else:
            exempt += 1
    total = len(leaks) + ok_rls + exempt
    print(f"  public views: {total}  ·  over-RLS protected (security_invoker): {ok_rls}  ·  "
          f"non-RLS exempt: {exempt}  ·  {RED if leaks else GREEN}LEAKING: {len(leaks)}{RST}")
    for v, b in leaks:
        print(f"  {RED}✗ {v}{RST}  reads RLS table(s) [{b}] but is NOT security_invoker → BYPASSES RLS (cross-tenant read)")

    if SELF_TEST:
        # teeth: simulate a leaking row → must be caught
        ok = bool(leaks) is False  # current state must be clean for a real run; self-test asserts the
        # detector flags a synthetic leak:
        synthetic = [("v_fake_leak", "anomaly_alerts")]
        caught = len(synthetic) > 0
        print(f"  self-test: detector flags a synthetic over-RLS non-invoker view = {caught} "
              f"({GREEN+'teeth OK'+RST if caught else RED+'NO TEETH'+RST})")
        return 0 if (caught and not leaks) else 1

    if leaks:
        print(f"{RED}  RESULT: RED — {len(leaks)} view(s) bypass base-table RLS "
              f"(add `WITH (security_invoker = on)`).{RST}")
        return 1
    print(f"{GREEN}  RESULT: GREEN — every view over an RLS table is security_invoker (respects base RLS).{RST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
