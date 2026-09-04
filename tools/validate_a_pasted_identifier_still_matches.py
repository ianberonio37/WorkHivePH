""" -*- coding: utf-8 -*-
A pasted value must still match, wherever whitespace changes MEANING (T123).

People paste. A part number arrives from a Viber message, a username from an email, a supplier
address from a PDF - and every one can carry a leading or trailing space the person cannot see.
Where that value is used for IDENTITY or MATCHING, the invisible character decides whether the
system works:

  * si-username / su-username - a space and sign-in simply fails, with correct credentials;
  * the inventory SEARCH - a space and a part that exists returns nothing, which reads as
    "we do not stock it" to someone standing at the shelf;
  * part_number / part_name on write - a space is baked into the record, so the row never matches
    its own search again;
  * a recipient email - a space and the report bounces.

★THE PROPERTY IS DELIBERATELY NOT "TRIM EVERYTHING". Free-form notes are exempt on purpose:
dayplanner's note and logbook's knowledge field are textareas where a person may indent lines, so
leading whitespace is CONTENT rather than an accident. A gate demanding .trim() on every text field
would be enforcing an opinion about prose, and would eventually be switched off. This holds exactly
the fields where whitespace changes an answer.

★AND THE SCAN THAT FOUND THIS NEEDED CAREFUL READING, WHICH IS WHY THE LIST IS EXPLICIT. A search
for untrimmed values reaching a payload flagged inventory's `q` and `cat`; both turned out to be the
remembered-filter SNAPSHOT, restored into the input and re-trimmed at the point of use. Judging by
the assignment rather than the use would have filed two defects against correct code, so this gate
names its subjects instead of pattern-matching for suspects.

★THE SELFTEST MUTATES COPIES, NEVER DISK. Its first version rewrote the real product files and
restored them in a finally block - one crash, or one board run reading a page mid-mutation, away
from a corrupted source or a voided board. audit() takes sources for exactly that reason.

TEETH: synthetic negatives - each guarded read stripped of its .trim() in turn, on a copy.
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?m)^\s*//.*$")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# (file, element id, what breaks without the trim)
IDENTITY_FIELDS = [
    ("index.html", "si-username",
     "a pasted username with a space fails sign-in with correct credentials"),
    ("index.html", "su-username",
     "a pasted username with a space creates an account nobody can sign into"),
    ("inventory.html", "search-input",
     "a pasted part number finds nothing, which reads as 'we do not stock it' at the shelf"),
    ("inventory.html", "f-part-number",
     "the space is baked into the record, so the row never matches its own search again"),
    ("inventory.html", "f-part-name",
     "the stored name carries an invisible character into every future lookup"),
    ("report-sender.html", "contact-email", "the report bounces"),
]


def _strip_comments(src: str) -> str:
    return LINE_COMMENT.sub("", BLOCK_COMMENT.sub(" ", HTML_COMMENT.sub(" ", src)))


def _read_pattern(eid: str) -> str:
    """Any READ of this element's value; an assignment (a reset to '') is not a read."""
    return (r"getElementById\(\s*['\"]" + re.escape(eid)
            + r"['\"]\s*\)\s*\.\s*value(?!\s*=)([^;\n]{0,40})")


def _trim_pattern(eid: str) -> str:
    return (r"(getElementById\(\s*['\"]" + re.escape(eid)
            + r"['\"]\s*\)\s*\.\s*value)\s*\.\s*trim\(\)")


def _load() -> dict:
    out = {}
    for fname, _, _ in IDENTITY_FIELDS:
        p = ROOT / fname
        out[fname] = io.open(p, encoding="utf-8", errors="replace").read() if p.exists() else None
    return out


def audit(sources: dict) -> list:
    out = []
    for fname, eid, consequence in IDENTITY_FIELDS:
        raw = sources.get(fname)
        if raw is None:
            out.append(f"{fname}: missing - re-point this gate")
            continue
        s = _strip_comments(raw)
        reads = list(re.finditer(_read_pattern(eid), s))
        if not reads:
            out.append(f"{fname}: #{eid} is never read - the field this gate protects was removed or "
                       f"renamed, and the property is no longer covered by anything")
            continue
        if not any(".trim(" in m.group(1) for m in reads):
            out.append(f"{fname}: #{eid} is read without .trim() - {consequence}. People paste, and a "
                       f"leading or trailing space is invisible to the person who pasted it")
    return out


def selftest() -> int:
    src = _load()
    cases = [("every identity field trims today", audit(src), 0)]
    for fname, eid, _ in IDENTITY_FIELDS:
        if src.get(fname) is None:
            continue
        mutated = dict(src)
        mutated[fname] = re.sub(_trim_pattern(eid), r"\1", src[fname])
        if mutated[fname] == src[fname]:
            cases.append((f"#{eid}: nothing to remove - the mutation is vacuous", ["vacuous"], 1))
            continue
        cases.append((f"dropping .trim() on #{eid} is caught", audit(mutated), 1))
    bad = 0
    for label, findings, want in cases:
        ok = (len(findings) == 0) if want == 0 else (len(findings) >= want)
        if not ok:
            bad += 1
        print(f"  {'ok  ' if ok else 'MISS'} {label} (findings={len(findings)})")
    print(f"\nSELFTEST {'FAILED' if bad else 'ok'} - {len(cases) - bad}/{len(cases)}")
    return 1 if bad else 0


def main() -> int:
    findings = audit(_load())
    print("a-pasted-identifier-still-matches - whitespace never decides whether the system works")
    print(f"  identity/matching fields held: {len(IDENTITY_FIELDS)} (free-form notes deliberately exempt)")
    if findings:
        print("\nFAIL - an invisible character can break identity or matching:")
        for f in findings:
            print(f"    {f}")
        return 1
    print("\nPASS - every field where whitespace changes an answer trims what was pasted into it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(selftest() if "--selftest" in sys.argv else main())
