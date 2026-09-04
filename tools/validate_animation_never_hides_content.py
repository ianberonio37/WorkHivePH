#!/usr/bin/env python3
"""An optional API's absence must never hide CONTENT (T119).

★THE DEFECT THIS LOCKS. index.html styled `.reveal { opacity: 0 }` and made those elements visible
only when an IntersectionObserver callback added `.visible`. On an engine without the API the
constructor THREW, the rest of that script block never ran, and all 14 .reveal elements stayed
invisible permanently: the landing page rendered 525 characters of text where every other page
rendered 1146+.

★NOTHING WOULD HAVE REPORTED IT. There was no failed request, no error state, no blank shell - the
page "loaded fine" and simply never faded its content in. The same shape as a skeleton that never
resolves. And the source SAID it was safe: the comment above the observer read "all browsers",
which is an assumption wearing the clothes of a check.

THE RULE: a page that hides content behind an animation must FEATURE-DETECT the API that reveals
it, and the no-support branch must FAIL OPEN - show the content. Losing a fade is cosmetic; losing
the content is the page. A guard that merely skips the observer while leaving `opacity: 0` in place
would satisfy a naive "is it guarded" check and still ship a blank page, so this gate requires BOTH
halves: every construction site guarded, AND a reveal-everything fallback wherever the hidden class
is styled hidden.

TEETH: synthetic negatives - an unguarded construction, and a guard with no fail-open branch.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (page, hidden-class, the class that reveals it)
# community's mechanism is different in kind: no opacity:0, but a VIRTUAL LIST whose .vcard-stub
# placeholders only become posts when an observer expands them. Same failure, same consequence —
# the page loads and the content is not there — so it is held to the same rule. Its stand-in
# observers are what make the guard sufficient there: eight other call sites do renderIO.observe
# as posts arrive, so an early return would have swapped a ReferenceError for a TypeError.
SURFACES = [
    ("index.html", "reveal", "visible"),
    ("community.html", "vcard-stub", "_expandAllStubs"),
]

CTOR = re.compile(r"new\s+IntersectionObserver\s*\(")
GUARD = re.compile(r"typeof\s+IntersectionObserver\s*(===|!==)\s*'function'")


def audit(src: str, hidden_cls: str, shown_cls: str) -> list:
    out = []
    ctors = list(CTOR.finditer(src))
    if not ctors:
        return []          # nothing to guard on this page
    guards = list(GUARD.finditer(src))
    if not guards:
        out.append(f"{len(ctors)} IntersectionObserver construction(s) and NO feature detection - "
                   f"an engine without the API throws and every element this page hides stays hidden")
        return out

    # Every construction must have a guard BEFORE it. Positional rather than syntactic: a guard
    # further down the file cannot protect a constructor that already ran.
    gpos = [g.start() for g in guards]
    for m in ctors:
        if not any(g < m.start() for g in gpos):
            line = src[:m.start()].count("\n") + 1
            out.append(f"IntersectionObserver constructed at line {line} with no feature check "
                       f"before it - this one throws first and takes the rest of the block with it")

    # And the hidden content must have a way to become visible WITHOUT the API.
    styled_hidden = re.search(r"\." + re.escape(hidden_cls) + r"\s*\{[^}]*opacity:\s*0", src)
    if styled_hidden:
        fail_open = re.search(
            r"typeof\s+IntersectionObserver\s*!==\s*'function'[\s\S]{0,400}?" + re.escape(shown_cls)
            + r"|else\s*\{[\s\S]{0,300}?\." + re.escape(hidden_cls)
            + r"[\s\S]{0,200}?add\(\s*['\"]" + re.escape(shown_cls), src)
        if not fail_open:
            out.append(f".{hidden_cls} is styled opacity:0 but nothing adds .{shown_cls} when the "
                       f"API is absent - the guard would skip the observer and leave the content invisible")
    return out


def selftest() -> int:
    src = io.open(ROOT / "index.html", encoding="utf-8", errors="replace").read()
    cases = [
        ("the real index.html is clean", src, 0),
        # Removing the FIRST guard must be caught even though later guards remain: a check that
        # runs after the throw protects nothing, which is why the match is positional.
        ("the first construction losing its guard is caught",
         src.replace("if (typeof IntersectionObserver === 'function') {\n    const observer =",
                     "if (true) {\n    const observer ="), 1),
        ("stripping ALL feature detection is caught",
         GUARD.sub("false", src), 1),
        ("a guard with no fail-open branch is caught",
         src.replace("document.querySelectorAll('.reveal').forEach(el => el.classList.add('visible'));",
                     "/* removed */"), 1),
    ]
    # community must not pass VACUOUSLY: it has no opacity:0 class, so only the guard half applies
    # there, and a gate that never bites on a surface is not covering it.
    csrc = io.open(ROOT / "community.html", encoding="utf-8", errors="replace").read()
    cases.append(("the real community.html is clean", csrc, 0))
    cases.append(("community losing its feature check is caught", GUARD.sub("false", csrc), 1))

    bad = 0
    for name, s, want in cases:
        f = audit(s, "reveal", "visible")
        ok = (len(f) == 0) if want == 0 else (len(f) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {name} (findings={len(f)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    findings = []
    for page, hid, shown in SURFACES:
        p = ROOT / page
        if not p.exists():
            findings.append(f"{page} is gone - re-point this gate")
            continue
        for f in audit(io.open(p, encoding="utf-8", errors="replace").read(), hid, shown):
            findings.append(f"{page}: {f}")
    print("animation-never-hides-content - an optional API's absence must not hide the page")
    print(f"  surfaces checked: {len(SURFACES)}")
    if findings:
        print("\nFAIL - content is hidden behind an API that may not exist:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every observer is feature-detected and the no-support path reveals the content.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
