#!/usr/bin/env python3
"""validate_credit_posture.py -- the facts that keep WorkHive Credits out of the heavy regimes, asserted.

Migration 20260803000012 said this file asserts against the live catalogue. It did not exist, so the
posture was documented rather than checked -- which is precisely the failure it was written to prevent.

WorkHive Credits stay a closed-loop prepaid instrument because of a short list of structural facts, and
each one is one well-meaning feature away from disappearing:

  NON-WITHDRAWABLE   no cash redemption anywhere in the schema. This is the prong that most clearly
                     separates a closed-loop instrument from e-money, and the BSP moratorium on new VASP
                     authorities (in force since 1 Sep 2022) means being classified into that regime is
                     not something anyone could apply their way out of.
  NON-TRANSFERABLE   no person-to-person movement, so no secondary market. The SEC investment-contract
                     framework weights resale heavily; no resale, no realizable gain.
  FIXED VALUE        1 credit = PHP1, permanently. Nothing appreciates, so there is no expectation of
                     profit for a Howey analysis to bite on.
  CAPPED SUPPLY      issued <= authorised, enforced by a CHECK. Lifetime liability has a ceiling.
  APPEND-ONLY LEDGER clients hold no INSERT/UPDATE/DELETE privilege on service_credit_ledger. This one is
                     load-bearing beyond bookkeeping: a guard was once added to refuse hand-minted
                     positive entries, and it broke settlement while defending against something table
                     privileges already made impossible.

Everything here is read from the catalogue, never from prose -- a comment cannot go stale into a lie if
nothing trusts it. The named-trigger roster is the part that earns its keep: a future migration that
CREATE OR REPLACEs a guard function is fine, but one that drops the trigger silently un-enforces a rule,
and nothing else in the suite would notice.

Usage:  python tools/validate_credit_posture.py [--selftest] [--inject cashout|transfer|cap|rate|append|trigger|balance]
"""
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

# Every trigger the credit economy's rules actually live in. A rule with no trigger is a comment.
REQUIRED_TRIGGERS = {
    "trg_credits_non_transferable":    "service_credit_ledger",
    "trg_listing_requires_reservation": "marketplace_listings",
    "trg_release_reservation":          "marketplace_listings",
    "trg_grant_listing_reward":         "marketplace_listings",
    "trg_first_listings_need_a_sale":   "marketplace_listings",
}

POSTURE = """
select no_cash_out_function::text, transfer_guard_live::text,
       authorised_credits::text, issued_credits::text, pesos_per_credit::text
  from public.v_credit_posture;
"""

TRIGGERS = """
select t.tgname, c.relname
  from pg_trigger t join pg_class c on c.oid = t.tgrelid
 where not t.tgisinternal and t.tgname in ({});
"""

# CONSERVATION. Every reward movement is a TRANSFER between two wallets, so its legs must net to zero on
# each job: a listing sale pairs reward_fund(-X) with reward_earn(+X); a credit payment pairs
# reward_spend(-X) with reward_fund(+X). A leg that nets non-zero is credits appearing or vanishing.
#
# This invariant is here because its absence was load-bearing: apply_credits_to_request shipped writing
# ONLY the buyer's leg. Every guard passed -- they each check one side -- and the credits simply ceased to
# exist, leaving the platform holding the cash that backed them. Nothing said the ledger must balance, so
# a one-sided entry looked exactly like a correct one.
UNBALANCED = """
select ref_id::text, sum(amount)::text
  from public.service_credit_ledger
 where entry_type in ('reward_earn','reward_spend','reward_fund') and ref_id is not null
 group by ref_id having abs(sum(amount)) > 0.005;
"""

# The append-only property, read as privileges rather than believed. `authenticated` and `anon` must hold
# nothing that writes.
CLIENT_WRITES = """
select grantee || ' ' || privilege_type
  from information_schema.role_table_grants
 where table_name = 'service_credit_ledger'
   and grantee in ('authenticated', 'anon')
   and privilege_type in ('INSERT', 'UPDATE', 'DELETE');
"""


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:200]
    return [ln.split("|") for ln in (r.stdout or "").splitlines() if ln.strip()], ""


def judge(no_cash_out, transfer_guard, authorised, issued, rate, missing_triggers, client_writes,
          unbalanced=()):
    """-> list of problems. Pure, so the reasoning is testable without a database in any given state."""
    p = []
    if not no_cash_out:
        p.append("a function that looks like a CASH-OUT path exists. Redemption for cash is the prong "
                 "that separates a closed-loop instrument from e-money, and the BSP VASP moratorium "
                 "means that reclassification cannot be applied away")
    if not transfer_guard:
        p.append("guard_credits_non_transferable is not installed, so credits can move person to person "
                 "- which hands them a secondary market and the resale prong with it")
    if authorised <= 0:
        p.append("the treasury declares no authorised supply, so the liability cap is not a cap")
    if issued > authorised:
        p.append(f"issued credits ({issued:,.2f}) exceed the authorised supply ({authorised:,.2f}) - "
                 f"lifetime liability has escaped its ceiling")
    if abs(rate - 1.0) > 1e-9:
        p.append(f"1 credit no longer equals PHP1 (reads {rate}). A rate that can move is an expectation "
                 f"of profit, which is exactly what the fixed value exists to deny")
    for t, tbl in sorted(missing_triggers.items()):
        p.append(f"trigger {t} is missing from {tbl} - the rule it carries is un-enforced, and a dropped "
                 f"trigger is invisible to every test that only checks the function still compiles")
    for ref, delta in sorted(unbalanced):
        p.append(f"job {ref[:8]} has reward legs that net to {delta:+.2f} instead of 0 - a reward is a "
                 f"TRANSFER between two wallets, so a non-zero total means credits were created or "
                 f"destroyed on that job")
    for g in sorted(client_writes):
        p.append(f"a client role holds a write privilege on the ledger ({g}). The ledger is append-only "
                 f"BY PRIVILEGE, and several guards are safe only because of it")
    return p


