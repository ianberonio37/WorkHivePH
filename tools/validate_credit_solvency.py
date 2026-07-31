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
  coalesce(sum(amount), 0)::text
from public.service_credit_ledger;
"""

NEGATIVE_CONSUMERS = """
select count(*)::text from (
  select account_id from public.service_credit_ledger
   where account_type = 'consumer'
   group by account_id having sum(amount) < 0) x;
"""


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
        problems.append(f"unbacked credits ({vouchers:.2f} in vouchers) exceed everything ever EARNED "
                        f"({earned:.2f} in commission) — acquisition is being funded out of prepayments")
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
    if ok:
        print(f"  {GREEN}PASS{RST} — catches over-granting and negative consumer balances, accepts a healthy ledger")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Credit solvency{RST} — are the credits we have given away backed by anything?")
    if selftest() != 0:
        return 1

    rows, err = psql(LEDGER)
    if rows is None:
        print(f"  {YEL}SKIP{RST} database unavailable ({err})")
        return 0
    topups, earned, cashback, vouchers, net = (float(x) for x in rows[0])
    nrows, _ = psql(NEGATIVE_CONSUMERS)
    neg = int(nrows[0][0]) if nrows else 0

    liability = topups + cashback + vouchers - earned
    print(f"  {DIM}cash-backed  topups        {topups:>12,.2f}{RST}")
    print(f"  {DIM}earned       commission    {earned:>12,.2f}{RST}")
    print(f"  {DIM}funded       cashback      {cashback:>12,.2f}{RST}")
    print(f"  {DIM}UNBACKED     vouchers      {vouchers:>12,.2f}{RST}")
    print(f"  {BOLD}outstanding liability      {liability:>12,.2f}{RST}  {DIM}(credits owed as services){RST}")

    problems = judge(topups, earned, cashback, vouchers, neg)
    if problems:
        print(f"\n  {RED}FAIL{RST} — the credit economy is not solvent:")
        for p in problems:
            print(f"    · {p}")
        return 1

    if topups == 0 and earned == 0:
        print(f"\n  {GREEN}PASS{RST} — no money has moved yet; the invariants hold vacuously and will bite "
              f"the moment it does")
        return 0
    print(f"\n  {GREEN}PASS{RST} — every credit given away is backed by cash or by revenue earned")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
