#!/usr/bin/env python3
"""validate_credit_solvency.py — is the credit economy still solvent, and is the ledger still the truth?

MARKETPLACE_CREDIT_SUSTAINABILITY §5 named liability cover "the one that matters", and §4.5 named spending
the float the most dangerous failure mode *because it is invisible until it is fatal*. This makes it visible.

WHAT SOLVENCY MEANS HERE, precisely. Credits enter three ways and they are not equal:

  BACKED BY CASH      topup            — a provider paid GCash for these
  BACKED BY REVENUE   cashback         — funded out of commission the platform earned
  BACKED BY NOTHING   voucher_grant    — platform-funded acquisition, minted from thin air

The first two are safe by construction: a top-up brought its own money, and the solvency CHECK on
hive_service_settings already refuses `cashback_pct > commission_pct + listing_fee_pct`, so cashback can
never outrun the take on a per-transaction basis.

**Vouchers are the live gap** (§13): they mint credits with no fee behind them at all, and NOTHING currently
bounds them. A generous promo is indistinguishable from an accident until the float is gone. So the invariant
this gate holds is:

    unbacked credits (vouchers) <= credits actually EARNED (commission)

If the platform has given away more than it has ever earned, it is funding acquisition out of other people's
prepayments — which works right up until they spend them.

ALSO ASSERTED: the ledger is the only source of truth for a balance. A negative PROVIDER balance is expected
and fine (commission is debited on completion and min_list_balance is what keeps wallets funded), but a
negative CONSUMER balance is not: consumers only ever receive cashback and spend it, so going negative means
something spent credits that were never minted.

Usage:  python tools/validate_credit_solvency.py [--selftest]
"""
import subprocess
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
CONTAINER = "supabase_db_workhive"

LEDGER = """
select
  coalesce(sum(amount) filter (where entry_type = 'topup'), 0)::text,
  coalesce(-sum(amount) filter (where entry_type = 'commission'), 0)::text,
  coalesce(sum(amount) filter (where entry_type = 'cashback'), 0)::text,
  coalesce(sum(amount) filter (where entry_type = 'voucher_grant'), 0)::text,
  coalesce(sum(amount), 0)::text,
  coalesce(sum(amount) filter (where entry_type = 'starter_grant'), 0)::text
from public.service_credit_ledger;
"""

NEGATIVE_CONSUMERS = """
select count(*)::text from (
  select account_id from public.service_credit_ledger
   where account_type = 'consumer'
   group by account_id having sum(amount) < 0) x;
"""


# ★FREE CREDIT NO GATE HELD TO ITS POLICY (BRH.10 AK, 2026-10-26). Starter grants are the one unbacked credit left, and
# this gate printed them as "by design" without asking a single grant record whether it followed the design. The
# policy, as claim_starter_grant writes it: once per person (credit_starter_grants' primary key), only to a holder of a
# seller profile, at the starter_grant knob's amount, minted through the treasury like any other credit. Every grant
# that reached the ledger by another door - a backfill, a script, a second claim - is what these counts refute.
STARTER_POLICY = """
with g as (select auth_uid, amount from public.credit_starter_grants),
     l as (select account_id, amount from public.service_credit_ledger where entry_type = 'starter_grant')
select
  (select count(*) from l where not exists (select 1 from g where g.auth_uid = l.account_id and g.amount = l.amount))::text,
  (select count(*) from g where not exists (select 1 from l where l.account_id = g.auth_uid and l.amount = g.amount))::text,
  (select count(*) from (select account_id from l group by account_id having count(*) > 1) x)::text,
  (select count(*) from g where not exists (select 1 from public.marketplace_sellers s where s.auth_uid = g.auth_uid))::text,
  (select count(*) from g where g.amount > coalesce(public.service_knob(null, 'starter_grant'), 0))::text,
  (select count(*) from g)::text;
"""


