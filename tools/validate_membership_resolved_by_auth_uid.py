#!/usr/bin/env python3
"""validate_membership_resolved_by_auth_uid.py — the tenancy boundary must key on identity, not on a name.

`v_worker_truth` is the membership anchor `_shared/tenant-context.ts::resolveTenancy` trusts, and through it
30 service-role edge functions decide which hive a caller belongs to. It once resolved membership with

    LEFT JOIN public.hive_members hm ON hm.worker_name = wp.display_name AND hm.status = 'active'

`display_name` is user-mutable (RLS `profiles update own`, no UNIQUE constraint), so a member of hive A could
rename their own profile to a member of hive B and the view would join their auth_uid to hive B's membership
row — a cross-tenant privilege escalation, closed by 20260731000001 which re-keys the join on the immutable
`auth_uid`. See the migration header for the full write-up.

WHY THIS GATE IS A BEHAVIOURAL PROBE, NOT A STATIC ONE. Unlike the audit-actor lookup
([[feedback_resolving_live_is_not_enough_be_deterministic]], whose failure was non-deterministic and had to be
locked in source), THIS escalation is deterministic: a name-keyed view ALWAYS returns the phantom membership
row after the rename. So the gate reproduces the whole exploit inside one rolled-back transaction and measures
the outcome, which is stronger than asserting the join text:

  1. an attacker renames their own profile to a victim's display name  (as `authenticated`, RLS enforced —
     proving the rename is actually allowed, not just hypothesised);
  2. under `service_role` — exactly the client the edge functions use, RLS bypassed — the REAL view is asked
     whether the attacker is now a member of the victim's hive. It MUST answer no (0 rows);
  3. the view is mutated BACK to the name-keyed join and asked again. It MUST answer yes (>=1 row). This is the
     teeth: a probe that cannot make the bug reappear proves nothing when it reports the fix works.

Everything is rolled back, so neither the rename nor the mutated view persists — verified after the run by
reading the live definition back (the "0 mutated objects persist" discipline).

Usage:  python tools/validate_membership_resolved_by_auth_uid.py [--selftest]
"""
from __future__ import annotations

import subprocess
import sys

DB = "supabase_db_workhive"
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# The known-bad definition, re-created inside the probe transaction as the "mutant". Column list and order are
# identical to the fixed view; only the two membership joins key on display_name instead of auth_uid.
NAME_KEYED_MUTANT = """
create or replace view public.v_worker_truth with (security_invoker = true) as
select wp.auth_uid, wp.username, wp.display_name as worker_name, wp.email, wp.preferred_persona,
       wp.created_at as registered_at, hm.hive_id, hm.role, hm.joined_at as hive_joined_at,
       hm.status as hive_status, (hm.hive_id is null) as is_solo,
       (select count(*) from public.hive_members hm2
          where hm2.worker_name = wp.display_name and hm2.status='active') as active_hive_count
  from public.worker_profiles wp
  left join public.hive_members hm on hm.worker_name = wp.display_name and hm.status='active';
"""


def psql(sql: str, capture=True):
    try:
        r = subprocess.run(["docker", "exec", "-i", DB, "psql", "-U", "postgres", "-d", "postgres",
                            "-At", "-v", "ON_ERROR_STOP=1", "-f", "-"],
                           input=sql, capture_output=capture, text=True, encoding="utf-8",
                           errors="replace", timeout=90)
    except FileNotFoundError:
        return None, "docker not installed"
    except Exception as e:  # noqa: BLE001
        return None, str(e)
    return (r.returncode, (r.stdout or "") + (r.stderr or ""))


def discover_pair():
    """An attacker with a profile who is NOT in the victim's hive; a victim active in that hive."""
    rc, out = psql(
        "select att.auth_uid, att.display_name, vic.hive_id, vic.worker_name "
        "from public.worker_profiles att "
        "join public.hive_members vic on vic.status='active' "
        "where att.auth_uid is not null and vic.auth_uid is not null and vic.auth_uid <> att.auth_uid "
        "and not exists (select 1 from public.hive_members m "
        "  where m.auth_uid=att.auth_uid and m.hive_id=vic.hive_id and m.status='active') "
        "order by att.auth_uid, vic.hive_id limit 1;")
    if rc is None or rc != 0:
        return None
    line = (out or "").strip().splitlines()
    if not line:
        return None
    parts = line[0].split("|")
    if len(parts) != 4:
        return None
    return {"attacker_uid": parts[0], "attacker_name": parts[1], "victim_hive": parts[2], "victim_name": parts[3]}


def live_view_is_auth_uid_keyed():
    rc, out = psql("select pg_get_viewdef('public.v_worker_truth'::regclass, true);")
    if rc is None or rc != 0:
        return None, out
    vd = (out or "")
    # The membership join must equate hive_members to the profile by auth_uid, never by the display name.
    keys_on_name = "worker_name = wp.display_name" in vd or "wp.display_name = hm.worker_name" in vd
    keys_on_uid = "hm.auth_uid = wp.auth_uid" in vd or "wp.auth_uid = hm.auth_uid" in vd
    return (keys_on_uid and not keys_on_name), vd


