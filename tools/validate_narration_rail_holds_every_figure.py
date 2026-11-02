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

★A REAL NUMBER UNDER THE WRONG NAME (ED R1, 2026-11-02): the V-belt narrative called the 7.5 kW the engineer typed
"the design power" - it is 9.0 kW, rated x service factor. 7.5 is a genuine input, so a rail that asks "does this
number exist?" passes it. namedFigureMismatch asks the other question: a section that names a design_<quantity>
result must quote THAT result. It is RUN here (node) against fixed cases, not pattern-matched, and the gate checks it
is applied to all three report sections, where a misnamed figure is dropped for the report's own text.

Usage: python tools/validate_narration_rail_holds_every_figure.py
"""
import json
import re
import shutil
import subprocess
import sys
import io
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
FN = ROOT / "supabase" / "functions" / "engineering-calc-agent" / "index.ts"


# (text, expected mismatch) against results {design_power_kW: 9.0, rated_power_kW: 7.5, design_flow_lpm: 1234.5}
NAMED_CASES = [
    ("To design a V-belt drive transmitting a design power of 7.5 kW from a 1450 rpm motor.", True),
    ("The design power is 9.0 kW (7.5 kW rated x 1.2 service factor).", False),
    ("The design power of 9 kW is carried by 3 belts.", False),
    ("Rated power 7.5 kW; design power 9.00 kW.", False),
    ("A design flow of 1,234.5 L/min is used.", False),
    ("A design flow of 1,500 L/min is used.", True),
    ("No design figures are named here; a 7.5 kW motor.", False),
]


def named_figure_fails(src: str) -> list[str]:
    body = re.search(r"function namedFigureMismatch\([\s\S]*?\n\}\n", src)
    if not body:
        return ["namedFigureMismatch is gone - a section can call the typed 7.5 kW 'the design power' and ship"]
    out = []
    if not re.search(r'for \(const f of \["objective", "assumptions", "recommendations"\]\)[\s\S]{0,120}'
                     r'namedFigureMismatch\(', src):
        out.append("namedFigureMismatch is not applied to objective, assumptions and recommendations")
    node = shutil.which("node")
    if not node:
        return out + ["node is not on PATH, so namedFigureMismatch could not be run against its cases"]
    js = (body.group(0).replace("(text: string, results: Record<string, unknown>): boolean", "(text, results)")
          + "\nconst r = {design_power_kW: 9.0, rated_power_kW: 7.5, design_flow_lpm: 1234.5};"
          + "\nconst cases = " + json.dumps(NAMED_CASES) + ";"
          + "\nconsole.log(JSON.stringify(cases.map(([t]) => namedFigureMismatch(t, r))));")
    res = subprocess.run([node, "-e", js], capture_output=True, text=True, encoding="utf-8", timeout=60)
    try:
        got = json.loads(res.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return out + [f"namedFigureMismatch did not run: {(res.stderr or res.stdout)[:200]}"]
    for (text, want), g in zip(NAMED_CASES, got):
        if g != want:
            out.append(f"namedFigureMismatch({text[:60]!r}) = {g}, expected {want}")
    return out


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

    fails += named_figure_fails(src)

    if fails:
        print(f"FAIL narration-rail-holds-every-figure - {len(fails)} problem(s):")
        for x in fails:
            print("    - " + x)
        print("    The spoken line is the headline an engineer hears. Every figure in it needs a source,")
        print("    and the exemptions exist so honest narrations are not muted.")
        return 1

    print("PASS narration-rail-holds-every-figure - every quoted figure must trace to a computed result "
          f"or a named exemption, and a named design figure must be that figure ({len(NAMED_CASES)} cases run).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
