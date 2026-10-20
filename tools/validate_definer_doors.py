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
               "prune_embedding_cache", "record_ai_chain_depth",
               # BRH-S (20261015950000, 20261021000005): no page or edge function calls these, or the page now reads an
               # owner-checked twin (my_provider_credit_balance, my_service_request_price); every SQL caller is definer
               "redeem_service_voucher", "rerank_kb_chunks", "service_agreed_base", "service_objection_deadline",
               "sync_pm_asset_identity", "photo_attach_stats", "provider_credit_balance", "service_request_price")
# signed-out entry points: a page a visitor opens calls them (or a policy anon is evaluated against does), and each
# returns only facts the platform shows the public. A declaration no page or policy uses any more fails as stale (S3).
SIGNED_OUT = {
    "check_username_available": "sign-up asks whether a username is free before an account exists",
    "increment_listing_view": "a visitor opening a public listing counts one view",
    "get_marketplace_price_comps": "the public marketplace shows price comparisons from published and sold listings",
    "get_marketplace_seller_public": "the public seller profile - a projection that names no contact, hive or account",
    "get_marketplace_trust_badges": "the public listing cards show each seller's trust tier",
    "listing_reservation_amount": "the public marketplace states a listing's reservation: arithmetic on its price",
    "service_knob": "the marketplace's published service terms (offer and quote windows, broadcast radius)",
    "service_knob_pct": "the marketplace's published percentages (commission, listing fee, cashback)",
    "semantic_search_industry_standards": "the voice companion's public reference: published industry standards",
    "semantic_search_platform_kg_facts": "the voice companion's public reference: the published knowledge graph",
    "seller_has_published_listing": "an anon row policy on marketplace_sellers and the public sellers view ask it",
}
POLICY_ONLY_SIGNED_OUT = {"seller_has_published_listing"}
# functions anon must keep: a row policy or security_invoker view anon is evaluated against calls them, so without anon's
# EXECUTE a signed-out read of those tables fails with permission denied instead of returning nothing. Each answers false
# or empty for a caller with no account (read through the local API as a visitor, 2026-10-21). A declaration that no
# anon-evaluated policy or anon-readable invoker view needs any more fails as stale.
POLICY_HELPERS = {
    "is_platform_admin": "admin branches of row policies anon is evaluated against; false for no account",
    "listing_is_mine": "the marketplace listings' owner policies; false for no account",
    "order_is_mine": "the marketplace orders' party policy; false for no account",
    "my_listing_ids": "v_marketplace_listings_truth (security_invoker) scopes the seller's own rows; empty for no account",
    "my_inquiry_ids": "v_marketplace_inquiries_truth (security_invoker); empty for no account",
    "user_hive_worker_names": "the personal-achievements policy; empty for no account",
    "user_supervisor_hive_ids": "the supervisor branches of hive policies; empty for no account",
}
Y_FIX = "20261015900000_brh_y_revokes_that_hold.sql"
REVOKE_PUBLIC = re.compile(r"\brevoke\s+(?:all|execute)(?:\s+privileges)?\s+on\s+(?:function|routine)\s+(?:public\.)?"
                           r"([a-z_][a-z0-9_]*)\s*\(([^)]*)\)\s+from\s+([a-z_, ]+)", re.I)
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
       || chr(1) || exists (select 1 from unnest(coalesce(p.proconfig, '{}'::text[])) c where c like 'search_path=%')::text
       || chr(1) || exists (select 1 from pg_depend d where d.classid = 'pg_proc'::regclass and d.objid = p.oid
                            and d.deptype = 'e')::text
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
        _, name, args, definer, anon, auth, svc, pinned, ext, rtype, body = chunk.split("\x01", 10)
        fns.append({"name": name, "args": args, "definer": definer == "true", "anon": anon == "true",
                    "authenticated": auth == "true", "service_role": svc == "true", "trigger": rtype == "trigger",
                    "pinned": pinned == "true", "extension": ext == "true",
                    "checks_caller": bool(CALLER_CHECK.search(body))})
    return fns


def judge(fns: list[dict], revoked: set[str], base: dict) -> tuple[list[str], dict]:
    issues = []
    # T1 (BRH-T): a function that resolves names through the CALLER's search_path lets a caller stand a temporary object
    # in for the one its body means; every public function outside an extension sets its own
    for f in fns:
        if not f["pinned"] and not f["extension"]:
            issues.append(f"T1 public.{f['name']}({f['args'][:60]}) sets no search_path of its own - pin it "
                          f"(set search_path = public, extensions, pg_temp, or '' with every name qualified)")
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
    # a function DECLARED for anon (a signed-out entry point or a policy helper) is anon's on purpose, whatever an older
    # migration once revoked (seller_has_published_listing: revoked in one migration, opened to visitors in a later one)
    y1_open = sorted({f["name"] for f in fns if f["anon"] and f["name"] in revoked and f["name"] not in POLICY_HELPERS
                      and f["name"] not in SIGNED_OUT})
    for n in y1_open:
        if n not in set(base.get("Y1_open", [])) and n not in set(s2_open):
            issues.append(f"Y1 public.{n}() was closed to anon by a migration and anon can execute it again - a revoke "
                          "from PUBLIC does not reach anon on Supabase, and a DROP + CREATE restores the defaults")
    return issues, {"S2_open": s2_open, "Y1_open": sorted(set(y1_open) - set(s2_open))}


