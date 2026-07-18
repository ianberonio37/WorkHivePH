#!/usr/bin/env python3
# DEEPWALK-CELL: * D9
"""
validate_supervisor_approval_backstop.py -- LOCK for the self-approval / delete-signed-off
governance-bypass class (deep-walk dim-2, found live 2026-07-07).

Bug class (CONFIRMED exploit): a table carrying an approval gate (approved_at / approved_by,
and/or status='approved') whose write RLS gates on hive MEMBERSHIP only (never role='supervisor')
lets ANY active member self-approve or delete signed-off work via a direct PostgREST/RLS write --
the supervisor sign-off is UI-only. A worker (Bryan) self-approved an rcm_fmea_modes row this way.

FIX: a BEFORE INSERT/UPDATE/DELETE trigger `tg_guard_approval` running
`wh_guard_supervisor_approval()` (migration 20260707000000) requires an active supervisor of the
row's hive to set/change approval columns or delete an approved row.

This gate FAILS if any APPROVAL_GATED table loses its guard trigger in the migrations (static),
and -- when docker is reachable -- cross-checks the LIVE DB has the trigger (drift-proof).

Usage:  python tools/validate_supervisor_approval_backstop.py [--json]
Exit 0 = clean, 1 = a required backstop is missing.
"""
import re, sys, subprocess, pathlib, json, glob, os

ROOT = pathlib.Path(__file__).resolve().parent.parent
MIG_DIR = ROOT / "supabase" / "migrations"
DB_CONTAINER = "supabase_db_workhive"

# Tables that carry the "worker submits -> supervisor approves" gate and MUST have the backstop.
# asset_nodes/rcm_* (status/approved_at) fixed in mig 20260707000000; inventory_items (status) +
# logbook (wo_state) fixed in mig 20260707000002. Extend when the same gate lands on another table.
APPROVAL_GATED = {"asset_nodes", "rcm_fmea_modes", "rcm_strategies", "inventory_items", "logbook"}
TRIGGER = "tg_guard_approval"
GUARD_FN = "wh_guard_supervisor_approval"


def migrations_text():
    out = []
    for p in sorted(glob.glob(str(MIG_DIR / "*.sql"))):
        try:
            out.append(open(p, encoding="utf-8", errors="ignore").read())
        except Exception:
            pass
    return "\n".join(out)


def static_check(text):
    """Every APPROVAL_GATED table has a CREATE TRIGGER tg_guard_approval ... ON <table>."""
    missing = []
    fn_defined = bool(re.search(rf"\bFUNCTION\s+(?:public\.)?{GUARD_FN}\b", text, re.I))
    for t in sorted(APPROVAL_GATED):
        # CREATE TRIGGER tg_guard_approval ... ON [public.]<t>  (INSERT/UPDATE/DELETE)
        pat = rf"CREATE\s+TRIGGER\s+{TRIGGER}\b[\s\S]{{0,200}}?\bON\s+(?:public\.)?{re.escape(t)}\b"
        if not re.search(pat, text, re.I):
            missing.append(t)
    return fn_defined, missing


def live_triggers():
    """Set of tables that have tg_guard_approval live, or None if docker unreachable."""
    sql = ("select tgrelid::regclass::text from pg_trigger "
           f"where tgname='{TRIGGER}' and not tgisinternal;")
    try:
        p = subprocess.run(["docker", "exec", DB_CONTAINER, "psql", "-U", "postgres", "-tA", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        if p.returncode != 0:
            return None
        return {ln.strip().replace("public.", "") for ln in p.stdout.splitlines() if ln.strip()}
    except Exception:
        return None


def main():
    as_json = "--json" in sys.argv
    text = migrations_text()
    fn_defined, missing_static = static_check(text)
    issues = []
    if not fn_defined:
        issues.append(f"guard function {GUARD_FN}() is not defined in any migration")
    for t in missing_static:
        issues.append(f"[static] table '{t}' has no {TRIGGER} trigger defined in migrations")

    live = live_triggers()
    live_note = "docker unreachable -- live cross-check skipped"
    if live is not None:
        live_note = f"live triggers on: {sorted(live) or 'none'}"
        for t in sorted(APPROVAL_GATED):
            if t not in live:
                issues.append(f"[live] table '{t}' is APPROVAL_GATED but has no {TRIGGER} trigger in the DB "
                              f"(apply migration 20260707000000) -- workers can self-approve/delete signed-off work")

    if as_json:
        print(json.dumps({"issues": issues, "count": len(issues),
                          "approval_gated": sorted(APPROVAL_GATED), "live": sorted(live) if live else None}, indent=2))
    else:
        print("supervisor-approval backstop (approval-gated tables require an active-supervisor trigger)")
        print(f"  {live_note}")
        if not issues:
            print(f"  PASS: all {len(APPROVAL_GATED)} approval-gated tables have the {TRIGGER} backstop "
                  f"({GUARD_FN} defined)")
        else:
            print(f"  FAIL: {len(issues)} backstop gap(s):")
            for i in issues:
                print(f"    {i}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
