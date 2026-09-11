#!/usr/bin/env python3
"""check_calc_citations.py — W3-CL Internal Control: can an engineer look up the constant behind the number?

An engineering calculator's output goes into a drawing, so it owes a citation somebody can open. Every one of
these 60 pages prints a labelled line — `… standard: ASME BPVC Sec. VIII Div.1 | ASME Sec. II Part D | DOLE
OSHS PD 856.` — inside a single `<small>` element. That line is the page's own structured statement of what
it was computed against, and this gate reads it.

★SIX PASSES OVER ONE QUESTION. Five of them measured the instrument, and each looked correct while it stood.
Kept in full, because the sequence is the lesson:

  1. "60/60 name a standard AND a clause."  The clause pattern allowed a letter after the keyword, so the
     HTML TAG NAMES `<section a…`, `<article c…` and the words "table t" scored as citations. Right answer,
     wrong reason — and a LIVE browser read of the rendered text, finding no clause where this found sixty,
     is what exposed it. When two instruments disagree, the disagreement is the finding.
  2. "11/60 name a clause."  Corrected to demand a digit — then over-corrected into demanding the literal
     words Table or Section, which is my vocabulary. This platform writes `ISO 22400-2`, `PEC 2017 Art. 4.50`,
     `CTI STD-201`: each names the exact part an engineer opens, and none says "Table".
  3. "60/60 cite specifically."  The family list carried bare two-letter alternatives (EN, UL) with no word
     boundary, so the pattern matched inside `min-height: 44px; padding: 12px` — a CSS block on every page.
     A clean sweep manufactured by matching a stylesheet. ★AN IMPOSSIBLY CLEAN NUMBER IS THE PROBE, NOT THE
     PRODUCT: it was the third suspiciously perfect answer and the first two were already known to be wrong.
  4. "54/60, six cite nothing."  Word boundaries fixed and stylesheets stripped, but the window between the
     family name and its number excluded periods — so `NSCP Vol.2` and `TEMA 10th Ed.` could never match —
     and the family list had never heard of CIBSE, TEMA or IPC. Six correct pages accused.
  5. "56 specific, 4 bare."  Read the generator's `standard` FIELD instead of the page. Deterministic, and
     still wrong: the comment beside that field says "fallback if calc doesn't return one", and I read past
     it. The page composes its citation from the CALCULATOR MODULE and uses that field only when the module
     returns nothing — so three of the four "bare" pages were never bare. `lighting-design` declares
     "IESNA | PGBC" and PRINTS "IESNA 10th Ed. | IES RP-1/7/28 | ASHRAE 90.1-2019 | PEC 2017".
     ★A FIELD NAMED FOR THE THING IS NOT ALWAYS THE THING. Read the comment beside it.
  6. This one. Read the labelled line the page itself prints, bounded by its `<small>` element rather than by
     a period — because `ASME BPVC Sec. VIII` contains the same period-space that ends the line, and pass 6's
     first draft truncated it to "ASME BPVC Sec" and called the page bare. The boundary of a structured value
     is its TAG, never its punctuation.
"""
from __future__ import annotations

import glob
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# the labelled line, bounded by the element that holds it
SMALL = re.compile(r"<small\b[^>]*>(.*?)</small>", re.I | re.S)
LABEL = re.compile(r"standard:\s*(.+?)\s*\.?\s*$", re.I | re.S)
TAGS = re.compile(r"<[^>]+>")

# specific = carries the part that identifies it: an edition year, a part number, an article, or a
# Roman-numeral section (ASME BPVC Sec. VIII names a part as precisely as ASME B31.1)
SPECIFIC = re.compile(r"[0-9]|\b(?:sec\.?|section|part|vol\.?|volume|ch\.?|chapter|div\.?)\s*[IVXL]+\b", re.I)