def judge_grants(unrecorded, unledgered, repeated, no_seller, over_amount):
    """-> list of problems with the starter grants. Pure, so the self-test needs no ledger in any state."""
    p = []
    if unrecorded:
        p.append(f"{unrecorded} starter-grant ledger entr(ies) have no matching grant record - credit minted outside claim_starter_grant")
    if unledgered:
        p.append(f"{unledgered} grant record(s) have no matching ledger entry - the grant and the balance disagree")
    if repeated:
        p.append(f"{repeated} account(s) received the starter grant more than once - the policy is once per person")
    if no_seller:
        p.append(f"{no_seller} grant(s) went to someone with no seller profile - the policy gates the grant on one")
    if over_amount:
        p.append(f"{over_amount} grant(s) exceed the starter_grant amount the policy sets")
    return p


def console_findings(src: str) -> list[str]:
    """BRH.10 AK: the operator console's cover says what backs what is owed, and why a low cover is low. Static, so it
    holds without a database; `src` is the console's queue script (platform-actions.html, cut into operator-actions.js)."""
    out = []
    if "sum('starter_grant')" not in src or "What is owed, by what backs it" not in src:
        out.append("the console does not split what is owed by its backing (top-ups / starter credit / the rest)")
    if "cp-cover-why" not in src or "starter credit" not in src:
        out.append("the console's cover gives no reason when starter credit holds it under 1.00")
    return out


def psql(sql):
    try:
        r = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres",
                            "-t", "-A", "-F", "|", "-c", sql],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or "")[:160]
    rows = [ln.split("|") for ln in (r.stdout or "").splitlines() if ln.strip()]
    return rows, ""


def judge(topups, earned, cashback, vouchers, neg_consumers):
    """-> list of problems. Pure arithmetic so it is testable without touching a real ledger."""
    problems = []
    if vouchers > earned:
        # Since 2026-08-03 the platform takes NO commission, so `earned` is structurally 0 going forward
        # and this rule gets STRICTER, not weaker: with no revenue there is nothing to fund a giveaway
        # from, so any voucher at all is a credit minted against someone else's prepayment. Saying
        # "backed by cash OR revenue" would describe a funding source that no longer exists.
        problems.append(
            f"unbacked credits ({vouchers:.2f} in vouchers) exceed everything ever EARNED "
            f"({earned:.2f} in commission)"
            + (" — and the platform now takes NO commission, so there is no revenue to fund a giveaway "
               "from at all: every voucher is minted against someone else's prepayment"
               if earned <= 0 else
               " — acquisition is being funded out of prepayments"))
    if neg_consumers:
        problems.append(f"{neg_consumers} consumer account(s) hold a NEGATIVE balance — consumers only "
                        f"receive and spend cashback, so this means credits were spent that were never minted")
    return problems


