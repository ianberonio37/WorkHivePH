#!/usr/bin/env python3
"""validate_definer_doors.py - BRH S, Q and Y (2026-10-21): no door into the database stands open to anyone holding the
site's public key.

Supabase's security advisor (emailed 2026-10-20) listed 94 SECURITY DEFINER functions the anon role could execute in
production. Two kinds needed nothing but the public key to do harm: ten hand-made debug_* functions no migration
creates (one returned the ten highest-level workers' names and account ids to anyone), and six server-only writers whose
bodies check no caller (enqueue_user_push queued a Web Push to any account with any link; consume_ai_global_budget spent
the platform's daily AI budget). 20261015500000_brh_close_anon_doors closed them in production the same day. And the
measurement found why such doors reopen: Supabase grants EXECUTE to anon EXPLICITLY on every new function, so
`revoke ... from public` never reaches it, and a DROP + CREATE restores the defaults (enqueue_user_push had been closed
on 2026-08-03 and reopened by its own re-creation on 2026-09-01).

LIVE (the local database, read-only):
  Q1  no public function named debug_* exists
  S1  the server-only functions refuse anon and authenticated, and the service role keeps them
  S2  every SECURITY DEFINER function anon may execute is accounted for: a trigger function (the API cannot call one),
      a body that asks who is calling, or a declared signed-out entry point - or it is one of the S rows still to walk
      (definer_doors_baseline.json); a NEW undeclared one fails
  Y1  every function a migration closed to anon (or to PUBLIC) refuses anon - or it is one of the Y rows still to walk
      (the baseline); a function closed in a migration and open again fails
The baseline may only shrink: `--rebase` writes the current open sets, and refuses to add to them.
SELF-TEST (--self-test), each in a transaction that is rolled back: anon granted EXECUTE on enqueue_user_push (S1), a
debug_ function created (Q1), an undeclared anon-executable definer function created (S2), and anon re-granted a
function a migration revoked that the baseline does not list (Y1). Each must fail the check.

    python tools/validate_definer_doors.py [--self-test] [--rebase] [--json]
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
DB = "supabase_db_workhive"
MIG = ROOT / "supabase" / "migrations"
BASELINE = ROOT / "definer_doors_baseline.json"
# every caller is the service role (edge functions' service-role clients) or another SECURITY DEFINER function
SERVER_ONLY = ("enqueue_user_push", "consume_ai_global_budget", "ai_cache_bump", "ai_cache_sweep_expired",
               "prune_embedding_cache", "record_ai_chain_depth")
# signed-out entry points: a page a visitor opens calls them, and each returns only facts the platform shows the public
SIGNED_OUT = {
    "check_username_available": "sign-up asks whether a username is free before an account exists",
    "increment_listing_view": "a visitor opening a public listing counts one view",
}
CALLER_CHECK = re.compile(r"auth\.uid\(\)|auth\.role\(\)|is_platform_admin|user_can_access_hive|is_hive_member|"
                          r"auth_worker_names|current_setting\('request\.jwt|hive_members|raise\s+exception", re.I)
REVOKE = re.compile(r"\brevoke\s+(?:all|execute)(?:\s+privileges)?\s+on\s+(?:function|routine)\s+(?:public\.)?"
                    r"([a-z_][a-z0-9_]*)\s*\(([^)]*)\)\s+from\s+([a-z_, ]+)", re.I)


def psql(sql: str) -> tuple[int, str, str]:
    r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres", "-At", "-v",
                        "ON_ERROR_STOP=1"], input=sql, capture_output=True, text=True, encoding="utf-8", timeout=300)
    return r.returncode, r.stdout, r.stderr


def strip_sql(sql: str) -> str:
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"--[^\n]*", " ", sql)


def revoked_in_migrations() -> set[str]:
    out = set()
    for f in sorted(MIG.glob("*.sql")):
        for m in REVOKE.finditer(strip_sql(f.read_text(encoding="utf-8", errors="replace"))):
            if {r.strip().lower() for r in m.group(3).split(",")} & {"anon", "public"}:
                out.add(m.group(1).lower())
    return out


STATE_SQL = """
select 'F' || chr(1) || p.proname || chr(1) || pg_get_function_identity_arguments(p.oid) || chr(1) || p.prosecdef::text
       || chr(1) || has_function_privilege('anon', p.oid, 'execute')::text
       || chr(1) || has_function_privilege('authenticated', p.oid, 'execute')::text
       || chr(1) || has_function_privilege('service_role', p.oid, 'execute')::text
       || chr(1) || p.prorettype::regtype::text || chr(1) || case when p.prosecdef then pg_get_functiondef(p.oid) else '' end
       || chr(2)
