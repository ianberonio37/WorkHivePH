"""narration-rail-holds-every-figure - T83: a rail that accepts one true number accepts the lie
beside it (2026-08-26).

engineering-calc-agent computes a design deterministically, then asks a model for a report
narrative plus a spoken `narration` that must "quote the single headline design value verbatim".
A rail already existed to protect that, with the comment: "AI-1 grounding rail: silence the spoken
line if it quotes an unverifiable figure."

★THE RAIL CHECKED THE OPPOSITE OF ITS OWN COMMENT. It was `nums.some(...)` - it passed as soon as
ONE number in the narration matched a computed result. So "Provide a 61 kW unit at 45.2 kW bus"
passed on the 45.2 while the 61 was invented, and the invented number is the one SPOKEN as the
headline, on a calculation an engineer signs. Measured against pre-fix HEAD: that narration
returned true. It now returns false, and pure fabrication is still caught, so this is a strict
tightening rather than a rewrite.

★`every` ALONE WOULD HAVE BEEN ITS OWN FAILURE. A rail that mutes honest narrations teaches people
to ignore it. Narrations legitimately carry figures that are not results: the INPUTS they were
computed from, small counts ("2 units"), and standard designations ("IEC 62305-3", "PEC 2017").
Those are exempted by name; everything else must match a computed value within tolerance, and at
least one must be a real RESULT so that merely echoing the inputs does not count as quoting the
answer. Seven cases were exercised against the shipped function, including each exemption.

THE ASSERTION: the rail holds EVERY quoted figure to a source, and receives the inputs it needs to
recognise a typed value.

Usage: python tools/validate_narration_rail_holds_every_figure.py
"""
import re
import sys
import io
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "engineering-calc-agent" / "index.ts"


def main() -> int:
    if not FN.exists():
        print("SKIP narration-rail-holds-every-figure - engineering-calc-agent not present")
        return 0

    src = FN.read_text(encoding="utf-8", errors="replace")
    body = re.search(r"function narrationQuotesResult\([\s\S]*?\n\}", src)
    if not body:
        print("FAIL narration-rail-holds-every-figure - the grounding rail is gone entirely; the spoken "
              "headline would be whatever the model said.")
        return 1
    b = body.group(0)
    fails = []

    if re.search(r"return\s+nums\.some\s*\(", b):
        fails.append("the rail returns nums.some(...) - it passes as soon as ONE quoted number matches, "
                     "so a fabricated headline rides along beside a real figure")
    if "return false" not in b:
        fails.append("no quoted figure is ever rejected - the rail cannot refuse anything")
    if not re.search(r"inputs", b):
        fails.append("the rail never sees the inputs, so a value the engineer typed reads as an "
                     "invention and honest narrations get silenced")
    if not re.search(r"NFPA|IEC|ASHRAE", b):
        fails.append("standard designations are not exempted, so 'IEC 62305-3' counts as a fabricated "
                     "figure and the rail mutes correct narrations")
    if not re.search(r"narrationQuotesResult\(parsed\.narration,\s*results,\s*inputs\)", src):
        fails.append("the call site does not pass inputs, so the exemption above cannot apply")

    if fails:
        print(f"FAIL narration-rail-holds-every-figure - {len(fails)} problem(s):")
        for x in fails:
            print("    - " + x)
        print("    The spoken line is the headline an engineer hears. Every figure in it needs a source,")
        print("    and the exemptions exist so honest narrations are not muted.")
        return 1

    print("PASS narration-rail-holds-every-figure - every quoted figure must trace to a computed result "
          "or a named exemption.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
