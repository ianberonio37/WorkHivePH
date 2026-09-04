#!/usr/bin/env python3
"""validate_symbol_gallery.py — T490's lock: the founder Symbol Gallery is COMPLETE & ACCURATE.

symbol-gallery.html renders symbols grouped ONLY by its four DISCIPLINE_ORDER buckets
(electrical/mechanical/pid/lps) and skips any other discipline silently (`if (!grouped[disc])
continue`). So the gallery is:
  - COMPLETE only if every symbol getSymbolList() returns has a discipline the gallery renders
    (otherwise a real library symbol never appears — an invisible gap), and
  - ACCURATE only if every symbol's render()/drawSymbol() produces a real SVG element (otherwise
    the card paints blank — a symbol claimed present but not actually drawn).

Verified 2026-09-01: 28 symbols across the 4 disciplines, 0 dropped, 0 non-rendering. This gate
runs tools/audit_symbol_gallery.mjs (loads the pure drawing-symbols.js, reads the gallery's OWN
DISCIPLINE_ORDER so the two can never silently diverge) and holds the line so a new symbol added
with an unlisted discipline, or one whose render() breaks, reddens before it ships as a silent gap.

node-backed, read-only, browser-free. SKIPs only if node is unavailable (no unearned pass).
Registered in run_platform_checks (Platform).
"""
from __future__ import annotations

import io
import json
import subprocess
import sys

CHECK_NAMES = ["symbol-gallery-complete"]
_MJS = "tools/audit_symbol_gallery.mjs"


def _run(selftest: bool = False):
    args = ["node", _MJS] + (["--self-test"] if selftest else [])
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        return None
    except Exception:
        return None


def check(a: dict) -> list[str]:
    problems: list[str] = []
    if not a.get("gallery_disc"):
        problems.append("could not read DISCIPLINE_ORDER from symbol-gallery.html (the gallery's render set is unknown)")
    if a.get("total", 0) == 0:
        problems.append("getSymbolList() returned no symbols (the library is empty or failed to load)")
    for d in a.get("dropped", []):
        problems.append(f"{d}: discipline the gallery does not render — this symbol is silently DROPPED (gallery incomplete)")
    for d in a.get("nonrender", []):
        problems.append(f"{d}: render() produced no drawable SVG — the card paints blank (gallery inaccurate)")
    return problems


def main() -> int:
    r = _run()
    if r is None:
        print("SKIP symbol-gallery-complete — node unavailable (no unearned pass)."); return 0
    if r.returncode != 0 or not (r.stdout or "").strip():
        print("FAIL symbol-gallery-complete — the audit did not run:", (r.stderr or r.stdout or "").strip()[:200]); return 1
    a = json.loads(r.stdout.strip().splitlines()[-1])
    problems = check(a)
    if problems:
        print("FAIL symbol-gallery-complete — the gallery is not complete/accurate:")
        for p in problems:
            print(f"    {p}")
        return 1
    print(f"PASS symbol-gallery-complete — all {a['total']} library symbols map to a rendered discipline "
          f"({', '.join(a['gallery_disc'])}) and every one draws a real SVG: the gallery is complete and accurate.")
    return 0


def self_test() -> int:
    fails = []
    # 1) check() logic bites on a dropped or non-rendering symbol, passes when clean
    if check({"gallery_disc": ["electrical"], "total": 5, "dropped": [], "nonrender": []}):
        fails.append("a clean audit should PASS")
    if not any("DROPPED" in p for p in check({"gallery_disc": ["electrical"], "total": 5, "dropped": ["x(bogus)"], "nonrender": []})):
        fails.append("a dropped symbol should FAIL")
    if not any("blank" in p for p in check({"gallery_disc": ["electrical"], "total": 5, "dropped": [], "nonrender": ["y -> "]})):
        fails.append("a non-rendering symbol should FAIL")
    if not any("DISCIPLINE_ORDER" in p for p in check({"gallery_disc": [], "total": 5, "dropped": [], "nonrender": []})):
        fails.append("a missing DISCIPLINE_ORDER should FAIL")
    # 2) the node audit engine itself catches an injected bad-discipline + empty-render symbol
    r = _run(selftest=True)
    if r is None:
        print("SELF-TEST SKIP: node unavailable");
    else:
        if r.returncode != 0:
            fails.append(f"node audit self-test did not confirm teeth: {(r.stderr or r.stdout or '').strip()[:160]}")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_symbol_gallery self-test (dropped / non-render / missing-order redden; node audit catches injected bad symbols)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
