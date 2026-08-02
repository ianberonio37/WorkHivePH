#!/usr/bin/env python3
"""simulate_credit_circuit.py -- the WorkHive credit economy, simulated against its own rules.

WHY THIS EXISTS AS A GATE RATHER THAN A NOTEBOOK. Every default in the credit economy was chosen from
simulation, and two of them were chosen AGAINST the first instinct because the numbers contradicted it.
A design justified by a measurement has to keep being measured, or the justification quietly becomes
folklore and the knob drifts to whatever felt right later.

WHAT IT ASSERTS (each is a claim the design rests on, not a statistic):

  1. the per-listing cap raises throughput at scale        measured 4.9x on industrial listings
  2. the starter grant raises cold-start throughput        measured 2.2x for cash-poor providers
  3. hoarding raises cash demand without stopping trade    measured +71% cash for the same sales
  4. the holding fee separates spam from slow selling      PHP8 honest vs PHP2,400 spam per year
  5. the supply cap binds where predicted                  ~20,000 active providers

TEETH. A simulator that cannot fail proves nothing, so `--inject` removes a lever and the run must go RED.
The plan requires this explicitly: remove the cap, the grant, or the holding fee and the corresponding
assertion has to break.

AND A GUARD AGAINST ITS OWN LAST BUG. An early version reported a catastrophic industrial jam that did not
exist: with one listing per provider, `int(1 * 0.5)` rounds to zero, so nothing ever sold and reservations
piled up artificially. That number was very nearly written into the plan as an economic finding. The
scenario set therefore pins a KNOWN-GOOD case whose expected output is fixed, and selling is probabilistic
rather than truncated.

Usage:
  python tools/simulate_credit_circuit.py                 run every assertion
  python tools/simulate_credit_circuit.py --inject cap    prove it fails without the per-listing cap
  python tools/simulate_credit_circuit.py --selftest      prove the pinned known-good case still holds
"""
from __future__ import annotations
import argparse, random, sys

G, R, Y, D, B, X = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

SUPPLY = 10_000_000
REWARD_PCT = 0.10
SPEND_CAP_PCT = 0.10
CAP_PER_LISTING = 500
STARTER_GRANT = 500
HOLDING_FEE = 0.02


class Circuit:
    """One month per step. Providers reserve to list; buyers earn OR spend, never both."""

    def __init__(self, n_prov, n_buy, price, sell_through, spend_prop, cash,
                 cap=CAP_PER_LISTING, grant=STARTER_GRANT, fee=HOLDING_FEE,
                 reward=REWARD_PCT, supply=SUPPLY, seed=11):
        random.seed(seed)
        self.price, self.st, self.sp = price, sell_through, spend_prop
        self.cap, self.fee, self.reward, self.sup = cap, fee, reward, supply
        self.avail = [float(grant)] * n_prov
        self.resv = [0.0] * n_prov
        self.buyers = [0.0] * n_buy
        self.treasury = supply - grant * n_prov
        self.budget = [float(cash)] * n_prov
        self.blocked = self.sold = 0
        self.cash_in = self.fee_burned = 0.0

    def need(self):
        n = self.price * self.reward
        return min(n, self.cap) if self.cap else n

    def _buy(self, i, amt):
        amt = min(amt, self.treasury, self.budget[i])
        if amt <= 0:
            return 0
        self.treasury -= amt
        self.avail[i] += amt
        self.cash_in += amt
        self.budget[i] -= amt
        return amt

    def step(self):
        need = self.need()
        for i in range(len(self.avail)):
            if self.avail[i] < need:
                self._buy(i, need - self.avail[i])
                if self.avail[i] < need:
                    self.blocked += 1
                    continue
            self.avail[i] -= need
            self.resv[i] += need

        if self.fee:                       # consumed from LIVE reservations, retired to treasury
            for i in range(len(self.resv)):
                burn = self.resv[i] * self.fee
                self.resv[i] -= burn
                self.treasury += burn
                self.fee_burned += burn

        for i in range(len(self.avail)):
            live = int(round(self.resv[i] / need)) if need > 0 else 0
            # PROBABILISTIC, never int(live * st): truncation made one-listing providers never sell,
            # which once produced a catastrophic jam that did not exist.
            for _ in range(sum(1 for _ in range(live) if random.random() < self.st)):
                self.resv[i] -= need
                self.sold += 1
                b = random.randrange(len(self.buyers))
                if self.buyers[b] >= self.price * SPEND_CAP_PCT and random.random() < self.sp:
                    self.buyers[b] -= self.price * SPEND_CAP_PCT      # SPEND: seller retains
                    self.avail[i] += need + self.price * SPEND_CAP_PCT
                else:
                    self.buyers[b] += need                            # EARN: passes to the buyer

    def run(self, months):
        for _ in range(months):
            self.step()
        return self


def check(name, got, want, ok, detail=""):
    mark = f"{G}PASS{X}" if ok else f"{R}FAIL{X}"
    print(f"  {mark}  {name}")
    print(f"        {D}{detail or f'{got} vs expected {want}'}{X}")
    return ok


