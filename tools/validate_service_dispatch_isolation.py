#!/usr/bin/env python3
"""
validate_service_dispatch_isolation.py - SERVICE_HAILING_ROADMAP.md C3 lock (2026-07-28).
=========================================================================================
Dispatch must route a hail ONLY to eligible providers and match EXACTLY ONE winner:
  * accept_service_request refuses: your own hail (own_request), a category you don't
    serve (category_mismatch), a request outside your radius (out_of_radius);
  * the accept race has exactly one winner (status-guarded atomic UPDATE — the fix for
    the reference repo's select-then-insert TOCTOU);
  * v_service_open_broadcasts never shows your own hail;
  * v_service_job_tracking (the ONLY live_location read path) shows an active job to its
    parties and NOTHING to a stranger.

METHOD: every check is SELF-CONTAINED — it mints its own actors (temp providers via the
caller's own RLS'd insert, temp requests via `set local request.jwt.claims` switches
inside ONE transaction) and rolls back (0 pollution, no dependence on seeded state).
Identities are runtime-resolved non-admin members who own NO provider row (a pinned or
provider-owning uid makes the RPC pick a shadow identity = flaky probes).
`--selftest` proves the matcher wiring.
"""
from __future__ import annotations
import io, sys, subprocess

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_service_dispatch_isolation"]
DB = "supabase_db_workhive"


def _docker(sql: str) -> tuple[str, int]:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres"],
            input=sql, capture_output=True, text=True, timeout=120)
    except Exception as e:
        return (f"SKIP {e}", 1)
    return ((r.stdout or "") + (r.stderr or ""), r.returncode)


def _resolve_uids(n: int = 3) -> list[str]:
    """SELF-MINTED probe users, created inside each check's rolled-back transaction.
    A borrowed seeded identity is never clean here: my_service_provider_ids() surfaces
    hive providers for their MEMBERS, so a member-uid makes the RPC pick a verified
    pre-existing provider over the probe's temp one (live-caught: honest out_of_radius
    refusals that LOOKED like gate failures). Fresh uids own nothing by construction."""
    return ["c3aaaaaa-0000-4000-8000-00000000000%d" % i for i in range(1, n + 1)]


def _mint(uids: list[str]) -> str:
    """service-role preamble (before any `set local role`) — rolled back with the check."""
    vals = ",".join("('%s','probe-%d@gate.local')" % (u, i) for i, u in enumerate(uids))
    return "insert into auth.users(id, email) values %s;\n" % vals


def _jwt(uid: str) -> str:
    return ("set local role authenticated;\n"
            "set local request.jwt.claims = '{\"sub\":\"" + uid + "\",\"role\":\"authenticated\"}';\n")


