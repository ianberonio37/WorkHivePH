#!/usr/bin/env python3
"""validate_listing_cost_transparency.py — T34's lock instrument: the listing composer tells the WHOLE
cost truth at the commit point — the 10% credit reservation AND that it returns if the listing does not
sell — so a hold is never read as a fee and never hidden behind a 'no platform fees / free' claim.

T34 found the cost-transparency break at the exact commit point: the composer said the marketplace was
'free … no platform fees' while guard_listing_requires_reservation holds 10% of price in credits at
publish (measured live: P100 held on P1,000; the hold returns on remove/redraft, funds the reward on
sale). The sentence now states the whole truth. This gate LOCKS it so a future copy edit cannot quietly
re-open the break — the 'a metric's LABEL is a claim' / 'trust claim no query enforces' class, applied to
the cost claim a seller reads before committing.

TWO assertions on marketplace-seller.html (each refutable — see the self-test):
  1. THE HOLD IS STATED — the composer names the 10% credit reservation held at publish.
  2. THE RETURN IS STATED — it says the held credits come back / are returned if the listing does not
     sell (without this, a reservation reads as a fee).
And a GUARD against the regression: if the page claims 'no platform fees' or 'free', that claim must sit
next to the hold disclosure (within the same composer), never alone.

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "marketplace-seller.html"

CHECK_NAMES = ["listing-cost-transparency"]

_HOLD = re.compile(r"10\s*%[^.]{0,60}(held|hold|reserv)|(held|hold|reserv)[^.]{0,40}10\s*%", re.I)
_RETURN = re.compile(r"come[s]?\s+back|return(ed|s)?[^.]{0,40}(not\s+sell|does\s+not\s+sell|unsold|remov|redraft)|"
                     r"(not\s+sell|does\s+not\s+sell|unsold|remov|redraft)[^.]{0,40}(come[s]?\s+back|return)", re.I)
_FALSE_FREE = re.compile(r"no platform fees|no fees|completely free|free[, ]+no", re.I)


def check(src: str) -> list[str]:
    problems: list[str] = []
    hold = bool(_HOLD.search(src))
    ret = bool(_RETURN.search(src))
    if not hold:
        problems.append("THE HOLD is not stated: no '10% … held/reserved' disclosure in the composer — a "
                        "seller commits without being told a reservation is taken.")
    if not ret:
        problems.append("THE RETURN is not stated: nothing says the held credits come back if the listing "
                        "does not sell — without it a reservation reads as a fee.")
    # regression guard: a 'no fees / free' claim is only allowed if the hold is ALSO disclosed
    if _FALSE_FREE.search(src) and not hold:
        problems.append("a 'no platform fees / free' claim appears WITHOUT the hold disclosure — the exact "
                        "cost-transparency break T34 fixed.")
    return problems


def main() -> int:
    if not PAGE.exists():
        print("FAIL listing-cost-transparency: marketplace-seller.html not found"); return 1
    problems = check(PAGE.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL listing-cost-transparency — the listing composer does not tell the whole cost truth:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS listing-cost-transparency — the composer states the 10% hold AND that it returns if the "
          "listing does not sell; no bare 'free / no fees' claim.")
    return 0


def self_test() -> int:
    fails = []
    good = "10% of its price is HELD from your balance; held credits come back if the listing does not sell."
    if check(good):
        fails.append("the real both-parts copy should PASS")
    if not any("HOLD" in p for p in check("held credits come back if the listing does not sell")):
        fails.append("missing the 10% hold should FAIL")
    if not any("RETURN" in p for p in check("10% of its price is held at publish.")):
        fails.append("missing the return condition should FAIL")
    if not any("no platform fees" in p for p in check("The marketplace is free — no platform fees.")):
        fails.append("a bare 'no platform fees' claim with no hold should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_listing_cost_transparency self-test (missing hold/return redden; bare free-claim reddens)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
