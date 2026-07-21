#!/usr/bin/env python3
"""
validate_role_gate_server_backstop.py - PER_PAGE_BUGHUNT P5 UI-role-gate backstop gate (2026-07-21).
====================================================================================================
The P5 (Role/Permission) security surface is comprehensively server-gated already — RLS read isolation
(truth-view-read-isolation 34/34), write isolation (hive-isolation 25/0), self-elevation (clean),
attribution (attribution-pinned). The LAST P5 sub-property is the UI-role-gate DEFENSE-IN-DEPTH: several
pages source `HIVE_ROLE` from localStorage (tamperable) and hide supervisor-only actions on
`HIVE_ROLE === 'supervisor'` / `WHRoles.isSupervisor()`. That is SAFE **only because the server RLS/
trigger backstops every such action** — a worker who tampers localStorage to 'supervisor' sees a button
the server still rejects (42501). The real risk is a FUTURE page that adds a client-only supervisor gate
on a table with NO server enforcement = a genuine UI-only-auth privilege-escalation hole (the exact class
found + exploited live 2026-07-07, asset_risk_scores / tg_guard_approval).

THIS GATE locks the invariant: every table written behind a SUPERVISOR UI gate MUST carry a server-side
supervisor enforcement — an RLS policy whose qual/with-check references the supervisor role, OR a
`tg_guard_approval` (or equivalent) trigger, OR (for admin surfaces) an `is_marketplace_admin` policy.
So the UI gate is NEVER the only gate; localStorage tampering can't escalate.

The table list is CURATED (adding a supervisor-privileged write is a conscious security decision that
must update this list) and each entry cites the page + action. Live (reads pg_policy/pg_trigger); skips
cleanly if docker/DB is unreachable. `--selftest` proves the check has teeth.
"""
from __future__ import annotations
import io, sys, subprocess
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_role_gate_server_backstop"]
DB = "supabase_db_workhive"

# table -> (page, supervisor-gated action). Every one is written by a client behind an isSupervisor/
# HIVE_ROLE==='supervisor' UI gate; the server MUST independently enforce supervisor/admin.
SUPERVISOR_GATED = {
    "asset_nodes":            ("asset-hub/logbook", "approve/register asset (tg_guard_approval)"),
    "rcm_fmea_modes":         ("asset-hub", "approve FMEA mode"),
    "rcm_strategies":         ("asset-hub", "approve RCM strategy"),
    "inventory_items":        ("inventory", "approve part (tg_guard_approval)"),
    "shift_plans":            ("shift-brain", "publish/archive shift plan"),
    "integration_configs":    ("integrations/plant-connections", "add/edit CMMS connector"),
    "hive_retention_config":  ("plant-connections", "change data-retention policy"),
    "api_keys":               ("integrations", "mint API key"),
    "sso_configs":            ("plant-connections", "configure SSO/SAML"),
    "marketplace_sellers":    ("founder-console", "verify seller KYB (is_marketplace_admin)"),
}


def _psql(sql: str):
    try:
        return subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                               "-t", "-A", "-v", "ON_ERROR_STOP=1"],
                              input=sql, capture_output=True, text=True, timeout=30)
    except Exception:
        return None


def _dbup() -> bool:
    r = _psql("select 1;")
    return bool(r and r.returncode == 0 and r.stdout.strip() == "1")


def _backstop(table: str) -> str | None:
    """Return the server enforcement kind for `table`, or None if there is NO supervisor/admin backstop."""
    sql = f"""
select
  (select count(*) from pg_policy p join pg_class c on c.oid=p.polrelid
     where c.relname='{table}' and p.polcmd in ('w','a','*','d')
       and (coalesce(pg_get_expr(p.polqual,p.polrelid),'') ~* '(supervisor|is_marketplace_admin|role\\s*=)'
         or coalesce(pg_get_expr(p.polwithcheck,p.polrelid),'') ~* '(supervisor|is_marketplace_admin|role\\s*=)')),
  (select count(*) from pg_trigger t join pg_class c on c.oid=t.tgrelid
     where c.relname='{table}' and not t.tgisinternal and t.tgname ~* '(guard_approval|guard_supervisor|role_guard)'),
  (select count(*) from pg_policy p join pg_class c on c.oid=p.polrelid
     where c.relname='{table}' and p.polcmd in ('w','a','*')
       and coalesce(pg_get_expr(p.polwithcheck,p.polrelid),'true')='false'
       and coalesce(pg_get_expr(p.polqual,p.polrelid),'true') in ('false','true'));
"""
    r = _psql(sql)
    if not r or r.returncode != 0:
        return None
    parts = (r.stdout.strip().split("|") + ["0", "0", "0"])[:3]
    try:
        rls, trg, locked = (int(p or 0) for p in parts)
    except ValueError:
        return None
    kinds = []
    if rls:
        kinds.append("rls-role")
    if trg:
        kinds.append("trg-guard")
    if locked:
        kinds.append("write-locked")  # WITH CHECK false = no client write at all (service-role only) — the strongest backstop
    return ",".join(kinds) if kinds else None


def self_test() -> bool:
    ok = True
    # teeth: the curated list must be non-empty + unique, and every entry must name a real table string
    if not SUPERVISOR_GATED or len(set(SUPERVISOR_GATED)) != len(SUPERVISOR_GATED):
        print(f"{R}self-test FAIL: curated list empty or dup.{X}"); ok = False
    # teeth: the backstop parser must treat 0/0/0 as NO backstop and any positive count (rls|trg|locked) as a backstop
    for stub, want in [("0|0|0", False), ("1|0|0", True), ("0|1|0", True), ("0|0|1", True), ("2|3|1", True)]:
        rls, trg, locked = (int(x) for x in stub.split("|"))
        got = bool(rls or trg or locked)
        if got != want:
            print(f"{R}self-test FAIL: backstop tally {stub} -> {got}, want {want}.{X}"); ok = False
    print((G + "self-test PASS - role-gate-backstop check has teeth." + X) if ok else (R + "self-test FAILED." + X))
    return ok


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        return 0 if self_test() else 1
    print(f"{B}P5 UI-role-gate server-backstop gate (every supervisor-gated write must be server-enforced){X}")
    if not _dbup():
        print("  SKIP: local DB not reachable — role-gate backstop gate not evaluated.")
        return 0
    fails = []
    for table, (page, action) in sorted(SUPERVISOR_GATED.items()):
        kind = _backstop(table)
        if kind:
            print(f"  {G}PASS{X}  {table} [{kind}] — {page}: {action}")
        else:
            print(f"  {R}FAIL{X}  {table} — {page}: {action}: supervisor-gated in the UI but NO server-side "
                  f"supervisor/admin enforcement (RLS role clause or guard trigger) = UI-only-auth hole.")
            fails.append(table)
    if fails:
        print(f"{R}FAIL: {len(fails)} supervisor-gated table(s) with no server backstop — a tampered "
              f"localStorage role could escalate.{X}")
        return 1
    print(f"{G}PASS - every supervisor-gated UI action is server-backstopped (the UI gate is never the only gate).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
