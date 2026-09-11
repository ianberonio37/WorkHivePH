#!/usr/bin/env python3
"""validate_wh_help_parity.py - the .wh-help rule exists TWICE and the two copies must agree.

★A RULE HELD ONLY BY A COMMENT IS NOT HELD (2026-09-10). `.wh-help` - the "How this page works"
disclosure carried by ~30 pages - is declared in components.css AND injected by utils.js for pages that
do not link the stylesheet. utils.js already carries the standing note: "identical to components.css
(2026-09-07): a second, different rule after first paint was a layout shift". That was a MEASURED bug -
voice-journal's summary read 24px then 55px at 118ms - and the only thing preventing its return was a
comment asking the next editor to remember.

It was tested immediately. Fixing an off-scale 14px bottom margin (R1: the declared spacing scale is
4/8/12/16/24/32) meant editing 16px into BOTH files; changing one alone would have re-armed the exact
shift the note warns about, silently, on every page carrying the block. A human remembered this time.
This gate is so the next one does not have to: it compares the two declarations property by property
and fails on any disagreement, so the pair cannot drift back apart.

Scope note: it compares only the selectors present in BOTH sources. utils.js deliberately ships a
subset (it stands down entirely when components.css is linked), so a rule that lives in only one file
is not a failure - a rule that lives in both with DIFFERENT values is.

  python tools/validate_wh_help_parity.py            # report
  python tools/validate_wh_help_parity.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "components.css"
JS = ROOT / "utils.js"


def norm_value(v: str) -> str:
    """Normalise a declaration value so only REAL differences survive.

    ★A GATE THAT REDS ON FORMATTING IS A FALSE RED (2026-09-10, caught by its own first live run).
    The first version failed on three pairs that are the same value written differently:
    `rgba(255, 255, 255, 0.02)` vs `rgba(255,255,255,0.02)`, and `var(--wh-radius, 12px)` vs `12px`.
    Neither can shift a layout or change a pixel, and a gate that cries about them would be ignored
    within a week - or worse, "fixed" by making one file's formatting match the other's, which teaches
    the wrong rule. Two normalisations, both value-preserving: whitespace after commas inside a function
    is dropped, and `var(--name, fallback)` is reduced to its fallback (which is exactly what the
    utils.js copy is - the value used when the stylesheet defining the custom property is absent).
    """
    v = re.sub(r"\s+", " ", v).strip().lower()
    v = re.sub(r",\s+", ",", v)                       # rgba(255, 255, 255, .02) == rgba(255,255,255,.02)
    prev = None
    while prev != v:                                   # nested var() fallbacks
        prev = v
        v = re.sub(r"var\(\s*--[\w-]+\s*,\s*([^()]*?)\s*\)", r"\1", v)
    return v.strip()


def decls(block: str) -> dict:
    """`margin:0 0 16px;background:rgba(...)` -> {prop: normalised value}."""
    out = {}
    for part in block.split(";"):
        if ":" not in part:
            continue
        k, _, v = part.partition(":")
        k = k.strip().lower()
        v = norm_value(v)
        if k and v and not k.startswith("/*"):
            out[k] = v
    return out


def rules_from(text: str, selectors: list) -> dict:
    """selector -> {prop: value}, reading the LAST occurrence (later rules win in CSS)."""
    found = {}
    for sel in selectors:
        # match `<sel> {  ... }` allowing the selector to be preceded by a quote (the JS string form)
        for m in re.finditer(re.escape(sel) + r"\s*\{([^}]*)\}", text):
            body = m.group(1)
            # strip CSS comments so a note inside a rule is never read as a declaration
            body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
            found[sel] = decls(body)
    return found


SELECTORS = [".wh-help", ".wh-help > summary", ".wh-help > p", ".wh-help > ul"]


def compare(css_text: str, js_text: str) -> list:
    a = rules_from(css_text, SELECTORS)
    b = rules_from(js_text, SELECTORS)
    problems = []
    shared = sorted(set(a) & set(b))
    if not shared:
        problems.append("neither source declares any .wh-help rule - the gate is watching nothing "
                        "(a lock nothing runs locks nothing)")
        return problems
    for sel in shared:
        for prop in sorted(set(a[sel]) & set(b[sel])):
            if a[sel][prop] != b[sel][prop]:
                problems.append(f"{sel} {{{prop}}}: components.css has {a[sel][prop]!r} but "
                                f"utils.js injects {b[sel][prop]!r} - a second, DIFFERENT rule after "
                                f"first paint is a layout shift")
    return problems


def main() -> int:
    if not CSS.exists() or not JS.exists():
        print("FAIL wh-help-parity - components.css or utils.js is missing")
        return 1
    problems = compare(io.open(CSS, encoding="utf-8").read(), io.open(JS, encoding="utf-8").read())
    if problems:
        print("FAIL wh-help-parity - the two .wh-help declarations disagree:")
        for p in problems:
            print("  " + p)
        return 1
    print("PASS wh-help-parity - components.css and the utils.js fallback declare the same .wh-help "
          "values, so no page can shift when the injected rule lands after first paint")
    return 0


def _self_test() -> int:
    fails = []
    css = ".wh-help {\n  margin: 0 0 16px;\n  padding: 10px 14px;\n}\n"
    js_ok = "'.wh-help{margin:0 0 16px;padding:10px 14px}' +"
    js_bad = "'.wh-help{margin:0 0 14px;padding:10px 14px}' +"

    if compare(css, js_ok):
        fails.append("identical declarations must PASS (whitespace and formatting differ by design)")
    p = compare(css, js_bad)
    if not p or "margin" not in p[0]:
        fails.append("a differing margin must FAIL and name the property")
    if p and ("16px" not in p[0] or "14px" not in p[0]):
        fails.append("the failure must show BOTH values so the fix is obvious")

    # a property in only one source is not a disagreement
    if compare(css, "'.wh-help{margin:0 0 16px}' +"):
        fails.append("a property declared in only one source must not fail - utils.js ships a subset")
    # a comment inside the rule must not be read as a declaration
    if compare(".wh-help {\n /* note: keep in sync */ margin: 0 0 16px;\n}", "'.wh-help{margin:0 0 16px}'"):
        fails.append("a CSS comment inside the rule must not be parsed as a declaration")
    # watching nothing must be loud
    if not compare("body{}", "var x = 1"):
        fails.append("if neither file declares .wh-help the gate must say it is watching nothing")

    # formatting is NOT a difference: these three pairs are the same value written differently
    for a, b, why in (
        ("rgba(255, 255, 255, 0.02)", "rgba(255,255,255,0.02)", "spaces after commas inside a function"),
        ("var(--wh-radius, 12px)", "12px", "a var() with a fallback vs that same fallback"),
        ("1px solid rgba(255, 255, 255, 0.06)", "1px solid rgba(255,255,255,0.06)", "both, in a shorthand"),
    ):
        if norm_value(a) != norm_value(b):
            fails.append(f"{why} must normalise equal ({a!r} vs {b!r}) - a gate that reds on formatting "
                         "is a false red")
    # ...but a real difference in the same shapes must still be caught
    if norm_value("var(--wh-radius, 12px)") == norm_value("16px"):
        fails.append("a var() fallback that genuinely differs must still fail")
    if norm_value("rgba(255,255,255,0.02)") == norm_value("rgba(255,255,255,0.06)"):
        fails.append("a real alpha change must still fail")

    print("FAIL validate_wh_help_parity self-test - " + "; ".join(fails) if fails
          else "self-test OK: identical values pass, a differing value fails and names both sides, a "
               "one-sided property is allowed, an in-rule comment is not a declaration, and a gate "
               "watching nothing says so")
    return 1 if fails else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        raise SystemExit(_self_test())
    raise SystemExit(main())
