#!/usr/bin/env python3
"""Gate `retired-page-inert` - a retired page's overlay must cover the TAB KEY, not only the eyes.

Found 2026-10-06 walking LXP209 (founder-console) at a true 1280. Four pages are retired behind
`#wh-retired-overlay` (position:fixed, inset:0, z-index:100000, opaque) and their boot guards correctly
skip the retired page's WORK - measured on founder-console, only 4 network requests, so it does not even
fetch. But the old page was still in the document and still in the TAB ORDER:

  * founder-console: 32 tabbable controls, 2 of them in the overlay - so 30 belonged to the retired
    console, and elementFromPoint confirmed the opaque overlay was the top-most element at each of their
    centres. A keyboard user tabbed through thirty invisible controls on a page that says it has moved,
    and a screen reader read the whole retired console out underneath the notice.
  * marketplace-admin: 65 tabbable controls outside the overlay.

★THE LATE-INJECTED CHROME IS THE PART THAT HID. A single DOMContentLoaded pass still left four controls
focusable on marketplace-admin - the skip link, #wh-hub's Hive Board FAB, and wayfinding's Back and Home -
because they mount into the body afterwards. They are inerted rather than kept as escape hatches for a
measured reason: their z-indexes are 9000-10001 against the overlay's 100000 and the overlay is top-most
at each of their centres, so a sighted reader sees two links in the notice while a keyboard reader would
find six. The overlay's own links are the exits that ARE visible, and they stay focusable.

The fix lives in utils.js (whInertBehindRetiredOverlay) rather than in the four pages, because the overlay
being pasted four times is what let this go unnoticed. This gate therefore checks two things: that the
shared block still does what it claims, and that EVERY page carrying the overlay actually loads utils.js -
a retired page that does not would be silently unprotected.

Static, so it runs in --fast with no browser.
"""
import glob
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bug_repro_inventory import _strip_comments_js  # noqa: E402  (blanks comments)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTILS = os.path.join(ROOT, "utils.js")
OVERLAY_ID = "wh-retired-overlay"


def _fn_body_js(src, name):
    """The source of one top-level `function name(...) {...}` in a JS file, by brace matching."""
    m = re.search(r"^(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", src, re.M)
    if not m:
        return None
    i = src.index("{", m.end() - 1)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return src[i:j + 1]
        j += 1
    return None


def main():
    failures = []

    if not os.path.exists(UTILS):
        print("FAIL retired-page-inert - utils.js not found")
        return 1
    usrc = io.open(UTILS, encoding="utf-8").read()

    # --- the shared block still exists and still does the three things it has to ---------------
    m = re.search(r"\(function whInertBehindRetiredOverlay\(\)[\s\S]{0,4000}?\n\}\)\(\);", usrc)
    # ★COMMENTS BLANKED ONCE, FOR EVERY CHECK BELOW - not per-check, which is how two of these
    # went green on their own teeth test. Disabling aria-hidden and the observer in CODE still passed,
    # because both words survive in the prose that explains why they are there. Third time in this
    # session a gate of mine read its own explanation as evidence; the stripper is shared, so there is
    # no excuse for grepping raw source.
    block = _strip_comments_js(m.group(0)) if m else ""
    if not block:
        failures.append(
            "whInertBehindRetiredOverlay is gone from utils.js. Without it every control on a retired "
            "page is focusable again behind an opaque overlay - measured at 30 on founder-console and "
            "65 on marketplace-admin.")
    else:
        if not re.search(r"setAttribute\(\s*['\"]inert['\"]", block):
            failures.append("the shared block no longer sets `inert`, which is what removes the retired "
                            "page from the tab order.")
        if "aria-hidden" not in block:
            failures.append(
                "the shared block no longer sets aria-hidden. inert alone removes the subtree for "
                "assistive tech in modern engines, but this platform has already measured a role query "
                "counting inert controls (see _signinInertPage in index.html) - aria-hidden is the belt "
                "to that brace.")
        # The CONSTRUCTION, not the token: `typeof MutationObserver === 'function'` guards the same
        # block, so a bare token test stayed green when the teeth test replaced the observer with null.
        if not re.search(r"new\s+MutationObserver\s*\(", block) or ".observe(" not in block:
            failures.append(
                "the bounded MutationObserver is gone. A single DOMContentLoaded pass left FOUR controls "
                "focusable on marketplace-admin (the skip link, the hub FAB, wayfinding's Back and Home) "
                "because shared chrome mounts into the body afterwards.")
        if not re.search(r"sib\s*===\s*ov|=== ov\b", block):
            failures.append(
                "the shared block no longer excludes the overlay itself, so it would inert the notice's "
                "own exit links - the only controls a reader can actually see on a retired page.")

    # --- a retired page reports no data failures -----------------------------------------------
    # The last escaper found on founder-console was not the retired console at all: at ~45s a shared
    # CONNECTION NOTICE mounted, carried by the page-view log's own failed request, after the inerting
    # observer's bounded window had closed - two focusable controls ("Reload" and the dismiss) inside a
    # notice that is behind the opaque overlay and self-expires at ~75s. Extending the observer forever
    # would have hidden the symptom; the true statement is upstream: this page shows the reader no data,
    # so "part of this page could not be loaded" is not true of anything they are looking at.
    notice = _fn_body_js(usrc, "_whShowNotice")
    if not notice:
        failures.append("_whShowNotice not found in utils.js - the notice-suppression check cannot run.")
    else:
        ncode = _strip_comments_js(notice)
        if not re.search(r"getElementById\(\s*['\"]wh-retired-overlay['\"]\s*\)", ncode):
            failures.append(
                "_whShowNotice no longer suppresses itself on a retired page. A retired page makes no data "
                "claims, so a data-failure notice there is both untrue of what the reader sees and an "
                "invisible focus trap behind the overlay (measured as 2 escapers at t=46s on "
                "founder-console). It must return early when #wh-retired-overlay is present.")

    # --- every page that carries the overlay loads the shared fix ------------------------------
    carriers, unprotected = [], []
    for path in sorted(glob.glob(os.path.join(ROOT, "*.html"))):
        rel = os.path.basename(path)
        src = io.open(path, encoding="utf-8").read()
        if not re.search(r'<div[^>]*id="' + re.escape(OVERLAY_ID) + r'"', src):
            continue
        carriers.append(rel)
        if not re.search(r'<script[^>]+src="utils\.js"', src):
            unprotected.append(rel)

    if not carriers:
        print("PASS retired-page-inert - no page is currently retired behind #%s, so there is nothing to "
              "inert. The shared block stays in utils.js for the next one." % OVERLAY_ID)
        return 0

    for rel in unprotected:
        failures.append(
            "%s carries the retired overlay but does not load utils.js, so the shared inerting never "
            "runs there and its whole retired page stays Tab-reachable behind the notice." % rel)

    if failures:
        print("FAIL retired-page-inert - %d problem(s):" % len(failures))
        for f in failures:
            print("  - %s" % f)
        return 1

    print("PASS retired-page-inert - the shared whInertBehindRetiredOverlay sets inert + aria-hidden, "
          "spares the overlay's own exit links, and re-applies through a bounded observer for chrome that "
          "mounts late; all %d retired page(s) load it (%s)."
          % (len(carriers), ", ".join(carriers)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
