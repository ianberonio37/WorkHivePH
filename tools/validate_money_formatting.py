#!/usr/bin/env python3
"""money-formatting — T133: absent is not zero, especially in pesos (2026-08-26).

whFmtPeso exists for one reason, recorded in its own header: `Number(null)` is 0
and finite, so a null amount slips through as a confident "₱0.00". A filed top-up
of PHP300 once rendered as PHP0.00 and a ledger line of unknown value rendered as
"+₱0" — a sentence saying the entry moved nothing. The helper prints a GAP for
absent and still prints ₱0 for a real zero, because a person can act on "we do
not know" and cannot act on a wrong number.

THE FINDING. founder-console — the owner's own cockpit — had ZERO adoption and
two hand-rolled formatters, one of them literally `Number(n || 0)`, which IS the
bug. The same file already carried a note about what that costs: a money number
frozen at ₱0 "does not read as by design, it reads as a feed that died". Its
GCash top-up row used `Number(r.amount)` with no null guard at all, so an absent
amount printed ₱NaN on the screen where money enters the business. Both now route
through the helper.

THE ASSERTION: on the money surfaces, a peso sign may not be concatenated to a
raw number. Each exception is allowlisted BY FILE with its reason, so a
deliberate local formatter stays legal and an accidental one does not.

★SCOPED TO MONEY SURFACES. A gate policing every ₱ on the platform would catch
option labels ("₱ off") and prose, and be switched off. These are the pages where
a wrong figure costs somebody money.

Usage: python tools/validate_money_formatting.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

MONEY_PAGES = [
    "founder-console.html", "platform-actions.html", "marketplace.html",
    "marketplace-seller.html", "marketplace-admin.html",
]

# a peso sign glued to a number, with no helper in sight
HAND_ROLLED = re.compile(r"'₱'\s*\+\s*(?:Number|parseFloat|parseInt|String)?\s*\(?\s*[\w.]+|₱\$\{")

# deliberate local formatters, each with the reason it is allowed to stay
ALLOWED = {
    "platform-actions.html": (
        "the moderation row's 'Negotiable (listed at ₱0)' branch — a MEASURED decision from "
        "2026-08-05: a bare ₱0 read to a moderator like a mistake worth rejecting, so the zero "
        "case says what it means instead of being formatted away"),
}


def main() -> int:
    fails, notes = [], []
    for page in MONEY_PAGES:
        f = ROOT / page
        if not f.exists():
            notes.append(f"{page}: not on disk")
            continue
        lines = io.open(f, encoding="utf-8", errors="replace").read().splitlines()
        hand = []
        for i, line in enumerate(lines):
            if line.lstrip().startswith(("//", "*", "<!--")):
                continue
            if not HAND_ROLLED.search(line):
                continue
            # ★A TERNARY SPANS LINES, AND THE FIRST VERSION OF THIS GATE DID NOT. It flagged the
            # GUARDED FALLBACK half of `whFmtPeso(n) : '₱' + Number(n || 0)...` as a hand-rolled
            # formatter, because the helper sat on the line above. Acting on that would have meant
            # "fixing" code that was already correct - and the fallback exists precisely so the page
            # still renders if utils.js has not loaded. Look at a small window, not one line.
            window = " | ".join(lines[max(0, i - 2): i + 2])
            if "whFmtPeso" in window:
                continue
            # an explicit absent-branch is the behaviour the helper provides, hand-written
            if re.search(r"==\s*null\s*\?|===\s*null\s*\?|!=\s*null\s*\?", window):
                continue
            hand.append((i + 1, line.strip()[:70]))
        uses = sum(1 for l in lines if "whFmtPeso" in l)
        status = f"whFmtPeso x{uses}, hand-rolled {len(hand)}"
        print(f"  {page:<26} {status}")
        if hand and page not in ALLOWED:
            for ln, txt in hand[:3]:
                fails.append(f"{page}:{ln} builds a peso amount by hand — {txt}")
        elif hand:
            notes.append(f"{page}: {len(hand)} allowed — {ALLOWED[page]}")

    for n in notes:
        print(f"    note: {n}")
    if fails:
        print("FAIL money-formatting:")
        for x in fails:
            print("    - " + x)
        print("    Use whFmtPeso: it prints a GAP for an absent value and ₱0 for a real zero, which is")
        print("    the distinction between 'nothing happened' and 'we do not know'. Number(n || 0)")
        print("    collapses both into a confident wrong number.")
        return 1
    print(f"PASS money-formatting — {len(MONEY_PAGES)} money surface(s) render amounts through the helper "
          f"that tells absent from zero.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
