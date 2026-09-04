#!/usr/bin/env python3
"""failed-read-is-not-empty - a read that FAILED must not render as "there is nothing" (2026-08-27).

The shape: a loader catches, blanks its list (`_x = []`), toasts, and re-renders. The toast fades.
The EMPTY STATE is what stays on screen - so an unread table ends as "No pending listings", "No
seller profiles yet", "be the first to sell". Those are factual CLAIMS about the world, made at the
exact moment the platform could not read it.

★AND THE PLATFORM ALREADY KNEW. marketplace.html carries the diagnosis in its own source, from a
deepwalk: "the toast alone was insufficient - it fades, leaving the GRID showing the first-run 'be
the first to sell' CTA on a full marketplace", and sets `_loadError`. marketplace-seller-profile
carries its own version: "Only a read that ANSWERED may license a conclusion about this seller",
and sets `_reviewsFailed`. Both were fixed. marketplace-admin - the MODERATION queue, where "nothing
to review" is the sentence most likely to make someone stop looking - never got the fix, and was
found by this sweep on 2026-08-27.

That is the second fix-that-did-not-travel in one session (see report-clobber-guard). A lesson
living in one file's source protects that file; a gate is what makes it the platform's.

THE RULE: if a catch blanks a list on a page that owns an empty state, the same catch must record
that the read FAILED - any `<name>Failed|<name>Error|<name>Err = true` - so the renderer can tell an
empty table from an unread one. The flag's NAME is not prescribed; three pages spell it three ways
(_loadError, _reviewsFailed, _readFailed) and all three are correct.

Self-test: `--selftest`.
"""
import glob
import io
import os
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# a catch that blanks a list variable
BLANKING = re.compile(r"catch\s*\([^)]*\)\s*\{(?P<body>[^{}]{0,400}?)\b_?\w+\s*=\s*\[\]", re.S)
# any flag that records the failure, however the page spells it
# The flag may be a bare identifier (_loadError) or a property on a small record
# (_readFailed.listings) - marketplace-admin uses the second, and the first version of this
# regex could not see it, so a page I had just fixed still read as broken.
FLAG = re.compile(r"\b_?\w*(?:Failed|Error|Err)\b(?:\.\w+)?\s*=\s*true", re.I)
HAS_EMPTY = re.compile(r"empty-state|emptyState|empty_state")


def scan_source(src: str, label: str = "source") -> list:
    if not HAS_EMPTY.search(src):
        return []                       # no empty state to be mistaken for
    out = []
    for m in BLANKING.finditer(src):
        # THE CATCH MUST WRAP A READ. Not every `catch { x = [] }` is a load failure: alert-hub
        # parses a legacy double-encoded parts field per row and falls back to [] when it is
        # malformed, which is correct and has nothing to do with empty states. The first version of
        # this gate reported that as a defect. Requiring a query in the preceding context keeps the
        # check aimed at loaders, which is what the rule is about.
        before = src[max(0, m.start() - 700):m.start()]
        if not re.search(r"\.select\s*\(|\.rpc\s*\(|functions\s*\.\s*invoke\s*\(", before):
            continue
        # the flag may be set in the catch body, or on the line that blanked
        window = src[m.start():m.end() + 220]
        if not FLAG.search(window):
            line = src[:m.start()].count("\n") + 1
            out.append(f"{label}:{line} a catch blanks its list without recording that the read "
                       f"FAILED - the empty state will claim there is nothing")
    return out


def selftest() -> int:
    ok = True

    def chk(name, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {'PASS' if good else 'FAIL'}  {name}: got {got}, want {want}")

    # a realistic loader: the fixture must contain the QUERY, because the rule is scoped to
    # catches that wrap a read - without one the check correctly ignores it.
    bad = ("<div class='empty-state'>Nothing here</div>"
           "<script>try { const {data} = await db.from('t').select('*'); _rows = data; } "
           "catch (_e) { _rows = []; showToast('could not load'); } renderRows();</script>")
    chk("blanking with no failure flag fails", len(scan_source(bad)), 1)

    good = bad.replace("_rows = []; showToast", "_rows = []; _loadError = true; showToast")
    chk("recording the failure passes", len(scan_source(good)), 0)

    alt = bad.replace("_rows = []; showToast", "_rows = []; _reviewsFailed = true; showToast")
    chk("a differently-named flag also passes", len(scan_source(alt)), 0)

    no_empty = bad.replace("<div class='empty-state'>Nothing here</div>", "")
    chk("a page with no empty state is out of scope", len(scan_source(no_empty)), 0)

    live = []
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        live += scan_source(io.open(f, encoding="utf-8", errors="replace").read(), os.path.basename(f))
    chk("every live page passes", live, [])
    print(f"\n  SELFTEST: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()

    problems, scanned = [], 0
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        src = io.open(f, encoding="utf-8", errors="replace").read()
        if HAS_EMPTY.search(src):
            scanned += 1
        problems += scan_source(src, os.path.basename(f))

    print("a failed read is not an empty one")
    print(f"  pages owning an empty state: {scanned}")
    print(f"  loaders that blank without recording the failure: {len(problems)}")
    if not problems:
        print("\n  PASS - every loader that blanks its list says the read failed.")
        return 0
    print("\n  FAIL - these will claim 'there is nothing' about a table nobody read:")
    for p in problems:
        print(f"    {p}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
