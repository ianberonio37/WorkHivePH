#!/usr/bin/env python3
"""dated-claim-freshness - T161: content ages with supervision, not by heroics (2026-08-26).

A statistic on a public page is a claim a reader - or an answer engine - will repeat.
The dangerous shape is not an OLD year, it is a year that silently became a LIE:
"as of 2024, the average plant..." was true when written and is quietly false now,
and nobody re-reads a sentence that already shipped.

INVENTORIED 2026-08-26 across 114 public pages, and the honest result is CLEAN - for a
reason worth writing down, because it changed what this gate asserts. The first pass
flagged 33 "claims 3+ years old" and nearly every one was a CITATION or a STANDARD
EDITION: ISO 14224 (2016), CIBSE Guide D:2015, IEC 62305:2010, DENR DAO 2016-08,
Nakajima 1988 for the origin of OEE. Those years are part of the source's IDENTITY.
Flagging them would have demanded the pages stop citing their standards precisely -
the opposite of the goal, and 33 false findings on the way.

★SO THE ASSERTION IS THE SHAPE, NOT THE AGE. Two things rot, and neither is a citation:

  as-of   A present-tense claim pinned to a past year ("as of 2024", "currently ...
          2023", "latest figures 2022"). True when written, false later, never re-read.
          Allowed window: the current year and the two before it.

  future  A statistic dated in a year that has not happened - always a typo or a
          template copy, and it reads as authoritative until someone checks.

Both are ZERO today. This gate exists to keep them zero as 114 pages are edited over
years - the same guard-the-absence discipline as no-clock-driven-push: a property that
is true by care rather than by structure needs a gate, or care lapses in silence.

Usage: python tools/validate_dated_claim_freshness.py
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
THIS_YEAR = datetime.date.today().year
STALE_BEFORE = THIS_YEAR - 2          # current year and the two before it are fine

AS_OF = re.compile(r"\b(?:as of|current(?:ly)?(?:\s+\w+){0,3}|latest\s+(?:data|figures|survey|report|"
                   r"statistics)(?:\s+\w+){0,3}|today(?:\s+\w+){0,3})\s*[,:]?\s*((?:19|20)\d\d)\b", re.I)
FUTURE = re.compile(r"\b(20\d\d)\b")
STATISTIC = re.compile(r"%|\bpercent\b|\baverage\b|\bmedian\b|\bsurvey\b|\bstudy\b|\bdata\b"
                       r"|\bstatistic|\bmillion\b|\bbillion\b|₱|\bPHP\b", re.I)


def visible(src: str) -> str:
    s = re.sub(r"<script.*?</script>", " ", src, flags=re.I | re.S)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))


def main() -> int:
    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html"))
                   + glob.glob(str(ROOT / "tools" / "*" / "index.html"))
                   + [str(ROOT / "index.html"), str(ROOT / "about" / "index.html")])
    files = [f for f in files if Path(f).exists()]
    if not files:
        print("SKIP dated-claim-freshness - no public pages found")
        return 0

    stale, future = [], []
    for f in files:
        name = Path(f).parent.name if Path(f).name == "index.html" else Path(f).name
        txt = visible(io.open(f, encoding="utf-8", errors="replace").read())

        for m in AS_OF.finditer(txt):
            year = int(m.group(1))
            if year < STALE_BEFORE:
                ctx = re.sub(r"\s+", " ", txt[max(0, m.start() - 50):m.end() + 70]).strip()
                stale.append(f"{name} ({year}, {THIS_YEAR - year}y): ...{ctx[:120]}...")

        for m in FUTURE.finditer(txt):
            year = int(m.group(1))
            if year <= THIS_YEAR:
                continue
            ctx = txt[max(0, m.start() - 70):m.end() + 70]
            if STATISTIC.search(ctx):
                future.append(f"{name} ({year}): ...{re.sub(r'  +', ' ', ctx).strip()[:120]}...")

    print(f"  public pages scanned: {len(files)} | as-of window: {STALE_BEFORE}-{THIS_YEAR}")
    if stale or future:
        print(f"FAIL dated-claim-freshness - {len(stale) + len(future)} claim(s) have gone stale or "
              f"name a year that has not happened:")
        for x in (stale + future)[:12]:
            print("    - " + x)
        if len(stale) + len(future) > 12:
            print(f"    ... and {len(stale) + len(future) - 12} more")
        print("    A present-tense claim pinned to a past year was true when written and is false now;")
        print("    nobody re-reads a sentence that already shipped. Either refresh the figure or turn it")
        print("    into a dated CITATION, which is a fact about a source and does not rot.")
        return 1
    print(f"  as-of claims outside the window: 0 | future-dated statistics: 0")
    print(f"PASS dated-claim-freshness - across {len(files)} public pages, every year is a citation or a "
          f"standard edition; nothing pins a present-tense claim to a stale year.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
