""" -*- coding: utf-8 -*-
A public claim about how many calculators we have must match how many we have (T151/T161).

Three surfaces make this claim and two of them were wrong:

  * engineering-design.html's meta description said "46 calculation types ... and Structural";
  * assistant.html's GROUNDING - the text the AI answers from - said "46 calculation types across
    ... Structural, Machine Design, Vertical Transportation";
  * the /learn free-calculators page says "60 free calculators", which is about the 60 PUBLIC
    /tools pages and is correct - a different population, deliberately not gated here.

Measured from CALC_TYPES_UI, the file's own declared sole source of truth: **55 types across SIX
disciplines** - HVAC & Cooling 10, Mechanical 4, Electrical 14, Plumbing 10, Fire Protection 5,
Machine Design 12.

★THE COUNT BEING LOW IS THE FORGIVABLE HALF. The damaging half is the DISCIPLINE list: both claims
named Structural, and the assistant's also named Vertical Transportation, neither of which exists
in this calculator. An SEO snippet promising a structural calculator sends a searcher to a page
that has none; the assistant's grounding is worse, because the AI states it confidently, in
conversation, to someone who then goes looking. A wrong number is a stale fact - a wrong CAPABILITY
is a promise the product cannot keep.

★AND THIS IS WHY THE GATE COUNTS RATHER THAN COMPARING TWO STRINGS: the drift happened because the
number was typed by a human who was right at the time. Anything hand-maintained against a growing
registry is a future defect with a date on it. This reads the registry.

The learn page's 60 is deliberately OUT of scope: it counts public /tools pages, a different
population, and folding two populations into one gate is how a correct claim gets "fixed" into a
wrong one.

TEETH: synthetic negatives - the count drifted, a phantom discipline restored, a real one dropped.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "engineering-design.js"
CLAIMANTS = [
    ("engineering-design.html", "the SEO snippet a searcher arrives on"),
    ("assistant.html", "the grounding the AI answers from, stated confidently in conversation"),
]

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# disciplines that have never existed in CALC_TYPES_UI but were claimed publicly
PHANTOMS = ["Structural", "Vertical Transportation"]


def _strip_comments(src: str) -> str:
    """The fix comment quotes the old wrong claim, including the phantom discipline."""
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def count_registry(src: str) -> tuple:
    """(total types, [discipline names]) read from CALC_TYPES_UI itself."""
    m = re.search(r"CALC_TYPES_UI\s*=\s*\{", src)
    if not m:
        return (0, [])
    # walk to the matching brace so a later object cannot bleed in
    i = m.end() - 1
    depth = 0
    for j in range(i, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                break
    body = src[i:j + 1]
    body_nc = LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", body))
    disciplines = re.findall(r"(?m)^\s*'([^']+)'\s*:\s*\[", body_nc)
    total = len(re.findall(r"\{\s*id\s*:", body_nc))
    return (total, disciplines)


def audit(reg_src: str, claim_sources: dict) -> list:
    total, disciplines = count_registry(reg_src)
    out = []
    if total == 0 or not disciplines:
        out.append("engineering-design.js: CALC_TYPES_UI could not be read - this gate's denominator "
                   "is gone, and a count check with no count passes silently")
        return out

    for fname, why in CLAIMANTS:
        raw = claim_sources.get(fname)
        if raw is None:
            out.append(f"{fname}: missing - re-point this gate")
            continue
        s = _strip_comments(raw)
        m = re.search(r"(\d{2,3})\s+calculation types", s)
        if not m:
            out.append(f"{fname}: no longer states a calculation-type count - {why} has lost the "
                       f"claim entirely, which is not a fix, just a silence")
            continue
        claimed = int(m.group(1))
        if claimed != total:
            out.append(f"{fname}: claims {claimed} calculation types, CALC_TYPES_UI holds {total} - "
                       f"{why}. Hand-maintained counts against a growing registry are future defects "
                       f"with a date on them")
        for ph in PHANTOMS:
            if ph in disciplines:
                continue                      # it became real; not a phantom any more
            if re.search(r"\b" + re.escape(ph) + r"\b", s):
                out.append(f"{fname}: names '{ph}' as a discipline of this calculator and it does not "
                           f"exist in CALC_TYPES_UI - {why}. A wrong NUMBER is a stale fact; a wrong "
                           f"CAPABILITY is a promise the product cannot keep")
    return out


def _load() -> dict:
    out = {}
    for fname, _ in CLAIMANTS:
        p = ROOT / fname
        out[fname] = io.open(p, encoding="utf-8", errors="replace").read() if p.exists() else None
    return out


def selftest() -> int:
    reg = io.open(REGISTRY, encoding="utf-8", errors="replace").read()
    src = _load()
    total, disciplines = count_registry(reg)
    cases = [("the registry parses to a real count", [] if total > 0 and disciplines else ["unreadable"], 0),
             ("every public claim matches the registry", audit(reg, src), 0)]
    for fname, _ in CLAIMANTS:
        if src.get(fname) is None:
            continue
        drifted = dict(src)
        drifted[fname] = re.sub(r"\d{2,3}(\s+calculation types)", r"46\1", src[fname])
        cases.append((f"a drifted count in {fname} is caught", audit(reg, drifted), 1))
        phantom = dict(src)
        phantom[fname] = src[fname].replace("and Machine Design", "and Structural", 1) \
                                   .replace("Fire Protection, and Machine Design", "Fire Protection, Structural", 1)
        if phantom[fname] != src[fname]:
            cases.append((f"a phantom discipline in {fname} is caught", audit(reg, phantom), 1))
    bad = 0
    for label, findings, want in cases:
        ok = (len(findings) == 0) if want == 0 else (len(findings) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(findings)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    if not REGISTRY.exists():
        print("FAIL - engineering-design.js is gone; re-point this gate")
        return 1
    reg = io.open(REGISTRY, encoding="utf-8", errors="replace").read()
    total, disciplines = count_registry(reg)
    findings = audit(reg, _load())
    print("the-calc-count-is-true - a public claim about how many calculators we have matches the registry")
    print(f"  CALC_TYPES_UI: {total} types across {len(disciplines)} disciplines ({', '.join(disciplines)})")
    if findings:
        print("\nFAIL - a public surface claims something the calculator does not have:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every claiming surface states the registry's real count and only its real disciplines.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