def selftest():
    """Prove the arithmetic, without needing a ledger in any particular state."""
    print("  selftest: the solvency arithmetic must catch each failure and pass a healthy ledger")
    ok = True
    if not judge(10000, 500, 200, 900, 0):
        print(f"  {RED}FAIL{RST} — vouchers exceeding earned revenue was not caught"); ok = False
    if not judge(10000, 500, 200, 100, 3):
        print(f"  {RED}FAIL{RST} — negative consumer balances were not caught"); ok = False
    if judge(10000, 500, 200, 100, 0):
        print(f"  {RED}FAIL{RST} — a healthy ledger was flagged"); ok = False
    for args, what in (((1, 0, 0, 0, 0), "a grant minted outside the claim"), ((0, 1, 0, 0, 0), "a grant with no ledger entry"),
                       ((0, 0, 1, 0, 0), "a second grant to one person"), ((0, 0, 0, 1, 0), "a grant to someone with no seller profile"),
                       ((0, 0, 0, 0, 1), "a grant above the policy amount")):
        if not judge_grants(*args):
            print(f"  {RED}FAIL{RST} — {what} was not caught"); ok = False
    if judge_grants(0, 0, 0, 0, 0):
        print(f"  {RED}FAIL{RST} — grants that follow the policy were flagged"); ok = False
    good = "sum('starter_grant') What is owed, by what backs it id=\"cp-cover-why\" starter credit"
    if console_findings(good) or len(console_findings("Liability cover: cash in vs credits owed")) != 2:
        print(f"  {RED}FAIL{RST} — the console-reason check does not tell a cover with its reason from one without"); ok = False
    if ok:
        print(f"  {GREEN}PASS{RST} — catches over-granting, negative consumer balances and every starter-grant policy breach, "
              f"accepts a healthy ledger")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Credit solvency{RST} — are the credits we have given away backed by anything?")
    if selftest() != 0:
        return 1

    # the console half needs no database: the queue source and its generated cut must both carry the reason
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    static = []
    for name in ("platform-actions.html", "operator-actions.js"):
        f = root / name
        static += [f"{name}: {x}" for x in console_findings(f.read_text(encoding="utf-8", errors="ignore") if f.exists() else "")]
    if static:
        print(f"\n  {RED}FAIL{RST} — the console's cover does not say what backs it:")
        for x in static:
            print(f"    · {x}")
        return 1

    rows, err = psql(LEDGER)
    if rows is None:
        print(f"  {YEL}SKIP{RST} database unavailable ({err})")
        return 0
    topups, earned, cashback, vouchers, net, starter = (float(x) for x in rows[0])
    nrows, _ = psql(NEGATIVE_CONSUMERS)
    neg = int(nrows[0][0]) if nrows else 0

    # what is owed is the WHOLE ledger (2026-10-23): a balance is the sum of an account's rows, any type. The
    # four-type sum left out starter grants (3,500 on the local ledger), adjustments and holding fees, and so
    # did the console's cover figure it mirrored.
    liability = net
    print(f"  {DIM}cash-backed  topups        {topups:>12,.2f}{RST}")
    print(f"  {DIM}earned       commission    {earned:>12,.2f}{RST}")
    print(f"  {DIM}funded       cashback      {cashback:>12,.2f}{RST}")
    print(f"  {DIM}UNBACKED     vouchers      {vouchers:>12,.2f}{RST}")
    print(f"  {DIM}UNBACKED     starter grant {starter:>12,.2f}  (by design: once per verified seller, against the cap){RST}")
    print(f"  {BOLD}outstanding liability      {liability:>12,.2f}{RST}  {DIM}(credits owed as services){RST}")

    problems = judge(topups, earned, cashback, vouchers, neg)
    grows, gerr = psql(STARTER_POLICY)
    if grows is None:
        problems.append(f"the starter grants could not be read against their policy ({gerr}) - unread is not compliant")
    else:
        g = [int(x) for x in grows[0]]
        problems += judge_grants(*g[:5])
        print(f"  {DIM}starter grants: {g[5]} on record, each checked against the policy (once, to a seller, at the knob's amount, in the ledger){RST}")
    if problems:
        print(f"\n  {RED}FAIL{RST} — the credit economy is not solvent:")
        for p in problems:
            print(f"    · {p}")
        return 1

    if topups == 0 and earned == 0:
        print(f"\n  {GREEN}PASS{RST} — no money has moved yet; the invariants hold vacuously and will bite "
              f"the moment it does")
        return 0
    if starter > 0:
        # "backed by cash or revenue" is true of the vouchers only: starter grants are free credit by design
        print(f"\n  {GREEN}PASS{RST} — no voucher outruns revenue and no consumer is negative. Not every credit "
              f"is backed: {starter:,.2f} are starter grants, issued free against the supply cap")
        return 0
    if earned <= 0:
        print(f"\n  {GREEN}PASS{RST} — every credit outstanding is backed by CASH. The platform takes no "
              f"commission, so cash is the only backing there is, and nothing has been given away without it")
    else:
        print(f"\n  {GREEN}PASS{RST} — every credit given away is backed by cash or by revenue earned "
              f"(historical commission: {earned:,.2f}; the rate is now 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
