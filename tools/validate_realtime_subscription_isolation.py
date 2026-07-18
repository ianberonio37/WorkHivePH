#!/usr/bin/env python3
"""validate_realtime_subscription_isolation.py — Arc J (Realtime) keystone gate.

THE THREAT (read-path twin of the Arc G DEFINER-IDOR / Arc H view-security_invoker work):
Supabase Realtime `postgres_changes` broadcasts row changes to every subscriber on a channel.
The CHANNEL NAME (`hive-feed:<HIVE_ID>`) and the client-supplied `filter` (`hive_id=eq.<X>`) are
NOT security boundaries — they are strings the client picks and can change at will. The ONLY tenant
boundary for a realtime subscription is the table's **SELECT RLS policy**, evaluated by Realtime
against the subscribing connection's role/JWT. Therefore:

  A table in the `supabase_realtime` publication that has RLS off, OR a PERMISSIVE always-true
  (`USING (true)` / NULL-qual) SELECT/ALL policy, streams EVERY row change to ANY anon subscriber —
  cross-tenant LIVE exfiltration, strictly worse than the on-demand read Arc G's gate covers
  (a stream, not a one-shot query).

KEYSTONE FINDING (2026-06-21): `platform_feedback` was in the publication with anon `USING(true)`
SELECT/UPDATE/DELETE policies → any anon client could live-stream every feedback submission
(incl. contact_email PII) and tamper/delete rows. Arc G's permissive-bypass gate had EXEMPTED it
("public board, by design"); the realtime lens disproved that by evidence. Fixed 20260621000003.

WHAT THIS GATE MEASURES (live, via docker psql — the publication is the exact broadcast set):
For every table in the `supabase_realtime` publication, it must be SAFE to broadcast:
  (1) RLS is ENABLED  (relrowsecurity = true), and
  (2) it has NO permissive always-true SELECT/ALL policy (an anon-readable live stream).
A table failing either is EXPOSED. Forward-only DOWN ratchet (baseline-locked), like the Arc G gate.

BY-DESIGN exemptions (truly platform-public streams, evidence-required): NONE currently. A table is
only exempt if EVERY column it broadcasts is intended to be world-readable in real time. "It has a
public face" is not enough — platform_feedback proved that. Add here only with written evidence.

USAGE:  python tools/validate_realtime_subscription_isolation.py   [--update-baseline]
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
BASELINE = ROOT / "realtime_subscription_isolation_baseline.json"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

# Tables whose EVERY broadcast column is intentionally world-readable in real time (evidence-required).
BY_DESIGN: dict[str, str] = {}


def query_published_posture() -> list[dict] | None:
    """One row per table in the supabase_realtime publication, with its isolation posture."""
    sql = """
    WITH published AS (
      SELECT c.oid, c.relname, c.relrowsecurity
      FROM pg_publication_tables pt
      JOIN pg_class c ON c.relname = pt.tablename
      JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = pt.schemaname
      WHERE pt.pubname = 'supabase_realtime' AND pt.schemaname = 'public'
    )
    SELECT p.relname,
           p.relrowsecurity AS rls_on,
           COALESCE((
             SELECT count(*) FROM pg_policy pol
             WHERE pol.polrelid = p.oid AND pol.polpermissive
               AND pol.polcmd IN ('r','*')
               AND (pol.polqual IS NULL OR pg_get_expr(pol.polqual, pol.polrelid) = 'true')
               -- Only an APP-FACING always-true policy is an anon-subscribable live stream. Realtime
               -- evaluates the subscriber's OWN SELECT policy, so a `USING(true)` policy scoped to a
               -- restricted infra role (grafana_reader — the monitoring read granted in
               -- infra/mcp/grafana/grafana_reader.sql, NEVER to anon/authenticated) streams to that role
               -- only, not to an anon subscriber. Count it as an exposure ONLY when the always-true
               -- policy applies to PUBLIC (polroles has oid 0) or anon/authenticated. (Same infra-role
               -- exemption as Arc G's permissive-bypass detector + the db-adoption D2 census.)
               AND EXISTS (SELECT 1 FROM unnest(pol.polroles) pr(oid)
                           WHERE pr.oid = 0
                              OR pr.oid IN (SELECT r.oid FROM pg_roles r WHERE r.rolname IN ('anon','authenticated')))
           ), 0) AS permissive_always_true
    FROM published p
    ORDER BY p.relname;"""
    try:
        proc = subprocess.run(
            ["docker", "exec", DB, "psql", "-U", "postgres", "-d", "postgres", "-tA", "-F", "|", "-c", sql],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        if proc.returncode != 0:
            return None
        rows = []
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            name, rls, perm = line.split("|")
            rows.append({"table": name, "rls_on": rls == "t", "permissive": int(perm)})
        return rows
    except Exception:
        return None


def main() -> int:
    update = "--update-baseline" in sys.argv[1:]
    rows = query_published_posture()
    if rows is None:
        print(f"  {RED}ERROR{RST}: could not introspect (is {DB} running?)")
        return 1

    exposed, bydesign = [], []
    for r in rows:
        unsafe = (not r["rls_on"]) or (r["permissive"] > 0)
        if not unsafe:
            continue
        if r["table"] in BY_DESIGN:
            bydesign.append(r)
        else:
            exposed.append(r)

    print("=" * 78)
    print("  Arc J — Realtime subscription isolation (publication = the live broadcast set)")
    print("=" * 78)
    print(f"  tables in supabase_realtime publication: {len(rows)}  ·  exposed: {len(exposed)}")
    for r in bydesign:
        print(f"    {YEL}by-design{RST} {r['table']} — {BY_DESIGN[r['table']]}")
    for r in exposed:
        why = "RLS OFF" if not r["rls_on"] else f"{r['permissive']} always-true SELECT/ALL policy (live anon stream)"
        print(f"    {RED}EXPOSED{RST}  {r['table']} — {why}")

    base = {}
    if BASELINE.exists():
        try: base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception: base = {}
    baseline_n = base.get("exposed_count", None)
    names = sorted(r["table"] for r in exposed)

    if update or baseline_n is None:
        BASELINE.write_text(json.dumps({"exposed_count": len(exposed), "exposed": names}, indent=2), encoding="utf-8")
        print(f"\n  baseline set: {len(exposed)} exposed published table(s) (forward-only DOWN ratchet)")
        return 0

    print(f"\n  baseline {baseline_n} exposed · now {len(exposed)}")
    if len(exposed) > baseline_n:
        new = sorted(set(names) - set(base.get("exposed", [])))
        print(f"  {RED}REGRESSION{RST}: {len(exposed)-baseline_n} NEW exposed published table(s): {', '.join(new)}")
        print(f"  A published table with RLS-off or an always-true policy is a cross-tenant LIVE stream.")
        return 1
    if len(exposed) < baseline_n:
        print(f"  {GREEN}PROGRESS{RST}: {baseline_n-len(exposed)} fewer — run --update-baseline to lock the gain")
        return 0
    print(f"  {GREEN}HELD{RST} — every realtime-published table is RLS-gated with no anon-open stream")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
