#!/usr/bin/env python3
"""validate_ai_context_quality.py — T16's gate, built after the citation (the 'a lock nothing runs' repair).

Locks the two properties T16's walk established (2026-08-28 basis):
  1. MIRROR AGREEMENT, COUNTED FROM THE REGISTRY: every hardcoded "NN calc types" /
     "NN calculation types" claim the companion or assistant makes must equal the count
     DERIVED from engineering-design.js CALC_TYPES_UI (available: true entries) — the
     full board once caught companion-launcher saying 46 while assistant said 55, and the
     fix was to count the registry rather than pick a side. A drifted claim reddens here.
  2. GROUNDING DECLARED AT THE SURFACE: assistant.html keeps its two plain-words grounding
     declarations (empty state: "grounded in your own hive data"; live state: "grounded in
     this hive") — the companion must keep telling workers where answers come from.

Static file scan, no DB, fast. --self-test proves teeth (a planted 46 must be CAUGHT).
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ED = ROOT / "engineering-design.js"
CONSUMERS = [ROOT / "companion-launcher.js", ROOT / "assistant.html"]
CLAIM_RE = re.compile(r"(\d+)\s+calc(?:ulation)?\s+types?", re.I)


def registry_count(text: str) -> int:
    m = re.search(r"CALC_TYPES_UI\s*=\s*\{", text)
    if not m:
        return -1
    # count available:true inside the object literal (brace-balanced slice)
    depth, i = 0, m.end() - 1
    for j in range(i, len(text)):
        if text[j] == "{":
            depth += 1
        elif text[j] == "}":
            depth -= 1
            if depth == 0:
                block = text[i : j + 1]
                return len(re.findall(r"available\s*:\s*true", block))
    return -1


def check(ed_text: str, consumers: list[tuple[str, str]]) -> list[str]:
    problems: list[str] = []
    n = registry_count(ed_text)
    if n <= 0:
        return [f"CALC_TYPES_UI not found/parsable in engineering-design.js (count={n})"]
    for name, text in consumers:
        for mm in CLAIM_RE.finditer(text):
            claimed = int(mm.group(1))
            if claimed != n:
                problems.append(
                    f"{name}: claims '{mm.group(0)}' but the registry (CALC_TYPES_UI available:true) counts {n}"
                )
    a_text = dict(consumers).get("assistant.html", "")
    if "grounded in your own hive data" not in a_text:
        problems.append("assistant.html: empty-state grounding declaration missing ('grounded in your own hive data')")
    if "grounded in this hive" not in a_text:
        problems.append("assistant.html: live-state grounding declaration missing ('grounded in this hive')")
    return problems


def self_test() -> int:
    ed = "const CALC_TYPES_UI = { a: [{available: true}, {available: true}] };"
    good = [("companion-launcher.js", "Ask about any of the 2 calc types"), ("assistant.html", "2 calculation types grounded in your own hive data grounded in this hive")]
    bad = [("companion-launcher.js", "Ask about any of the 46 calc types"), ("assistant.html", "2 calc types grounded in your own hive data grounded in this hive")]
    nog = [("companion-launcher.js", "2 calc types"), ("assistant.html", "2 calc types")]
    if check(ed, good):
        print("SELF-TEST FAIL: clean case reddened")
        return 1
    if not any("46" in p for p in check(ed, bad)):
        print("SELF-TEST FAIL: planted 46 not caught")
        return 1
    if not any("grounding declaration" in p for p in check(ed, nog)):
        print("SELF-TEST FAIL: missing grounding declaration not caught")
        return 1
    print("PASS validate_ai_context_quality self-test (drifted count + missing declaration both redden)")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    ed_text = io.open(ED, encoding="utf-8", errors="replace").read()
    consumers = [(p.name, io.open(p, encoding="utf-8", errors="replace").read()) for p in CONSUMERS]
    problems = check(ed_text, consumers)
    if problems:
        print("FAIL ai-context-quality:")
        for p in problems:
            print("    " + p)
        return 1
    n = registry_count(ed_text)
    claims = sum(len(CLAIM_RE.findall(t)) for _, t in consumers)
    print(
        f"PASS ai-context-quality — {claims} calc-type claim(s) all equal the registry count ({n}), "
        "and the assistant declares its grounding on both the empty and live states."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
