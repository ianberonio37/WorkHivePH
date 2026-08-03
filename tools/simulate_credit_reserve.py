#!/usr/bin/env python3
"""simulate_credit_reserve.py — does the 10,000,000 reserve survive, and what is the minimum listing?

IAN'S MODEL, STATED PRECISELY (2026-08-03, his correction — the earlier reading was wrong):

  · A provider may list a product OR a service ONLY while holding the listing's 10% in credits.
    No credits -> no listing. The provider BUYS credits from WorkHive first.
  · Buying DEDUCTS from the 10,000,000 reserve and ADDS to credits in circulation. The cap is a
    reserve pool, not an accounting ceiling.
  · A buyer holding NO credits pays the full GCash price and RECEIVES the 10% (the provider's
    reservation passes to them).
  · A buyer holding credits may pay AT MOST 10% of the price in credits, the rest in cash.

THE RULE, as of migration 35:

    reserve  R(P) = 0.10 * P, NO ceiling       listing_reservation_amount()
    spend    S    <= 0.10 * P, no ceiling      guard_reward_spend_cap()

Symmetric at every price: what a provider commits to list is exactly what the buyer receives, and
exactly the most that buyer can later spend on a purchase of the same size.

Until mig 35 the reserve side was min(0.10*P, PHP500) while the spend side was uncapped, so a
PHP50,000 sale gave the buyer PHP500 but let them spend PHP5,000 — a 10x asymmetry, and a
PHP1,000,000 listing committed 0.05% of its value rather than 10%. Ian: "there should be no capped
as long as it should be 10% of the listing price". cap_versus_flat() measures what that ceiling was
buying, so the trade is known rather than assumed.

THE THREE QUESTIONS THIS ANSWERS:
  1. Does the reserve deplete, and what actually exhausts it?
  2. What is the binding constraint on marketplace size?
  3. Where should the MINIMUM LISTING price sit?

WHY A SIMULATION AND NOT ARITHMETIC. The closed form is easy for one trade and useless in aggregate,
because the flows are coupled: a buyer can only spend what some provider's reservation earlier gave
them, and a provider can only list if some buyer's spend (or a fresh purchase) funded them. That
feedback is what decides whether credits circulate or silt up, and it is not visible in a formula.

TEETH. `--inject` breaks a lever and the matching finding must MOVE. A simulator that reports the
same answer with the mechanism removed was never measuring the mechanism.

Usage:
  python tools/simulate_credit_reserve.py                    all scenarios
  python tools/simulate_credit_reserve.py --minimum          the minimum-listing sweep only
  python tools/simulate_credit_reserve.py --inject nocap     prove the PHP500 cap is load-bearing
  python tools/simulate_credit_reserve.py --selftest         pinned known-good arithmetic
"""
import argparse
import random
import sys

GREEN, RED, YEL, DIM, BOLD, CYAN, RST = (
    "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[96m", "\033[0m")

SUPPLY_CAP = 10_000_000
REWARD_PCT = 0.10
SPEND_CAP_PCT = 0.10
# NO CAP is the rule (Ian, 2026-08-03; mig 35). None = no ceiling. The old PHP500 value is kept only
# as a named contrast in cap_versus_flat(), never as a default -- a default is what silently governs.
MAX_PER_LISTING = None
LEGACY_CAP = 500           # what the code did until mig 35, retained to measure what changed
MIN_LIST_BALANCE = 200     # a provider must hold this much before listing at all


def reservation(price, max_per_listing=MAX_PER_LISTING, reward_pct=REWARD_PCT):
    """R(P) = pct * P, with no ceiling. The live listing_reservation_amount(), in Python.

    A cap makes the reservation SUBLINEAR: at PHP500 a PHP1,000,000 listing committed 0.05% of its
    value instead of 10%, and its buyer received PHP500 instead of PHP50,000. Passing
    max_per_listing is only for measuring that difference, never for running the model."""
    r = price * reward_pct
    if max_per_listing is not None:
        r = min(r, max_per_listing)
    return round(r, 2)


