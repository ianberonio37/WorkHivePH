#!/usr/bin/env python3
# DEEPWALK-CELL: * D4
"""
validate_clickable_keyboard_a11y.py  --  RESOLVED-invariant lock for mouse-only-clickable keyboard
a11y (dim-8), fixed platform-wide 2026-07-07.

A `<div|span|li onclick=...>` with no role=button / no keyboard path is mouse-only (keyboard +
screen-reader users can't reach or activate it). Instead of freezing the backlog behind a
forward-only ratchet (which would leave the issue PERSISTING forever), it was FIXED for real: a
runtime keyboard-a11y polyfill in utils.js (`whClickableKbdA11y`) upgrades EVERY such element
(static + dynamically-rendered) to focusable + role=button + Enter/Space activation. utils.js loads
on every active page, so the class is RESOLVED, not baselined.

This gate enforces that the fix stays in place (NOT a count ratchet):
  1. utils.js still contains the polyfill.
  2. Every ACTIVE production page that has a mouse-only clickable is covered — it either loads
     utils.js (the polyfill runs) or fixes the element inline (role=button + tabindex + onkeydown).
Retired pages (architecture.html, symbol-gallery.html) + test/backup HTML are out of scope.

Usage:  python tools/validate_clickable_keyboard_a11y.py [--json] [--selftest]
Exit 0 = fix intact + all active pages covered, 1 = polyfill missing or an active page uncovered.
"""
import re, sys, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
UTILS = ROOT / "utils.js"
POLYFILL_MARKER = "whClickableKbdA11y"
# The polyfill must also guarantee a VISIBLE focus ring (WCAG 2.4.7) on the elements it upgrades —
# keyboard-focusable is useless if the user can't SEE where focus is. injectFocusStyle() adds a
# scoped `.wh-kbd-a11y:focus-visible{outline:...}` rule (a page's own focus style still wins).
FOCUS_VISIBLE_MARKER = "wh-kbd-a11y-style"

CLICK_RE = re.compile(r"<(?:div|span|li)\b[^>]*\bonclick=", re.I)
# a clickable that is INLINE-fixed (has tabindex + onkeydown on the same tag) is fine even w/o utils.js
INLINE_OK_RE = re.compile(r"<(?:div|span|li)\b[^>]*\bonclick=[^>]*>", re.I)
UTILS_SRC_RE = re.compile(r"src=[\"'][^\"']*utils\.js", re.I)
SKIP_RE = re.compile(r"(?:-test|test|\.backup\d*)\.html$", re.I)
RETIRED = {"architecture.html", "symbol-gallery.html"}


def has_uncovered_clickable(text):
    """True if the page has a mouse-only clickable that is NOT inline-fixed."""
    for m in INLINE_OK_RE.finditer(text):
        tag = m.group(0)
        inline_fixed = ("tabindex=" in tag and "onkeydown=" in tag) or re.search(r'role=["\'](?:button|tab|menuitem|switch)["\']', tag, re.I)
        if not inline_fixed:
            return True
    return False


def analyze():
    viols = []
    # 1) polyfill present in utils.js
    utils_src = UTILS.read_text(encoding="utf-8", errors="ignore") if UTILS.exists() else ""
    if POLYFILL_MARKER not in utils_src:
        viols.append({"issue": f"utils.js is missing the {POLYFILL_MARKER} keyboard-a11y polyfill (the platform-wide fix is gone)"})
        return viols  # if the polyfill is gone, per-page coverage is moot
    # 1b) polyfill must inject the visible-focus ring too (operable is not enough — must be VISIBLY focused)
    if FOCUS_VISIBLE_MARKER not in utils_src:
        viols.append({"issue": f"utils.js polyfill no longer injects the '{FOCUS_VISIBLE_MARKER}' focus-visible ring (WCAG 2.4.7: keyboard focus must be VISIBLE)"})
    # 2) every active clickable-bearing page loads utils.js (or fixes inline)
    for p in sorted(ROOT.glob("*.html")):
        if SKIP_RE.search(p.name) or p.name in RETIRED:
            continue
        t = p.read_text(encoding="utf-8", errors="ignore")
        if has_uncovered_clickable(t) and not UTILS_SRC_RE.search(t):
            viols.append({"file": p.name, "issue": "has a mouse-only clickable but does not load utils.js (polyfill) nor fix it inline"})
    return viols


def selftest():
    # polyfill-present is assumed; test the per-page coverage logic
    cases = [
        ("uncovered clickable, no utils.js", '<div onclick="x()">y</div>', True),
        ("clickable + utils.js loaded", '<script src="utils.js"></script><div onclick="x()">y</div>', False),
        ("inline-fixed clickable, no utils.js", '<div onclick="x()" tabindex="0" onkeydown="k()">y</div>', False),
        ("no clickable at all", '<div>y</div>', False),
    ]
    ok = True
    for name, html, expect_uncovered in cases:
        got = has_uncovered_clickable(html) and not UTILS_SRC_RE.search(html)
        status = "PASS" if got == expect_uncovered else "FAIL"
        if got != expect_uncovered:
            ok = False
        print(f"  selftest {status}: {name}  (expected uncovered={expect_uncovered}, got={got})")
    return 0 if ok else 1


def main():
    if "--selftest" in sys.argv:
        rc = selftest()
        print("clickable-keyboard-a11y selftest:", "OK" if rc == 0 else "FAILED")
        return rc
    as_json = "--json" in sys.argv
    viols = analyze()
    if as_json:
        print(json.dumps({"violations": viols, "count": len(viols)}, indent=2))
    else:
        print("clickable-keyboard-a11y (runtime polyfill in utils.js makes every mouse-only clickable keyboard-operable — RESOLVED, not ratcheted)")
        if not viols:
            print("  PASS: polyfill present in utils.js + every active clickable-bearing page is covered")
        else:
            print(f"  FAIL: {len(viols)} issue(s):")
            for v in viols:
                print(f"    {v.get('file','utils.js')}: {v['issue']}")
    return 1 if viols else 0


if __name__ == "__main__":
    sys.exit(main())
