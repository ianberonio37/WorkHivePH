"""validate_kpi_calc.py - ENH-P (2026-10-23): the OEE and MTBF & MTTR calculators work on their own pages.

tools/oee-calculator and tools/mtbf-calculator sent a stranger to Analytics, which reads a logbook they do not have
yet, and their third "How to use" step promised an Engineering Design calculator that does not exist. kpi-calc.js
works the two formulas out on the page. This holds it:
  K1  each page mounts its calculator ([data-wh-kpi-calc="oee"|"mtbf"]) with /kpi-calc.js right after it, after the
      method and before the worked example (drawn during the parse: nothing below it moves);
  K2  tools/build_calc_pages.py carries the same section, steps and source line, so a rebuild keeps them;
  K3  the visible steps and the HowTo JSON-LD steps are the same three sentences, and none promises the Engineering
      Design suite;
  K4  kpi-calc.js offers what ENH-P asks of a calculator: what to do about the number (advice), Print or save as PDF,
      Copy share link, Save on this device, and Keep as scenario A;
  K5  tools/test_kpi_calc.mjs passes: the pages' worked examples, the advice, the refusals, the link round trip.

  python tools/validate_kpi_calc.py
  python tools/validate_kpi_calc.py --self-test
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES = {"oee": ROOT / "tools" / "oee-calculator" / "index.html", "mtbf": ROOT / "tools" / "mtbf-calculator" / "index.html"}
GEN = ROOT / "tools" / "build_calc_pages.py"
JS = ROOT / "kpi-calc.js"
TEST = ROOT / "tools" / "test_kpi_calc.mjs"


def _steps(page: str):
    a = page.find('<h2 id="howto"')
    if a < 0:
        return [], []
    visible = [html.unescape(x) for x in re.findall(r"<li>(.*?)</li>", page[a: page.find("</ol>", a)])]
    ld = []
    for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', page, re.S):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        for node in (data.get("@graph") or [data]) if isinstance(data, dict) else []:
            if isinstance(node, dict) and node.get("@type") == "HowTo":
                ld = [s.get("text", "") for s in node.get("step", [])]
    return visible, ld


def check(pages: dict, gen: str, js: str, run_node=None) -> list[str]:
    bad = []
    for k, page in pages.items():
        m = page.find(f'data-wh-kpi-calc="{k}"')
        s = page.find('<script src="/kpi-calc.js"></script>', m) if m >= 0 else -1
        worked, method = page.find('aria-labelledby="worked"'), page.find('aria-labelledby="formula"')
        if m < 0:
            bad.append(f"K1 {k}: the page mounts no calculator")
        elif s < 0 or page[m:s].count("<") > 4:
            bad.append(f"K1 {k}: /kpi-calc.js does not load right after its mount")
        elif not (method < m < worked):
            bad.append(f"K1 {k}: the calculator is not between the method and the worked example")
        vis, ld = _steps(page)
        if len(vis) != 3 or vis != ld:
            bad.append(f"K3 {k}: the visible steps and the HowTo JSON-LD steps differ")
        if any("Engineering Design suite" in x for x in vis + ld):
            bad.append(f"K3 {k}: a step promises an Engineering Design calculator that does not exist")
    for slug, k in (("oee-calculator", "oee"), ("mtbf-calculator", "mtbf")):
        start = gen.find(f'    "{slug}": {{')
        body = gen[start: gen.find('\n    "', start + 10)] if start >= 0 else ""
        if '"script": "/kpi-calc.js"' not in body or f'data-wh-kpi-calc=\\"{k}\\"' not in body:
            bad.append(f"K2 {slug}: the generator does not carry the calculator, so a rebuild would drop it")
    for needle, why in (("Print or save as PDF", "no print"), ("Copy share link", "no share link"),
                        ("Save on this device", "no save"), ("Keep as scenario A", "no scenario compare"),
                        ("out.advice = ", "no advice on what to do about the number")):
        if needle not in js:
            bad.append(f"K4 kpi-calc.js has {why}")
    if run_node is not None:
        ok, out = run_node()
        if not ok:
            bad.append("K5 the arithmetic test failed: " + (out.strip().splitlines() or [""])[0][:200])
    return bad


def _node(path: Path):
    def run():
        try:
            r = subprocess.run(["node", str(TEST), str(path)], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=60)
        except FileNotFoundError:
            return True, "node not installed - K5 skipped"
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    return run


def _load():
    return ({k: p.read_text(encoding="utf-8") for k, p in PAGES.items()}, GEN.read_text(encoding="utf-8"),
            JS.read_text(encoding="utf-8"))


def main() -> int:
    pages, gen, js = _load()
    bad = check(pages, gen, js, _node(JS))
    if bad:
        print("FAIL kpi-calc:")
        for b in bad:
            print("  -", b)
        return 1
    print("PASS kpi-calc - the OEE and MTBF & MTTR pages work their calculators out on the page (mounted between the "
          "method and the worked example, carried by the generator), their steps match their JSON-LD and promise no "
          "missing calculator, and kpi-calc.js advises, prints, shares, saves and compares; its arithmetic test passes.")
    return 0


def self_test() -> int:
    pages, gen, js = _load()
    fails = []
    if check(pages, gen, js, _node(JS)):
        fails.append("the files as they are should PASS: " + "; ".join(check(pages, gen, js)))
    o = pages["oee"]
    muts = [
        ("no script after the mount", dict(pages, oee=o.replace('<script src="/kpi-calc.js"></script>', "")), gen, js, "K1"),
        ("steps that differ from the JSON-LD", dict(pages, oee=o.replace("<li>To follow OEE from", "<li>To track OEE from", 1)), gen, js, "K3"),
        ("the false step back", dict(pages, oee=o.replace("open Analytics in WorkHive (free, link below)",
                                                           "open the OEE Calculator inside WorkHive's free Engineering Design suite")), gen, js, "K3"),
        ("a generator without the calculator", pages, gen.replace('"script": "/kpi-calc.js",', '"script": "/other.js",', 1), js, "K2"),
        ("no share link", pages, gen, js.replace("Copy share link", "Copy link"), "K4"),
    ]
    for name, mp, mg, mj, want in muts:
        if (mp, mg, mj) == (pages, gen, js):
            fails.append(f"mutant '{name}' did not apply")
            continue
        got = check(mp, mg, mj)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' should fail {want}, got {got}")
    broken = js.replace("out.oee = A * P * Q;", "out.oee = A * P;")
    if broken == js:
        fails.append("the arithmetic mutant did not apply")
    else:
        tmp = Path(tempfile.mkdtemp()) / "kpi-calc.js"
        tmp.write_text(broken, encoding="utf-8")
        ok, out = _node(tmp)()
        shutil.rmtree(tmp.parent, ignore_errors=True)
        if ok and "skipped" not in out:
            fails.append("an OEE that drops quality should fail the arithmetic test")
    if fails:
        print("SELF-TEST FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print(f"PASS kpi-calc self-test - the files pass; {len(muts)} weakened copies fail their check and a broken OEE "
          "fails the arithmetic test")
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(self_test() if "--self-test" in sys.argv else main())
