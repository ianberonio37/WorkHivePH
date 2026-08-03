#!/usr/bin/env python3
"""validate_payment_rails.py -- three GCash accounts, and only one of them may ever be on a given screen.

THE TOPOLOGY, because it is the whole reason this gate exists. WorkHive has no business registration and
therefore no merchant account, so every rail is a PERSONAL GCash number:

    JOB PAYMENT     buyer's GCash  ->  PROVIDER's own GCash        (the platform never touches it)
    CREDIT TOP-UP   provider's GCash -> THE FOUNDER's personal GCash 0995 009 2416
    CREDITS SPEND   no GCash at all - a ledger transfer between two wallets

THE INVARIANT: the founder's number may appear ONLY on the provider's top-up card. It must never appear
on a buyer-facing payment step. If a buyer ever reads 0995 009 2416 beside "pay for this job", they send
job money to a person who is not party to the job, cannot fulfil it, and has no way to reconcile it
against any request. The money is not lost to a bug - it is lost to a stranger's honest reading of the
screen, which is worse, because nothing errors and nobody finds out until the provider asks where their
payment is.

This is also the specific friction Ian named: "I want it hassle free for my users, like the hassle of
payment two gcash accounts or anything". A buyer must see exactly ONE number - the provider's. A provider
sees exactly one OTHER number - the founder's - and only when stocking credits.

WHAT IS ASSERTED
  1. Every occurrence of the founder number sits on an allowed surface (the provider top-up card).
  2. No buyer-facing payment surface contains the founder number, in any spacing or punctuation.
  3. The buyer's confirm-payment step states that WorkHive holds no money - the no-custody sentence is
     load-bearing for a first-time user deciding whether this is a scam.
  4. The buyer's payment step names the PROVIDER as the payee, so "who do I pay" has one answer.

Usage:  python tools/validate_payment_rails.py [--selftest]
"""
from __future__ import annotations
import os
import re
import sys

GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The founder's personal number, in every spacing/punctuation a human or a template might produce.
FOUNDER_DIGITS = "09950092416"
FOUNDER_RE = re.compile(r"0\D?9\D?9\D?5\D?0\D?0\D?9\D?2\D?4\D?1\D?6")

# The ONLY surface allowed to print it: the provider's credit top-up card.
ALLOWED_SURFACES = {"marketplace-seller.html"}

# Buyer-facing payment surfaces: a buyer decides "who do I pay" here.
BUYER_PAYMENT_SURFACES = {"marketplace.html", "marketplace-seller-profile.html"}

NO_CUSTODY_RE = re.compile(r"never holds your money|does not hold your money|hindi hinahawakan", re.I)
PAYEE_RE = re.compile(r"pay the provider|provider directly|directly to the provider|"
                      r"binabayaran ang provider|direkta", re.I)


def read(name):
    p = os.path.join(ROOT, name)
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return None


def judge(occurrences, buyer_hits, no_custody, names_payee):
    """-> list of problems. Pure, so the reasoning is testable without the repo."""
    p = []
    for surface in sorted(occurrences):
        if surface not in ALLOWED_SURFACES:
            p.append(f"the founder's personal GCash number appears on {surface}, which is not the "
                     f"provider top-up card. Only the top-up flow may show it.")
    for surface in sorted(buyer_hits):
        p.append(f"{surface} shows the FOUNDER's number on a BUYER-FACING payment step. A buyer reading "
                 f"that pays the wrong person for a job the founder is not party to, and nothing errors.")
    if not no_custody:
        p.append("the buyer's confirm-payment step never says WorkHive holds no money - the sentence a "
                 "first-time user decides on")
    if not names_payee:
        p.append("the buyer's payment step does not name the PROVIDER as the payee, so 'who do I pay' "
                 "has no answer on the screen where it is asked")
    return p


def selftest():
    print("  selftest: each rail failure must be caught, and a correct topology must pass clean")
    ok = True
    if not judge({"marketplace.html"}, set(), True, True):
        print(f"  {RED}FAIL{RST} - the founder number on a non-top-up surface was not caught"); ok = False
    if not judge(set(), {"marketplace.html"}, True, True):
        print(f"  {RED}FAIL{RST} - the founder number on a BUYER payment step was not caught"); ok = False
    if not judge(set(), set(), False, True):
        print(f"  {RED}FAIL{RST} - a missing no-custody sentence was not caught"); ok = False
    if not judge(set(), set(), True, False):
        print(f"  {RED}FAIL{RST} - an unnamed payee was not caught"); ok = False
    if judge({"marketplace-seller.html"}, set(), True, True):
        print(f"  {RED}FAIL{RST} - a correct topology was flagged"); ok = False
    if ok:
        print(f"  {GREEN}PASS{RST} - catches all four rail failures, accepts the correct topology")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Payment rails{RST} - three GCash accounts, and only one may be on any given screen")
    if selftest() != 0:
        return 1

    occurrences, buyer_hits = set(), set()
    for fn in sorted(os.listdir(ROOT)):
        if not fn.endswith(".html"):
            continue
        src = read(fn)
        if src is None:
            continue
        # comments and docs describe the topology; only RENDERED strings can mislead a person
        body = re.sub(r"<!--[\s\S]*?-->", "", src)
        body = re.sub(r"/\*[\s\S]*?\*/", "", body)
        if FOUNDER_RE.search(body):
            occurrences.add(fn)
            if fn in BUYER_PAYMENT_SURFACES:
                buyer_hits.add(fn)

    mkt = read("marketplace.html") or ""
    no_custody = bool(NO_CUSTODY_RE.search(mkt))
    names_payee = bool(PAYEE_RE.search(mkt))

    print(f"  {DIM}founder number appears on : {', '.join(sorted(occurrences)) or '(nowhere)'}{RST}")
    print(f"  {DIM}buyer payment surfaces    : {', '.join(sorted(BUYER_PAYMENT_SURFACES))}{RST}")
    print(f"  {DIM}no-custody sentence       : {'present' if no_custody else 'MISSING'}{RST}")
    print(f"  {DIM}payee named as provider   : {'yes' if names_payee else 'NO'}{RST}")

    problems = judge(occurrences, buyer_hits, no_custody, names_payee)
    if problems:
        print(f"\n  {RED}FAIL{RST} - the payment rails can send money to the wrong person:")
        for x in problems:
            print(f"    . {x}")
        return 1
    print(f"\n  {GREEN}PASS{RST} - the founder's number lives only on the top-up card, the buyer's payment "
          f"step names the provider, and it says the platform holds nothing")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
