#!/usr/bin/env python3
"""page_kind.py - ONE source-level answer to "does this served page have a data layer at all?"

★A STATIC DOCUMENT IS THE POSTER'S SIBLING (survey_ufai_rubric.js, 2026-09-11): the rubric excuses E3/G1/I2
on a page that ships NO data client - no utils.js tag, no Supabase client, no inline script that fetches -
because asking a brochure for a status region is asking a poster for a status region. Wave 4 (2026-09-14)
seeded a layer story for EVERY (served page, layer) cell, and two layer gates that had only ever seen root
pages graded the public-root and learn pages as defects: privacy-policy "has no bound on what it loads"
(it loads nothing), an article's illustrative figures "name no period" (they are not measurements of the
reader's plant). A page that loads nothing has nothing to bound, no period to state and no trail to leave.
This is the rubric's own `_noDataClient` test, read from source so every gate says the same thing:

    from page_kind import is_static_doc
    if is_static_doc(page): verdict = "n/a"

MEASURED, NEVER DECLARED: the test is the ABSENCE of a client, which cannot be wrong about a page that
really does stream; status.html (inline fetch of /health) and every DB-backed page keep being graded.

  python tools/page_kind.py --list       # every served .html with its kind
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_INLINE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.I | re.S)
_DATA = re.compile(r"fetch\(|XMLHttpRequest|createClient|supabase|\.rpc\(|/rest/v1/|/functions/v1/", re.I)
_CACHE: dict[str, bool] = {}


def is_static_doc(page: str) -> bool:
    """True when the page ships no data layer: no utils.js script tag, no Supabase client tag, and no inline
    script that fetches. `page` is a repo-relative path (root file, learn/<slug>/index.html, tools/...)."""
    if page in _CACHE:
        return _CACHE[page]
    try:
        src = (ROOT / page).read_text(encoding="utf-8", errors="replace")
    except OSError:
        _CACHE[page] = False
        return False
    has_utils = bool(re.search(r'<script[^>]+src="[^"]*utils\.js', src, re.I))
    has_client = bool(re.search(r'<script[^>]+src="[^"]*(supabase|@supabase)[^"]*"', src, re.I))
    inline_fetch = any(_DATA.search(m.group(1) or "") for m in _INLINE.finditer(src))
    _CACHE[page] = not (has_utils or has_client or inline_fetch)
    return _CACHE[page]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import glob
    pages = sorted(p.replace("\\", "/") for pat in ("*.html", "learn/*/index.html", "learn/index.html", "tools/*/index.html",
                                                    "about/index.html", "feedback/index.html", "privacy-policy/index.html",
                                                    "terms-of-service/index.html")
                   for p in glob.glob(str(ROOT / pat)))
    rel = [str(Path(p).relative_to(ROOT)).replace("\\", "/") for p in pages]
    n = 0
    for p in rel:
        s = is_static_doc(p)
        n += s
        if "--list" in sys.argv:
            print(f"  {'static' if s else 'data  '}  {p}")
    print(f"{n} static document(s) of {len(rel)} served pages")
