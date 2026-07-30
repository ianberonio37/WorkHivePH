#!/usr/bin/env python3
"""validate_payment_disclosure.py — MK8: while the platform holds no money, it must SAY so, there.

WorkHive's marketplace is contact-only. `PAYMENTS_ENABLED = false`, there is no escrow, and the buyer
arranges payment with a stranger off-platform. The whole of the money risk therefore sits at one
step — the moment the buyer sends an inquiry and takes the conversation off the site.

The `marketplace_orders` table already carries an escrow-shaped vocabulary (`pending_payment`,
`escrow_hold`, `released`, `refunded`) for a flow that is switched OFF. That is fine as schema; it is
NOT fine as a promise. RA 11967 (the PH Internet Transactions Act) requires consumer education on the
red flags in internet transactions, and a marketplace that stays silent lets a buyer assume protection
by default — the default assumption everywhere else online is that the platform holds the money.

The disclosure exists today, added during a deepwalk and locked by nothing:

    Before you pay: inspect the item first. Meet at the seller's business address or a public place.
    Avoid paying in full up front to a new seller. WorkHive never holds your payment, so we cannot
    reverse it.

TWO INVARIANTS, both only meaningful while the switch is off:
  1. the money step CARRIES that disclosure — "payment is off-platform" states a fact but does not
     warn; the buyer has to be told the platform cannot reverse anything
  2. no buyer-facing copy PROMISES escrow, buyer protection, a money-back guarantee or a secure/held
     payment — a promise the switch makes false

Usage:  python tools/validate_payment_disclosure.py [--selftest]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# The buyer's money step. Where the inquiry is composed is where the risk is taken.
MONEY_STEP = "marketplace.html"
SWITCH = "marketplace-admin.html"

# What the buyer must be told, as CLAIMS rather than as one exact sentence — the wording should be
# free to improve without reddening the gate, but the substance may not quietly drop out.
REQUIRED = [
    (r"never holds? your payment|does not hold your payment|we do not hold",
     "that WorkHive never holds the payment"),
    (r"cannot reverse|can'?t reverse|cannot refund|no refund",
     "that WorkHive therefore cannot reverse it"),
    (r"inspect|meet .*(public|business address)|in person",
     "a concrete precaution (inspect first / meet in a public or business place)"),
]

# Promises the switch makes false. `escrow_hold` as a STATUS STRING is schema, not a promise, so the
# search is for prose: the words as they would appear to a person.
FORBIDDEN = [
    (r"buyer protection|purchase protection|protected purchase", "buyer/purchase protection"),
    (r"money.?back guarantee", "a money-back guarantee"),
    (r"we hold your (payment|money|funds)", "that WorkHive holds the money"),
    (r"payments? (is|are) (secured|protected) by", "that payments are secured by the platform"),
    (r"escrow.protected|protected by escrow", "escrow protection"),
]


def payments_enabled() -> bool | None:
    p = os.path.join(ROOT, SWITCH)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        m = re.search(r"PAYMENTS_ENABLED\s*=\s*(true|false)", f.read())
    return None if not m else (m.group(1) == "true")


def visible_text(src: str) -> str:
    """Strip <script> and HTML comments: a reassurance living in a comment reassures nobody, and a
    forbidden phrase inside a code comment explaining why it is forbidden is not a promise."""
    src = re.sub(r"<script\b.*?</script>", " ", src, flags=re.S | re.I)
    src = re.sub(r"<!--.*?-->", " ", src, flags=re.S)
    return src


def check(src_visible: str):
    out = []
    for pat, claim in REQUIRED:
        ok = re.search(pat, src_visible, re.I) is not None
        out.append((ok, f"the money step states {claim}",
                    "a buyer who is never told assumes the platform stands behind the payment"))
    for pat, what in FORBIDDEN:
        hit = re.search(pat, src_visible, re.I)
        out.append((hit is None, f"no copy promises {what}",
                    f"found {hit.group(0)!r} while PAYMENTS_ENABLED is false" if hit else ""))
    return out


def main():
    if "--selftest" in sys.argv:
        return selftest()
    on = payments_enabled()
    print("=" * 84)
    print(f"  {BOLD}Payment disclosure (MK8) — a platform that holds no money must say so, there{RST}")
    print("=" * 84)
    if on is None:
        print(f"  {YEL}SKIP{RST} could not read PAYMENTS_ENABLED from {SWITCH}")
        return 0
    if on:
        print(f"  {YEL}SKIP{RST} PAYMENTS_ENABLED is TRUE — escrow exists, so these invariants are "
              f"about a different product. Re-derive them when payments ship.")
        return 0
    p = os.path.join(ROOT, MONEY_STEP)
    if not os.path.exists(p):
        print(f"  {YEL}SKIP{RST} {MONEY_STEP} not found")
        return 0
    with open(p, encoding="utf-8") as f:
        vis = visible_text(f.read())
    res = check(vis)
    bad = 0
    for ok, claim, detail in res:
        print(f"  {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}  {claim}"
              + (f"\n        {DIM}{detail}{RST}" if not ok and detail else ""))
        bad += 0 if ok else 1
    print()
    if bad:
        print(f"{RED}FAIL{RST} — {bad}/{len(res)} disclosure invariant(s) broken. The buyer is about "
              f"to hand money to a stranger the platform cannot vouch for.")
        return 1
    print(f"{GREEN}PASS{RST} — {len(res)} invariants: the money step warns plainly, and nothing "
          f"promises a protection this platform does not provide")
    return 0


def selftest():
    ok = True
    honest = ("<p>Before you pay: inspect the item first. Meet at a public place. WorkHive never "
              "holds your payment, so we cannot reverse it.</p>")
    silent = "<p>The marketplace is free: you arrange payment directly with the seller.</p>"
    lying = honest + "<p>Every order is covered by buyer protection.</p>"
    commented = silent + "<!-- WorkHive never holds your payment, so we cannot reverse it -->"
    for src, want, label in (
            (honest, 0, "an honest money step passes"),
            (silent, 3, "stating the fact without WARNING is caught (3 missing claims)"),
            (lying, 1, "a buyer-protection promise is caught even beside an honest warning"),
            (commented, 3, "a warning that lives only in an HTML COMMENT does not count")):
        got = len([r for r in check(visible_text(src)) if not r[0]])
        if got != want:
            print(f"  {RED}FAIL{RST} {label} (found {got}, expected {want})"); ok = False
        else:
            print(f"  {GREEN}PASS{RST} {label}")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