from pg_proc p join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.prokind = 'f';
"""


def state(prefix_sql: str = "") -> list[dict] | str:
    """Every public function as the roles see it. prefix_sql runs first inside the same rolled-back transaction (the
    self-test's mutants)."""
    sql = "begin;\n" + prefix_sql + "\n" + STATE_SQL + "\nrollback;\n"
    code, out, err = psql(sql)
    if code:
        return f"could not read the functions: {(err or out).strip()[-300:]}"
    fns = []
    for chunk in out.split("\x02"):
        chunk = chunk.strip()
        if not chunk.startswith("F\x01"):
            j = chunk.find("F\x01")
            if j < 0:
                continue
            chunk = chunk[j:]
        _, name, args, definer, anon, auth, svc, rtype, body = chunk.split("\x01", 8)
        fns.append({"name": name, "args": args, "definer": definer == "true", "anon": anon == "true",
                    "authenticated": auth == "true", "service_role": svc == "true", "trigger": rtype == "trigger",
                    "checks_caller": bool(CALLER_CHECK.search(body))})
    return fns


def judge(fns: list[dict], revoked: set[str], base: dict) -> tuple[list[str], dict]:
    issues = []
    for f in fns:
        if f["name"].startswith("debug_"):
            issues.append(f"Q1 public.{f['name']}({f['args']}) exists - a hand-made debug function no product path "
                          f"calls; production held ten, one returning workers' names and account ids to anyone")
    for name in SERVER_ONLY:
        for f in (x for x in fns if x["name"] == name):
            if f["anon"] or f["authenticated"]:
                issues.append(f"S1 public.{name}({f['args']}) is executable by "
                              f"{'anon' if f['anon'] else 'authenticated'} - it is server-only (every caller is the "
                              f"service role or another definer function) and checks no caller")
            if not f["service_role"]:
                issues.append(f"S1 public.{name}({f['args']}) refuses the service role - its callers would break")
    s2_open = sorted({f["name"] for f in fns if f["definer"] and f["anon"] and not f["trigger"] and not f["checks_caller"]
                      and f["name"] not in SIGNED_OUT and f["name"] not in SERVER_ONLY
                      and not f["name"].startswith("debug_")})
    for n in s2_open:
        if n not in set(base.get("S2_open", [])):
            issues.append(f"S2 public.{n}() is SECURITY DEFINER, anon may execute it, and its body checks no caller - "
                          "close it to anon, make it ask who is calling, or declare it a signed-out entry point "
                          "with its reason")
    y1_open = sorted({f["name"] for f in fns if f["anon"] and f["name"] in revoked})
    for n in y1_open:
        if n not in set(base.get("Y1_open", [])) and n not in set(s2_open):
            issues.append(f"Y1 public.{n}() was closed to anon by a migration and anon can execute it again - a revoke "
                          "from PUBLIC does not reach anon on Supabase, and a DROP + CREATE restores the defaults")
    return issues, {"S2_open": s2_open, "Y1_open": sorted(set(y1_open) - set(s2_open))}


def load_base() -> dict:
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run(prefix_sql: str = "") -> tuple[list[str], dict]:
    fns = state(prefix_sql)
    if isinstance(fns, str):
        return [f"LIVE {fns}"], {}
    return judge(fns, revoked_in_migrations(), load_base())


def self_test() -> list[str]:
    fails = []
    clean, _ = run()
    if clean:
        fails.append(f"the clean run is not green: {clean[:2]}")
    mutants = [
        ("anon re-granted a server-only writer",
         "grant execute on function public.enqueue_user_push(uuid[], text, text, text, text) to anon;", "S1"),
        ("a hand-made debug function", "create function public.debug_selftest() returns int language sql as 'select 1';", "Q1"),
        ("an undeclared anon-executable definer that asks no one",
         "create function public.wh_selftest_open() returns int language sql security definer as 'select 1'; "
         "grant execute on function public.wh_selftest_open() to anon;", "S2"),
        ("anon re-granted a function a migration closed",
         "grant execute on function public.my_recent_xp(integer) to anon;", "Y1"),
    ]
    for name, sql, want in mutants:
        got, _ = run(sql)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")
    return fails


def main() -> int:
    as_json = "--json" in sys.argv
    if "--self-test" in sys.argv:
        fails = self_test()
        print(json.dumps({"self_test": "FAIL" if fails else "PASS", "fails": fails}, indent=1) if as_json else
              ("SELF-TEST PASS (4 live mutants caught in rolled-back transactions; the clean run is green)"
               if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails)))
        return 1 if fails else 0
    issues, now = run()
    if "--rebase" in sys.argv:
        base = load_base()
        grew = {k: sorted(set(now.get(k, [])) - set(base.get(k, []))) for k in ("S2_open", "Y1_open")} if base else {}
        if any(grew.values()):
            print(f"refused: the open sets would GROW {grew} - close those, do not baseline them")
            return 1
        BASELINE.write_text(json.dumps({"note": "BRH S and Y rows still to walk (2026-10-21) - may only shrink", **now},
                                       indent=1) + "\n", encoding="utf-8")
        print(f"baseline written: S2 {len(now['S2_open'])} · Y1 {len(now['Y1_open'])}")
        return 0
    if as_json:
        print(json.dumps({"validator": "definer_doors", "status": "FAIL" if issues else "PASS", "issues": issues,
                          "open": now}, indent=1))
    else:
        print("Definer doors (BRH S/Q/Y): nothing in the database stands open to anyone holding the public key")
        for i in issues:
            print("  [FAIL] " + i)
        print(f"  PASS - no debug function; the {len(SERVER_ONLY)} server-only writers refuse anon and authenticated; "
              f"{len(now.get('S2_open', []))} S and {len(now.get('Y1_open', []))} Y functions still to walk (baselined)"
              if not issues else f"  FAIL - {len(issues)} problem(s)")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
