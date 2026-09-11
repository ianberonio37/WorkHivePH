#!/usr/bin/env python3
"""check_learn_provenance.py — W3-LN Internal Control, answered from the articles themselves.

A learn article is the platform's front door for a stranger: it makes claims about Philippine plants, rates,
codes and practice, and the reader has no account, no context and no reason to trust it yet. So it owes three
things it can be held to without a browser: **sources** it can be checked against, a **freshness** statement
so a 2024 rate is not read as today's, and a **provenance chip** or dateline that says where the page's own
numbers came from.

★VOCABULARY FIRST, THE WAY W3-CL LEARNED IT. A checker that only knows "Sources:" will accuse an article
that writes "According to the Department of Energy" or cites DOE/IEA/DOLE/PSA inline. The patterns below
were widened against the articles' own words before any count was believed.
"""
from __future__ import annotations

import glob
import re
from pathlib import Path

SOURCES = re.compile(
    r"(\bsources?\b|\breferences?\b|according to|\bcites?\b|\bper the\b|"
    r"\bDOE\b|\bIEA\b|\bDOLE\b|\bPSA\b|\bDTI\b|\bDENR\b|\bDPWH\b|\bERC\b|\bMERALCO\b|\bPSME\b|\bIIEE\b|"
    r"department of energy|department of labou?r|philippine statistics|energy regulatory)", re.I)
FRESH = re.compile(
    r"(updated|last (?:reviewed|checked|updated)|as of|reviewed on|published|"
    r"\b20[12][0-9]\b\s*(?:data|figures|rates|prices)|in\s+(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+20[12][0-9])", re.I)
CHIP = re.compile(r'(wh-source-chip|source-chip|provenance|class="[^"]*dateline)', re.I)


def main() -> int:
    rows = []
    for p in sorted(glob.glob("learn/*/index.html")):
        raw = Path(p).read_text(encoding="utf-8", errors="replace")
        txt = re.sub(r"<[^>]+>", " ", raw)
        slug = p.replace("\\", "/").split("/")[1]
        rows.append((slug, bool(SOURCES.search(txt)), bool(FRESH.search(txt)), bool(CHIP.search(raw))))

    n = len(rows)
    src = sum(1 for _s, a, _b, _c in rows if a)
    fresh = sum(1 for _s, _a, b, _c in rows if b)
    chip = sum(1 for _s, _a, _b, c in rows if c)
    print(f"learn articles: {n}")
    print(f"  names sources or an authority: {src}/{n}")
    print(f"  says how fresh it is:          {fresh}/{n}")
    print(f"  carries a provenance chip:     {chip}/{n}")
    missing = [(s, a, b, c) for s, a, b, c in rows if not (a and b)]
    if missing:
        print(f"\n  articles missing sources or freshness ({len(missing)}):")
        for s, a, b, _c in missing:
            gap = ", ".join(x for x, ok in (("no sources", a), ("no freshness", b)) if not ok)
            print(f"     {s[:56]:58} {gap}")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
