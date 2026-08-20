#!/usr/bin/env python3
"""
validate_safety_field_provenance.py — a safety field must come from its COLUMN, never from prose.

WHY THIS IS A GATE AND NOT A BANK ROW. `PB-logbook-105` asserts "LOTO status is read from the
loto_applied column, never re-derived from a free-text regex". That is a claim about DERIVATION, and
the bank's evidence kinds are live-walk / gate / psql / declared-na — none of which a source reading
satisfies. The honest way to make the row bankable is to write the check that enforces it, so the claim
is re-proved on every run instead of resting on one afternoon's grep.

WHY IT MATTERS MORE THAN MOST DOMAIN TRUTHS. Lock-out/tag-out is the record that a machine was isolated
before someone put their hands in it. Two derivations look identical on screen and are not the same
thing:

  · `entry.loto_applied` — a boolean the worker set, stored, auditable, and defensible to DOLE.
  · `/loto|lock ?out/i.test(entry.action)` — an inference from prose. It says LOTO was applied when the
    action text happens to contain the word, including "LOTO not required", "forgot LOTO", or a note
    ABOUT loto in an unrelated entry. It also says LOTO was NOT applied whenever the worker isolated
    the machine correctly and simply did not write the word.

Both failure directions are dangerous, and the second is worse: an isolation that happened but reads as
absent invites a supervisor to "correct" a record that was already right.

WHAT THIS CHECKS (source-tier, deterministic, no browser):
  1. Every page that RENDERS a safety field reads it from the column.
  2. No page derives a safety field by pattern-matching free text.
Layer 2 is the one with teeth; layer 1 exists so deleting the column read cannot silently pass.

Exit 1 on a real violation, 0 otherwise. A missing page is a FAIL, not a skip — a check that quietly
passes because it found nothing is the shape this platform has been bitten by before.
"""
import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# field -> (column, the WORDS that would indicate a prose derivation of THAT field, pages)
# The words are per-field on purpose: the first version shared one pattern list across every field, so
# a planted LOTO regex was reported twice — once correctly as LOTO, once as "permit appears to be
# derived from free text" on the strength of the word `loto`. A finding that names the wrong field
# sends someone to the wrong line, and is exactly the sloppiness this gate exists to prevent elsewhere.
SAFETY_FIELDS = {
    "LOTO":   ("loto_applied", r"loto|lock\s?out|tag\s?out", ["logbook.html"]),
    "permit": ("permit_reference", r"permit|work\s?permit|hot\s?work", ["logbook.html"]),
}

FREE_TEXT_FIELDS = r"(action|problem|knowledge|root_cause|notes?|text|transcript|description)"


def prose_patterns(words: str):
    """The three shapes a prose derivation takes, bound to ONE field's vocabulary."""
    return [
        re.compile(rf"/[^/\n]{{0,20}}({words})[^/\n]{{0,20}}/[gimsuy]*\s*\.\s*test\s*\(", re.I),
        re.compile(rf"{FREE_TEXT_FIELDS}\s*\)?\s*\.\s*(includes|indexOf|search|match)\s*\(\s*['\"`][^'\"`]*"
                   rf"({words})", re.I),
        re.compile(rf"({words})[^\n]{{0,40}}\.\s*test\s*\(\s*[a-z_$][\w.$]*\.{FREE_TEXT_FIELDS}", re.I),
    ]


def main() -> int:
    failures, checked = [], 0
    print("\n" + "=" * 72)
    print("  SAFETY FIELD PROVENANCE — a safety record comes from its column, never from prose")
    print("=" * 72)

    for label, (column, words, pages) in SAFETY_FIELDS.items():
        for page in pages:
            fp = ROOT / page
            if not fp.exists():
                failures.append(f"{page} is missing — {label} provenance cannot be checked, and a check "
                                f"that passes because it found nothing is worse than no check")
                continue
            src = fp.read_text(encoding="utf-8", errors="replace")
            checked += 1

            reads = len(re.findall(rf"\b{re.escape(column)}\b", src))
            if reads == 0:
                failures.append(f"{page}: no reference to `{column}` at all — {label} is either gone or "
                                f"now derived some other way; both need a human")
            else:
                print(f"  PASS  {page}: {label} read from `{column}` ({reads} references)")

            for pat in prose_patterns(words):
                for m in pat.finditer(src):
                    line = src[:m.start()].count("\n") + 1
                    failures.append(f"{page}:{line}: {label} appears to be DERIVED FROM FREE TEXT — "
                                    f"`{m.group(0)[:70]}`. An isolation record inferred from prose is "
                                    f"true when the word appears (including \"LOTO not required\") and "
                                    f"false whenever a worker isolated the machine and did not write it.")

    print()
    if failures:
        print(f"  {len(failures)} FAILURE(S):")
        for f in failures:
            print(f"    ✗ {f}")
        return 1
    print(f"  PASS — {checked} page/field pair(s): every safety field is read from its column, and no "
          f"page infers one from free text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
