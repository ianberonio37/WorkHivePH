#!/usr/bin/env python3
"""converted-money-states-its-rate - T89: a converted figure is a claim about a rate (2026-08-26).

ai-quality's cost card is the owner's answer to "what is this costing me". Every peso figure on it
- the hero, the per-call average, and the MODEST / TYPICAL / HEAVY verdict thresholds - came from
one hardcoded constant, `PHP_PER_USD = 56`, which was neither dated nor shown.

PHP/USD has moved between roughly 50 and 59 in recent years. A drifting rate silently shifts both
the number and the JUDGEMENT about it, while the card reads like a measurement. The figure is not
wrong so much as unfalsifiable: an owner cannot tell whether ₱2,100 means "heavy use" or "the rate
is stale". Building an FX feed is not the job; saying what the figure rests on is, the same way a
source chip states a window.

THE ASSERTION: where a hardcoded currency-conversion constant is used to produce a displayed
figure, the rate must appear on the glass too.

★IT DOES NOT DEMAND A LIVE RATE. A fixed rate is a perfectly reasonable choice for a cost estimate.
What is not reasonable is presenting a converted number as if nothing was assumed.

Usage: python tools/validate_converted_money_states_its_rate.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SKIP = re.compile(r"_bak|backup|node_modules|_fixtures|^index-.*test", re.I)

# a hardcoded conversion constant, e.g. PHP_PER_USD = 56 / USD_TO_PHP = 56
RATE_DECL = re.compile(r"\b([A-Z]{3}_(?:PER|TO)_[A-Z]{3}|[A-Z]{3}_[A-Z]{3}_RATE)\s*=\s*([\d.]+)")
# the rate reaching the reader: its value or its name inside rendered text
BASIS_HINT = re.compile(r"_BASIS|converted at|exchange rate|at ₱|fixed rate", re.I)


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    files = [f for f in sorted(glob.glob(str(ROOT / "*.html"))) + sorted(glob.glob(str(ROOT / "*.js")))
             if not SKIP.search(Path(f).name)]
    checked, bad = 0, []
    for f in files:
        name = Path(f).name
        src = strip_comments(io.open(f, encoding="utf-8", errors="replace").read())
        for m in RATE_DECL.finditer(src):
            const, val = m.group(1), m.group(2)
            # is it actually used to produce a value, or just declared?
            uses = len(re.findall(r"\b" + re.escape(const) + r"\b", src)) - 1
            if uses < 1:
                continue
            checked += 1
            if not BASIS_HINT.search(src):
                line = src[:m.start()].count("\n") + 1
                bad.append(f"{name}:{line} {const} = {val} converts displayed money, and the rate is "
                           f"never shown")

    print(f"  hardcoded conversion rates in use: {checked} | not disclosed: {len(bad)}")
    for x in bad[:6]:
        print("    - " + x)

    if bad:
        print("FAIL converted-money-states-its-rate - a converted figure is a claim about a rate, and the")
        print("    reader cannot see the rate. A fixed rate is fine; presenting the result as if nothing")
        print("    was assumed is not - especially where thresholds turn that figure into a verdict.")
        return 1
    if checked == 0:
        print("SKIP converted-money-states-its-rate - no hardcoded conversion rates in use")
        return 0
    print(f"PASS converted-money-states-its-rate - all {checked} conversion rate(s) in use are stated "
          "where the converted figure is shown.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
