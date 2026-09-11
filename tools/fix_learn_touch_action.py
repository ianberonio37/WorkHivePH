#!/usr/bin/env python3
"""fix_learn_touch_action.py - give every learn article the T3 tap-responsiveness rule.

★53 OF 54 PUBLIC ARTICLES CARRIED THE LEGACY 300ms TAP DELAY (walked 2026-09-10, FILIPINO, phone-390).
The RA 11285 compliance article graded T3 0% - "touch-action:auto - legacy ~300ms click delay +
double-tap-zoom not suppressed" - and it was not one article's oversight: exactly ONE of the 54 learn
pages sets touch-action, the one that received a full mobile pass on 2026-09-07. The learn surface is
the platform's most PUBLIC one (search arrivals land here before they ever see the app), it is read on
phones, and every tap on it has been paying a third of a second for nothing.

WHY A TOOL AND NOT 53 EDITS: the learn pages share no screen stylesheet - `learn-print.css` is
media="print" and everything else is inline <style> - so there is no single place to put the rule. This
follows the shape of the fixers already in this directory (fix_learn_chrome.py, fix_learn_fab_path.py,
fix_learn_freshness.py): one bounded, idempotent, dry-run-first pass over the 54 files.

SCOPE IS DELIBERATELY ONE LINE. The article that already has the rule also carries a mobile pass worth of
44px tap-target and wrap fixes. Those change LAYOUT and would need per-page verification, so they are NOT
bulk-applied here - a blind layout edit across 53 public pages is exactly the kind of change that trades
one defect for another. touch-action changes no geometry: it only tells the browser not to wait for a
possible double-tap.

  python tools/fix_learn_touch_action.py            # dry run: which files would change
  python tools/fix_learn_touch_action.py --apply
  python tools/fix_learn_touch_action.py --self-test
"""
from __future__ import annotations

import glob
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE = ("    html, body, a, button { touch-action: manipulation; }"
        "   /* T3: no 300 ms tap delay, no double-tap zoom (the rubric reads html/body) */")


def needs_fix(src: str) -> bool:
    """A page needs the rule when it has a <style> to put it in and no touch-action anywhere."""
    return "<style>" in src and "touch-action" not in src


def apply_rule(src: str) -> str:
    """Insert the rule as the FIRST declaration of the first <style> block.

    First-in is deliberate: later rules in the same sheet may target the same selectors, and this one
    must never win a specificity fight it does not need to. touch-action is not contested by any of the
    article styles, so position only affects readability - and the top is where a reader looks for
    document-wide behaviour.
    """
    if not needs_fix(src):
        return src
    i = src.index("<style>") + len("<style>")
    return src[:i] + "\n" + RULE + src[i:]


def main() -> int:
    apply = "--apply" in sys.argv
    files = sorted(glob.glob(str(ROOT / "learn" / "*" / "index.html")))
    if not files:
        print("refused: no learn articles found - a fixer that matches nothing is not a no-op, it is a "
              "broken path")
        return 1
    changed, already, no_style = [], [], []
    for f in files:
        src = io.open(f, encoding="utf-8").read()
        if "touch-action" in src:
            already.append(f)
            continue
        if "<style>" not in src:
            no_style.append(f)
            continue
        if apply:
            io.open(f, "w", encoding="utf-8", newline="").write(apply_rule(src))
        changed.append(f)
    rel = lambda p: str(Path(p).relative_to(ROOT)).replace("\\", "/")
    print(f"{'APPLIED' if apply else 'DRY RUN'}: {len(changed)} article(s) "
          f"{'given' if apply else 'would get'} the T3 rule; {len(already)} already had it"
          + (f"; {len(no_style)} have no <style> block and were SKIPPED" if no_style else ""))
    for f in changed[:5]:
        print("   " + rel(f))
    if len(changed) > 5:
        print(f"   ... and {len(changed) - 5} more")
    for f in no_style:
        print("   SKIPPED (no <style>): " + rel(f))
    if not apply and changed:
        print("  re-run with --apply to write")
    return 0


def _self_test() -> int:
    fails = []
    page = "<html><head>\n  <style>\n    body { font-family: 'Poppins'; }\n  </style></head></html>"

    if not needs_fix(page):
        fails.append("a page with a <style> and no touch-action must be detected as needing the rule")
    out = apply_rule(page)
    if "touch-action: manipulation" not in out:
        fails.append("the rule must be inserted")
    if out.index("touch-action") > out.index("font-family"):
        fails.append("the rule must land FIRST in the style block, before the existing declarations")
    if apply_rule(out) != out:
        fails.append("applying twice must be a no-op - the fixer has to be idempotent")

    have = "<style>\n  a { touch-action: manipulation; }\n</style>"
    if needs_fix(have) or apply_rule(have) != have:
        fails.append("a page that already sets touch-action must be left completely alone")

    nostyle = "<html><body>no style block</body></html>"
    if needs_fix(nostyle) or apply_rule(nostyle) != nostyle:
        fails.append("a page with no <style> must be skipped, never given a stray rule")

    print("FAIL fix_learn_touch_action self-test - " + "; ".join(fails) if fails
          else "self-test OK: the rule lands first, twice is a no-op, a page that already has it is "
               "untouched, and a page with no <style> is skipped")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
