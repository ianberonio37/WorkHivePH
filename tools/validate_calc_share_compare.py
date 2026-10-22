"""validate_calc_share_compare.py - ENH-P (2026-10-23): a calculation can be shared by link and kept as scenario A,
in the calculator every tools/<slug>/ page opens (engineering-design.html?calc=<slug>).

What a unit test cannot see is the wiring, so this holds it:
  S1  the report's action row offers Share link and Compare beside Download PDF and Save, the share-link fallback
      field exists, and the compare card sits OUTSIDE #report-panel (the printed report stays the report);
  S2  a link carries the inputs in the FRAGMENT (#share=), never the query - a fragment is never sent to a server,
      a log or a page view;
  S3  opening a link reduces its inputs to the form's own keys and types (edShareSanitize) BEFORE the engine call,
      and draws through _renderComputed, the one path a Run takes;
  S4  the identity gate carries a link's fragment through sign-in, and the C27 deep-link poller stands aside for it
      (its late selectCalcType would empty the report the link just drew), and a second link to the calculator
      already open (only its #fragment differs, so init does not run again) opens on hashchange;
  S5  every report path - a Run, a link, a saved calculation reopened - ends in edAfterReport;
  S6  tools/test_calc_share_compare.mjs passes (the pure core: round trip, damaged links, sanitising, compare).

  python tools/validate_calc_share_compare.py
  python tools/validate_calc_share_compare.py --self-test   (the files as they are pass; seven weakened copies fail)
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "engineering-design.js"
HTML = ROOT / "engineering-design.html"
TEST = ROOT / "tools" / "test_calc_share_compare.mjs"


def _fn(js: str, name: str) -> str:
    """The body of a top-level function, up to the next top-level declaration."""
    m = re.search(r"^(?:async\s+)?function\s+" + re.escape(name) + r"\s*\(", js, re.M)
    if not m:
        return ""
    nxt = re.search(r"^(?:async\s+)?function\s+\w+\s*\(|^const\s+\w+\s*=|^let\s+\w+\s*=", js[m.end():], re.M)
    return js[m.start(): m.end() + (nxt.start() if nxt else len(js))]


def check(js: str, html: str, run_node=None) -> list[str]:
    bad = []
    # S1
    for needle, why in (('onclick="edShareLink()"', "no Share link button in the report's action row"),
                        ('id="ed-compare-btn"', "no Compare button in the report's action row"),
                        ('onclick="edCompareKeep()"', "the Compare button does not keep scenario A"),
                        ('id="ed-share-box"', "no share-link fallback field (a browser with no clipboard and no share sheet)"),
                        ('id="ed-share-url"', "no share-link field to copy from")):
        if needle not in html:
            bad.append("S1 " + why)
    cmp_at, panel_at = html.find('id="ed-compare"'), html.find('id="report-panel"')
    if cmp_at < 0 or panel_at < 0 or cmp_at > panel_at:
        bad.append("S1 the compare card is missing or inside/after #report-panel - the printed report would carry it")
    # S2
    share = _fn(js, "edShareLink")
    if "'#share='" not in share or re.search(r"[?&]share=", share.replace("'#share='", "")):
        bad.append("S2 a share link does not carry its inputs in the #fragment (a query is sent to the server and logged)")
    # S3
    opener = _fn(js, "edOpenSharedFromHash")
    s_at, i_at = opener.find("edShareSanitize(defaults, p.i)"), opener.find("invokeWithTimeout(")
    if s_at < 0 or i_at < 0 or s_at > i_at:
        bad.append("S3 a link's inputs reach the engine without edShareSanitize against the form's own defaults")
    if "_renderComputed(inputs, data)" not in opener:
        bad.append("S3 a shared link does not draw through _renderComputed, the path a Run takes")
    if "edShareText" not in _fn(js, "edShareValue") or "[<>\"'`&\\\\]" not in _fn(js, "edShareText"):
        bad.append("S3 the sanitiser no longer strips the characters markup needs from text")
    # S4
    init = _fn(js, "init")
    if not re.search(r"const _ret\s*=.*\+\s*_share;", init):
        bad.append("S4 the identity gate drops a shared link's #fragment at sign-in")
    if not re.search(r"share=/\.test\(window\.location\.hash \|\| ''\)\) return;", _fn(js, "applyCalcDeepLink")):
        bad.append("S4 the C27 deep-link poller does not stand aside for a shared link (it would empty the report)")
    if "edOpenSharedFromHash()" not in init:
        bad.append("S4 init never opens a shared link")
    if not re.search(r"addEventListener\('hashchange',[\s\S]{0,200}?share=[\s\S]{0,120}?edOpenSharedFromHash\(\)", init):
        bad.append("S4 a second link to the calculator already open is never opened (only its #fragment differs, so "
                   "the browser jumps within the page and init does not run again)")
    # S5
    if "_renderComputed(inputs, data);" not in _fn(js, "runCalculation"):
        bad.append("S5 runCalculation does not draw through _renderComputed")
    for fn in ("_renderComputed", "viewHistoryReport"):
        if "edAfterReport();" not in _fn(js, fn):
            bad.append(f"S5 {fn} does not end in edAfterReport (scenario A and the link offer go stale)")
    # S6
    if run_node is not None:
        ok, out = run_node()
        if not ok:
            bad.append("S6 the core test failed: " + out.strip().splitlines()[0][:200] if out.strip() else "S6 the core test failed")
    return bad


def _node(path: Path):
    def run():
        try:
            r = subprocess.run(["node", str(TEST), str(path)], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
        except FileNotFoundError:
            return True, "node not installed - S6 skipped"
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    return run


def main() -> int:
    js, html = JS.read_text(encoding="utf-8"), HTML.read_text(encoding="utf-8")
    bad = check(js, html, _node(JS))
    if bad:
        print("FAIL calc-share-compare:")
        for b in bad:
            print("  -", b)
        return 1
    print("PASS calc-share-compare - Share link and Compare sit in the report's action row; a link's inputs ride in the "
          "#fragment, are reduced to the form's own keys and types before the engine runs, and survive sign-in; every "
          "report path ends in edAfterReport; the core test passes.")
    return 0


def self_test() -> int:
    js, html = JS.read_text(encoding="utf-8"), HTML.read_text(encoding="utf-8")
    fails = []
    if check(js, html, _node(JS)):
        fails.append("the files as they are should PASS: " + "; ".join(check(js, html, _node(JS))))
    mutants = [
        ("the inputs in the query", js.replace("'#share=' + edShareEncode", "'&share=' + edShareEncode"), html, "S2"),
        ("no sanitising before the engine", js.replace("edShareSanitize(defaults, p.i)", "p.i"), html, "S3"),
        ("the gate drops the fragment", js.replace(": '') + _share;", ": '');"), html, "S4"),
        ("a second link on the open page is ignored",
         js.replace("  window.addEventListener('hashchange', () => {\n", "  window.addEventListener('pagehide', () => {\n"), html, "S4"),
        ("the poller does not stand aside",
         js.replace("  if (/(?:^|[#&])share=/.test(window.location.hash || '')) return;\n", ""), html, "S4"),
        ("the compare card inside the printed report",
         js, html.replace('          <section id="ed-compare" class="ed-compare" hidden aria-label="Scenario A and this result"></section>\n', "")
             .replace('<div id="report-panel"></div>', '<div id="report-panel"><section id="ed-compare"></section></div>'), "S1"),
    ]
    for name, mjs, mhtml, want in mutants:
        if mjs == js and mhtml == html:
            fails.append(f"mutant '{name}' did not apply - its anchor moved")
            continue
        got = check(mjs, mhtml)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' should fail {want}, got {got}")
    # the core test must bite too: a sanitiser that keeps '<' fails it
    weak = js.replace("[<>\"'`&\\\\]/g, ''", "[\"'`&\\\\]/g, ''")
    if weak == js:
        fails.append("the sanitiser mutant did not apply - its anchor moved")
    else:
        tmp = Path(tempfile.mkdtemp()) / "engineering-design.js"
        tmp.write_text(weak, encoding="utf-8")
        ok, out = _node(tmp)()
        shutil.rmtree(tmp.parent, ignore_errors=True)
        if ok and "skipped" not in out:
            fails.append("a sanitiser that keeps '<' should fail the core test")
    if fails:
        print("SELF-TEST FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print(f"PASS calc-share-compare self-test - the files pass; {len(mutants)} weakened copies fail their check, and a "
          "sanitiser that keeps '<' fails the core test")
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(self_test() if "--self-test" in sys.argv else main())