class World:
    """One marketplace. Every peso and credit is conserved by construction, and _audit() proves it."""

    def __init__(self, rng, max_per_listing=MAX_PER_LISTING, min_listing=0,
                 min_list_balance=MIN_LIST_BALANCE):
        self.rng = rng
        self.max_per_listing = max_per_listing
        self.min_listing = min_listing
        self.min_list_balance = min_list_balance

        self.reserve = SUPPLY_CAP          # credits WorkHive has never sold
        self.provider_wallets = {}         # free credits, per provider
        self.buyer_wallets = {}            # free credits, per buyer
        self.locked = 0.0                  # credits reserved against live listings
        self.cash_in = 0.0                 # pesos WorkHive collected for credits (a LIABILITY)

        self.listed = 0
        self.blocked_no_reserve = 0        # could not list: the 10M is exhausted
        self.blocked_cannot_afford = 0     # could not list: provider could not fund the 10%
        self.blocked_below_minimum = 0     # refused by the minimum-listing rule
        self.sold_earn = 0                 # buyer paid full cash and EARNED the reservation
        self.sold_spend = 0                # buyer paid part in credits
        self.gmv = 0.0
        self.credits_earned_total = 0.0
        self.credits_spent_total = 0.0
        self.reserve_low_water = SUPPLY_CAP

    # ── invariant: nothing is created or destroyed ──────────────────────────────────────────────
    def circulation(self):
        return sum(self.provider_wallets.values()) + sum(self.buyer_wallets.values()) + self.locked

    def _audit(self):
        total = self.reserve + self.circulation()
        assert abs(total - SUPPLY_CAP) < 0.01, f"credits leaked: {total} != {SUPPLY_CAP}"
        # every credit in circulation was bought for exactly PHP1
        assert abs(self.cash_in - (SUPPLY_CAP - self.reserve)) < 0.01, \
            f"cash {self.cash_in} != credits sold {SUPPLY_CAP - self.reserve}"

    def buy_credits(self, provider, amount):
        """Provider buys credits from WorkHive. Reserve -> circulation. Returns what they got."""
        got = min(amount, self.reserve)
        if got <= 0:
            return 0.0
        self.reserve -= got
        self.provider_wallets[provider] = self.provider_wallets.get(provider, 0.0) + got
        self.cash_in += got
        self.reserve_low_water = min(self.reserve_low_water, self.reserve)
        return got

    def try_list(self, provider, price):
        """-> True if the listing went live."""
        if price < self.min_listing:
            self.blocked_below_minimum += 1
            return False
        need = reservation(price, self.max_per_listing)
        have = self.provider_wallets.get(provider, 0.0)

        # A provider short of the reservation buys the shortfall -- and enough to clear the
        # min_list_balance floor, which is the real gate on a first listing.
        target = max(need, self.min_list_balance)
        if have < target:
            self.buy_credits(provider, target - have)
            have = self.provider_wallets.get(provider, 0.0)

        if have < need:
            # Only reachable when the reserve itself ran dry.
            if self.reserve <= 0:
                self.blocked_no_reserve += 1
            else:
                self.blocked_cannot_afford += 1
            return False

        self.provider_wallets[provider] = have - need
        self.locked += need
        self.listed += 1
        return True

    def sell(self, provider, buyer, price, buyer_will_spend):
        """Complete a sale. Exactly one of the two paths fires -- earn or spend, never both."""
        need = reservation(price, self.max_per_listing)
        self.locked -= need
        self.gmv += price
        bal = self.buyer_wallets.get(buyer, 0.0)
        spend_cap = price * SPEND_CAP_PCT      # NOTE: no PHP500 ceiling on the spend side

        if buyer_will_spend and bal > 0:
            spend = min(bal, spend_cap)
            self.buyer_wallets[buyer] = bal - spend
            # the provider receives the spent credits AND keeps their own reservation back
            self.provider_wallets[provider] = self.provider_wallets.get(provider, 0.0) + need + spend
            self.credits_spent_total += spend
            self.sold_spend += 1
        else:
            # the reservation passes to the buyer: this is the ONLY way a buyer ever gets credits
            self.buyer_wallets[buyer] = bal + need
            self.credits_earned_total += need
            self.sold_earn += 1