def assertions(inject=None):
    """Each returns True/False. `inject` disables a lever so the run MUST go red."""
    cap = None if inject == "cap" else CAP_PER_LISTING
    grant = 0 if inject == "grant" else STARTER_GRANT
    fee = 0.0 if inject == "fee" else HOLDING_FEE
    results = []

    # 1 | the per-listing cap raises throughput at scale
    flat = Circuit(3000, 30000, 25000, 0.5, 0.5, 10**9, cap=None, grant=0, fee=0).run(12)
    capped = Circuit(3000, 30000, 25000, 0.5, 0.5, 10**9, cap=cap, grant=0, fee=0).run(12)
    ratio = capped.sold / max(1, flat.sold)
    results.append(check(
        "per-listing cap raises throughput at scale", f"{ratio:.1f}x", ">=1.5x", ratio >= 1.5,
        f"flat 10% sold {flat.sold:,} | capped sold {capped.sold:,} -> {ratio:.1f}x"))

    # 2 | the starter grant raises cold-start throughput
    nohelp = Circuit(500, 5000, 2000, 0.5, 0.5, 400, cap=cap, grant=0, fee=0).run(24)
    helped = Circuit(500, 5000, 2000, 0.5, 0.5, 400, cap=cap, grant=grant, fee=0).run(24)
    lift = helped.sold / max(1, nohelp.sold)
    results.append(check(
        "starter grant raises cold-start throughput", f"{lift:.1f}x", ">=1.5x", lift >= 1.5,
        f"no help sold {nohelp.sold:,} | granted sold {helped.sold:,} -> {lift:.1f}x"))

    # 3 | hoarding costs cash without stopping trade
    healthy = Circuit(500, 5000, 2000, 0.5, 0.5, 10**9, cap=cap, grant=0, fee=0).run(24)
    hoard = Circuit(500, 5000, 2000, 0.5, 0.0, 10**9, cap=cap, grant=0, fee=0).run(24)
    more_cash = hoard.cash_in / max(1.0, healthy.cash_in)
    same_trade = abs(hoard.sold - healthy.sold) / max(1, healthy.sold) < 0.10
    results.append(check(
        "hoarding raises cash demand, trade continues", f"{more_cash:.2f}x cash", ">=1.3x",
        more_cash >= 1.3 and same_trade,
        f"cash PHP{healthy.cash_in:,.0f} -> PHP{hoard.cash_in:,.0f} ({more_cash:.2f}x) "
        f"with sales {healthy.sold:,} vs {hoard.sold:,}"))

    # 4 | the holding fee separates spam from slow selling
    res = 2000 * REWARD_PCT
    honest = res * fee * 2                 # sells in two months
    spam = 50 * res * fee * 12             # 50 junk listings held a year
    results.append(check(
        "holding fee separates spam from slow selling", f"PHP{honest:,.0f} vs PHP{spam:,.0f}",
        "honest<PHP20, spam>PHP1000", honest < 20 and spam > 1000,
        f"honest 2-month listing PHP{honest:,.0f} | 50 junk listings for a year PHP{spam:,.0f}"))

    # 5 | the supply cap binds where predicted
    big = Circuit(20000, 100000, 2000, 0.5, 0.5, 10**9, cap=cap, grant=0, fee=0).run(12)
    used = big.cash_in / SUPPLY
    results.append(check(
        "supply cap binds at scale", f"{used:.0%} of supply", ">=95%", used >= 0.95,
        f"20,000 providers consumed PHP{big.cash_in:,.0f} of the PHP{SUPPLY:,} supply"))

    return results


def selftest():
    """The pinned known-good case. An early version reported a jam that did not exist because
    int(1 * 0.5) truncates to zero; if that regresses, sales collapse and this catches it."""
    print(f"  {D}selftest: a one-listing-per-provider market must still SELL{X}")
    c = Circuit(100, 1000, 2000, 0.5, 0.5, 10**9, cap=CAP_PER_LISTING, grant=0, fee=0).run(6)
    ok = c.sold > 100
    print(f"  {(G+'PASS'+X) if ok else (R+'FAIL'+X)}  100 providers, 50% sell-through, 6 months "
          f"-> {c.sold:,} sold {D}(truncation bug would give ~0){X}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", choices=["cap", "grant", "fee"],
                    help="disable a lever; the run MUST go red")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()

    print(f"{B}WorkHive credit circuit -- simulation gate{X}")
    print("=" * 78)

    if a.selftest:
        return 0 if selftest() else 1

    if not selftest():
        print(f"\n  {R}selftest failed -- refusing to report results from an instrument that is broken{X}")
        return 1
    print()

    if a.inject:
        print(f"  {Y}INJECTED: '{a.inject}' disabled -- this run is EXPECTED to fail{X}\n")

    results = assertions(a.inject)
    passed, total = sum(results), len(results)
    print()

    if a.inject:
        if passed < total:
            print(f"  {G}TEETH CONFIRMED{X} -- removing '{a.inject}' broke {total - passed} assertion(s). "
                  f"{D}A simulator that cannot fail proves nothing.{X}")
            return 0
        print(f"  {R}NO TEETH{X} -- removing '{a.inject}' changed nothing. The assertion is vacuous.")
        return 1

    if passed == total:
        print(f"  {G}{B}All {total} assertions hold.{X} {D}Every credit-economy default is still "
              f"backed by the measurement that chose it.{X}")
        return 0
    print(f"  {R}{B}{total - passed} of {total} assertions FAILED.{X}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
