#!/usr/bin/env python3
"""verdict-needs-a-denominator - T65: one tap is not a judgement about the AI (2026-08-26).

ai-quality's Worker Trust card is where an owner decides whether the AI is worth paying for. It
turned thumbs into a percentage and then into a VERDICT: HEALTHY in green at 70%+, WATCH in amber,
LOW TRUST in red below 50%.

FOUND: no sample floor. With a single rating the card read "100% · HEALTHY" in green, or
"0% · LOW TRUST" in red - a confident judgement about the whole AI layer from one tap. The zero
case was already handled honestly ("NO DATA") and the raw counts were already shown beside the
figure, so the gap was narrow and specific: a PERCENTAGE needs a denominator before it can carry a
verdict, and below about five ratings a single tap moves it twenty points or more.

The number is still shown - hiding it would be its own dishonesty - but it is not dressed as a
verdict until it can support one, and the card says what would make it meaningful. Exercised
against the shipped branch: 1 rating and 4 ratings read TOO FEW RATINGS in grey, 5 ratings and up
resolve to a real tag, and a genuine 2-up/8-down still lands as LOW TRUST in red.

★THE POINT IS NOT TO HIDE BAD NEWS. A real verdict must still land, or the gate would be teaching
the page to say nothing. What it forbids is a verdict the data cannot support, in either direction.

★SAME DISCIPLINE THE RELIABILITY WORKBENCH APPLIES to a Weibull fit with too few failures: say the
sample is too small and what would fix it, rather than fitting a curve to three points.

Usage: python tools/validate_verdict_needs_a_denominator.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "ai-quality.html"


def main() -> int:
    if not PAGE.exists():
        print("SKIP verdict-needs-a-denominator - ai-quality.html not present")
        return 0

    src = PAGE.read_text(encoding="utf-8", errors="replace")
    fails = []

    if "thumbsUp" not in src:
        print("SKIP verdict-needs-a-denominator - the trust card no longer reads thumbs")
        return 0

    if not re.search(r"MIN_RATINGS_FOR_VERDICT\s*=\s*(\d+)", src):
        fails.append("no minimum-ratings floor: a single thumbs tap produces HEALTHY in green or "
                     "LOW TRUST in red, a verdict about the whole AI layer from one rating")
    else:
        n = int(re.search(r"MIN_RATINGS_FOR_VERDICT\s*=\s*(\d+)", src).group(1))
        if n < 3:
            fails.append(f"the floor is {n}, low enough that one tap still swings the verdict")
        if not re.search(r"thumbsTotal\s*<\s*MIN_RATINGS_FOR_VERDICT", src):
            fails.append("the floor is declared but never compared against the rating count")
        if not re.search(r"TOO FEW RATINGS", src):
            fails.append("below the floor the card does not say the sample is too small, so the "
                         "reader cannot tell a withheld verdict from a missing one")

    # the verdict must still be reachable - a card that never judges is its own failure
    if not re.search(r"'LOW TRUST'", src) or not re.search(r"'HEALTHY'", src):
        fails.append("the real verdicts are gone; suppressing bad news is not honesty either")

    # ★AND THE HEADLINE, which this gate did not cover and which is the louder claim (2026-08-28).
    # The floor was declared INSIDE the trust card, so computeVerdict - the page's banner - read
    # thumbsPct < 0.5 straight off one rating. Measured on the live page: 348 AI calls and a single
    # thumbs-down produced "⚠ AI is struggling for your hive" directly above the card's own "0 up /
    # 1 down: too few to judge yet (5+ needed)". Two verdicts about one number, and the guarded one
    # was the quieter. A gate scoped to the card while the banner runs unguarded is the too-narrow
    # -scope failure this codebase keeps producing.
    verdict_fn = re.search(r"function computeVerdict\(s\)\s*\{(.*?)\n    \}", src, re.S)
    if not verdict_fn:
        fails.append("computeVerdict not found - the headline verdict cannot be checked")
    else:
        body = verdict_fn.group(1)
        if not re.search(r"thumbsTotal\s*>=\s*MIN_RATINGS_FOR_VERDICT", body):
            fails.append("the HEADLINE verdict does not gate thumbs on the minimum: one rating can "
                         "still colour the banner the card refuses to colour")
        if not re.search(r"Not enough ratings", body):
            fails.append("below the floor the headline has no honest label, so it falls through to "
                         "a health verdict - trading a false alarm for a false reassurance")

    if fails:
        print(f"FAIL verdict-needs-a-denominator - {len(fails)} problem(s):")
        for x in fails:
            print("    - " + x)
        print("    This card is where an owner decides whether the AI is worth paying for. A percentage")
        print("    needs a denominator before it can carry a colour.")
        return 1

    print("PASS verdict-needs-a-denominator - the trust verdict waits for enough ratings to support it, "
          "says so meanwhile, and still judges once it can.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
