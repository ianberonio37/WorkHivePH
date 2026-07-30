#!/usr/bin/env python3
"""validate_gate_panel_honesty.py — the console that reports the gates must itself be honest.

S8-gates in the marketplace test bank. Everything else on this platform is watched by a gate; the
surface that DISPLAYS those gates was watched by nothing, and it has already failed twice:

  * G2 (fixed earlier this session) — the fail list printed each gate's `label`, which is written for
    the engineer reading run_platform_checks.py and carries file paths, roadmap filenames and internal
    vocabulary. That engineering prose leaked straight into user-facing chrome.
  * TRUNCATION (found 2026-07-29 by this gate's own hunt) — the regressions block rendered
    `regs.slice(0, 6)` with no overflow line. A regression is the highest-severity signal the page
    carries: a gate that was PASSING and now is not. Everything past the sixth simply vanished, and a
    truncated list with nothing after it reads as "that is all of them."

THREE INVARIANTS:
  1. the visible text of a gate row is the SHORT id-derived name, never the raw engineering label
  2. the full label survives as a tooltip, so nothing is lost - shortening is not hiding
  3. any list that truncates DISCLOSES the remainder ("+N more"), because silent truncation and
     "there were only six" are indistinguishable to the reader

Usage:  python tools/validate_gate_panel_honesty.py [--selftest]
"""
from __future__ import annotations

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "founder-console.html")
GREEN, RED, YEL, DIM, BOLD, RST = "\033[92m", "\033[91m", "\033[93m", "\033[2m", "\033[1m", "\033[0m"

# The gate-bearing lists on the console. Each is (variable, the window to inspect after its slice).
SLICE = re.compile(r"\b([A-Za-z_$][\w$]*)\.slice\(0,\s*(\d+)\)")


def check_page(src: str):
    """-> list of (ok, name, detail)."""
    out = []

    # 1 + 2 — the gate rows render the short name, with the label kept as the tooltip.
    has_shortener = re.search(r"gateName\s*=\s*v\s*=>", src) is not None
    out.append((has_shortener, "gate rows use a short id-derived name (gateName)",
                "the console prints the raw engineering label into user chrome"))
    # Proximity, not an exact literal. The real markup is `title="' + escHtml(v.label || '') + '">`
    # — a title attribute opened inside one string, concatenated, and closed in the next — and a regex
    # that spelled the quote sequence out reddened on correct code
    # ([[feedback_red_gate_may_be_inaccuracy_not_backlog]]). Ask "is the label near the row", which is
    # the actual claim, and let the exact quoting be whatever it needs to be.
    # EVERY occurrence, not the first. `fail-label` appears in the <style> block long before the
    # render site, so `.find()` anchored on the CSS rule and the check reddened on correct code — the
    # same shape as a grep matching a comment instead of the link
    # ([[feedback_grep_matched_the_comment_not_the_link]]).
    fail_row = any("escHtml(v.label" in src[m.start():m.start() + 120]
                   for m in re.finditer(r"fail-label", src))
    out.append((bool(fail_row), "the full engineering label survives as a tooltip",
                "shortening without a tooltip is hiding, not summarising"))
    leaks = re.search(r"escHtml\(v\.label \|\| ''\)\s*\+\s*'</div>", src)
    out.append((leaks is None, "no gate row prints v.label as its VISIBLE text",
                "a raw label is back in the visible chrome"))

    # 3 — every truncating list on the gate/regression panel discloses the remainder. Checked by
    # looking for a `<var>.length > <n>` disclosure near each `<var>.slice(0, n)`, so a NEW truncated
    # list added later must bring its own disclosure or this gate reds.
    watched = {"fails", "regs"}
    for m in SLICE.finditer(src):
        var, n = m.group(1), m.group(2)
        if var not in watched:
            continue
        window = src[m.end():m.end() + 900]
        disclosed = re.search(rf"{re.escape(var)}\.length\s*>\s*{n}\b", window) is not None
        out.append((disclosed, f"`{var}` truncates at {n} and DISCLOSES the remainder",
                    f"{var} silently drops everything past {n} — the reader sees a short list and "
                    f"believes it is the whole list"))
    return out


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if not os.path.exists(PAGE):
        print("  SKIP: founder-console.html not found")
        return 0
    with open(PAGE, encoding="utf-8") as f:
        src = f.read()
    print("=" * 84)
    print(f"  {BOLD}Gate panel honesty — the surface that reports the gates{RST}")
    print("=" * 84)
    results = check_page(src)
    bad = 0
    for ok, name, detail in results:
        print(f"  {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}  {name}"
              + (f"  {DIM}[{detail}]{RST}" if not ok else ""))
        bad += 0 if ok else 1
    print()
    if bad:
        print(f"{RED}FAIL{RST} — {bad}/{len(results)} honesty invariant(s) broken on the gate panel")
        return 1
    print(f"{GREEN}PASS{RST} — {len(results)} invariants: short names, nothing lost to the tooltip, "
          f"and no list truncates without saying so")
    return 0


def selftest():
    ok = True
    base = ("const gateName = v => String(v.id).replace(/x/,'');"
            "'<div class=\"fail-label\" title=\"' + escHtml(v.label || '') + '\">'"
            "+ fails.slice(0, 12).map(x=>x).join('') + (fails.length > 12 ? 'more' : '')"
            "+ regs.slice(0, 6).map(x=>x).join('') + (regs.length > 6 ? 'more' : '')")
    good = [r for r in check_page(base) if not r[0]]
    if good:
        print(f"  {RED}FAIL{RST} an honest panel was flagged: {good[0][1]}"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} an honest panel passes all invariants")

    silent = base.replace("+ (regs.length > 6 ? 'more' : '')", "")
    caught = [r for r in check_page(silent) if not r[0]]
    if not any("regs" in r[1] for r in caught):
        print(f"  {RED}FAIL{RST} a SILENTLY truncated regression list was not caught"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} a silently truncated regression list is caught")

    noshort = base.replace("const gateName = v => String(v.id).replace(/x/,'');", "")
    if not any("short id-derived" in r[1] for r in check_page(noshort) if not r[0]):
        print(f"  {RED}FAIL{RST} a panel with no shortener was not caught"); ok = False
    else:
        print(f"  {GREEN}PASS{RST} a panel that lost its shortener is caught")
    print(f"\n  SELFTEST: {GREEN + 'PASS' + RST if ok else RED + 'FAIL' + RST}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
