#!/usr/bin/env python3
"""ai-draft-shows-its-basis - T80: an AI draft a human must approve says what it read.

fmea-populator reads a year of corrective logbook entries, clusters them by root cause, and
writes suggested failure modes to rcm_fmea_modes with source='ai_logbook' and approved_at NULL.
An engineer then approves them, and approval is what makes a mode count in v_fmea_truth and
drive maintenance strategy.

FOUND 2026-08-26: the row announced itself honestly - a "from AI logbook scan" pill and a
confidence badge, provenance done properly - and said NOTHING about what it read. The engineer
was asked to approve a failure mode with no way to check the claim, on a screen whose output
shapes how a machine gets maintained. The function held the exact cluster and simply never
recorded it; the `notes` column existed and sat unused. Confirmed in the fixture: a live
ai_logbook row ("Lip seal leaking", 0.552 confidence) with notes NULL.

Same lesson AH15 learned about citations: the one thing a citation is FOR is letting a reader
verify. Written as the window and root cause a person can filter the logbook by, not raw uuids,
which nobody can check by reading.

★IT CHECKS BOTH HALVES, because a basis that is written but never rendered helps no one, and a
render with nothing to show is a blank line. The AI6 pair: stamped at the WRITE, visible at the
READ.

★AND ONLY FOR DRAFTS AWAITING A HUMAN. A mode an engineer wrote themselves needs no such note;
the point is not provenance theatre, it is that whoever is asked to APPROVE can check.

Usage: python tools/validate_ai_draft_shows_its_basis.py
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
WRITER = ROOT / "supabase" / "functions" / "fmea-populator" / "index.ts"
READER = ROOT / "asset-hub.html"


def strip_comments(src: str) -> str:
    def blank(m):
        return "".join(c if c == "\n" else " " for c in m.group(0))
    s = re.sub(r"<!--.*?-->", blank, src, flags=re.S)
    # (?!quote): accept="image/*" is NOT a comment opener
    s = re.sub(r"/\*(?![\"']).*?\*/", blank, s, flags=re.S)
    return re.sub(r"(?m)^[ \t]*//[^\n]*$", blank, s)


def main() -> int:
    if not WRITER.exists() or not READER.exists():
        print("SKIP ai-draft-shows-its-basis - fmea-populator or asset-hub not present")
        return 0

    w = strip_comments(WRITER.read_text(encoding="utf-8", errors="replace"))
    r = strip_comments(READER.read_text(encoding="utf-8", errors="replace"))
    fails = []

    # WRITE: the row the engineer will approve carries a basis
    if not re.search(r"source:\s*[\"']ai_logbook[\"']", w):
        print("SKIP ai-draft-shows-its-basis - the populator no longer stamps source='ai_logbook'")
        return 0
    if not re.search(r"notes:\s*\w+\(", w):
        fails.append("fmea-populator inserts an ai_logbook row without a notes basis - the engineer "
                     "is asked to approve a failure mode with nothing to check it against")
    elif not re.search(r"function\s+fmeaGroundingNote[^{]*\{(?:[^{}]|\{[^{}]*\})*root cause", w, re.S):
        fails.append("the basis is written but does not name the cluster (count / root cause / window) - "
                     "an engineer cannot pull up 'some entries' in the logbook")

    # READ: it reaches the person doing the approving
    if not re.search(r"\.select\([^)]*\bnotes\b[^)]*rcm|rcm[^)]*\.select\([^)]*\bnotes\b", r, re.S) \
       and not re.search(r"select\(\s*['\"][^'\"]*\bnotes\b[^'\"]*['\"]\s*\)", r):
        fails.append("asset-hub does not select notes, so the basis never leaves the database")
    elif not re.search(r"source[^;\n]{0,60}startsWith\(\s*['\"]ai_['\"]\s*\)[^;\n]{0,60}\.notes", r):
        fails.append("asset-hub selects notes but never renders it on AI-sourced rows - a basis "
                     "nobody sees is the same as no basis")

    if fails:
        print(f"FAIL ai-draft-shows-its-basis - {len(fails)} half/halves of the pair broken:")
        for x in fails:
            print("    - " + x)
        print("    Approval is what makes an AI-drafted mode count in v_fmea_truth and shape how a")
        print("    machine gets maintained. Whoever is asked to approve has to be able to check it.")
        return 1

    print("PASS ai-draft-shows-its-basis - AI-drafted failure modes record the cluster they came from, "
          "and it is shown to the engineer being asked to approve them.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