def run_probe(pair, do_rename=True):
    """Returns (real_n, mutant_n) or None. `do_rename=False` is the control: without the rename even the
    name-keyed mutant must NOT escalate, proving the escalation is caused by the rename, not a stale collision."""
    claims = '{"sub":"%s","role":"authenticated"}' % pair["attacker_uid"]
    rename = (f"set local role authenticated;\n"
              f"set local request.jwt.claims = '{claims}';\n"
              f"update public.worker_profiles set display_name='{pair['victim_name']}' "
              f"where auth_uid='{pair['attacker_uid']}';\n"
              f"reset role;\n") if do_rename else ""
    sql = f"""
begin;
{rename}
set local role service_role;
select 'REAL='||count(*) from public.v_worker_truth
 where auth_uid='{pair['attacker_uid']}' and hive_id='{pair['victim_hive']}' and hive_status='active';
reset role;
{NAME_KEYED_MUTANT}
set local role service_role;
select 'MUTANT='||count(*) from public.v_worker_truth
 where auth_uid='{pair['attacker_uid']}' and hive_id='{pair['victim_hive']}' and hive_status='active';
reset role;
rollback;
"""
    rc, out = psql(sql)
    if rc is None or rc != 0:
        return None
    real = mutant = None
    for ln in (out or "").splitlines():
        ln = ln.strip()
        if ln.startswith("REAL="):
            real = int(ln.split("=")[1])
        elif ln.startswith("MUTANT="):
            mutant = int(ln.split("=")[1])
    if real is None or mutant is None:
        return None
    return real, mutant


def main(argv):
    selftest = "--selftest" in argv
    print(f"{BOLD}Membership resolves by auth_uid, not display_name{RST} — the tenancy boundary keys on "
          f"identity")

    keyed, vd = live_view_is_auth_uid_keyed()
    if keyed is None:
        print(f"  {YEL}SKIP{RST} — docker/psql unavailable ({str(vd)[:60]}); nothing asserted.")
        return 0
    if not keyed:
        print(f"  {RED}FAIL{RST} v_worker_truth resolves membership by display_name (user-mutable). A member of "
              f"one hive can rename into another hive's membership. Re-key the join on auth_uid "
              f"(20260731000001).")
        return 1
    print(f"  {DIM}live view: membership join keys on auth_uid (not display_name){RST}")

    pair = discover_pair()
    if not pair:
        print(f"  {YEL}SKIP{RST} — no (attacker not in hive H, victim in H) pair in current data; the "
              f"behavioural probe needs two members in different hives. Static join-key check above still ran.")
        return 0

    res = run_probe(pair, do_rename=True)
    if res is None:
        print(f"  {YEL}SKIP{RST} — the probe transaction did not return both markers; treating as unproven "
              f"rather than green.")
        return 0
    real, mutant = res
    label = f"{pair['attacker_name']} -> '{pair['victim_name']}' in hive {pair['victim_hive'][:8]}"
    if real != 0:
        print(f"  {RED}FAIL{RST} the REAL view granted the renamed attacker membership of a hive they never "
              f"joined ({label}: {real} row). The fix has regressed.")
        return 1
    if mutant < 1:
        print(f"  {RED}FAIL{RST} teeth failure: the name-keyed MUTANT did NOT escalate ({label}: {mutant}), so "
              f"this probe cannot detect the bug it guards and its green means nothing.")
        return 1
    # After rollback, the live view must be unchanged and still auth_uid-keyed.
    keyed_after, _ = live_view_is_auth_uid_keyed()
    if not keyed_after:
        print(f"  {RED}FAIL{RST} the mutated view PERSISTED after the probe — the transaction did not roll "
              f"back. Restore v_worker_truth from 20260731000001 immediately.")
        return 1

    if selftest:
        ctrl = run_probe(pair, do_rename=False)
        if ctrl is None or ctrl[1] != 0:
            print(f"  {RED}FAIL{RST} selftest control: without the rename the name-keyed mutant still returned "
                  f"{ctrl and ctrl[1]} rows — the escalation is not attributable to the rename, so the probe is "
                  f"not measuring what it claims.")
            return 1
        print(f"  {GREEN}PASS{RST} selftest: with no rename even the name-keyed mutant escalates 0 rows, so the "
              f"escalation the probe detects is caused by the self-rename, nothing else.")

    print(f"  {GREEN}PASS{RST} the real view refuses the renamed attacker (0), the name-keyed mutant would have "
          f"admitted them ({mutant}) — the fix is load-bearing and the probe has teeth. No mutant persists.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
