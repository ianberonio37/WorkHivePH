#!/usr/bin/env python3
"""validate_rls_no_permissive_bypass.py — Arc G G2: legacy always-true RLS policy detector.

THE FINDING (Arc G G2 live two-tenant sweep, 2026-06-20): several core hive-private tables are
readable/writable CROSS-TENANT despite having a correct hive-scoped policy — because a LEGACY
pre-auth `USING (true)` PERMISSIVE policy (`allow_anon_all`, `open`, `anon_select_*`, `anon read *`)
sits alongside it. Postgres OR's permissive policies, so an always-true one DEFEATS every other policy
on the table: RLS is effectively OFF. A hive-A member (or an anonymous client) can read/write hive-B's
inventory, PM scope, assets, members, calcs. This is the pre-auth open-RLS state that
`project_rls_decision` deferred (RLS was a no-op while every query used the anon key with no session);
the Supabase-Auth migration adds the proper auth.uid() policies but has not yet REMOVED the legacy-open
ones, so the proper ones are inert.

This validator MEASURES the exposure precisely (the actionable root cause): every hive-scoped, RLS-enabled
table with a PERMISSIVE always-true (`USING true` or NULL qual) SELECT/ALL policy. It is a forward-only
DOWN ratchet — the count can only shrink as the auth migration drops the legacy-open policies (a
deliberately Ian-gated architectural step, NOT a blind drop: dropping one breaks any remaining anon-key
read/write of that table, so each removal must be paired with confirming the app uses an auth session).

BY-DESIGN exemptions (cross-hive on purpose, evidence-curated): NONE currently. Add here only with a
written reason AND live evidence the always-true policy leaks nothing private.

RETRACTED 2026-06-21 (Arc J realtime sweep): platform_feedback was exempted here as "global public
product-feedback board — cross-hive by design." The Arc J realtime lens disproved that by EVIDENCE —
the table is in the supabase_realtime publication, and a rolled-back two-tenant probe showed any anon
client could read PRIVATE (is_public=false) rows incl. contact_email PII, UPDATE/DELETE any row, and
subscribe to a LIVE change-stream of all submissions. "Public board" means anon reads PUBLISHED rows,
not unrestricted read/write of the whole table. Fixed in 20260621000003 (scoped policies +
is_platform_admin()); the exemption is gone so this ratchet now PROTECTS the table from a regression.
See [[feedback_classify_by_evidence_not_heuristic]].

USAGE:  python tools/validate_rls_no_permissive_bypass.py   [--update-baseline]
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
BASELINE = ROOT / "rls_permissive_bypass_baseline.json"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

# cross-hive BY DESIGN — an always-true policy is acceptable (evidence required).
BY_DESIGN = {
    "platform_feedback": "global public product-feedback board — cross-hive by design",
}


def query_open_tables() -> list[str] | None:
    sql = """
    SELECT DISTINCT c.relname
    FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relrowsecurity AND p.polpermissive
      AND p.polcmd IN ('r','*') AND (p.polqual IS NULL OR pg_get_expr(p.polqual,p.polrelid)='true')
      AND EXISTS (SELECT 1 FROM information_schema.columns col
                  WHERE col.table_schema='public' AND col.table_name=c.relname AND col.column_name='hive_id')
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
    update = "--update-baseline" in sys.argv[1:]
    tables = query_open_tables()
    if tables is None:
        print(f"  {RED}ERROR{RST}: could not introspect (is {DB} running?)")
        return 1
    exposed = [t for t in tables if t not in BY_DESIGN]
    bydesign = [t for t in tables if t in BY_DESIGN]

    print("=" * 74)
    print("  Arc G G2 — legacy always-true RLS policy (tenant-isolation bypass) detector")
    print("=" * 74)
    print(f"  hive-scoped RLS tables with a PERMISSIVE always-true SELECT/ALL policy: {len(tables)}")
    for t in bydesign:
        print(f"    {YEL}by-design{RST} {t} — {BY_DESIGN[t]}")
    for t in exposed:
        print(f"    {RED}EXPOSED{RST}  {t} — legacy USING(true) defeats its hive-scoped policy (cross-tenant read/write)")

    base = {}
    if BASELINE.exists():
        try: base = json.loads(BASELINE.read_text(encoding="utf-8"))
        except Exception: base = {}
    baseline_n = base.get("exposed_count", None)

    if update or baseline_n is None:
        BASELINE.write_text(json.dumps({"exposed_count": len(exposed), "exposed": exposed}, indent=2), encoding="utf-8")
        print(f"\n  baseline set: {len(exposed)} exposed hive-private tables (forward-only DOWN ratchet)")
        print(f"  {YEL}KNOWN auth-migration gap{RST} — fix = drop the legacy-open policy once the table's anon-key")
        print(f"  reads/writes are confirmed gone (Ian-gated; project_rls_decision). NOT a blind drop.")
        return 0

    print(f"\n  baseline {baseline_n} exposed · now {len(exposed)}")
    if len(exposed) > baseline_n:
        new = sorted(set(exposed) - set(base.get("exposed", [])))
        print(f"  {RED}REGRESSION{RST}: {len(exposed)-baseline_n} NEW exposed table(s): {', '.join(new)}")
        return 1
    if len(exposed) < baseline_n:
        print(f"  {GREEN}PROGRESS{RST}: {baseline_n-len(exposed)} table(s) hardened since baseline — run --update-baseline to lock the gain")
        return 0
    print(f"  {GREEN}HELD{RST} — no regression (still the known {len(exposed)}-table auth-migration gap)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
