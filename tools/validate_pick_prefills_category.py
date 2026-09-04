#!/usr/bin/env python3
"""validate_pick_prefills_category.py — T21's lock: pick-from-registered prefills the REQUIRED
Category, because the type map speaks the vocabulary the data actually uses.

Walked live (T21): picking a registered asset prefilled name/tag/location and left Category empty —
TYPE_TO_CATEGORY was keyed by a hypothesized machine vocabulary ('Pump', 'Motor', 'HVAC'...) while
the picker aliases type:iso_class whose REAL values are discipline words (Mechanical 58,
Electrical 17, Pneumatic 11, Instrumentation, Hydraulic, legacy 'PUMP'); every lookup missed (an
oracle's vocabulary is part of the oracle). Fixed 2026-09-02: discipline keys added, lookups go
through the case-insensitive _typeToCategory resolver, verified live in-page across the whole real
vocabulary (6/6 resolve; unknown/empty degrade to '' safely).

Lock: (1) the map carries the discipline keys the data uses; (2) the pick site calls the resolver,
not the raw dict. Teeth: both redden when reverted.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK_NAMES = ["pick-prefills-category"]

DISCIPLINE_KEYS = ("'Mechanical'", "'Electrical'", "'Instrumentation'", "'Pneumatic'", "'Hydraulic'")
RESOLVER_USE_RE = re.compile(r"mappedCat = _typeToCategory\(a\.type\)")
RESOLVER_DEF_RE = re.compile(r"_typeToCategory\s*=\s*\(t\)\s*=>[\s\S]{0,400}?toLowerCase\(\)")


def problems_for(src: str) -> list[str]:
    out = []
    missing = [k for k in DISCIPLINE_KEYS if k + ":" not in src.replace(" ", "")]
    if missing:
        out.append("pm-scheduler.html: TYPE_TO_CATEGORY lost discipline key(s) " + ", ".join(missing)
                   + " — the map no longer speaks the data's iso_class vocabulary (T21 empty-category)")
    if not RESOLVER_DEF_RE.search(src):
        out.append("pm-scheduler.html: the case-insensitive _typeToCategory resolver is gone — "
                   "legacy-cased rows ('PUMP') miss again")
    if not RESOLVER_USE_RE.search(src):
        out.append("pm-scheduler.html: pickRegisteredAsset bypasses the resolver (raw dict lookup)")
    return out


def main() -> int:
    src = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()
    bad = problems_for(src)
    if bad:
        print("FAIL pick-prefills-category:")
        for p in bad:
            print("    " + p)
        return 1
    print("PASS pick-prefills-category — the type map speaks the real iso_class vocabulary and the "
          "pick site resolves case-insensitively (Category prefills; supervisor confirms).")
    return 0


def self_test() -> int:
    src = io.open(ROOT / "pm-scheduler.html", encoding="utf-8", errors="replace").read()
    fails = []
    if problems_for(src):
        fails.append("HEAD should PASS")
    if not any("vocabulary" in p for p in problems_for(src.replace("'Mechanical':      'Rotating Equipment',", ""))):
        fails.append("dropping a discipline key must redden")
    if not any("bypasses" in p for p in problems_for(RESOLVER_USE_RE.sub("mappedCat = TYPE_TO_CATEGORY[a.type] || ''", src))):
        fails.append("reverting to the raw lookup must redden")
    if fails:
        print("SELF-TEST FAIL:", "; ".join(fails)); return 1
    print("PASS validate_pick_prefills_category self-test (dropped key + raw lookup both redden; HEAD clean)")
    return 0


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(self_test() if "--self-test" in sys.argv else main())
