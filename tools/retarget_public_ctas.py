#!/usr/bin/env python3
"""retarget_public_ctas.py — T1.0: point every public-surface CTA at the REAL front door.

WHY THIS EXISTS (Trajectory T1, 2026-08-24). The public template families sold two different
lies to the platform's entire top-of-funnel:

  * learn/*/index.html (55 guides): nav + callouts + footer all said "Join the Hive" and linked
    /#join — the landing page's EMAIL WAITLIST — while zero of them offered a Sign In link.
    A reader who wanted the product was routed to a mailing-list form and told a hive-join
    link would arrive "once your facility is provisioned" (false: signup is instant).
  * tools/*/index.html (60 calculators): the full-suite CTA read "free, no sign-up needed for
    the calculators" and linked /engineering-design.html — a page whose init() REQUIRES
    identity (engineering-design.js gate). Doubly false at the moment of the click.

The fix is one policy, applied uniformly:
  * every /#join href becomes /?signup=1 (the index resolver opens the real signup modal);
  * the nav "Join the Hive" item becomes a Sign In + Sign Up Free pair (every sign-in surface
    offers sign-up and vice versa — Ian verbatim);
  * the tools-page claim tells the truth: the EMBEDDED calculator is free on the page with no
    sign-up; the full suite is free WITH an account (~30 seconds — true since instant signup);
  * edited pages get their dateModified + footer "Last updated" stamp bumped (the 92-stamp
    CI lesson: platform_catalog.json must be regenerated after this script runs —
    `python tools/platform_catalog.py` — or the Persona Corpus Freshness gate goes red).

Idempotent: run twice, the second run reports 0 changes. --check reports without writing.
"""
import argparse
import datetime
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.date.today().isoformat()

# The exact nav item the templates share (35 learn + 60 tools pages carry it verbatim).
NAV_JOIN = '<a href="/#join" class="nav-link">Join the Hive</a>'
NAV_AUTH = ('<a href="/?signin=1" class="nav-link">Sign In</a>\n'
            '      <a href="/?signup=1" class="nav-link">Sign Up Free</a>')

# Variant learn template (18 pages): a compact "Join" pill instead of the nav trio, and no
# Sign In anywhere. After the /#join retarget the pill reads Join -> /?signup=1 (truthful);
# this rule adds the missing Sign In beside it so the pair policy holds on every template.
VARIANT_JOIN = ('<a href="/?signup=1" class="bg-orange-wh text-navy-wh px-4 py-1.5 rounded-lg '
                'font-semibold text-xs hover:bg-orange-light transition-colors">Join</a>')
VARIANT_AUTH = ('<a href="/?signin=1" class="nav-link" style="font-size:0.75rem;">Sign In</a>\n      '
                + VARIANT_JOIN)

# tools/ claim rewrites — the FAQ sentence appears TWICE per page (JSON-LD + visible <details>)
# and both must change identically (machine-readable truth = human-readable truth).
FAQ_LIE = "free to use, no sign-up needed for the tools."
FAQ_TRUTH = ("free to use right on this page, no sign-up needed for the embedded calculator. "
             "The full WorkHive calculator suite is also free with an account: sign-up takes "
             "about 30 seconds.")
CTA_LIE = ": free, no sign-up needed for the calculators."
CTA_TRUTH = ": free with a WorkHive account. Sign-up takes about 30 seconds."


def bump_stamps(text: str) -> str:
    """Move EVERY modified-date surface together — the calc-claim gate's date_agreement check
    (2026-08-24) proved a partial bump is worse than none: the first version matched only the
    tools-style ISO footer, so 29 learn pages got a fresh JSON-LD dateModified beside a stale
    visible byline. Never touches Published/datePublished."""
    human = datetime.date.today().strftime("%d %b %Y").lstrip("0")
    text = re.sub(r'"dateModified":\s*"\d{4}-\d{2}-\d{2}"',
                  f'"dateModified": "{TODAY}"', text)
    # tools-style ISO footer AND learn-style human byline/footer, one rule ("Updated <time"
    # is a substring of "Last updated <time", so both label forms are covered):
    text = re.sub(r'([Uu]pdated <time datetime=")\d{4}-\d{2}-\d{2}(">)[^<]+(</time>)',
                  lambda m: m.group(1) + TODAY + m.group(2)
                  + (TODAY if re.fullmatch(r"[\d-]+", m.group(0).split(">")[-2].split("<")[0]) else human)
                  + m.group(3), text)
    text = re.sub(r'(property="article:modified_time" content=")\d{4}-\d{2}-\d{2}',
                  r'\g<1>' + TODAY, text)
    return text


def rewrite(path: Path, is_tools: bool):
    # newline="" preserves each file's existing line endings verbatim — a retarget must not
    # also be a silent CRLF/LF flip (that noise is how real diffs get buried).
    with path.open(encoding="utf-8", newline="") as f:
        text = f.read()
    orig = text
    changes = []

    if NAV_JOIN in text:
        text = text.replace(NAV_JOIN, NAV_AUTH)
        changes.append("nav: Join-the-Hive -> Sign In + Sign Up Free")

    n = text.count('href="/#join"')
    if n:
        text = text.replace('href="/#join"', 'href="/?signup=1"')
        changes.append(f"{n} /#join href(s) -> /?signup=1")

    if "signin=1" not in text and VARIANT_JOIN in text:
        text = text.replace(VARIANT_JOIN, VARIANT_AUTH, 1)
        changes.append("variant nav: Sign In added beside the Join pill")

    if is_tools:
        n = text.count(FAQ_LIE)
        if n:
            text = text.replace(FAQ_LIE, FAQ_TRUTH)
            changes.append(f"{n} FAQ claim(s) trued (JSON-LD + visible)")
        n = text.count(CTA_LIE)
        if n:
            text = text.replace(CTA_LIE, CTA_TRUTH)
            changes.append(f"{n} suite-CTA claim(s) trued")

    if text != orig:
        text = bump_stamps(text)
        return changes, text
    return changes, None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report only, write nothing")
    args = ap.parse_args()

    # The learn HUB lives at learn/index.html — outside the */index.html glob; the first run
    # missed it (a roster is a silent claim about scope — enumerate the hub explicitly).
    pages = [ROOT / "learn" / "index.html"] + \
            sorted((ROOT / "learn").glob("*/index.html")) + \
            sorted(p for p in (ROOT / "tools").glob("*/index.html"))
    edited = 0
    for page in pages:
        is_tools = page.parent.parent.name == "tools"
        changes, new_text = rewrite(page, is_tools)
        if new_text is not None:
            edited += 1
            if not args.check:
                # Atomic write: never open('w') the original before the content is ready.
                tmp = page.with_suffix(".html.tmp")
                tmp.write_text(new_text, encoding="utf-8", newline="")
                tmp.replace(page)
            rel = page.relative_to(ROOT)
            print(f"{'WOULD EDIT' if args.check else 'EDITED'} {rel}: " + "; ".join(changes))
    print(f"\n{edited} page(s) {'need editing' if args.check else 'edited'} "
          f"of {len(pages)} scanned.")
    if edited and not args.check:
        print("REMINDER: run `python tools/platform_catalog.py` now — the freshness CI gate "
              "compares the committed catalog against a regeneration.")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    raise SystemExit(main())
