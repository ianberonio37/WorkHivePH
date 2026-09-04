#!/usr/bin/env python3
"""wrap_public_tables.py — T2: public-page tables scroll in their OWN container.

MEASURED 2026-08-24 (T2 reading-experience probe, 390w): bare <table> elements inside
div.prose-wh force the WHOLE page to pan — 171px of horizontal scroll on the digital-logbook
guide, 134px on the CMMS comparison (WCAG 1.4.10 reflow, on the exact pages the funnel lands
search traffic on). The app pages solved this long ago; the learn/tools templates never got
the container.

Fix shape: wrap each bare <table> in
    <div data-table-scroll style="overflow-x:auto;-webkit-overflow-scrolling:touch;"
         role="region" aria-label="Scrollable table" tabindex="0">
— inline style (no CSS dependency on 115 template instances), role+tabindex so keyboard and
AT users can reach and pan the region (a scrollable area with no tab stop is unreachable
without a mouse). display stays table: semantics intact.

Idempotent: tables already inside a data-table-scroll wrapper are skipped. Edited pages get
their dateModified + "Last updated" stamps bumped (reuses retarget_public_ctas.bump_stamps);
regenerate platform_catalog.json after running (the freshness CI gate).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from retarget_public_ctas import bump_stamps  # noqa: E402

WRAP_OPEN = ('<div data-table-scroll style="overflow-x:auto;-webkit-overflow-scrolling:touch;" '
             'role="region" aria-label="Scrollable table" tabindex="0">')

TABLE_RE = re.compile(r"<table\b.*?</table>", re.S | re.I)


def wrap(text: str) -> tuple[str, int]:
    n = 0
    out = []
    last = 0
    for m in TABLE_RE.finditer(text):
        pre = text[max(0, m.start() - 220):m.start()]
        out.append(text[last:m.start()])
        if "data-table-scroll" in pre:
            out.append(m.group(0))          # already wrapped
        else:
            out.append(WRAP_OPEN + m.group(0) + "</div>")
            n += 1
        last = m.end()
    out.append(text[last:])
    return "".join(out), n


def main() -> int:
    check = "--check" in sys.argv
    pages = ([ROOT / "learn" / "index.html"]
             + sorted((ROOT / "learn").glob("*/index.html"))
             + sorted((ROOT / "tools").glob("*/index.html")))
    edited = total = 0
    for page in pages:
        with page.open(encoding="utf-8", newline="") as f:
            text = f.read()
        new, n = wrap(text)
        if n:
            edited += 1
            total += n
            if not check:
                new = bump_stamps(new)
                tmp = page.with_suffix(".html.tmp")
                tmp.write_text(new, encoding="utf-8", newline="")
                tmp.replace(page)
            print(f"{'WOULD WRAP' if check else 'WRAPPED'} {page.relative_to(ROOT)}: {n} table(s)")
    print(f"\n{edited} page(s), {total} table(s) {'need wrapping' if check else 'wrapped'} "
          f"of {len(pages)} scanned.")
    if edited and not check:
        print("REMINDER: python tools/platform_catalog.py (freshness CI compares committed vs regenerated)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
