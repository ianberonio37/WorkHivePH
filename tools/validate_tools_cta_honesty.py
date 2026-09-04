#!/usr/bin/env python3
"""tools-cta-honesty — T3/T153: the calculator pages state the account requirement (2026-08-26).

The 60 /tools/ pages are the top of this funnel: a searcher looking for "OEE
calculator" lands on one, and what it promises decides whether the next click is
trust or a bounce.

MEASURED 2026-08-26, and the human-facing story is HONEST. None of the 60 embeds
a calculator - they are landing pages that explain a calculation and hand off -
and every one says so plainly: "Open the interactive OEE Calculator in WorkHive:
free with a WorkHive account. Sign-up takes about 30 seconds." ZERO pages still
carry the "no sign-up needed" claim that T3 recorded, which linked into a gated
page and was false twice over.

THE ASSERTION: no tools page may claim a calculator needs no account, and every
one must state the requirement where it hands off. That is what keeps a fixed
claim fixed - the old wording lived in a template, so it came back everywhere at
once when it came back at all.

★A RECORDED FINDING THIS GATE DELIBERATELY DOES NOT ENFORCE. Every one of the 60
declares JSON-LD "@type": "SoftwareApplication" with an Offer of price 0 and a
url pointing at the LANDING page - so a search or answer engine reads "there is a
free web application here", follows the url, and finds a page about an
application that lives somewhere else. The human-facing CTA is honest; the
machine-facing claim overclaims. Pointing that url at the app would make it true
in one line, but rewriting the structured data of 60 pages changes how the
platform is presented in search - an outward-facing decision with consequences
nobody can quietly reverse, so it is written up rather than done.

Usage: python tools/validate_tools_cta_honesty.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

FALSE_CLAIM = re.compile(r"no sign-?up needed|no account needed|without signing up|no registration|"
                         r"no account required", re.I)
# the handoff must say an account is involved
STATES_ACCOUNT = re.compile(r"with a WorkHive account|free with an account|sign-?up|create an account|"
                            r"account required", re.I)
HANDOFF = re.compile(r'href="/?engineering-design\.html')


def main() -> int:
    files = sorted(glob.glob(str(ROOT / "tools" / "*" / "index.html")))
    if not files:
        print("SKIP tools-cta-honesty — no tools pages found")
        return 0

    liars, silent = [], []
    for f in files:
        name = Path(f).parent.name
        src = io.open(f, encoding="utf-8", errors="replace").read()
        if FALSE_CLAIM.search(src):
            liars.append(name)
        if HANDOFF.search(src) and not STATES_ACCOUNT.search(src):
            silent.append(name)

    print(f"  tools pages checked: {len(files)}")
    fails = []
    if liars:
        fails.append(f"{len(liars)} page(s) claim a calculator needs NO sign-up while handing off to a "
                     f"gated page: {', '.join(liars[:6])}")
    if silent:
        fails.append(f"{len(silent)} page(s) hand off to the app without saying an account is involved: "
                     f"{', '.join(silent[:6])}")

    if fails:
        print("FAIL tools-cta-honesty:")
        for x in fails:
            print("    - " + x)
        print("    A searcher who follows a 'no sign-up' promise into a sign-in wall does not try again.")
        print("    Say what it costs at the moment of the click: 'free with a WorkHive account'.")
        return 1
    print(f"PASS tools-cta-honesty — all {len(files)} calculator pages state the account requirement "
          f"where they hand off, and none claims otherwise.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
