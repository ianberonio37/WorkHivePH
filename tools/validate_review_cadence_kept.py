#!/usr/bin/env python3
"""review-cadence-kept - T162: a promise to re-check is a promise (2026-08-26).

The competitor-comparison pages are the most perishable content on the platform and
they are written well: every competitor price is DATED ("published entry pricing,
August 2026"), sourced ("vendor published pricing and feature pages, accessed August
2026"), caveated ("SaaS pricing moves, confirm current terms with the vendor"), and
generous to the competition ("the strongest mobile-first product in the category").
Nothing in the comparison itself needed fixing.

★THE RISK IS HIDDEN INSIDE THAT QUALITY. Each of the three pages also says "Pricing
verified against vendor and directory listings on 5 August 2026" and "This comparison
is reviewed quarterly for pricing and feature accuracy." Those are not descriptions -
they are COMMITMENTS with a clock running on them. Left alone they decay into the
worst kind of claim: an explicit, confident promise of currency, printed beside prices
nobody has re-checked in a year. A reader trusts the page MORE because of that
sentence, which is exactly what makes it expensive when it stops being true.

THE ASSERTION: where a page states a verification date AND a review cadence, the date
must still be inside the cadence it promised. Quarterly means 92 days.

MEASURED 2026-08-26: 3 pages, all verified 5 August 2026 - 21 days old, comfortably
inside. This gate is not fixing anything today; it is what makes the promise
self-enforcing, so the page cannot keep asserting a currency nobody maintained. When
it goes red the fix is a real one - re-verify the prices and move the date, or delete
the commitment.

NO GRACE PERIOD, deliberately: the page names the cadence itself, so the cadence is
the bar. The passing output prints the days remaining, so this arrives as a countdown
rather than a surprise.

Usage: python tools/validate_review_cadence_kept.py
"""
import datetime
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

VERIFIED = re.compile(r"verified[^.]{0,80}?on\s+(\d{1,2}\s+[A-Za-z]+\s+20\d\d)", re.I)
CADENCE = re.compile(r"reviewed\s+(quarterly|monthly|annually|yearly|every\s+(\d+)\s+months?)", re.I)
DAYS = {"monthly": 31, "quarterly": 92, "annually": 366, "yearly": 366}


def visible(src: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", src, flags=re.I | re.S)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))


def main() -> int:
    today = datetime.date.today()
    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html"))
                   + glob.glob(str(ROOT / "tools" / "*" / "index.html"))
                   + [str(ROOT / "index.html")])
    files = [f for f in files if Path(f).exists()]

    checked, overdue, soon, unparsed = 0, [], [], []
    for f in files:
        name = Path(f).parent.name if Path(f).name == "index.html" else Path(f).name
        txt = visible(io.open(f, encoding="utf-8", errors="replace").read())
        v, c = VERIFIED.search(txt), CADENCE.search(txt)
        if not (v and c):
            continue
        checked += 1
        word = c.group(1).lower()
        limit = DAYS.get(word) or (int(c.group(2)) * 31 if c.group(2) else 92)
        try:
            when = datetime.datetime.strptime(v.group(1).strip(), "%d %B %Y").date()
        except ValueError:
            unparsed.append(f"{name}: cannot read verification date \"{v.group(1)}\"")
            continue
        age = (today - when).days
        if age > limit:
            overdue.append(f"{name}: verified {v.group(1)} ({age}d ago) but promises review "
                           f"{word} ({limit}d)")
        elif limit - age <= 21:
            soon.append(f"{name}: {limit - age}d left on its {word} promise")

    print(f"  pages promising a review cadence: {checked}")
    for s in soon:
        print(f"    due soon - {s}")
    fails = overdue + unparsed
    if fails:
        print(f"FAIL review-cadence-kept - {len(fails)} page(s) no longer keep the promise they print:")
        for x in fails:
            print("    - " + x)
        print("    These pages print competitor PRICES beside an explicit promise of currency, and a")
        print("    reader trusts them more because of it. Re-verify the figures and move the date, or")
        print("    remove the commitment - but do not keep asserting a freshness nobody maintains.")
        return 1
    if checked == 0:
        print("PASS review-cadence-kept - no page currently promises a review cadence.")
        return 0
    print(f"PASS review-cadence-kept - all {checked} page(s) that promise a review cadence are still "
          f"inside it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
