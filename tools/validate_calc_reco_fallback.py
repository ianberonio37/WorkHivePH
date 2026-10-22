"""validate_calc_reco_fallback.py - ENH-P (2026-10-23): when no model answers, a calculator's report still says what to
buy or do.

The engine (engineering-calc-agent) writes its own advice for 40 calculator types when every model is busy, and for the
rest one generic sentence: "Refer to the results summary table for specific design values...". 45 report renderers carry
calculator-specific advice for exactly that case (`narrative?.recommendations || ...`), but the generic sentence is never
empty, so it pre-empted all of it: Fluid Power's "Specify cylinder", Heat Exchanger's "Specify TEMA class", Vibration's
remedies and 11 more never showed. The ENH-P walk read the generic sentence on all four calculators it re-checked.
engineering-design.js now reads that sentence as no advice (edNarrative) wherever a report is drawn.

  R1  the page's ED_GENERIC_RECO matches the engine's generic sentence, read from the engine's own source - if the
      engine's wording changes, the page must change with it;
  R2  both places a report is drawn pass the narrative through edNarrative: _renderComputed (a Run, a shared link)
      and viewHistoryReport (a saved report), before the report reads it;
  R3  no renderer prints a bare "Recommendations:" with nothing after it (narrative.recommendations||'').

  python tools/validate_calc_reco_fallback.py
  python tools/validate_calc_reco_fallback.py --self-test   (the files as they are pass; four weakened copies fail)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "engineering-design.js"
ENGINE = ROOT / "supabase" / "functions" / "engineering-calc-agent" / "index.ts"


def _fn(js: str, name: str) -> str:
    m = re.search(r"^function\s+" + re.escape(name) + r"\s*\(", js, re.M)
    if not m:
        return ""
    nxt = re.search(r"^(?:async\s+)?function\s+\w+\s*\(", js[m.end():], re.M)
    return js[m.start(): m.end() + (nxt.start() if nxt else len(js))]


def check(js: str, ts: str) -> list[str]:
    bad = []
    lit = re.search(r'let recommendations = "([^"]+)";', ts)
    pat = re.search(r"const ED_GENERIC_RECO = /(.+?)/;", js)
    if not lit:
        bad.append("R1 the engine's generic recommendation sentence was not found - the check lost its anchor")
    elif not pat:
        bad.append("R1 the page has no ED_GENERIC_RECO, so the engine's generic sentence hides every report's own advice")
    elif not re.search(pat.group(1).replace("\\b", r"\b"), lit.group(1)):
        bad.append("R1 ED_GENERIC_RECO no longer matches the engine's generic sentence: " + lit.group(1)[:80])
    rc = _fn(js, "_renderComputed")
    at_norm, at_last = rc.find("edNarrative(data.narrative)"), rc.find("_lastNarrative =")
    if at_norm < 0 or at_last < 0 or at_norm > at_last:
        bad.append("R2 _renderComputed draws a Run or a shared link without edNarrative - the generic sentence wins")
    vh = _fn(js, "viewHistoryReport")
    if "edNarrative(row.narrative)" not in vh or vh.find("edNarrative(row.narrative)") > vh.find("_lastNarrative"):
        bad.append("R2 viewHistoryReport draws a saved report without edNarrative - the generic sentence wins")
    if "ED_GENERIC_RECO.test(" not in _fn(js, "edNarrative"):
        bad.append("R2 edNarrative no longer tests the generic sentence")
    n = len(re.findall(r"<strong>Recommendations:</strong>\s*\$\{escHtml\(narrative\.recommendations\s*\|\|\s*''\)\}", js))
    if n:
        bad.append(f"R3 {n} renderer(s) print a bare 'Recommendations:' with nothing after it when there is no advice")
    return bad


def main() -> int:
    js, ts = JS.read_text(encoding="utf-8"), ENGINE.read_text(encoding="utf-8")
    bad = check(js, ts)
    if bad:
        print("FAIL calc-reco-fallback:")
        for b in bad:
            print("  -", b)
        return 1
    print("PASS calc-reco-fallback - the engine's generic sentence reads as no advice wherever a report is drawn (a Run, "
          "a shared link, a saved report), so each renderer's own advice shows; no bare 'Recommendations:' line")
    return 0


def self_test() -> int:
    js, ts = JS.read_text(encoding="utf-8"), ENGINE.read_text(encoding="utf-8")
    fails = []
    if check(js, ts):
        fails.append("the files as they are should PASS: " + "; ".join(check(js, ts)))
    mutants = [
        ("a Run without the normaliser", js.replace("  data = Object.assign({}, data, { narrative: edNarrative(data.narrative) });\n", ""), ts, "R2"),
        ("a saved report without it", js.replace("edNarrative(row.narrative)", "row.narrative"), ts, "R2"),
        ("the engine reworded", js, ts.replace('let recommendations = "Refer to the results summary table',
                                               'let recommendations = "See the results table'), "R1"),
        ("a bare Recommendations line", js.replace(
            "${narrative.recommendations ? `<p><strong>Recommendations:</strong> ${escHtml(narrative.recommendations)}</p>` : ''}",
            "<p><strong>Recommendations:</strong> ${escHtml(narrative.recommendations||'')}</p>", 1), ts, "R3"),
    ]
    for name, mjs, mts, want in mutants:
        if mjs == js and mts == ts:
            fails.append(f"mutant '{name}' did not apply - its anchor moved")
            continue
        got = check(mjs, mts)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' should fail {want}, got {got[:2]}")
    if fails:
        print("SELF-TEST FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print(f"PASS calc-reco-fallback self-test - the files pass; {len(mutants)} weakened copies fail their check")
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(self_test() if "--self-test" in sys.argv else main())
