#!/usr/bin/env python3
"""counted-noun-ratchet — T131: software that cannot count to one (2026-08-26).

"1 entries found". "1 assets". "1 parts". Individually trivial, collectively the
thing that makes a product feel unfinished — and n=1 is not an edge case on this
platform, it is what a filtered list shows the moment a search gets specific.

WHAT IS COUNTED: a count interpolated straight into a plural noun with NO
singular branch anywhere near it. The count must be one that can GENUINELY be 1 —
a `.length`, a `*Count`, a `*_count`, a `*Total`. Deliberately NOT things like
`${period} days`, which is 30/60/90 by construction and never reads "1 days":
a census padded with cases that cannot occur produces a number nobody trusts and
a gate everyone learns to ignore. The first pass of this measurement counted 82
that way; the honest figure is 30.

★ZERO IS NOT THE GOAL, and this ratchet must not be read as demanding it. The
sites are spread across 13 files, most on secondary or admin surfaces, and
rewriting all of them in one sweep would be a large unreviewed change to render
paths for a grammar nit. What was FIXED is the one a worker meets daily — the
counter under the logbook's search box, which said "1 entries found" the moment
a search narrowed to a single result. What must not happen is the number GROWING.

The idiom to use is the platform's own, already present in several files:
`${n} asset${n === 1 ? '' : 's'}` — no helper, no new dependency, reads like the
code around it.

Usage: python tools/validate_counted_noun_ratchet.py
"""
import glob
import io
import json
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / "tools" / "counted_noun_baseline.json"

COUNTABLE = re.compile(
    r"\$\{([A-Za-z_][\w.]*(?:\.length|Count|_count|Total|[Nn]um)[\w.]*|\w*(?:count|len)\w*)\}\s+([a-z]{3,14}s)\b")
SINGULAR_NEAR = re.compile(
    r"===\s*1\s*\?|==\s*1\s*\?|length\s*===\s*1|whPlural|pluralize|\?\s*['\"][^'\"]{0,24}['\"]\s*:")
NOT_NOUNS = {"https", "always", "was"}

# ★THIS RULE IS ENGLISH-ONLY, AND FILIPINO HAS WORDS THAT END IN "s" (2026-09-11). COUNTABLE requires a
# noun matching [a-z]{3,14}s, on the assumption that a trailing "s" is an English plural. Filipino does
# not inflect nouns for number - "1 bukas na item" and "6 bukas na item" are both correct, and adding an
# English-style plural would be WRONG - so `${carryCount} bukas na item` (shift-brain, "open items
# carried forward") was flagged as a page that cannot count to one. It is the THIRD instrument today
# whose rule was written for English and met Filipino text: B3's readability grade keyed on the reader's
# preference, J1/Z3's destructive-control vocabulary, and now this.
# The test must be on the ENCLOSING STRING LITERAL, never the line: a _t('… 5 parts …', '… 5 parts …')
# call puts both languages on one line, and a line-level check would mask a real English offence sitting
# beside its translation. [[feedback_an_oracles_vocabulary_is_part_of_the_oracle]]
FIL_MARKER = re.compile(r"\b(ang|ng|mga|sa|para|hindi|walang|wala|kang|mo|ito|iyon|kapag|nang|ay|na)\b", re.I)


def _enclosing_literal(line: str, pos: int) -> str:
    """The quote-delimited string the match at `pos` sits inside ('' when it is not inside one)."""
    for q in ("`", "'", '"'):
        starts = [i for i, ch in enumerate(line) if ch == q and (i == 0 or line[i - 1] != "\\")]
        for a, b in zip(starts[0::2], starts[1::2]):
            if a < pos < b:
                return line[a + 1:b]
    return ""


def scan():
    hits = []
    for f in sorted(glob.glob(str(ROOT / "*.html"))):
        lines = io.open(f, encoding="utf-8", errors="replace").read().splitlines()
        for i, line in enumerate(lines):
            for m in COUNTABLE.finditer(line):
                if m.group(2) in NOT_NOUNS:
                    continue
                lit = _enclosing_literal(line, m.start())
                if lit and FIL_MARKER.search(lit):
                    continue          # Filipino prose: this rule does not apply to it
                if SINGULAR_NEAR.search("\n".join(lines[max(0, i - 2): i + 3])):
                    continue
                hits.append((Path(f).name, i + 1, m.group(0).strip()[:46]))
    return hits


def main() -> int:
    hits = scan()
    n = len(hits)
    per_file = {}
    for f, _, _ in hits:
        per_file[f] = per_file.get(f, 0) + 1
    for f, c in sorted(per_file.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {f}: {c}")

    if not BASELINE.exists():
        BASELINE.write_text(json.dumps({"count": n, "established": "2026-08-26"}, indent=1), encoding="utf-8")
        print(f"BASELINE established: {n} counted nouns with no singular branch (forward-only)")
        return 0

    base = json.loads(BASELINE.read_text(encoding="utf-8")).get("count", n)
    if n > base:
        print(f"FAIL counted-noun-ratchet — grew {base} -> {n}. New sites:")
        for f, ln, txt in hits[-5:]:
            print(f"    {f}:{ln}  {txt}")
        print("    Use the platform's own idiom: `${n} entr${n === 1 ? 'y' : 'ies'}`.")
        return 1
    if n < base:
        BASELINE.write_text(json.dumps({"count": n, "ratcheted": "auto"}, indent=1), encoding="utf-8")
        print(f"PASS counted-noun-ratchet — improved {base} -> {n}; ratchet lowered.")
        return 0
    print(f"PASS counted-noun-ratchet — held at {n} (baseline {base}). Zero is not the goal; growth is "
          f"the failure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
