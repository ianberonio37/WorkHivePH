#!/usr/bin/env python3
"""funnel-cls — T160: the SEO funnel must not jump while you read it (2026-08-26).

CLS is where a page loses a searcher without erroring: text settles, the reader's
eye is already moving, and the line they were on is somewhere else. On the funnel
it costs twice, because Core Web Vitals feed ranking — the pages most dependent
on search were the ones shifting.

MEASURED, THEN ISOLATED, THEN FIXED. The learn template shifted 0.384 CLS at 390
— nearly 4x the 0.1 "good" bar. The recorded suspicion was an element injected at
~1s, and it was wrong: a MutationObserver armed alongside the shift observer
recorded NO insertion of any size. What the timeline showed instead was a 0.182
shift at 903ms and document.fonts.ready at 907ms. Blocking the font stylesheet
took CLS to 0.000; blocking the Tailwind CDN only took it to 0.156. The font swap
was the whole cause.

THE FIX was one parameter: display=swap -> display=optional across 113 public
pages. `optional` gives the font ~100ms and then never swaps, so the page cannot
jump; measured on a real load it still renders Poppins. The only reader who now
sees the fallback is on a genuinely slow first load — exactly the reader who
previously got the jump instead.

THE ASSERTION: no public page loads a webfont with display=swap. Static, because
the parameter is the cause and a live CLS run is slow and flaky by nature — this
gate catches the regression at its source rather than re-measuring the symptom.

★WHY NOT ASSERT A CLS NUMBER: a lab CLS reading on loopback is optimistic and
noisy, and a gate that fails intermittently gets ignored. The parameter is
deterministic and it IS the defect.

Usage: python tools/validate_funnel_cls.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SWAP = re.compile(r"display=swap", re.I)
FONT_LINK = re.compile(r"fonts\.googleapis\.com/css", re.I)


def main() -> int:
    pages = (glob.glob(str(ROOT / "learn" / "*" / "index.html"))
             + glob.glob(str(ROOT / "tools" / "*" / "index.html"))
             + [str(ROOT / "index.html"), str(ROOT / "public-feed.html"),
                str(ROOT / "about" / "index.html")])
    pages = [p for p in pages if Path(p).exists()]
    if not pages:
        print("SKIP funnel-cls — no public pages found")
        return 0

    swapping, withfont = [], 0
    for p in pages:
        src = io.open(p, encoding="utf-8", errors="replace").read()
        if not FONT_LINK.search(src):
            continue
        withfont += 1
        if SWAP.search(src):
            rel = Path(p).parent.name if Path(p).name == "index.html" else Path(p).name
            swapping.append(rel)

    print(f"  public pages loading a webfont: {withfont} | using display=swap: {len(swapping)}")
    if swapping:
        print(f"FAIL funnel-cls — {len(swapping)} page(s) load a webfont with display=swap:")
        print(f"    {', '.join(swapping[:10])}")
        print("    Measured on this template, swap IS the layout shift: 0.384 CLS at 390, and blocking")
        print("    the font stylesheet took it to 0.000. Use display=optional - it still renders the")
        print("    brand font, and the only reader who sees the fallback is on a slow first load, which")
        print("    is precisely the reader who otherwise gets the jump.")
        return 1
    print(f"PASS funnel-cls — all {withfont} webfont-loading public pages use a non-shifting display "
          f"strategy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