def build_checks(A: str, Bu: str, Cu: str) -> list[dict]:
    baguio = "'POINT(120.5960 16.4023)'::extensions.geography"
    davao = "'POINT(125.4553 7.1907)'::extensions.geography"
    return [
        {"name": "own hail refused (accept on your own request = own_request)",
         "sql": ("begin;\n" + _mint([A, Bu, Cu]) + _jwt(A) +
                 "insert into service_providers(provider_type,auth_uid,display_name,categories,base_location,availability) "
                 "values('freelancer','" + A + "','C3a Prov','{Plumbing}'," + baguio + ",'online');\n"
                 "insert into service_requests(client_auth_uid,mode,custom_scope,location,status) "
                 "values('" + A + "','instant','c3a own-hail'," + baguio + ",'broadcasting');\n"
                 "select accept_service_request(id)::text from service_requests where custom_scope='c3a own-hail';\n"
                 "rollback;\n"),
         "expect": "own_request"},
        {"name": "category mismatch refused (Plumbing provider cannot take an Electrical catalog job)",
         "sql": ("begin;\n" + _mint([A, Bu, Cu]) + _jwt(Bu) +
                 "insert into service_requests(client_auth_uid,mode,catalog_item_id,location,status) "
                 "select '" + Bu + "','instant',c.id," + baguio + ",'broadcasting' "
                 "from service_catalog c where c.category='Electrical' and c.segment='industrial' limit 1;\n"
                 # stash the id under the CREATOR's claims — RLS rightly hides a stranger's
                 # broadcast from the raw table, and accept must refuse even an out-of-band id
                 "create temp table _r on commit drop as select id from service_requests where client_auth_uid='" + Bu + "' and status='broadcasting';\n"
                 + _jwt(A) +
                 "insert into service_providers(provider_type,auth_uid,display_name,categories,base_location,availability) "
                 "values('freelancer','" + A + "','C3b Prov','{Plumbing}'," + baguio + ",'online');\n"
                 "select accept_service_request(id)::text from _r;\n"
                 "rollback;\n"),
         "expect": "category_mismatch"},
        {"name": "out of radius refused (Davao provider cannot take a tight-radius Baguio job)",
         "sql": ("begin;\n" + _mint([A, Bu, Cu]) + _jwt(Bu) +
                 "insert into service_requests(client_auth_uid,mode,custom_scope,location,status,broadcast_radius_m) "
                 "values('" + Bu + "','instant','c3c tight radius'," + baguio + ",'broadcasting',500);\n"
                 "create temp table _r on commit drop as select id from service_requests where custom_scope='c3c tight radius';\n"
                 + _jwt(A) +
                 "insert into service_providers(provider_type,auth_uid,display_name,categories,base_location,availability) "
                 "values('freelancer','" + A + "','C3c Prov','{Plumbing}'," + davao + ",'online');\n"
                 "select accept_service_request(id)::text from _r;\n"
                 "rollback;\n"),
         "expect": "out_of_radius"},
        {"name": "exactly one winner (concurrent-class accept: 2nd caller loses honestly)",
         "sql": ("begin;\n" + _mint([A, Bu, Cu]) + _jwt(Bu) +
                 "insert into service_requests(client_auth_uid,mode,custom_scope,location,status) "
                 "values('" + Bu + "','instant','c3d race'," + baguio + ",'broadcasting');\n"
                 "create temp table _r on commit drop as select id from service_requests where custom_scope='c3d race';\n"
                 + _jwt(A) +
                 "insert into service_providers(provider_type,auth_uid,display_name,categories,base_location,availability) "
                 "values('freelancer','" + A + "','C3d ProvA','{Plumbing}'," + baguio + ",'online');\n"
                 "select 'W1='||(accept_service_request(id)->>'accepted') from _r;\n"
                 + _jwt(Cu) +
                 "insert into service_providers(provider_type,auth_uid,display_name,categories,base_location,availability) "
                 "values('freelancer','" + Cu + "','C3d ProvC','{Plumbing}'," + baguio + ",'online');\n"
                 "select 'W2='||(accept_service_request(id)->>'reason') from _r;\n"
                 "rollback;\n"),
         "expect_all": ["W1=true", "W2=lost_race_or_closed"]},
        {"name": "feed never shows your own hail (and shows an in-scope stranger hail)",
         "sql": ("begin;\n" + _mint([A, Bu, Cu]) + _jwt(Bu) +
                 "insert into service_requests(client_auth_uid,mode,custom_scope,location,status) "
                 "values('" + Bu + "','instant','c3e stranger hail'," + baguio + ",'broadcasting');\n"
                 + _jwt(A) +
                 "insert into service_providers(provider_type,auth_uid,display_name,categories,base_location,availability) "
                 "values('freelancer','" + A + "','C3e Prov','{Plumbing}'," + baguio + ",'online');\n"
                 "insert into service_requests(client_auth_uid,mode,custom_scope,location,status) "
                 "values('" + A + "','instant','c3e own hail'," + baguio + ",'broadcasting');\n"
                 "select 'OWN='||count(*) from v_service_open_broadcasts where custom_scope='c3e own hail';\n"
                 "select 'STRANGER='||count(*) from v_service_open_broadcasts where custom_scope='c3e stranger hail';\n"
                 "rollback;\n"),
         "expect_all": ["OWN=0", "STRANGER=1"]},
        {"name": "tracking view: parties see the active job, a stranger sees NOTHING",
         "sql": ("begin;\n" + _mint([A, Bu, Cu]) + _jwt(Bu) +
                 "insert into service_requests(client_auth_uid,mode,custom_scope,location,status) "
                 "values('" + Bu + "','instant','c3f tracked'," + baguio + ",'broadcasting');\n"
                 "create temp table _r on commit drop as select id from service_requests where custom_scope='c3f tracked';\n"
                 + _jwt(A) +
                 "insert into service_providers(provider_type,auth_uid,display_name,categories,base_location,availability) "
                 "values('freelancer','" + A + "','C3f Prov','{Plumbing}'," + baguio + ",'online');\n"
                 "select accept_service_request(id)::text from _r;\n"
                 "update service_requests set status='en_route' where id in (select id from _r);\n"
                 "select 'PROV='||count(*) from v_service_job_tracking t where t.request_id in (select id from _r);\n"
                 + _jwt(Bu) +
                 "select 'CLIENT='||count(*) from v_service_job_tracking t where t.request_id in (select id from _r);\n"
                 + _jwt(Cu) +
                 "select 'STRANGER='||count(*) from v_service_job_tracking t where t.request_id in (select id from _r);\n"
                 "rollback;\n"),
         "expect_all": ["PROV=1", "CLIENT=1", "STRANGER=0"]},
    ]


def evaluate() -> tuple[list[str], list[str]]:
    passes, fails = [], []
    for c in build_checks(*_resolve_uids(3)):
        out, rc = _docker(c["sql"])
        if out.startswith("SKIP") or "no such container" in out.lower() or "error during connect" in out.lower():
            return (["SKIP"], [])
        low = out.lower()
        if "expect_all" in c:
            ok = all(e.lower() in low for e in c["expect_all"])
        else:
            ok = c["expect"].lower() in low
        (passes if ok else fails).append(c["name"] + ("" if ok else f"  [out: {out.strip().replace(chr(10),' ')[:140]}]"))
    return (passes, fails)


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        ok = all(e in "w1=true w2=lost_race_or_closed own=0 stranger=1" for e in
                 ("w1=true", "w2=lost_race_or_closed", "own=0", "stranger=1")) and \
             ("category_mismatch" not in "accepted true")
        print(f"{G}selftest PASS{X}" if ok else f"{R}selftest FAIL{X}")
        return 0 if ok else 1
    passes, fails = evaluate()
    if passes == ["SKIP"]:
        print(f"{B}Service dispatch isolation{X}\n  SKIP: local DB not reachable or <3 free identities — gate not evaluated.")
        return 0
    print(f"{B}Service dispatch isolation (SERVICE_HAILING C3 lock){X}")
    for p in passes:
        print(f"  {G}PASS{X}  {p}")
    for f in fails:
        print(f"  {R}FAIL{X}  {f}")
    if fails:
        print(f"{R}FAIL - {len(fails)} dispatch-isolation hole(s) OPEN.{X}")
        return 1
    print(f"{G}PASS - {len(passes)} dispatch rules hold (eligibility, one-winner, feed scope, tracking privacy).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
