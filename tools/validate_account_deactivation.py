#!/usr/bin/env python3
"""validate_account_deactivation.py — Arc I I8/I: GDPR/PDPA account offboarding (soft-deactivate + anonymize).

The account-deletion RPC must implement the soft-deactivate + anonymize model SAFELY:
  1. SELF-SCOPED by auth.uid() with NO user parameter — a `p_user_id`/`p_auth_uid` arg would be a
     cross-user IDOR (delete/anonymize anyone). (Arc G/H DEFINER-gate lesson.)
  2. ANONYMIZE PII on worker_profiles (display_name + email) — right-to-erasure of personal data.
  3. PRESERVE operational records — the fn must NOT DELETE from logbook / pm_completions /
     engineering_calcs / inventory_items etc. (history/audit integrity; Ian's chosen model).
  4. REVOKE hive access — set hive_members.status away from 'active' (e.g. 'deactivated').
  5. Hardened: SECURITY DEFINER + SET search_path (CVE-2018-1058), and REVOKE from PUBLIC + anon,
     GRANT to authenticated/service_role (Arc H PUBLIC-default blind spot).

Baseline 0 — any violation is a regression. The auth.users login-ban (Supabase admin API) is the
named attributed residual, out of this in-DB RPC's scope.

USAGE:      python tools/validate_account_deactivation.py
Self-test:  python tools/validate_account_deactivation.py --self-test
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "supabase" / "migrations"
FN = "deactivate_my_account"
GREEN, RED, YEL = "\033[92m", "\033[91m", "\033[93m"; RST = "\033[0m"

# operational tables whose rows must be PRESERVED (a DELETE FROM these inside the fn = data destruction)
OPERATIONAL = ["logbook", "pm_completions", "pm_assets", "pm_scope_items", "engineering_calcs",
               "inventory_items", "inventory_transactions", "checklist_records", "parts_records"]


def _find_fn_body(sql: str) -> str:
    """Extract the CREATE FUNCTION ... $$ ... $$ body for the deactivation fn."""
    m = re.search(rf"CREATE\s+OR\s+REPLACE\s+FUNCTION[^;]*?{re.escape(FN)}\s*\(([^)]*)\)(.*?)\$\$(.*?)\$\$",
                  sql, re.S | re.I)
    if not m:
        return ""
    return m.group(0)


def audit(sql: str) -> tuple[list[tuple[str, str]], str]:
    out: list[tuple[str, str]] = []
    body = _find_fn_body(sql)
    if not body:
        out.append(("FAIL", f"{FN}() not found / not a CREATE OR REPLACE FUNCTION"))
        return out, body
    # the parameter list = text between the first ( and )
    params = re.search(rf"{re.escape(FN)}\s*\(([^)]*)\)", body)
    param_txt = (params.group(1) if params else "").strip()

    self_scoped = ("auth.uid()" in body) and (param_txt == "" or "p_user" not in param_txt
                                              and "p_auth" not in param_txt and "p_uid" not in param_txt)
    out.append(("OK" if self_scoped else "FAIL",
                f"self-scoped by auth.uid(), no cross-user param (params: '{param_txt or 'none'}')"))

    anon_name = bool(re.search(r"display_name\s*=\s*'[^']*'", body))
    anon_email = bool(re.search(r"email\s*=\s*null", body, re.I))
    out.append(("OK" if (anon_name and anon_email) else "FAIL",
                f"anonymizes PII (display_name set + email NULLed: name={anon_name} email={anon_email})"))

    deletes = [t for t in OPERATIONAL if re.search(rf"delete\s+from\s+(public\.)?{t}\b", body, re.I)]
    out.append(("FAIL", f"DESTROYS operational records: DELETE FROM {deletes}") if deletes
               else ("OK", "preserves operational records (no DELETE FROM logbook/PM/calcs/inventory)"))

    revokes_access = bool(re.search(r"hive_members[\s\S]{0,80}status\s*=", body, re.I))
    out.append(("OK" if revokes_access else "FAIL", "revokes hive access (hive_members.status updated)"))

    # ★ The status value the fn writes MUST be allowed by a CHECK constraint declared in this migration.
    # (Caught live 2026-06-21: hive_members_status_check allowed only active/kicked, so 'deactivated'
    # violated it — the static gate now requires the migration to self-contain the constraint extension.)
    sval = re.search(r"hive_members[\s\S]{0,80}status\s*=\s*'([a-z_]+)'", body, re.I)
    sv = sval.group(1) if sval else None
    constraint_ok = (sv is None) or bool(re.search(rf"CHECK\s*\([^)]*'{re.escape(sv)}'", sql, re.I))
    out.append(("OK" if constraint_ok else "FAIL",
                f"status value '{sv}' is permitted by a CHECK constraint in this migration "
                f"(no post-baseline constraint violation)"))

    definer = "security definer" in body.lower()
    search_path = bool(re.search(r"set\s+search_path", body, re.I))
    out.append(("OK" if (definer and search_path) else "FAIL",
                f"hardened: SECURITY DEFINER={definer} + SET search_path={search_path} (CVE-2018-1058)"))

    # grants are outside the $$ body — check the whole migration around the fn
    revoke_public = bool(re.search(rf"REVOKE[\s\S]*{re.escape(FN)}[\s\S]*FROM\s+PUBLIC", sql, re.I)
                         or re.search(rf"REVOKE[\s\S]*FROM\s+PUBLIC", sql, re.I))
    grant_authed = bool(re.search(rf"GRANT\s+EXECUTE\s+ON\s+FUNCTION[\s\S]*{re.escape(FN)}[\s\S]*TO[\s\S]*(authenticated|service_role)", sql, re.I))
    out.append(("OK" if (revoke_public and grant_authed) else "FAIL",
                f"grants: REVOKE PUBLIC={revoke_public} + GRANT authenticated/service_role={grant_authed} (PUBLIC-default blind spot)"))
    return out, body


def _load_migration() -> str:
    for p in sorted(MIGRATIONS.glob("*account_deactivation*.sql")):
        return p.read_text(encoding="utf-8", errors="replace")
    # fallback: any migration defining the fn
    for p in MIGRATIONS.glob("*.sql"):
        t = p.read_text(encoding="utf-8", errors="replace")
        if FN in t:
            return t
    return ""


def _self_test() -> int:
    bad = """
    CREATE OR REPLACE FUNCTION public.deactivate_my_account(p_user_id uuid) RETURNS void
    LANGUAGE plpgsql AS $$ BEGIN
      DELETE FROM public.logbook WHERE auth_uid = p_user_id;
    END; $$;
    """
    good = """
    ALTER TABLE public.hive_members ADD CONSTRAINT hive_members_status_check
      CHECK (status IN ('active','kicked','deactivated'));
    CREATE OR REPLACE FUNCTION public.deactivate_my_account() RETURNS void
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    DECLARE uid uuid := auth.uid(); BEGIN
      UPDATE public.worker_profiles SET display_name='Deleted user', email=NULL WHERE auth_uid=uid;
      UPDATE public.hive_members SET status='deactivated' WHERE auth_uid=uid;
    END; $$;
    REVOKE ALL ON FUNCTION public.deactivate_my_account() FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.deactivate_my_account() TO authenticated, service_role;
    """
    bad_fails = any(s == "FAIL" for s, _ in audit(bad)[0])
    good_passes = not any(s == "FAIL" for s, _ in audit(good)[0])
    ok = bad_fails and good_passes
    print(f"  self-test: bad(IDOR+DELETE)→FAIL={bad_fails}  good→clean={good_passes}  {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--self-test" in sys.argv[1:]:
        return _self_test()
    sql = _load_migration()
    if not sql:
        print(f"{RED}FAIL{RST} — no migration defines {FN}()")
        return 1
    findings, _ = audit(sql)
    fails = [m for s, m in findings if s == "FAIL"]
    print("=" * 74)
    print("  validate_account_deactivation — Arc I I8/I (GDPR/PDPA soft-deactivate + anonymize)")
    print("=" * 74)
    for sev, msg in findings:
        c = GREEN if sev == "OK" else RED
        print(f"  {c}{sev:<4}{RST} {msg}")
    print("-" * 74)
    if fails:
        print(f"  {RED}FAIL{RST} — {len(fails)} offboarding-safety violation(s)")
        return 1
    print(f"  {GREEN}PASS{RST} — self-scoped anonymize + access-revoke; operational history preserved; hardened")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
