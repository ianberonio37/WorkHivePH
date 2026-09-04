#!/usr/bin/env python3
"""canonical-resolves - T158: a canonical must name a URL that exists (2026-08-26).

A rel=canonical is a claim: "the real version of this page lives HERE." When the URL
it names does not exist, the page is telling every crawler that its authoritative
copy is at nothing.

FOUND AND FIXED 2026-08-26, verified against PRODUCTION, not inferred:
    https://workhiveph.com/workhive/public-feed.html -> 404
    https://workhiveph.com/public-feed.html          -> 200
FIFTEEN pages carried the dead form - a /workhive/ segment left over from an earlier
deploy path, still being shipped long after the site moved to the domain root.

★WHY IT SURVIVED: every existing check asked whether a canonical was PRESENT. All 15
were present, well-formed, absolute, and unique - and pointed at a 404. Presence is
the easy half of a claim; this gate checks the half that costs something.

★THE ONE THAT MATTERED MOST was public-feed, the anonymous shop window and the only
one of the 15 meant to be found by strangers: a shared link to it carried a signal
saying the real page was elsewhere, at a URL that does not resolve.

THE ASSERTION: every canonical on a public page resolves to a file in this repo,
under the site's own URL-to-file mapping (/ -> index.html, /dir/ -> dir/index.html,
/page.html -> page.html). Static and deterministic - the path IS the defect, and a
live HTTP check would make the gate depend on the network to state a fact about a
string.

Usage: python tools/validate_canonical_resolves.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
SITE = "workhiveph.com"
CANON = re.compile(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)', re.I)


def target_for(url: str):
    """Map a site URL to the file that would serve it, or None if off-site."""
    m = re.match(rf"https?://(?:www\.)?{re.escape(SITE)}(/.*)?$", url.strip(), re.I)
    if not m:
        return None
    path = (m.group(1) or "/").split("?")[0].split("#")[0]
    if path.endswith("/"):
        return path.lstrip("/") + "index.html"
    return path.lstrip("/")


def main() -> int:
    files = sorted(set(
        glob.glob(str(ROOT / "*.html"))
        + glob.glob(str(ROOT / "learn" / "*" / "index.html"))
        + glob.glob(str(ROOT / "tools" / "*" / "index.html"))
        + glob.glob(str(ROOT / "about" / "index.html"))
        + glob.glob(str(ROOT / "feedback" / "index.html"))
        + glob.glob(str(ROOT / "privacy-policy" / "index.html"))
        + glob.glob(str(ROOT / "terms-of-service" / "index.html"))
    ))
    if not files:
        print("SKIP canonical-resolves - no pages found")
        return 0

    checked, offsite, broken = 0, 0, []
    for f in files:
        src = io.open(f, encoding="utf-8", errors="replace").read()
        m = CANON.search(src)
        if not m:
            continue
        url = m.group(1)
        tgt = target_for(url)
        if tgt is None:
            offsite += 1
            continue
        checked += 1
        if not (ROOT / tgt).exists():
            broken.append(f"{Path(f).relative_to(ROOT).as_posix()} -> {url} (no {tgt})")

    print(f"  pages with an on-site canonical: {checked}"
          + (f" | off-site: {offsite}" if offsite else ""))
    if broken:
        print(f"FAIL canonical-resolves - {len(broken)} canonical(s) name a URL that does not exist:")
        for b in broken[:12]:
            print("    - " + b)
        if len(broken) > 12:
            print(f"    ... and {len(broken) - 12} more")
        print("    A canonical says 'the real version of this page lives here'. Pointing it at a 404")
        print("    tells every crawler the authoritative copy is at nothing. Verified against prod when")
        print("    this gate was born: /workhive/public-feed.html was 404 while /public-feed.html was 200.")
        return 1
    print(f"PASS canonical-resolves - all {checked} on-site canonicals name a page that exists.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
