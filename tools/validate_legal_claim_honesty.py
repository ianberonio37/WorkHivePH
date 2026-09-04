#!/usr/bin/env python3
"""legal-claim-honesty — T172: the terms may not promise what the product lacks (2026-08-26).

THE DEFECT. terms-of-service said, in two places:

  "You may export your data at any time and delete your account…"
  "You may stop using WorkHive and delete your account at any time."

Neither surface exists. There is no export-my-data control (T77) and no
account-deletion door (T164). A marketing page overclaiming is bad; a TERMS page
overclaiming is a promise at legal weight, made to a Philippine user exercising a
PDPA right, and it is the document they would point to.

THE FIX WAS NOT TO DELETE THE RIGHT — the right is real and the privacy policy
already documents how it is honoured: email admin@workhiveph.com with the subject
"Data Rights Request". The terms now say that, and say plainly that it is handled
by hand rather than through a button. Same right, true sentence. Both the HTML
and its .md twin were corrected, because a promise that survives in either copy is
a promise the product still has not kept.

THE ASSERTION: no legal surface may claim a SELF-SERVE capability the product does
not have. Each banned phrasing is paired with the control that would make it true,
so the day somebody builds account deletion, the claim becomes allowed by the same
gate that forbids it now.

★NOT A PROSE LINT. It checks a short list of specific self-serve promises against
specific missing controls. A gate that tried to grade legal writing would produce
false reds forever and teach everyone to ignore it; this one asks a single
answerable question — does the thing this sentence promises exist?

Usage: python tools/validate_legal_claim_honesty.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
LEGAL_DIRS = ["terms-of-service", "privacy-policy", "about"]

# phrase -> (what it promises, how to detect the capability actually shipping)
CLAIMS = [
    (re.compile(r"you may (?:export|download) your data at any time", re.I),
     "self-serve data export",
     lambda: _any_source(r"export[-_ ]?my[-_ ]?data|data-export-btn|exportMyData")),
    (re.compile(r"delete your account at any time(?!,? by emailing)", re.I),
     "self-serve account deletion",
     lambda: _any_source(r"deleteAccount|delete-account-btn|account-delete")),
    (re.compile(r"you may .{0,40}delete your account, after which", re.I),
     "self-serve account deletion",
     lambda: _any_source(r"deleteAccount|delete-account-btn|account-delete")),
]


def _any_source(pattern: str) -> bool:
    rx = re.compile(pattern, re.I)
    for f in glob.glob(str(ROOT / "*.html")) + glob.glob(str(ROOT / "*.js")):
        try:
            if rx.search(io.open(f, encoding="utf-8", errors="replace").read()):
                return True
        except OSError:
            continue
    return False


def main() -> int:
    files = []
    for d in LEGAL_DIRS:
        files += glob.glob(str(ROOT / d / "**" / "*.html"), recursive=True)
        files += glob.glob(str(ROOT / d / "**" / "*.md"), recursive=True)
    if not files:
        print("SKIP legal-claim-honesty — no legal surface found on disk")
        return 0

    fails = []
    checked = 0
    for f in sorted(files):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        checked += 1
        for rx, promise, exists in CLAIMS:
            m = rx.search(src)
            if m and not exists():
                fails.append(f"{Path(f).relative_to(ROOT)}: promises {promise} "
                             f"(\"{m.group(0)[:60]}\") — no such control exists in the product")

    print(f"  legal surfaces checked: {checked}")
    if fails:
        print("FAIL legal-claim-honesty:")
        for x in sorted(set(fails)):
            print("    - " + x)
        print("    Either ship the control, or describe the path that DOES exist. The right itself is")
        print("    real — the privacy policy documents it as emailing admin@workhiveph.com with the")
        print("    subject \"Data Rights Request\" — so saying that is both true and no weaker.")
        return 1
    print(f"PASS legal-claim-honesty — {checked} legal surface(s) claim no self-serve capability the "
          f"product does not have.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
