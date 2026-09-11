#!/usr/bin/env python3
"""audit_rubric_language_bias.py — find every text-matching check in the UFAI rubric that reads only
ENGLISH, before a walk trips over it.

★WHY. Four independent English-only vocabularies were found in survey_ufai_rubric.js in a single day,
each by accident, each one-directional (the English page passes, its faithful translation fails):

  B3  readability   Flesch-Kincaid, fitted to English, graded Filipino +4.53 harder for the same sentence
  E3  freshness     "Kakakalkula lang" is the shipped translation of "Recomputed just now" - unreadable
  X1  guidance      "Irehistro muna ang mga asset" names its recovery path - unreadable (3rd widening)
  --  permission    "Para sa supervisor lang" is "Supervisors only" - so an honest wall read as a broken page

Finding these one walk at a time does not converge, and LOANWORDS are what hide them: of the 44 English
strings carrying a freshness word, 25 keep that word through translation, so the check looks like it
works right up until it meets the 19 that do not.

★THE INSTRUMENT. i18n/*.json is a PARALLEL CORPUS - each English string beside its shipped Filipino.
For any prose-matching regex, run it over both halves of every pair: if it matches the English side of N
pairs but the Filipino side of far fewer, the check is reading the LANGUAGE rather than the property it
claims to measure. That ratio is computable for every regex in the file at once, with no browser and no
walk.

The output ranks checks by their EN->FIL retention. A LOW retention is a candidate, not a verdict: some
vocabularies SHOULD be English-only (JARGON matches RPC/JSON/HTTP 500, which are language-neutral tokens
that appear verbatim in both). The tool narrows dozens of regexes to the few worth reading.

    python tools/audit_rubric_language_bias.py                # ranked report
    python tools/audit_rubric_language_bias.py --min-en 8     # only checks with enough English evidence
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUBRIC = os.path.join(ROOT, "survey_ufai_rubric.js")

# `const NAME = /body/flags;`  — the shape the rubric uses for its vocabularies.
NAMED_RE = re.compile(r"const\s+([A-Z][A-Z0-9_]{2,})\s*=\s*/((?:[^/\\\n]|\\.)+)/([gimsuy]*)\s*;")
# `const NAME = new RegExp( 'a' + 'b', 'i');` — the shape they take once they grow too long.
NAMED_STR = re.compile(r"const\s+([A-Z][A-Z0-9_]{2,})\s*=\s*new RegExp\(([\s\S]{0,4000}?),\s*'([gimsuy]*)'\s*\)\s*;")


def js_to_py(body: str) -> str:
    """JS regex bodies are close enough to Python's for these vocabularies; normalise the differences."""
    return body.replace("(?<=", "(?<=").replace(r"\d", r"\d")


def load_regexes() -> list[tuple[str, "re.Pattern"]]:
    src = io.open(RUBRIC, encoding="utf-8").read()
    out = []
    for m in NAMED_RE.finditer(src):
        name, body, flags = m.group(1), m.group(2), m.group(3)
        try:
            out.append((name, re.compile(js_to_py(body), re.I if "i" in flags else 0)))
        except re.error:
            pass
    for m in NAMED_STR.finditer(src):
        name, expr, flags = m.group(1), m.group(2), m.group(3)
        # concatenated string literals, with // comments interleaved — strip the comments, join the parts
        expr = re.sub(r"//[^\n]*", "", expr)
        parts = re.findall(r"'((?:[^'\\]|\\.)*)'", expr)
        if not parts:
            continue
        body = "".join(p.replace("\\\\", "\\") for p in parts)
        try:
            out.append((name, re.compile(js_to_py(body), re.I if "i" in flags else 0)))
        except re.error:
            pass
    return out


def corpus() -> list[tuple[str, str]]:
    pairs = []
    for p in sorted(glob.glob(os.path.join(ROOT, "i18n", "*.json"))):
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        for en, fil in d.items():
            if isinstance(en, str) and isinstance(fil, str) and fil.strip() and not en.startswith("_"):
                pairs.append((en, fil))
    return pairs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-en", type=int, default=5,
                    help="ignore checks matching fewer than this many English strings (too little evidence)")
    a = ap.parse_args()
    pairs = corpus()
    rows = []
    for name, rx in load_regexes():
        en_hits = [(en, fil) for en, fil in pairs if rx.search(en)]
        if len(en_hits) < a.min_en:
            continue
        kept = sum(1 for en, fil in en_hits if rx.search(fil))
        rows.append((kept / len(en_hits), name, len(en_hits), kept,
                     [(e, f) for e, f in en_hits if not rx.search(f)][:2]))
    rows.sort()
    print(f"parallel EN/FIL pairs: {len(pairs)}   checks with >= {a.min_en} English matches: {len(rows)}\n")
    print(f"{'retention':>9}  {'check':22s} {'EN':>4} {'FIL':>4}   the English side matched, the Filipino did not")
    for ret, name, n, kept, ex in rows:
        flag = "  <-- ENGLISH-ONLY?" if ret < 0.5 else ("  <-- thin" if ret < 0.8 else "")
        print(f"  {ret * 100:6.0f}%  {name:22s} {n:4d} {kept:4d}{flag}")
        for e, f in ex:
            print(f"             EN  {e[:64]!r}")
            print(f"             FIL {f[:64]!r}")
    print("\nA low retention is a CANDIDATE, not a verdict: a vocabulary of language-neutral tokens")
    print("(JARGON: RPC / JSON / HTTP 500) correctly matches both halves and needs no widening.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
