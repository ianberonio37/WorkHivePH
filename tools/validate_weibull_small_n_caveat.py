#!/usr/bin/env python3
"""validate_weibull_small_n_caveat.py — T26's lock instrument: a Weibull fit on FEW failures is shown with
a confidence caveat, never as a decisive two-decimal verdict — so a supervisor is not led to defend a
number that a month later flips from wear-out to infant-mortality on one more failure.

T26 measured it on asset M-001: two fits a month apart flipped beta 1.29 -> 0.71 (wear-out -> infant, eta
448d -> 13d) on 8-9 failures, each stated with decisive point estimates and NO caveat. The fix:
_renderWeibullFit (asset-hub.html) appends a small-sample confidence note when n_failures < 15 (rendered
client-side so stored pre-diagnostic fits get it too). This gate locks the caveat so a future edit cannot
drop it and let a low-n fit read as decisive — the 'a figure needs its qualifier NEXT TO it' class.

Assertions on asset-hub.html (each refutable — see the self-test):
  1. THE THRESHOLD — a `n_failures < 15` (or `nF < 15`) small-sample branch in the Weibull render.
  2. THE CAVEAT — that branch appends a confidence/caution note (not just computes a flag).

Read-only; no browser; no DB. Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "asset-hub.html"

CHECK_NAMES = ["weibull-small-n-caveat"]

_THRESHOLD = re.compile(r"""(n_?F(?:ailures)?)\s*<\s*15""")
# the caveat text/element created in the small-n neighbourhood
_CAVEAT = re.compile(r"<\s*15[^}]{0,400}(caveat|confidence|caution|few failures|small sample|treat[^.]{0,30}caution|wide)", re.I | re.S)


def check(src: str) -> list[str]:
    problems: list[str] = []
    if not _THRESHOLD.search(src):
        problems.append("no `n_failures < 15` small-sample branch — a fit on few failures is not flagged as "
                        "low-confidence.")
    if not _CAVEAT.search(src):
        problems.append("the small-sample branch renders no confidence caveat — a low-n fit would still "
                        "read as a decisive verdict (the number needs its qualifier next to it).")
    return problems


def main() -> int:
    if not PAGE.exists():
        print("FAIL weibull-small-n-caveat: asset-hub.html not found"); return 1
    problems = check(PAGE.read_text(encoding="utf-8", errors="replace"))
    if problems:
        print("FAIL weibull-small-n-caveat — a low-n Weibull fit is shown without its confidence caveat:")
        for p in problems:
            print(f"    {p}")
        return 1
    print("PASS weibull-small-n-caveat — a fit with n_failures < 15 appends a confidence caveat, so a "
          "small-sample estimate is never presented as a decisive verdict.")
    return 0


def self_test() -> int:
    fails = []
    good = "const nF=fit.n_failures; if (nF > 0 && nF < 15) { const caveat=document.createElement('div'); caveat.textContent='Wide confidence at few failures — treat with caution'; }"
    if check(good):
        fails.append("the real small-n caveat should PASS")
    if not any("< 15" in p for p in check("const c=document.createElement('div'); c.textContent='confidence';")):
        fails.append("missing the n<15 threshold should FAIL")
    if not any("caveat" in p for p in check("if (nF < 15) { flag=true; }")):
        fails.append("a n<15 branch with no caveat text should FAIL")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_weibull_small_n_caveat self-test (missing threshold / no-caveat redden)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