def run(label, rng_seed=7, n_providers=400, n_buyers=2000, rounds=600,
        price_fn=None, spend_propensity=0.5, max_per_listing=MAX_PER_LISTING,
        min_listing=0, sell_prob=0.55, verbose=False):
    rng = random.Random(rng_seed)
    price_fn = price_fn or (lambda r: r.choice([800, 1500, 3000, 5000, 12000, 45000]))
    w = World(rng, max_per_listing=max_per_listing, min_listing=min_listing)

    live = []   # (provider, price)
    for _ in range(rounds):
        # providers try to list
        for _ in range(max(1, n_providers // 20)):
            p = rng.randrange(n_providers)
            price = price_fn(rng)
            if w.try_list(p, price):
                live.append((p, price))
        # some live listings sell
        rng.shuffle(live)
        keep = []
        for (p, price) in live:
            if rng.random() < sell_prob / 10:
                b = rng.randrange(n_buyers)
                will_spend = rng.random() < spend_propensity
                w.sell(p, b, price, will_spend)
            else:
                keep.append((p, price))
        live = keep
        w._audit()

    w._audit()
    pct_left = 100.0 * w.reserve / SUPPLY_CAP
    if verbose:
        print(f"  {BOLD}{label}{RST}")
        print(f"    listed {w.listed:>6}  sold {w.sold_earn + w.sold_spend:>6} "
              f"(earn {w.sold_earn} / spend {w.sold_spend})   GMV PHP{w.gmv:>13,.0f}")
        print(f"    reserve left {pct_left:>6.2f}%   circulation PHP{w.circulation():>10,.0f}   "
              f"cash held PHP{w.cash_in:>10,.0f}")
        blocked = w.blocked_no_reserve + w.blocked_cannot_afford + w.blocked_below_minimum
        print(f"    blocked {blocked:>6}  ({DIM}reserve-dry {w.blocked_no_reserve} · "
              f"unaffordable {w.blocked_cannot_afford} · below-min {w.blocked_below_minimum}{RST})")
    return w


def scenarios(inject=None):
    print(f"{BOLD}Credit reserve — Ian's model, measured{RST}")
    print(f"{DIM}  reserve R(P)=10%*P (NO cap, mig 35)   spend S<=10%*P   "
          f"supply {SUPPLY_CAP:,}{RST}\n")

    cap = LEGACY_CAP if inject == "nocap" else MAX_PER_LISTING
    if inject == "nocap":
        print(f"  {YEL}INJECTED{RST}: the retired PHP500 cap is put BACK, to show what it changed\n")

    results = {}
    cases = [
        ("baseline            mixed prices, half the buyers spend", dict(spend_propensity=0.5)),
        ("HOARDERS            buyers never spend their credits",    dict(spend_propensity=0.0)),
        ("spenders            buyers always spend when able",       dict(spend_propensity=1.0)),
        ("all-small           every listing PHP500-PHP5,000",
         dict(price_fn=lambda r: r.choice([500, 800, 1500, 3000, 5000]), spend_propensity=0.5)),
        ("all-industrial      every listing PHP20,000-PHP500,000",
         dict(price_fn=lambda r: r.choice([20000, 50000, 120000, 500000]), spend_propensity=0.5)),
    ]
    for label, kw in cases:
        w = run(label, max_per_listing=cap, **kw)
        results[label.split()[0]] = w
        pct = 100.0 * w.reserve / SUPPLY_CAP
        colour = GREEN if pct > 50 else YEL if pct > 10 else RED
        blocked = w.blocked_no_reserve + w.blocked_cannot_afford
        print(f"  {label:<52} reserve {colour}{pct:>6.2f}%{RST} left · "
              f"sold {w.sold_earn + w.sold_spend:>5} · blocked {blocked:>5} · "
              f"GMV PHP{w.gmv:>12,.0f}")
    print()
    return results


def minimum_listing_sweep():
    """Where should the floor sit? Measured on the three things a floor actually changes."""
    print(f"{BOLD}Minimum listing amount — what a floor buys and what it costs{RST}\n")
    print(f"  {DIM}reward = 10% of price, so the floor decides whether the credit a buyer earns is a "
          f"number they can act on{RST}")
    print(f"  {DIM}spam cost = the 10% a squatter must LOCK per listing (recoverable on delist) "
          f"+ the 2%/month holding fee{RST}\n")
    print(f"  {'floor':>8}  {'reward at floor':>16}  {'lock 100 listings':>18}  "
          f"{'holding/yr':>11}   verdict")
    for floor in [0, 50, 100, 200, 500, 1000, 2000, 5000]:
        reward = reservation(floor) if floor else 0.0
        lock100 = reservation(floor) * 100 if floor else 0.0
        holding = floor * 0.02 * 12
        if floor == 0:
            verdict = "no floor: a PHP1 listing earns PHP0.10 - unusable, and free to spam"
        elif reward < 1:
            verdict = f"{RED}reward PHP{reward:.2f} rounds to nothing a buyer can spend{RST}"
        elif reward < 20:
            verdict = f"{YEL}reward PHP{reward:.0f} is real but not persuasive{RST}"
        elif floor >= 2000:
            verdict = f"{YEL}excludes genuine small parts (a PHP800 bearing){RST}"
        else:
            verdict = f"{GREEN}reward PHP{reward:.0f} is noticeable; spam locks PHP{lock100:,.0f}/100{RST}"
        print(f"  {('none' if not floor else f'PHP{floor:,}'):>8}  "
              f"{('-' if not floor else f'PHP{reward:,.2f}'):>16}  "
              f"{('-' if not floor else f'PHP{lock100:,.0f}'):>18}  "
              f"{('-' if not floor else f'PHP{holding:,.0f}'):>11}   {verdict}")
    print()

    # And the throughput cost of each floor, measured rather than reasoned.
    print(f"  {DIM}throughput cost of the floor, on a price mix that includes genuine small parts:{RST}")
    mix = lambda r: r.choice([200, 400, 800, 1500, 3000, 5000, 12000, 45000])
    for floor in [0, 100, 500, 1000, 2000]:
        w = run("", price_fn=mix, min_listing=floor, spend_propensity=0.5)
        lost = w.blocked_below_minimum
        pct_lost = 100.0 * lost / max(1, lost + w.listed)
        colour = GREEN if pct_lost < 15 else YEL if pct_lost < 30 else RED
        print(f"    floor {('none' if not floor else f'PHP{floor:,}'):>8}: "
              f"{w.listed:>5} listed · {lost:>5} refused ({colour}{pct_lost:.1f}% of attempts{RST}) · "
              f"GMV PHP{w.gmv:>12,.0f}")
    print()


def binding_constraint():
    print(f"{BOLD}What actually bounds the marketplace{RST}\n")
    print(f"  {DIM}Every live listing LOCKS its reservation, so the reserve caps how much can be "
          f"listed AT ONCE.{RST}")
    for price, label in [(1000, "small parts"), (5000, "the cap's hinge"), (50000, "industrial"),
                         (500000, "major equipment")]:
        r = reservation(price)
        max_live = SUPPLY_CAP / r
        print(f"    PHP{price:>8,} listings  reserve PHP{r:>6,.2f} each  ->  "
              f"{BOLD}{max_live:>12,.0f}{RST} concurrent listings "
              f"({DIM}PHP{max_live * price:>16,.0f} of inventory{RST})  {DIM}{label}{RST}")
    print(f"\n  {BOLD}PHP100,000,000 of concurrent inventory, at EVERY price point.{RST}"
          f"{DIM} That is what a flat 10% against a 10,000,000 reserve means, and it is the same "
          f"number whether the marketplace lists bearings or turbines — which is exactly what makes "
          f"the rule legible.{RST}")
    print(f"  {DIM}The lever for growing past it is the SUPPLY CAP itself, not a per-listing ceiling. "
          f"Credits sell 1:1, so PHP10,000,000 of cash collected backs PHP100,000,000 of listed "
          f"inventory — a 10x multiplier that is inherent to the 10% rule.{RST}\n")


def cap_versus_flat():
    """IAN'S RULE ('10% of the total listing') vs THE CODE (min(10%, PHP500)).

    They are different rules and the code has been running the capped one since migration
    20260803000006, where a 720-run sweep chose it AGAINST instinct: 'at 20,000 providers listing
    PHP25,000 items, a flat 10% sold 4,077 listings; a PHP500 ceiling sold 19,994 (4.9x)'.

    That measurement was taken under the OLD economy (commission + cashback, both now retired), so it
    is re-run here under Ian's clarified rules rather than quoted. A number inherited from a superseded
    model is folklore until it is measured again."""
    print(f"{BOLD}The PHP500 cap vs a flat 10% — re-measured under the clarified rules{RST}\n")
    print(f"  {DIM}Ian's stated rule is a flat 10%. The code caps at PHP500. This is the cost of "
          f"each, on the industrial mix where they diverge most.{RST}\n")
    print(f"  {'listing price':>14}  {'flat 10% locks':>15}  {'capped locks':>13}  "
          f"{'sold (flat)':>12}  {'sold (capped)':>14}  {'blocked (flat)':>15}")
    for price in [5_000, 25_000, 100_000]:
        pf = lambda r, _p=price: _p
        flat = run("", n_providers=20_000, n_buyers=40_000, rounds=200, price_fn=pf,
                   max_per_listing=None, spend_propensity=0.5, sell_prob=0.25)
        capped = run("", n_providers=20_000, n_buyers=40_000, rounds=200, price_fn=pf,
                     max_per_listing=LEGACY_CAP, spend_propensity=0.5, sell_prob=0.25)
        fb = flat.blocked_no_reserve + flat.blocked_cannot_afford
        fsold, csold = flat.sold_earn + flat.sold_spend, capped.sold_earn + capped.sold_spend
        ratio = (csold / fsold) if fsold else float("inf")
        colour = RED if ratio > 1.5 else GREEN
        print(f"  PHP{price:>11,}  PHP{price * 0.10:>12,.0f}  PHP{reservation(price, LEGACY_CAP):>10,.0f}  "
              f"{fsold:>12,}  {csold:>14,}  {RED if fb else GREEN}{fb:>15,}{RST}"
              f"   {colour}{ratio:.2f}x{RST}")
    print(f"\n  {DIM}The cap only matters ABOVE PHP5,000 — below that the two rules are identical, "
          f"because 10% is already under the ceiling.{RST}\n")


def scale_sweep():
    """WHERE DOES IT ACTUALLY BREAK? The baseline scenarios all report 'blocked 0', which is not a
    reassurance — it means the run never reached the constraint, and a simulation that never reaches
    its constraint has not tested it. So grow the marketplace until listings start being refused, and
    report the size at which that happens. THIS is the number the business plan needs."""
    print(f"{BOLD}Scale — at what size does the reserve actually bind?{RST}\n")
    print(f"  {DIM}Growing concurrent providers until a listing is refused for want of credits. "
          f"Worst case (nobody spends) alongside the realistic mix.{RST}\n")
    print(f"  {'providers':>10}  {'listings live':>14}  {'reserve left':>13}  {'blocked':>8}   "
          f"{'reserve left':>13}  {'blocked':>8}")
    print(f"  {'':>10}  {'':>14}  {CYAN}{'—— half spend ——':>22}{RST}   {YEL}{'—— none spend ——':>22}{RST}")
    for n in [500, 2_000, 10_000, 25_000, 60_000, 150_000]:
        rows = []
        for prop in (0.5, 0.0):
            # sell_prob low + many providers => listings accumulate, which is what locks credits up
            w = run("", n_providers=n, n_buyers=max(1000, n * 4), rounds=260,
                    spend_propensity=prop, sell_prob=0.25)
            blocked = w.blocked_no_reserve + w.blocked_cannot_afford
            rows.append((w, blocked))
        (w1, b1), (w2, b2) = rows
        p1 = 100.0 * w1.reserve / SUPPLY_CAP
        p2 = 100.0 * w2.reserve / SUPPLY_CAP
        c1 = GREEN if b1 == 0 else RED
        c2 = GREEN if b2 == 0 else RED
        print(f"  {n:>10,}  {w1.listed:>14,}  {p1:>12.2f}%  {c1}{b1:>8,}{RST}   "
              f"{p2:>12.2f}%  {c2}{b2:>8,}{RST}")
    print(f"\n  {DIM}A refusal here is not a provider inconvenience — it is a listing that never "
          f"reaches a buyer, so the reserve running dry presents as MISSING SUPPLY.{RST}\n")


def selftest():
    print("  selftest: pinned arithmetic and the conservation invariant")
    ok = True
    if reservation(5000) != 500.0:
        print(f"  {RED}FAIL{RST} reservation(5000) should be exactly the cap"); ok = False
    if reservation(1000) != 100.0:
        print(f"  {RED}FAIL{RST} reservation(1000) should be a true 10%"); ok = False
    # THE RULE, post-mig-35: a true 10% at every price, with no ceiling anywhere.
    if reservation(1_000_000) != 100_000.0:
        print(f"  {RED}FAIL{RST} a PHP1,000,000 listing must reserve a full 10% (PHP100,000), not a "
              f"capped figure — the ceiling was removed in mig 35"); ok = False
    if reservation(50_000) != 5_000.0:
        print(f"  {RED}FAIL{RST} reservation must stay linear above the old PHP5,000 hinge"); ok = False
    # and the legacy cap must still be measurable, or cap_versus_flat() proves nothing
    if reservation(1_000_000, max_per_listing=LEGACY_CAP) != 500.0:
        print(f"  {RED}FAIL{RST} the legacy-cap contrast is broken"); ok = False
    w = run("", rounds=60, spend_propensity=0.5)
    w._audit()   # raises if credits or cash leaked
    if w.listed == 0 or (w.sold_earn + w.sold_spend) == 0:
        print(f"  {RED}FAIL{RST} the pinned run neither listed nor sold anything — a vacuous pass")
        ok = False
    # hoarding must cost MORE reserve than spending: the whole thesis
    hoard = run("", spend_propensity=0.0)
    spend = run("", spend_propensity=1.0)
    if not hoard.reserve < spend.reserve:
        print(f"  {RED}FAIL{RST} hoarding did not consume more reserve than spending "
              f"({hoard.reserve:,.0f} vs {spend.reserve:,.0f}) — the model is not capturing the loop")
        ok = False
    if ok:
        print(f"  {GREEN}PASS{RST} — arithmetic pinned, credits+cash conserved, hoarding costs more "
              f"reserve than spending")
    return 0 if ok else 1


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--minimum", action="store_true")
    ap.add_argument("--inject", choices=["nocap"])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if selftest() != 0:
        return 1
    print()
    if a.minimum:
        minimum_listing_sweep()
        return 0
    scenarios(inject=a.inject)
    binding_constraint()
    cap_versus_flat()
    scale_sweep()
    minimum_listing_sweep()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