def standard_line(path: Path) -> str:
    """The page's own `standard:` line, read from the element that carries it."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    for m in SMALL.finditer(raw):
        inner = re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", m.group(1)))).strip()
        hit = LABEL.search(inner)
        if hit:
            return hit.group(1).strip().rstrip(".").strip()
    return ""


def pages():
    """Staged first — promotion to tools/ is Ian's gate, so staging is the generator's honest current output."""
    staged = ROOT / "seo_assets" / "calc_pages_staging"
    base = staged if staged.exists() else ROOT / "tools"
    return sorted(glob.glob(str(base / "*" / "index.html"))), base.name


def self_test() -> int:
    """★A GATE THAT READS 58/60 MUST BE MADE TO FAIL BEFORE THAT NUMBER MEANS ANYTHING.

    Five earlier passes produced confident numbers that were measuring the instrument, so these mutations are
    exactly the mistakes each pass made.
    """
    fails = []
    if SPECIFIC.search("IESNA"):
        fails.append("a bare family name 'IESNA' reads as specific")
    if SPECIFIC.search("DPWH Blue Book"):
        fails.append("'DPWH Blue Book' - a book with no edition - reads as specific")
    if not SPECIFIC.search("ASME BPVC Sec. VIII Div.1"):
        fails.append("a Roman-numeral part 'Sec. VIII' reads as bare")
    if not SPECIFIC.search("NSCP 2015"):
        fails.append("'NSCP 2015' does not read as specific")
    # the element boundary, not the punctuation: internal ". " must not truncate the line
    sample = "<p><small>Computed live; standard: ASME BPVC Sec. VIII Div.1 | ASME Sec. II Part D.</small></p>"
    got = ""
    for m in SMALL.finditer(sample):
        inner = re.sub(r"\s+", " ", html.unescape(TAGS.sub(" ", m.group(1)))).strip()
        hit = LABEL.search(inner)
        if hit:
            got = hit.group(1).strip().rstrip(".").strip()
    if "Part D" not in got:
        fails.append(f"an internal '. ' truncates the line: got {got!r}")
    if "Computed live" in got:
        fails.append("the label is not being stripped from the value")
    print("FAIL calc-citations self-test - " + "; ".join(fails) if fails
          else "self-test OK: 6 mutations, each caught - the gate can fail, so its number is a reading")
    return 1 if fails else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    files, where = pages()
    bare, none, ok = [], [], []
    for f in files:
        slug = Path(f).parent.name
        line = standard_line(Path(f))
        if not line:
            none.append((slug, ""))
        elif any(SPECIFIC.search(p) for p in line.split("|")):
            ok.append((slug, line))
        else:
            bare.append((slug, line))

    # ★PUBLISH WHAT EACH PAGE MUST SHOW, SO THE BROWSER LENS STOPS GUESSING. The live lens kept its own copy
    # of the clause pattern and went on asking the refuted question after this gate was corrected - one
    # instrument fixed, its twin still wrong, which is how forty pages were accused of naming no clause while
    # citing ASHRAE 62.1. Neither should own a pattern: this gate reads the page's own standard line and
    # writes down the token each page owes its reader; the browser checks only that the reader can see it.
    # Read from STAGING deliberately - a token taken from the live page would always be found there, and a
    # check that cannot fail is not a check. Against staging it catches exactly the promotion gap.
    # ★AND THE NEEDLE IS THE WHOLE CITATION, NOT ITS NUMBER. A first version published the digit-bearing
    # token alone - "10th", "2015", "62.1" - and 25 of the 60 needles were four characters or fewer. A page
    # can contain "2015" for a hundred reasons that have nothing to do with citing DPWH DGCS 2015, so that
    # check would pass by accident and read as evidence. The family name and its number together are what
    # makes a citation findable, so that whole phrase is the needle.
    tokens = {}
    for slug, line in ok + bare:
        first = next((p.strip() for p in line.split("|") if SPECIFIC.search(p)), line)
        tokens[slug] = {"declared": line, "must_show": re.sub(r"\s+", " ", first).strip().lower()}
    (ROOT / ".tmp").mkdir(exist_ok=True)
    (ROOT / ".tmp" / "calc_declared_standards.json").write_text(json.dumps(tokens, indent=1), encoding="utf-8")

    print(f"calculators: {len(files)}  (read from {where})")
    print(f"  the page's own standard line names an edition or part: {len(ok)}")
    print(f"  it names only bare family names:                       {len(bare)}")
    print(f"  no standard line at all:                               {len(none)}")
    for slug, line in bare:
        print(f"     bare: {slug:34} {line[:64]}")
    for slug, _ in none:
        print(f"     no standard line: {slug}")
    if bare:
        print(f"\n  {len(bare)} calculator(s) name a body without the edition or part inside it. An engineer")
        print("  checking a constant against \"DPWH Blue Book\" has a library; against \"DPWH DGCS 2015\" they")
        print("  have a page. That is a real Internal-Control backlog for W3-CL rather than a wrong number, so")
        print("  this gate FAILS only on a page that prints no standard line at all.")
    return 1 if none else 0


if __name__ == "__main__":
    raise SystemExit(main())
