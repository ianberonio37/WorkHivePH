#!/usr/bin/env python3
"""validate_injected_css_parity.py - a rule the shell scripts inject must size its text the way components.css does.

★A COPY THAT STAYS BEHIND IS A LAYOUT SHIFT (2026-11-04). utils.js injects a fallback copy of several component rules
(.wh-list-error, the skeleton rows, ...) for pages that do not link components.css - the same arrangement
validate_wh_help_parity.py already holds for .wh-help. The type scale moved components.css's `.wh-list-error` from 0.82rem
onto its 0.8rem step while utils.js kept 0.82rem, and `.wh-list-error button` had already drifted (0.75rem in the
stylesheet, 0.78rem injected) before this wave. On a page that carries both, the second rule to land re-sizes the text
after first paint. Nothing compared the copies outside .wh-help.

This compares every selector a shell script injects that components.css also declares, on font-size, read through the
tokens (var(--wh-fs-xs, 0.8rem) is 0.8rem: tokens.css is resolved, never the fallback alone). A selector in only one
source is not a failure - the scripts ship a subset - a selector in both with different sizes is.

    python tools/validate_injected_css_parity.py
    python tools/validate_injected_css_parity.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHELL_SCRIPTS = ("utils.js", "nav-hub.js", "maturity-gate.js", "wh-feedback-fab.js", "offline-banner.js")
_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_TOKEN = re.compile(r"(--wh-[\w-]+)\s*:\s*([^;]+);")


def tokens(text: str) -> dict:
    return {n: v.strip() for n, v in _TOKEN.findall(text)}


def to_px(value: str, toks: dict):
    v = value.strip().replace("!important", "").strip()
    m = re.fullmatch(r"var\(\s*(--wh-[\w-]+)\s*(?:,\s*(.+))?\)", v)
    if m:
        v = toks.get(m.group(1)) or (m.group(2) or "")
    m = re.fullmatch(r"(\d*\.?\d+)(rem|px|pt)", v.strip())
    if not m:
        return None
    return float(m.group(1)) * {"rem": 16, "px": 1, "pt": 4 / 3}[m.group(2)]


def css_sizes(css: str) -> dict:
    out = {}
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", _COMMENT.sub(" ", css)):
        fs = re.search(r"font-size\s*:\s*([^;}]+)", m.group(2))
        if fs:
            for sel in m.group(1).split(","):
                out[re.sub(r"\s+", " ", sel.strip())] = fs.group(1).strip()
    return out


def injected_sizes(js: str) -> dict:
    """Rules inside the script's CSS string literals: '<selector>{...font-size:...}'."""
    out = {}
    for lit in re.findall(r"'((?:[^'\\\n]|\\.)*)'", js):
        if "{" in lit and "font-size" in lit:
            out.update(css_sizes(lit))
    return out


def compare(components: str, scripts: dict, toks: dict) -> list:
    want = css_sizes(components)
    problems = []
    for name, js in scripts.items():
        for sel, val in injected_sizes(js).items():
            if sel not in want:
                continue
            a, b = to_px(want[sel], toks), to_px(val, toks)
            if a is None or b is None:
                continue
            if abs(a - b) > 1e-6:
                problems.append(f"{name}: `{sel}` injects {val} ({b:g}px) but components.css has {want[sel]} ({a:g}px) "
                                f"- a second, different size after first paint is a layout shift")
    return problems


def main() -> int:
    comp = io.open(ROOT / "components.css", encoding="utf-8").read()
    toks = tokens(io.open(ROOT / "tokens.css", encoding="utf-8").read())
    scripts = {s: io.open(ROOT / s, encoding="utf-8").read() for s in SHELL_SCRIPTS if (ROOT / s).exists()}
    shared = sum(1 for js in scripts.values() for sel in injected_sizes(js) if sel in css_sizes(comp))
    if not shared:
        print("FAIL injected-css-parity - no injected rule shares a selector with components.css: the gate is watching "
              "nothing")
        return 1
    problems = compare(comp, scripts, toks)
    if problems:
        print(f"FAIL injected-css-parity - {len(problems)} injected rule(s) size their text differently from "
              f"components.css:")
        for p in problems:
            print("  " + p)
        return 1
    print(f"PASS injected-css-parity - {shared} injected rule(s) shared with components.css declare the same font size")
    return 0


def self_test() -> int:
    toks = {"--wh-fs-xs": "0.8rem", "--wh-fs-2xs": "0.75rem"}
    comp = ".e{font-size:var(--wh-fs-xs, 0.8rem)}\n.e button{font-size:0.75rem}\n/* .c{font-size:9rem} */"
    bad = []
    if compare(comp, {"u.js": "x = '.e{font-size:0.8rem}' + '.e button{font-size:var(--wh-fs-2xs, 0.75rem)}';"}, toks):
        bad.append("the same size spelled as a token on one side and a literal on the other must PASS")
    p = compare(comp, {"u.js": "x = '.e{font-size:0.82rem}';"}, toks)
    if not p or "0.82rem" not in p[0]:
        bad.append("teeth: a copy left at 0.82rem against the stylesheet's 0.8rem must FAIL and name both")
    if compare(comp, {"u.js": "x = '.only-here{font-size:2rem}';"}, toks):
        bad.append("a selector in one source only is not a disagreement")
    if compare(comp, {"u.js": "x = '.c{font-size:1rem}';"}, toks):
        bad.append("a rule inside a stylesheet comment is not a declaration")
    if to_px("var(--wh-fs-xs, 0.95rem)", toks) != 12.8:
        bad.append("a var() resolves to the TOKEN, not its fallback")
    print("FAIL injected-css-parity self-test: " + "; ".join(bad) if bad
          else "self-test OK: 5 cases - token and literal spellings agree, a stale copy fails naming both, one-sided and "
               "commented rules are ignored, and a var() reads the token")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else main())
