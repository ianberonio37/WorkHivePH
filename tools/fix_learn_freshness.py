#!/usr/bin/env python3
"""fix_learn_freshness.py — show the reader the date the article already tells search engines.

★TWO INSTRUMENTS DISAGREED AND THE BROWSER WAS RIGHT. `check_learn_provenance.py` reads the raw HTML and
reports 54/54 articles "say how fresh they are". The live W3-LN walk, reading what a person can actually see,
found twelve that say nothing. Both were reading correctly: the freshness on those twelve exists ONLY inside
`<script type="application/ld+json">` as `"dateModified"`, which is machine metadata. **A date in JSON-LD is
a promise to a crawler, not to a person** — and for articles carrying engineering guidance, a reader who
cannot tell whether the advice is current has been told nothing at all.

42 of the 54 already print it in the footer:

    © 2026 WorkHive Platform · workhiveph.com · Last updated <time datetime="2026-08-24">24 Aug 2026</time>

so this gives the other twelve the same line, using each article's OWN `dateModified` — the date is lifted
from the page, never invented. Idempotent by marker, and reverting to byte-identical.

  python tools/fix_learn_freshness.py --check
  python tools/fix_learn_freshness.py --apply
  python tools/fix_learn_freshness.py --revert
"""
from __future__ import annotations

import glob
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARK = "wh-freshness"
STRIP = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
# ★A FRESHNESS WORD IS NOT A FRESHNESS LINE. The first version looked for "updated|reviewed|published"
# anywhere in the visible text and skipped an article whose PROSE happened to say "the AI brief is then
# reviewed and published by a supervisor" - a sentence about a workflow, matched as if it were the article's
# own date. The live walk was right and this was wrong. A date a reader can use is the word WITH a date beside
# it, so the pattern now demands one within a short window: a four-digit year or a month name.
FRESH = re.compile(
    r"(updated|last (?:reviewed|checked|updated)|as of|reviewed on|published)"
    r"[^.<]{0,30}?(20[0-9]{2}\b|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", re.I)
MODIFIED = re.compile(r'"dateModified"\s*:\s*"([0-9]{4}-[0-9]{2}-[0-9]{2})"')
FOOTER_P = re.compile(r"(<footer\b[^>]*>.*?<p[^>]*>)(.*?)(</p>)", re.I | re.S)


def visible(raw: str) -> str:
    return re.sub(r"<[^>]+>", " ", STRIP.sub(" ", raw))


def pretty(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
        return f"{d.day} {d.strftime('%b')} {d.year}"
    except ValueError:
        return iso


def fix_one(raw: str):
    if MARK in raw:
        return raw, None
    if FRESH.search(visible(raw)):
        return raw, None                       # the reader can already see a date
    m = MODIFIED.search(raw)
    if not m:
        return raw, None                       # nothing to surface; not this script's to invent
    iso = m.group(1)
    line = (f' · <span data-{MARK}>Last updated <time datetime="{iso}">{pretty(iso)}</time></span>')
    new, n = FOOTER_P.subn(lambda mm: mm.group(1) + mm.group(2).rstrip() + line + mm.group(3), raw, count=1)
    return (new, iso) if n else (raw, None)


def revert_one(raw: str) -> str:
    return re.sub(r'\s*·\s*<span data-' + MARK + r'>.*?</span>', "", raw, flags=re.S)


def main() -> int:
    mode = "--check"
    for a in sys.argv[1:]:
        if a in ("--check", "--apply", "--revert"):
            mode = a

    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))
    changed, already, none = [], 0, 0
    for f in files:
        p = Path(f)
        raw = p.read_text(encoding="utf-8", errors="replace")
        if mode == "--revert":
            if MARK in raw:
                p.write_text(revert_one(raw), encoding="utf-8", newline="")
                changed.append(p.parent.name)
            continue
        if MARK in raw:
            already += 1
            continue
        new, iso = fix_one(raw)
        if iso is None:
            none += 1
            continue
        changed.append(f"{p.parent.name} ({pretty(iso)})")
        if mode == "--apply":
            p.write_text(new, encoding="utf-8", newline="")

    verb = {"--check": "would gain", "--apply": "gained", "--revert": "reverted"}[mode]
    print(f"learn articles: {len(files)}")
    print(f"  {verb} a visible date: {len(changed)}")
    print(f"  already carried the marker: {already}")
    print(f"  the reader could already see a date, or there is none to surface: {none}")
    for c in changed[:8]:
        print(f"     {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
