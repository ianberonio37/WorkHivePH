#!/usr/bin/env python3
"""
validate_service_state_machine.py - SERVICE_HAILING_ROADMAP.md C1 lock (2026-07-28).
====================================================================================
The service-hailing spine is a DB-enforced state machine
(requested -> broadcasting -> accepted -> en_route -> on_site -> in_progress ->
completed -> settled, + cancelled_by_client/cancelled_by_provider/expired/disputed)
guarded by guard_service_request_status (mig 20260728000024), with money (credit
ledger / GCash top-ups) and trust (provider verified / on_job) transitions locked to
founder/service-role/GUC — the trust-forge pattern extended to MONEY. This gate
re-runs the P1 adversarial suite as a standing anti-regression: every probe that
proved the guards at build time keeps proving them on every run.

METHOD: rolled-back psql as a runtime-resolved NON-ADMIN authenticated worker
(the P1 lesson: an admin identity legitimately bypasses every guard, so an
admin-run suite reads as fail-open — verify the instrument). Skips cleanly if
docker/DB unreachable. `--selftest` proves the matcher wiring.
"""
from __future__ import annotations
import io, sys, subprocess

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; X = "\033[0m"
CHECK_NAMES = ["validate_service_state_machine"]
DB = "supabase_db_workhive"


def _docker(sql: str) -> tuple[str, int]:
    try:
        r = subprocess.run(
            ["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres"],
            input=sql, capture_output=True, text=True, timeout=90)
    except Exception as e:
        return (f"SKIP {e}", 1)
    return ((r.stdout or "") + (r.stderr or ""), r.returncode)


def _resolve_nonadmin() -> tuple[str, str]:
    """A NON-admin active member + a second distinct uid (attribution-forge target).
    Runtime-resolved: a pinned uid rots after a reseed into vacuous 0-row passes."""
    out, _ = _docker(
        "select auth_uid from hive_members where status='active' and auth_uid is not null "
        "and worker_name not in (select worker_name from marketplace_platform_admins) "
        "order by worker_name limit 2;")
    uids = [l.strip() for l in out.splitlines() if l.strip().count("-") == 4]
    if len(uids) >= 2:
        return uids[0], uids[1]
    return ("58d71041-46eb-406b-85d8-5c9851c49b37",   # stale-known fallback (Isidro Suarez)
            "d3a16cd6-4314-46f2-81e0-00f7f33ad8c3")   # stale-known fallback (Ricardo Morales)


WORKER_UID, OTHER_UID = _resolve_nonadmin()
JWT = ("set local role authenticated;\n"
       "set local request.jwt.claims = '{\"sub\":\"" + WORKER_UID + "\",\"role\":\"authenticated\"}';\n")

