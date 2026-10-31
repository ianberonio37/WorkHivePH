#!/usr/bin/env python3
"""engineering_design_census.py - the engineering design calculator, one calculator at a time (Wave ED, 2026-10-31).

Ian, 2026-10-31: "there are many flops in engineering design calculator, in the guide, you find it and you will see",
then "make necessary and appropriate number of trajectories to add to the roadmap", then "just make appropriate number
of trajectories for overall engineering design."

WHAT THE REGISTRY HAD: 451 rows on engineering-design.html, every one reading it as ONE page (a layer, an action, a
persona). The 52 rows that name a calculator walk its search door (tools/<slug>-calculator/), not the calculator inside
the app, and no row named the Guide tab. The engines are covered elsewhere - validate_calc_formula_accuracy.py holds a
hand-computed oracle for 58/58 calc types. What nobody walks is the PAGE each calculator is: its own form, its own report
renderer, its own guide entry, its own saved shape, its own bill of materials, its own drawing - 55 calculators, each a
separate piece of code a person meets on its own.

THE GUIDE, MEASURED LIVE (2026-10-31, the Playwright MCP, every calculator selected and its form read):
  three built calculators - Transformer Sizing, Harmonic Distortion, Clean Agent Suppression - open a Guide that says
  "No guide available yet ... check back after it is built"; across the other 52, the guide names 75 fields no form
  label matches and the forms carry 141 labels no guide describes (renames among them - the walk decides each one);
  Load Estimation's guide describes System Voltage, Phase Configuration, Power Factor and Demand Factor, none of which
  its form has. On a phone every tip, note and standard is 12.5px at 55% white, an empty formula entry opens a
  three-line hole, and a wrapped formula's continuation reads as the next formula.

THE LENSES - one row per (calculator, lens) the registry does not already hold, plus the guide renderer's own sites:
  G1 the guide tells the truth about this calculator      every built calculator      F CA
  F1 the form refuses what it cannot compute              every built calculator      F CA
  R1 the report reads true, on screen and on paper        every built calculator      F D
  S1 saved, reopened from History, the same calculation   every built calculator      F L
  B1 the bill of materials and scope are this result's    BOM_SOW_SUPPORTED           AV F
  D1 the drawing matches the numbers                      the drawing dispatch        F D
  GR the guide renderer, once for all 55                  a measured site each        F CA
  I1 every value the form sends reaches the engine        census_calc_input_reach.py  F D   (added 2026-10-31)

    python tools/engineering_design_census.py           # the table
    python tools/engineering_design_census.py --json    # the population the seeder reads
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))
import registry_io as _rio  # noqa: E402

PAGE = "engineering-design.html"
JS = ROOT / "engineering-design.js"
PERSONA = "solo-owner"

# key, lens, ask, layers, ufai
CALC_LENSES = [
    ("G1", "the guide tells the truth about this calculator",
     "the Guide tab names exactly the fields this calculator's form carries, describes every one, and its formulas, "
     "constants and standards are the ones the engine (python-api/calcs) and the report use - read at 390 and 1280",
     ["F", "CA"], ["U", "F"]),
    ("F1", "the form refuses what it cannot compute",
     "blank, zero, negative and out-of-range inputs are refused before Calculate with a sentence in crew words that names "
     "the field; every input shows its unit and a sane default; nothing the engine would reject reaches it",
     ["F", "CA"], ["U", "F"]),
    ("R1", "the report reads true, on screen and on paper",
     "every figure in this calculator's report is the engine's value with its unit and the standard clause behind it, the "
     "verdict (size, pass/fail, selection) matches the result card, and the printed/PDF report is whole - no clipped "
     "table, no figure that differs from the screen",
     ["F", "D"], ["U", "F"]),
    ("S1", "saved, reopened from History, the same calculation",
     "save this calculation, reopen it from History: the inputs, every figure and the report are the ones that were "
     "saved - this calculator's stored shape renders through its own renderer, nothing blank or recomputed differently",
     ["F", "L"], ["F", "I"]),
    ("B1", "the bill of materials and scope are this result's",
     "the BOM and SOW generated for this calculation size their items from its results (ratings, quantities, lengths), "
     "name its standard, and survive edit, save and download",
     ["AV", "F"], ["F", "A"]),
    ("D1", "the drawing matches the numbers",
     "the drawing this calculator draws carries the result's values (ratings, sizes, counts) in its labels and title "
     "block, is legible at 390 and 1280, and downloads as the same drawing",
     ["F", "D"], ["U", "F"]),
]
I1_LENS = "every value the form sends reaches the engine"
I1_ASK = ("each value this calculator's form sends is read by its engine and changes the result as the field says - or the "
          "form says plainly that it is recorded on the report only; none is typed and silently ignored")
# the guide renderer's measured sites: key -> lens (named here so the scoreboard reads the same words)
GR_LENSES = {"GR1": "the guide's text is too faint to read", "GR2": "an empty formula entry opens a hole",
             "GR3": "a wrapped formula reads as the next formula"}
GR_ASK = ("the Guide tab's renderer (renderGuide) reads at 390 and 1280 for every calculator: body text meets the page's "
          "contrast floor, a formula block has no holes and a wrapped formula reads as one formula")


def _force_utf8_stdout() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _block(src: str, start: str) -> str:
    """The text of a brace-balanced literal or body that begins at the first `start` - strings are skipped."""
    i = src.index(start)
    j = src.index("{", i)
    depth, k, q = 0, j, None
    while k < len(src):
        ch = src[k]
        if q:
            if ch == "\\":
                k += 2
                continue
            if ch == q:
                q = None
        elif ch == "/" and src[k + 1:k + 2] == "/":
            # a // comment runs to the end of the line - its apostrophes ("the guide's") open no string (2026-10-31)
            nl = src.find("\n", k)
            k = len(src) if nl < 0 else nl
            continue
        elif ch == "/" and src[k + 1:k + 2] == "*":
            end = src.find("*/", k + 2)
            k = len(src) if end < 0 else end + 2
            continue
        elif ch in "'\"`":
            q = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
        k += 1
    raise ValueError(f"unbalanced block at {start!r}")


def calculators(src: str) -> list[str]:
    ui = _block(src, "const CALC_TYPES_UI")
    return [m.group(1) for m in re.finditer(r"\{\s*id:\s*'([^']+)'[^}]*available:\s*true", ui)]


def guides(src: str) -> dict[str, dict]:
    """Each GUIDES entry: its field count, its formula lines, its empty formula entries."""
    g = _block(src, "const GUIDES")
    keys = list(re.finditer(r"^\s{2}'([^']+)':\s*\{", g, re.M))
    out = {}
    for n, m in enumerate(keys):
        body = g[m.end(): keys[n + 1].start() if n + 1 < len(keys) else len(g)]
        fm = re.search(r"formulas:\s*\[(.*?)\]\s*,\s*\n\s*fields:", body, re.S)
        lines = re.findall(r"'((?:[^'\\]|\\.)*)'", fm.group(1)) if fm else []
        out[m.group(1)] = {"fields": len(re.findall(r"\{\s*name:", body)), "formula_lines": len(lines),
                           "empty_formula": sum(1 for x in lines if not x.strip()),
                           "long_formula": sum(1 for x in lines if len(x) > 40)}
    return out


def bom_supported(src: str) -> set[str]:
    b = _block(src, "const BOM_SOW_SUPPORTED")
    return {x for arr in re.findall(r"\[([^\]]*)\]", b) for x in re.findall(r"'([^']+)'", arr)}


def drawn(src: str) -> set[str]:
    """Every calculator the drawing dispatch draws: the PYTHON_DIAGRAM_TYPES set and each `ct === '...'` branch of the
    function that consults it."""
    m = re.search(r"const PYTHON_DIAGRAM_TYPES = new Set\(\[(.*?)\]\)", src, re.S)
    s = set(re.findall(r"'([^']+)'", re.sub(r"//[^\n]*", "", m.group(1)))) if m else set()
    i = src.index("PYTHON_DIAGRAM_TYPES.has(ct)")
    # the NEAREST declaration above it - plain or async (_runDrawing is async; an earlier plain function is not it)
    fn_start = max(src.rfind("\nfunction ", 0, i), src.rfind("\nasync function ", 0, i))
    body = _block(src, src[fn_start + 1: src.index("(", fn_start + 1) + 1])
    return s | set(re.findall(r"ct === '([^']+)'", body))


def guide_renderer(src: str) -> dict:
    body = _block(src, "function renderGuide(")
    return {"faint": len(re.findall(r"rgba\(255,\s*255,\s*255,\s*0\.55\)", body))}


def _covered(rows: list[dict]) -> set[tuple[str, str]]:
    """(key, unit) already held: an ED row, or any in-scope row on this page that names the calculator AND the lens."""
    have = set()
    for x in rows:
        if x.get("status") == "descoped":
            continue
        ed = x.get("ed") or {}
        if ed.get("kind") == "engineering-design":
            have.add((ed.get("key"), ed.get("unit")))
    return have


def census() -> dict:
    src = JS.read_text(encoding="utf-8", errors="ignore")
    calcs, gd, boms, draws, gr = calculators(src), guides(src), bom_supported(src), drawn(src), guide_renderer(src)
    rows = _rio.load_doc()["trajectories"]
    have = _covered(rows)
    cells = []

    def add(key, lens, ask, layers, ufai, unit, detail):
        if (key, unit) in have:
            return
        cells.append({"key": key, "lens": lens, "ask": ask, "unit": unit, "page": PAGE, "persona": PERSONA,
                      "layers": layers, "ufai": ufai, "detail": detail, "page_class": "production"})

    for c in calcs:
        g = gd.get(c)
        for key, lens, ask, layers, ufai in CALC_LENSES:
            if key == "B1" and c not in boms:
                continue
            if key == "D1" and c not in draws:
                continue
            if key == "G1":
                detail = (f"{c} is built and available, and its Guide tab says \"No guide available yet ... check back after "
                          f"it is built\" - there is no GUIDES entry for it" if not g else
                          f"{c}'s guide names {g['fields']} field(s) and {g['formula_lines']} formula line(s); none of it has "
                          f"been read against the form, the engine or the report")
            elif key == "B1":
                detail = f"{c} is in BOM_SOW_SUPPORTED - the generator sizes a bill of materials and a scope from its result"
            elif key == "D1":
                detail = f"{c} is drawn by the drawing dispatch - a schematic labelled from the result"
            else:
                detail = f"{c} has its own form, renderer and stored shape on {PAGE}; no row walks it as its own calculator"
            add(key, lens, ask, layers, ufai, c, detail)

    # I1 - a value the form sends that its engine never reads (2026-10-31, found reading Pump and Pipe Sizing against their
    # engines: the pump's discharge back-pressure never reached TDH). Measured by tools/census_calc_input_reach.py; one row
    # per calculator that sends such a key - a defect site, each key decided on the walk: the engine uses it, or the form
    # says it is recorded only.
    import census_calc_input_reach as cir
    for r in cir.census()["rows"]:
        if r.get("unread") and r["calc"] in calcs:
            add("I1", I1_LENS, I1_ASK, ["F", "D"], ["F"], r["calc"],
                f"{r['calc']}'s form sends {len(r['unread'])} value(s) {r['module']}.py never reads: {', '.join(r['unread'])}")

    empty = sum(v["empty_formula"] for v in gd.values())
    long_ = sum(v["long_formula"] for v in gd.values())
    sites = [
        ("GR1", GR_LENSES["GR1"], "faint",
         f"renderGuide paints {gr['faint']} kinds of text (field tips, notes, standards, subtitle) at rgba(255,255,255,0.55) "
         f"- the page measured 0.6 at 14px as APCA Lc 55, under its floor of 60; these are 0.55 at 12.5px", gr["faint"]),
        ("GR2", GR_LENSES["GR2"], "empty",
         f"{empty} empty formula entr{'y' if empty == 1 else 'ies'} across {sum(1 for v in gd.values() if v['empty_formula'])} "
         f"guides each render as a blank line between two <br>s at line-height 2.1 - a three-line gap inside the card", empty),
        ("GR3", GR_LENSES["GR3"], "wrap",
         f"{long_} formula line(s) are over 40 characters - at 390 they wrap, and the continuation sits at the same indent "
         f"and spacing as the next formula", long_),
    ]
    for key, lens, unit, detail, n in sites:
        if n:
            add(key, lens, GR_ASK, ["F", "CA"], ["U"], "renderGuide:" + unit, detail)

    stale_bom = sorted(boms - set(calcs))
    pop = {"calculators": len(calcs), "with a guide": sum(1 for c in calcs if c in gd),
           "without a guide": sum(1 for c in calcs if c not in gd), "BOM/SOW": len(boms & set(calcs)),
           "drawn": len(draws & set(calcs)), "guide renderer sites": sum(1 for s in sites if s[4])}
    return {"population": pop, "cells": cells, "by_lens": dict(Counter(f"{c['key']} {c['lens']}" for c in cells)),
            "total": len(cells), "no_guide": [c for c in calcs if c not in gd], "stale_bom": stale_bom}


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    c = census()
    if a.json:
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return 0
    print("ENGINEERING DESIGN, one calculator at a time - " + " · ".join(f"{k} {v}" for k, v in c["population"].items()))
    for k, v in c["by_lens"].items():
        print(f"  {k:<62} {v:>4}")
    print(f"  {'= empty cells (rows owed)':<62} {c['total']:>4}")
    if c["no_guide"]:
        print("  built with no guide: " + "; ".join(c["no_guide"]))
    if c["stale_bom"]:
        print("  BOM_SOW_SUPPORTED names a calculator that no longer exists: " + "; ".join(c["stale_bom"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
