#!/usr/bin/env python3
"""share-card-completeness — T156: a shared link should look intentional (2026-08-26).

T125 established what this platform's sharing actually looks like: workers paste
links into Viber and Messenger group chats. That makes the Open Graph card the
first thing most people see of a page — often before the page itself.

THE FINDING. 60 of the ~116 public pages shipped NO og:image and no
twitter:card, and they were all the /tools/ calculators — the top of the funnel,
the pages most likely to be shared to a group chat by a worker who just used one.
Every one rendered as a bare grey link while the learn cluster's 53 articles
rendered a proper card. public-feed had an image and a title but no
og:description, so its card showed a headline, a picture, and whatever text the
platform chose to guess.

Fixed by reusing the SAME asset the learn cluster already uses
(brand_assets/og-social.png) rather than inventing a second one: two social
images drift, and one of them ends up stale.

THE ASSERTION: every public page carries og:title, og:description and og:image,
plus a twitter:card so the link expands rather than sitting flat.

★IT CHECKS THE IMAGE FILE EXISTS, not merely that the tag does. A card pointing
at a missing PNG renders exactly like a card with no image at all, and the tag
being present makes it look handled — the worst combination, because nobody
re-checks a field that is filled in.

★APP PAGES ARE OUT OF SCOPE. A signed-in surface behind an auth wall is not
shared to a group chat, and demanding cards there would be ceremony.

Usage: python tools/validate_share_card_completeness.py
"""
import glob
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# the surfaces a person actually shares: the funnel, not the signed-in app
PUBLIC = (["index.html", "public-feed.html"]
          + [str(Path(p).relative_to(ROOT)) for p in glob.glob(str(ROOT / "learn" / "*" / "index.html"))]
          + [str(Path(p).relative_to(ROOT)) for p in glob.glob(str(ROOT / "tools" / "*" / "index.html"))]
          + [str(Path(p).relative_to(ROOT)) for p in glob.glob(str(ROOT / "about" / "index.html"))])

NEEDED = {
    "og:title": r'property=["\']og:title["\']',
    "og:description": r'property=["\']og:description["\']',
    "og:image": r'property=["\']og:image["\']',
    "twitter:card": r'name=["\']twitter:card["\']',
}


def main() -> int:
    pages = [p for p in PUBLIC if (ROOT / p).exists()]
    if not pages:
        print("SKIP share-card-completeness — no public pages found")
        return 0

    missing, bad_image = [], []
    for rel in pages:
        src = io.open(ROOT / rel, encoding="utf-8", errors="replace").read()
        gaps = [k for k, pat in NEEDED.items() if not re.search(pat, src, re.I)]
        if gaps:
            missing.append(f"{rel}: no {', '.join(gaps)}")
        m = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)', src, re.I)
        if m:
            url = m.group(1)
            local = re.sub(r"^https?://[^/]+/", "", url)
            if not (ROOT / local).exists():
                bad_image.append(f"{rel}: og:image points at {local}, which is not on disk")

    print(f"  public pages checked: {len(pages)}")
    fails = missing + bad_image
    if fails:
        print(f"FAIL share-card-completeness — {len(fails)} page(s):")
        for x in fails[:10]:
            print("    - " + x)
        if len(fails) > 10:
            print(f"    ... and {len(fails) - 10} more")
        print("    Workers paste these links into Viber and Messenger, so the card is the first thing")
        print("    most people see of the page. Reuse brand_assets/og-social.png rather than adding a")
        print("    second image - two social images drift and one goes stale.")
        return 1
    print(f"PASS share-card-completeness — all {len(pages)} public pages carry a complete card, and every "
          f"image they promise is on disk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