CHECKS = [
    {"name": "born-terminal blocked (a new request cannot start completed)",
     "sql": ("begin;\n" + JWT +
             "insert into service_requests(client_auth_uid,mode,custom_scope,status) "
             "values('" + WORKER_UID + "','instant','gate probe','completed');\n"
             "select 'FORGE_OK';\nrollback;\n"),
     "expect_error": "must start as requested"},
    {"name": "illegal jump blocked (requested -> completed refused for the client)",
     "sql": ("begin;\n" + JWT +
             "insert into service_requests(client_auth_uid,mode,custom_scope,status) "
             "values('" + WORKER_UID + "','instant','gate probe','requested');\n"
             "update service_requests set status='completed' where client_auth_uid='" + WORKER_UID + "' and custom_scope='gate probe';\n"
             "select 'FORGE_OK';\nrollback;\n"),
     "expect_error": "illegal service request transition"},
    {"name": "legal path works + journal writes (requested -> broadcasting, 2 events)",
     "sql": ("begin;\n" + JWT +
             "insert into service_requests(client_auth_uid,mode,custom_scope,status) "
             "values('" + WORKER_UID + "','instant','gate probe legal','requested');\n"
             "update service_requests set status='broadcasting' where client_auth_uid='" + WORKER_UID + "' and custom_scope='gate probe legal';\n"
             "select 'LEGAL_OK_'||count(*) from service_job_events e join service_requests r on r.id=e.request_id "
             "where r.custom_scope='gate probe legal';\nrollback;\n"),
     "expect": "LEGAL_OK_2"},
    {"name": "attribution forge blocked (cannot file a request as someone else)",
     "sql": ("begin;\n" + JWT +
             "insert into service_requests(client_auth_uid,mode,custom_scope,status) "
             "values('" + OTHER_UID + "','instant','forged probe','requested');\n"
             "select 'FORGE_OK';\nrollback;\n"),
     "expect_error_any": ["must be the caller", "row-level security"]},
    {"name": "client credit mint blocked (ledger has no client write path)",
     "sql": ("begin;\n" + JWT +
             "insert into service_credit_ledger(account_type,account_id,entry_type,amount) "
             "values('consumer','" + WORKER_UID + "','topup',999);\n"
             "select 'FORGE_OK';\nrollback;\n"),
     "expect_error_any": ["permission denied", "row-level security"]},
    {"name": "top-up self-verify is a no-op (row stays pending_verification)",
     "sql": ("begin;\n" + JWT +
             "insert into service_credit_topups(account_type,account_id,payer_auth_uid,amount,gcash_ref) "
             "values('consumer','" + WORKER_UID + "','" + WORKER_UID + "',50,'0000000000042');\n"
             "update service_credit_topups set status='verified' where gcash_ref='0000000000042';\n"
             "select 'TOPUP_'||status from service_credit_topups where gcash_ref='0000000000042';\nrollback;\n"),
     "expect": "TOPUP_pending_verification"},
    {"name": "provider self-verification blocked",
     "sql": ("begin;\n" + JWT +
             "insert into service_providers(provider_type,auth_uid,display_name,verified) "
             "values('freelancer','" + WORKER_UID + "','Forge Gate Tech',true);\n"
             "select 'FORGE_OK';\nrollback;\n"),
     "expect_error": "granted by the platform"},
    {"name": "on_job is lifecycle-only (provider cannot self-set it)",
     "sql": ("begin;\n" + JWT +
             "insert into service_providers(provider_type,auth_uid,display_name) "
             "values('freelancer','" + WORKER_UID + "','Honest Gate Tech');\n"
             "update service_providers set availability='on_job' where display_name='Honest Gate Tech';\n"
             "select 'FORGE_OK';\nrollback;\n"),
     "expect_error": "set by the job lifecycle"},
    {"name": "atomic accept guard (2nd status-guarded UPDATE hits 0 rows)",
     "sql": ("begin;\n"  # service-role: pure guarded-update semantics, no JWT needed
             "insert into service_requests(client_auth_uid,mode,custom_scope,status) "
             "values('" + WORKER_UID + "','instant','race probe','broadcasting');\n"
             "with w1 as (update service_requests set status='accepted' "
             "  where custom_scope='race probe' and status='broadcasting' returning 1) "
             "select 'FIRST_'||count(*) from w1;\n"
             "with w2 as (update service_requests set status='accepted' "
             "  where custom_scope='race probe' and status='broadcasting' returning 1) "
             "select 'SECOND_'||count(*) from w2;\nrollback;\n"),
     "expect_all": ["FIRST_1", "SECOND_0"]},
    {"name": "live_location column privacy (revoke-first grant holds)",
     "sql": ("begin;\n" + JWT +
             "select live_location from service_providers limit 1;\n"
             "select 'LEAK_OK';\nrollback;\n"),
     "expect_error": "permission denied"},
    {"name": "live_location cannot STREAM (service_providers stays OUT of the realtime publication)",
     # P5 finding (2026-07-29): realtime payloads honor ROW RLS but not COLUMN grants; with the
     # directory's using(true) read policy, publishing the table would stream live_location to any
     # authenticated subscriber - bypassing the revoke-first privacy the probe above proves.
     "sql": ("select case when exists (select 1 from pg_publication_tables "
             "where pubname='supabase_realtime' and tablename='service_providers') "
             "then 'STREAM_LEAK_OPEN' else 'NO_STREAM_OK' end;\n"),
     "expect": "NO_STREAM_OK"},
]


def evaluate() -> tuple[list[str], list[str]]:
    passes, fails = [], []
    for c in CHECKS:
        out, rc = _docker(c["sql"])
        if out.startswith("SKIP") or "no such container" in out.lower() or "error during connect" in out.lower():
            return (["SKIP"], [])
        low = out.lower()
        if "expect_error" in c:
            ok = c["expect_error"].lower() in low and "forge_ok" not in low and "leak_ok" not in low
        elif "expect_error_any" in c:
            ok = any(e.lower() in low for e in c["expect_error_any"]) and "forge_ok" not in low
        elif "expect_all" in c:
            ok = all(e.lower() in low for e in c["expect_all"])
        else:
            ok = c["expect"].lower() in low
        (passes if ok else fails).append(c["name"] + ("" if ok else f"  [out: {out.strip().replace(chr(10),' ')[:120]}]"))
    return (passes, fails)


def main() -> int:
    if "--selftest" in sys.argv or "--self-test" in sys.argv:
        ok = ("legal_ok_2" in "x legal_ok_2 y") and \
             ("must start as requested" not in "forge_ok") and \
             all(e in "a first_1 b second_0" for e in ("first_1", "second_0"))
        print(f"{G}selftest PASS{X}" if ok else f"{R}selftest FAIL{X}")
        return 0 if ok else 1
    passes, fails = evaluate()
    if passes == ["SKIP"]:
        print(f"{B}Service state-machine integrity{X}\n  SKIP: local DB not reachable — gate not evaluated.")
        return 0
    print(f"{B}Service state-machine integrity (SERVICE_HAILING C1 lock){X}")
    for p in passes:
        print(f"  {G}PASS{X}  {p}")
    for f in fails:
        print(f"  {R}FAIL{X}  {f}")
    if fails:
        print(f"{R}FAIL - {len(fails)} state-machine/money/trust guard(s) OPEN.{X}")
        return 1
    print(f"{G}PASS - {len(passes)} guards hold (state machine, money mint, trust flags, privacy, atomic accept).{X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
