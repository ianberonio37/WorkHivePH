#!/usr/bin/env python3
"""validate_hive_capture_invariant.py — lock the invariant that makes a load-time hive capture SAFE.

WHY THIS EXISTS. `TB-A345-architecture-quality` sat `owed` on the marketplace test bank with a documented
finding: marketplace.html does `const HIVE_ID = whHiveId()` once at load and stamps it on every hail, which
would file work into the WRONG HIVE if the active hive could change while the page is open — and it cannot,
because reaching the marketplace requires a full page load, so the const is always read fresh. No defect.

That is a real finding, and it is also a claim resting on an invariant nobody was enforcing. "No defect
today, because of how navigation happens to work" is exactly the kind of conclusion that rots silently: add
an in-page hive switcher to the marketplace and every subsequent hail carries a stale tenant id, with no test
going red. The disposition rule on this platform is that a covered-by-nature cell should still get a gate
asserting the contract it rests on ([[feedback_build_structure_to_make_it_liveable]]) — so here it is.

CHECKING THE PREMISE CORRECTED IT, TWICE (both were mine, both in the owed cell's own reasoning):

  1. The cell said "every wh_active_hive_id write lives on hive.html". It does not — `index.html:2953`
     writes it too, during the sign-in hive bootstrap. The CONCLUSION survived (index -> marketplace is a
     full page load) but the stated premise was false, and a gate built on it would have been enforcing
     something untrue.
  2. index.html ALSO reads `whHiveId()` into a `const HIVE_ID` (line ~3802), which looks like the very
     stale-capture shape the finding is about. It is not: that capture is **function-scoped** inside the
     ops-home dashboard renderer, so it is re-read on every invocation, and the write at 2953 is deliberately
     followed by `_initDashboard(...)` to re-render against the new hive. Verified by reading both sites, not
     by trusting the comment.

So the distinction that actually matters is **scope**, not filename: a MODULE-scope capture is read once per
page load, while a FUNCTION-scope capture is re-read per call and cannot go stale. This gate therefore
asserts the two things that are cheap to check and hard to argue with, rather than trying to compute JS scope
with a regex (brace/regex-literal counting over inline script is precisely the brittle-validator trap this
platform has been bitten by — [[feedback_fixed_char_window_validator_is_brittle]],
[[feedback_python_heredoc_eats_js_regex_boundaries]]):

  A. THE WRITER ALLOWLIST. Exactly two shipped pages may write `wh_active_hive_id`. A third one appearing is
     not necessarily a bug, but it is always a decision that needs a human to re-check capture scope on the
     pages that read it — so it goes red with that instruction.
  B. THE CAPTURING PAGES MUST NOT WRITE IT. For each page that takes a load-time capture and stamps it on
     writes, assert zero writers in that same file. That is the live-bug condition: a writer in the same
     document can run after the capture.

Usage:  python tools/validate_hive_capture_invariant.py [--selftest]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

KEY = "wh_active_hive_id"
# A write is a setItem on the key. Reads (`getItem`, `whHiveId()`) are not writes and are not restricted.
WRITE_RE = re.compile(r"""(?:localStorage|sessionStorage)\s*\.\s*setItem\s*\(\s*['"]""" + KEY + r"""['"]""")

# The two pages that own switching the active hive. hive.html is the switcher UI; index.html bootstraps the
# active hive at sign-in. Both are full page loads away from any consumer page.
ALLOWED_WRITERS = {"hive.html", "index.html"}

# Pages that stamp a captured hive id onto WRITES, so a same-document writer would make those writes carry a
# stale tenant. marketplace.html is the one the owed cell analysed; the two sibling marketplace surfaces are
# included because they capture the same way and post to the same tables.
CAPTURE_AND_WRITE_PAGES = ("marketplace.html", "marketplace-seller.html", "marketplace-admin.html")

# Test harnesses may drive the key freely — they are not shipped surfaces.
EXCLUDE_DIRS = ("node_modules", ".git", "tests", "tools", "supabase", "substrate", ".tmp")


def shipped_pages():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.endswith(".html"):
                yield os.path.join(dirpath, fn)


def writers(read=None):
    """-> {basename: [line numbers]} for every shipped page that WRITES the active-hive key."""
    found = {}
    for path in shipped_pages():
        try:
            text = (read or (lambda p: open(p, encoding="utf-8", errors="replace").read()))(path)
        except OSError:
            continue
        hits = [i for i, line in enumerate(text.splitlines(), 1) if WRITE_RE.search(line)]
        if hits:
            found[os.path.basename(path)] = hits
    return found


def check(read=None):
    """-> (failures, notes). A failure is a broken invariant; a note is context worth printing."""
    found = writers(read)
    failures, notes = [], []

    unexpected = {f: ls for f, ls in found.items() if f not in ALLOWED_WRITERS}
    if unexpected:
        for f, ls in sorted(unexpected.items()):
            failures.append(
                f"{f} writes {KEY} (line{'s' if len(ls) > 1 else ''} {', '.join(map(str, ls[:4]))}) and is "
                f"not an allowed writer. Adding a writer is not automatically a bug — but every page that "
                f"takes a LOAD-TIME capture of the hive now has to be re-checked, because a capture made "
                f"before this write goes stale. Either add {f} to ALLOWED_WRITERS with a note on why the "
                f"capturing pages are still safe, or move the write behind a full page load.")

    for page in CAPTURE_AND_WRITE_PAGES:
        if page in found:
            failures.append(
                f"{page} both CAPTURES the hive at load and WRITES {KEY} (line "
                f"{found[page][0]}) in the same document. That is the live stale-tenant bug: the write can "
                f"run after the capture, so every subsequent hail/listing carries the PREVIOUS hive id. Fix "
                f"by reading whHiveId() at WRITE time instead of capturing it once.")

    missing = sorted(ALLOWED_WRITERS - set(found))
    if missing:
        # Not a failure: the allowlist going stale in the harmless direction. Printed so the list is curated
        # rather than accumulating names of pages that stopped writing years ago.
        notes.append(f"allowlisted but no longer writes {KEY}: {', '.join(missing)} — prune ALLOWED_WRITERS.")

    notes.append(f"writers found: {', '.join(f'{f}:{len(ls)}' for f, ls in sorted(found.items())) or 'none'}")
    return failures, notes


def selftest():
    """Teeth: a page that violates the invariant must FAIL. Without this the gate could be asserting nothing.

    The fake writer is injected through the reader function, so no file on disk is touched — the same reason
    the mutation harness injects its mutants inside a transaction rather than writing a migration.
    """
    print("  selftest: an injected writer on a capturing page must FAIL the gate")
    real = lambda p: open(p, encoding="utf-8", errors="replace").read()

    def poisoned(path):
        text = real(path)
        if os.path.basename(path) == "marketplace.html":
            return text + "\n<script>localStorage.setItem('wh_active_hive_id', 'poison');</script>\n"
        return text

    clean_f, _ = check(real)
    dirty_f, _ = check(poisoned)
    ok = not clean_f and len(dirty_f) >= 1 and any("marketplace.html" in f for f in dirty_f)
    if ok:
        print(f"  {GREEN}PASS{RST} — clean tree: 0 failures; with a writer injected into marketplace.html: "
              f"{len(dirty_f)} failure(s), naming that page. The gate discriminates.")
        return 0
    print(f"  {RED}FAIL{RST} — clean={len(clean_f)} dirty={len(dirty_f)}: the gate does not discriminate, so "
          f"a green result from it means nothing.")
    for f in (clean_f + dirty_f)[:4]:
        print(f"    {DIM}{f[:150]}{RST}")
    return 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    print(f"{BOLD}Hive-capture invariant{RST} — a load-time hive capture is only safe while nothing can "
          f"change the hive mid-page")
    failures, notes = check()
    for n in notes:
        print(f"  {DIM}{n}{RST}")
    print(f"  {DIM}exempt by construction: index.html captures whHiveId() INSIDE the ops-home renderer "
          f"(function-scoped, re-read per call) and re-renders via _initDashboard after its write{RST}")
    if failures:
        for f in failures:
            print(f"  {RED}FAIL{RST} {f}")
        return 1
    print(f"  {GREEN}PASS{RST} only {', '.join(sorted(ALLOWED_WRITERS))} write {KEY}, and no page that "
          f"captures the hive at load writes it — so TB-A345's A4 finding is now enforced, not just observed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
