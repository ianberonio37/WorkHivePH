"""report-grids-reflow - a report's fixed multi-column grid must collapse on a phone (2026-11-02).

The engineering reports are HTML templates in engineering-design.js, and many lay out their signature row or their
summary tiles with an INLINE grid: `display:grid;grid-template-columns:1fr 1fr 1fr`. An inline style beats every
stylesheet rule that lacks !important, and a `1fr` track never shrinks below its content's minimum width, so on a
390 px phone three columns of letter-spaced labels push the page sideways:
  - the STP report and 17 others (signature rows; fixed earlier with `.sig-block` + an !important 640 px rule);
  - UPS, PFC, Cable Tray, Duct, Refrigerant Pipe and AHU signature rows that never carried `.sig-block` - UPS ran to
    403 px at 390;
  - AHU's summary tiles (`repeat(3,1fr)`), which ran to 402 px once its fan-power tile read "0.643 W/L·s (max 1.7)".

ASSERTION: inside every report renderer (function render...Report), an inline grid of three or more fixed columns
carries a class that a 640 px rule collapses (`sig-block` -> one column, `res-tiles` -> two shrinkable columns), and
engineering-design.html still holds both rules with !important (which is what lets a class rule beat the inline style).

    python tools/validate_report_grids_reflow.py
    python tools/validate_report_grids_reflow.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "engineering-design.js"
HTML = ROOT / "engineering-design.html"
COLLAPSING = ("sig-block", "res-tiles")
GRID = re.compile(r"<div\b([^>]*?)style=\"[^\"]*display:\s*grid;\s*grid-template-columns:\s*"
                  r"(1fr(?:\s+1fr){2,}|repeat\(\s*[3-9]\s*,\s*1fr\s*\))[^\"]*\"")
FUNC = re.compile(r"^\s*(?:async\s+)?function\s+(\w+)\s*\(", re.M)
RULES = [
    re.compile(r"@media\s*\(max-width:\s*640px\)\s*\{\s*#report-panel\s+\.sig-block\s*\{[^}]*grid-template-columns:\s*1fr\s*!important"),
    re.compile(r"@media\s*\(max-width:\s*640px\)\s*\{\s*#report-panel\s+\.res-tiles\s*\{[^}]*grid-template-columns:[^;}]*minmax\(0,\s*1fr\)[^;}]*!important"),
]


def offenders(js: str) -> list[str]:
    funcs = [(m.start(), m.group(1)) for m in FUNC.finditer(js)]
    out = []
    for m in GRID.finditer(js):
        name = next((n for s, n in reversed(funcs) if s < m.start()), "")
        if not re.match(r"render\w*Report$", name):
            continue
        cls = re.search(r'class="([^"]*)"', m.group(1))
        if not cls or not any(c in cls.group(1).split() for c in COLLAPSING):
            line = js.count("\n", 0, m.start()) + 1
            out.append(f"{name} (engineering-design.js:{line}): grid-template-columns {m.group(2)} with no "
                       f"{' / '.join(COLLAPSING)} class")
    return out


def missing_rules(html: str) -> list[str]:
    names = ["the 640 px .sig-block -> 1fr !important rule", "the 640 px .res-tiles -> minmax(0, 1fr) !important rule"]
    return [n for n, r in zip(names, RULES) if not r.search(html)]


def check(js: str, html: str) -> list[str]:
    return offenders(js) + [f"engineering-design.html lacks {x}" for x in missing_rules(html)]


def main() -> int:
    js, html = JS.read_text(encoding="utf-8"), HTML.read_text(encoding="utf-8")
    if "--self-test" in sys.argv:
        planted = js + '\nfunction renderPlantedReport(inputs, r) {\n  return `<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem;"></div>`;\n}\n'
        a, b = check(planted, html), check(js, html.replace("#report-panel .res-tiles", "#report-panel .res-tile"))
        ok = any("renderPlantedReport" in x for x in a) and any(".res-tiles" in x for x in b)
        print(("PASS" if ok else "FAIL") + " report-grids-reflow --self-test: a planted unclassed grid and a removed rule "
              + ("are both caught" if ok else "were NOT both caught"))
        return 0 if ok else 1
    fails = check(js, html)
    if fails:
        print(f"FAIL report-grids-reflow - {len(fails)} problem(s):")
        for f in fails:
            print("    - " + f)
        print("    An inline grid of fixed 1fr columns keeps its content's minimum width on a 390 px phone and pushes")
        print("    the page sideways; give it the sig-block or res-tiles class so the 640 px rule collapses it.")
        return 1
    n = sum(1 for m in GRID.finditer(js))
    print(f"PASS report-grids-reflow - every fixed multi-column report grid ({n} found) collapses on a phone, and both "
          "640 px rules hold.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