def selftest():
    print("  selftest: each posture fact must be catchable, and a healthy posture must pass clean")
    ok = True
    cases = [
        ("cash-out path",      dict(no_cash_out=False)),
        ("transfer guard off", dict(transfer_guard=False)),
        ("supply overrun",     dict(issued=20_000_000.0)),
        ("no cap at all",      dict(authorised=0.0)),
        ("rate drift",         dict(rate=1.05)),
        ("dropped trigger",    dict(missing_triggers={"trg_credits_non_transferable": "service_credit_ledger"})),
        ("client can write",   dict(client_writes=["authenticated INSERT"])),
        ("one-sided reward",    dict(unbalanced=[("abcdef12-0000", -80.0)])),
    ]
    base = dict(no_cash_out=True, transfer_guard=True, authorised=10_000_000.0, issued=0.0,
                rate=1.0, missing_triggers={}, client_writes=[], unbalanced=[])
    for name, override in cases:
        if not judge(**{**base, **override}):
            print(f"  {RED}FAIL{RST} -- '{name}' was not caught"); ok = False
    if judge(**base):
        print(f"  {RED}FAIL{RST} -- a healthy posture was flagged"); ok = False
    if ok:
        print(f"  {GREEN}PASS{RST} -- catches all 8 posture failures, accepts a healthy posture")
    return 0 if ok else 1


def main(argv):
    inject = None
    if "--inject" in argv:
        inject = argv[argv.index("--inject") + 1]
    if "--selftest" in argv:
        return selftest()

    print(f"{BOLD}Credit posture{RST} -- non-withdrawable, non-transferable, fixed, capped, append-only")
    if selftest() != 0:
        return 1

    rows, err = psql(POSTURE)
    if rows is None:
        print(f"  {YEL}SKIP{RST} database unavailable ({err})")
        return 0
    # Both spellings: psql renders a raw boolean as 't', but the ::text cast in POSTURE yields 'true'.
    # Testing only for 't' read a perfectly healthy posture as two catastrophic failures -- the gate was
    # wrong about the schema, not the schema about itself.
    def istrue(v):
        return v.strip().lower() in ("t", "true")
    no_cash_out = istrue(rows[0][0])
    transfer_guard = istrue(rows[0][1])
    authorised, issued, rate = float(rows[0][2]), float(rows[0][3]), float(rows[0][4])

    names = ", ".join("'%s'" % t for t in REQUIRED_TRIGGERS)
    trows, _ = psql(TRIGGERS.format(names))
    present = {r[0] for r in (trows or [])}
    missing = {t: tbl for t, tbl in REQUIRED_TRIGGERS.items() if t not in present}

    wrows, _ = psql(CLIENT_WRITES)
    client_writes = [r[0] for r in (wrows or [])]

    urows, _ = psql(UNBALANCED)
    unbalanced = [(r[0], float(r[1])) for r in (urows or [])]

    if inject:                                  # teeth: each lever must break its OWN assertion
        if inject == "cashout":  no_cash_out = False
        elif inject == "transfer": transfer_guard = False
        elif inject == "cap":    issued = authorised + 1
        elif inject == "rate":   rate = 1.05
        elif inject == "append": client_writes = client_writes + ["authenticated INSERT"]
        elif inject == "balance": unbalanced = unbalanced + [("deadbeef-0000", -80.0)]
        elif inject == "trigger":
            k = sorted(REQUIRED_TRIGGERS)[0]; missing[k] = REQUIRED_TRIGGERS[k]
        else:
            print(f"  {RED}unknown --inject '{inject}'{RST}"); return 2
        print(f"  {YEL}INJECTED{RST} {inject} -- this run must FAIL, and on that assertion only")

    print(f"  {DIM}authorised supply   {authorised:>14,.2f}{RST}")
    print(f"  {DIM}issued              {issued:>14,.2f}{RST}")
    print(f"  {DIM}available to issue  {authorised - issued:>14,.2f}{RST}")
    print(f"  {DIM}1 credit            {rate:>14,.2f} PHP{RST}")
    print(f"  {DIM}rules installed     {len(REQUIRED_TRIGGERS) - len(missing)}/{len(REQUIRED_TRIGGERS)} triggers{RST}")

    print(f"  {DIM}reward legs         {'balanced' if not unbalanced else str(len(unbalanced)) + ' UNBALANCED'}{RST}")

    problems = judge(no_cash_out, transfer_guard, authorised, issued, rate, missing, client_writes,
                     unbalanced)
    if problems:
        print(f"\n  {RED}FAIL{RST} -- the credit posture has moved:")
        for p in problems:
            print(f"    . {p}")
        return 1
    print(f"\n  {GREEN}PASS{RST} -- no cash-out path, transfers guarded, {authorised:,.0f} capped at "
          f"1:1, ledger append-only by privilege")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