def helper_uses() -> dict[str, int] | str:
    """How many anon-evaluated row policies and anon-readable security_invoker views call each declared helper."""
    names = "|".join(re.escape(n) for n in POLICY_HELPERS)
    code, out, err = psql(
        "select x.m[1] || '|' || count(*)::text from (select regexp_matches(coalesce(qual, '') || ' ' || coalesce(with_check, ''), "
        f"'\\m({names})\\s*\\(', 'g') as m from pg_policies where schemaname = 'public' and roles && "
        "array['public', 'anon']::name[] union all select regexp_matches(pg_get_viewdef(c.oid), "
        f"'\\m({names})\\s*\\(', 'g') from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = "
        "'public' and c.relkind = 'v' and has_table_privilege('anon', c.oid, 'select') and coalesce(array_to_string("
        "c.reloptions, ','), '') ~ 'security_invoker=(true|on)') x group by x.m[1];")
    if code:
        return f"could not read the policies: {(err or out).strip()[-200:]}"
    return {ln.split("|")[0]: int(ln.split("|")[1]) for ln in out.splitlines() if "|" in ln}


def check_helpers() -> list[str]:
    uses = helper_uses()
    if isinstance(uses, str):
        return [f"Y3 LIVE {uses}"]
    issues = [f"Y3 {n} is declared a policy helper anon must keep, and no anon-evaluated policy or anon-readable invoker "
              f"view calls it any more - close it to anon (the declaration is stale)" for n in POLICY_HELPERS if not uses.get(n)]
    # S3: a declared signed-out entry point some page (or, for the policy-backed one, a policy) still calls
    front = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                      for p in list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")) + list(ROOT.glob("*/index.html")))
    for n in SIGNED_OUT:
        if n in POLICY_ONLY_SIGNED_OUT:
            code, out, _ = psql(f"select count(*) from pg_policies where schemaname = 'public' and "
                                f"(coalesce(qual, '') || coalesce(with_check, '')) ~ '\\m{n}\\s*\\(';")
            if code == 0 and out.strip() == "0":
                issues.append(f"S3 {n} is declared a signed-out entry point for a policy, and no policy calls it any more")
        elif not re.search(r"""rpc\(\s*['"]%s['"]""" % re.escape(n), front):
            issues.append(f"S3 {n} is declared a signed-out entry point, and no page or shared script calls it any more - "
                          "close it to anon (the declaration is stale)")
    return issues


def check_revokes(migs: list[tuple[str, str]] | None = None) -> list[str]:
    """Y2: from the Y fix on, a migration that revokes a function from PUBLIC names anon too - or grants anon explicitly,
    which says it means anon to keep it."""
    files = migs if migs is not None else [(f.name, f.read_text(encoding="utf-8", errors="replace"))
                                           for f in sorted(MIG.glob("*.sql"))]
    issues = []
    for name, text in files:
        if name <= Y_FIX:
            continue
        t = strip_sql(text)
        for m in REVOKE_PUBLIC.finditer(t):
            roles = {r.strip().lower() for r in m.group(3).split(",")}
            fn = m.group(1).lower()
            if "public" in roles and "anon" not in roles and not re.search(
                    r"\bgrant\s+(?:all|execute)[^;]*\bfunction\s+(?:public\.)?" + re.escape(fn) + r"\s*\([^;]*\bto\b[^;]*\banon\b", t, re.I):
                issues.append(f"Y2 {name}: revokes public.{fn}() from PUBLIC but not from anon - Supabase grants anon EXECUTE "
                              "explicitly on every new function, so this revoke never reaches it; name anon (or grant anon "
                              "explicitly to say it keeps it)")
    return issues


def load_base() -> dict:
    try:
        return json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def run(prefix_sql: str = "") -> tuple[list[str], dict]:
    fns = state(prefix_sql)
    if isinstance(fns, str):
        return [f"LIVE {fns}"], {}
    issues, now = judge(fns, revoked_in_migrations(), load_base())
    if not prefix_sql:
        issues += check_helpers() + check_revokes()
    return issues, now


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
        ("a function that takes the caller's search_path",
         "create function public.wh_selftest_unpinned() returns int language sql as 'select 1';", "T1"),
    ]
    for name, sql, want in mutants:
        got, _ = run(sql)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")
    # Y2 static: a later migration that revokes a function from PUBLIC only
    bad = [("29991231000000_selftest.sql", "revoke all on function public.my_recent_xp(integer) from public;\n"
                                           "grant execute on function public.my_recent_xp(integer) to authenticated;")]
    if not any(i.startswith("Y2") for i in check_revokes(bad)):
        fails.append("mutant 'a revoke from PUBLIC that leaves anon' was not caught (Y2)")
    ok = [("29991231000000_selftest.sql", "revoke all on function public.my_recent_xp(integer) from public, anon;")]
    if check_revokes(ok):
        fails.append("a revoke that names anon was flagged (Y2 false positive)")
    return fails


def main() -> int:
    as_json = "--json" in sys.argv
    if "--self-test" in sys.argv:
        fails = self_test()
        print(json.dumps({"self_test": "FAIL" if fails else "PASS", "fails": fails}, indent=1) if as_json else
              ("SELF-TEST PASS (5 live mutants caught in rolled-back transactions and the Y2 static mutant; the clean run is green)"
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
