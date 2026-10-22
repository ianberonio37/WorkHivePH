#!/usr/bin/env python3
"""validate_solar_planner.py - the solar power-station planner stays built (ENH-S, 2026-10-22).

Ian, 2026-10-14, by name: list the appliances, add up the daily watt-hours, size for the surge, choose the days of
autonomy, size the battery and the inverter, use the peak sun hours of the person's own area, size the charge
controller, then save, share and print the plan. It is built ONCE in solar-planner.js and used on the public calculator
(tools/solar-pv-calculator, a visitor, no account). An ENH row closes on the capability built and walked - and on a
gate that fails on the page as it was before the build. This is that gate:

  S1  the sizing chain holds every hand-worked case: tools/test_solar_planner.mjs (load Wh, losses, surge, inverter,
      battery by chemistry and depth of discharge, panels, system voltage, charge controller, cost, the share link)
  S2  the calculator page carries the planner: its section, the [data-wh-solar-planner] element and the script loaded
      AFTER that element (so the planner is drawn during the parse and nothing below it moves)
  S3  the page's chip says where its numbers come from - the planner calculates on the reader's device; "formula-only"
      would be untrue on a page that computes
  S4  the generator carries the same planner block (build_calc_pages.py), so a rebuild of the page cannot drop it
  S5  every capability's own mechanism is in solar-planner.js: add and remove an appliance, the stated losses, the
      starting surge, the days of autonomy, the battery chemistry with its depth of discharge, the inverter's headroom,
      the place's peak sun hours and a custom value, the charge controller, the cost with prices a person replaces,
      save on the device, a share link that carries the whole plan, and the printed spec sheet
  S6  the Engineering Design suite's Solar PV type carries the same planner: the disclosure under its daily-energy field,
      solar-planner.js loaded when the type opens, "Use this plan in the calculation" filling the suite's own daily
      energy (and off-grid, days, depth of discharge, battery voltage, panels, place), and a share link that opens this
      calculator (?calc=solar-pv-system)

    python tools/validate_solar_planner.py              the gate
    python tools/validate_solar_planner.py --self-test  each check broken in a copy (the page as it was before the build
                                                        among them) must be caught; the clean run is green
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = "tools/solar-pv-calculator/index.html"
JS = "solar-planner.js"
GEN = "tools/build_calc_pages.py"
ED = "engineering-design.js"
TEST = "tools/test_solar_planner.mjs"
BEFORE_BUILD = "2980a3c0"   # HEAD when the planner was built: the page as it was, which the gate must fail

# S5: (capability, a pattern its mechanism cannot work without)
CAPS = [
    ("add an appliance", r"function add\(p\)"),
    ("remove an appliance", r"data-del"),
    ("the stated losses", r"INV_EFF\s*=\s*0\.93.*WIRE_EFF\s*=\s*0\.97"),
    ("the starting surge", r"r\.watts \* \(r\.surge - 1\)"),
    ("the days of autonomy", r"batteryOutWh \* days / chem\.dod"),
    ("the battery chemistry and depth of discharge", r"lifepo4:\s*\{[^}]*dod:\s*0\.8.*leadacid:\s*\{[^}]*dod:\s*0\.5"),
    ("the inverter's headroom and surge rating", r"INV_HEADROOM\s*=\s*1\.25.*SURGE_OF_RATED\s*=\s*2"),
    ("the place's peak sun hours", r"\['Metro Manila', 4\.5\]"),
    ("a custom peak sun hours", r"Another place - enter its sun hours"),
    ("the charge controller", r"arrayWp / sysV \* CC_FACTOR"),
    ("the cost with replaceable prices", r"state\.prices\[p\[0\]\]\s*=\s*Number"),
    ("save on the device", r"localStorage\.setItem\(STORE"),
    ("a share link carrying the plan", r"'#plan=' \+ encode\(state\)"),
    ("a share link read back", r"plan=\(\[\^&\]\+\)"),
    ("the printed spec sheet", r"addEventListener\('beforeprint'"),
    # the suite prints its report with body * { visibility: hidden } - the sheet printed blank until it asked back
    ("the printed sheet visible past a host page's print rules", r"wh-sp-sheet \*\{visibility:visible !important\}"),
]


def _read(rel: str, files: dict | None) -> str:
    if files is not None and rel in files:
        return files[rel]
    return (ROOT / rel).read_text(encoding="utf-8", errors="replace")


def check(files: dict | None = None, run_test: bool = True) -> list[str]:
    issues = []
    if run_test:
        t = files.get(TEST + "::result") if files else None
        if t is None:
            r = subprocess.run(["node", TEST], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
            t = (r.returncode, (r.stdout or "") + (r.stderr or ""))
        if t[0] != 0:
            issues.append("S1 the sizing chain no longer holds its hand-worked cases: "
                          + " | ".join(ln.strip() for ln in t[1].splitlines() if "FAIL" in ln)[:300])
    page, js, gen = _read(PAGE, files), _read(JS, files), _read(GEN, files)
    i_sec = page.find('<section aria-labelledby="planner">')
    i_mount = page.find("data-wh-solar-planner")
    i_script = page.find('<script src="/solar-planner.js"></script>')
    if i_sec < 0 or i_mount < 0 or i_script < 0:
        issues.append(f"S2 {PAGE} does not carry the planner - its section, the [data-wh-solar-planner] element or "
                      "the /solar-planner.js script is missing (the page as it was before the build)")
    elif not (i_sec < i_mount < i_script):
        issues.append(f"S2 {PAGE} loads /solar-planner.js before its [data-wh-solar-planner] element - the planner is "
                      "then drawn after the page, and the content below it moves")
    if "the planner calculates on your device" not in page or "Static · formula-only" in page:
        issues.append(f"S3 {PAGE}'s chip does not say the planner calculates on the reader's device - a page that "
                      "computes cannot call itself formula-only")
    gi = gen.find('"solar-pv-calculator": {')
    ge = gen.find("\n    },", gi)
    entry = gen[gi:ge] if gi >= 0 else ""
    if '"tool":' not in entry or "data-wh-solar-planner" not in entry or "/solar-planner.js" not in entry:
        issues.append(f"S4 {GEN} has no planner block for solar-pv-calculator - a rebuild of the page would drop it")
    if "{tool_html}" not in gen:
        issues.append(f"S4 {GEN}'s template no longer places a calculator's tool block")
    flat = re.sub(r"\s+", " ", js)
    for name, rx in CAPS:
        if not re.search(rx, flat, re.S):
            issues.append(f"S5 {JS} lost {name}")
    ed = _read(ED, files)
    k = ed.find("if (calcType === 'Solar PV System') {")
    form = ed[k:ed.find("if (calcType === 'Power Factor Correction')", k)] if k >= 0 else ""
    fb = ed[ed.find("function _edSolarPlanner()"):ed.find("const PV_T_MIN")] if "function _edSolarPlanner()" in ed else ""
    missing = [w for w, ok in (
        ("the planner disclosure in the Solar PV form", 'id="pv-planner-box"' in form and 'id="pv-planner"' in form),
        ("the planner started when the type opens", "_edSolarPlanner();" in form),
        ("solar-planner.js loaded", "sc.src = 'solar-planner.js'" in fb),
        ("the plan carried into the suite's daily energy", "set('f-pv-energy'" in fb and "toggle('tg-pv-type', 'Off-Grid')" in fb),
        ("a share link that opens this calculator", "'?calc=solar-pv-system'" in fb),
    ) if not ok]
    if missing:
        issues.append(f"S6 {ED}'s Solar PV type does not carry the planner: " + "; ".join(missing))
    return issues


def self_test() -> list[str]:
    fails = []
    if check():
        fails.append(f"the clean run is not green: {check()[:2]}")
    page = _read(PAGE, None)
    js = _read(JS, None)
    gen = _read(GEN, None)
    ed = _read(ED, None)
    ok_test = (0, "PASS")
    try:
        ed_before = subprocess.run(["git", "show", f"{BEFORE_BUILD}:{ED}"], cwd=ROOT, capture_output=True, text=True,
                                   encoding="utf-8", errors="replace").stdout
    except Exception:
        ed_before = ''
    try:
        before = subprocess.run(["git", "show", f"{BEFORE_BUILD}:{PAGE}"], cwd=ROOT, capture_output=True, text=True,
                                encoding="utf-8", errors="replace").stdout
    except Exception:
        before = ""
    sec_start = page.find('    <section aria-labelledby="planner">')
    sec_end = page.find("</section>", sec_start) + len("</section>")
    mutants = [
        ("the page as it was before the build", {PAGE: before}, "S2"),
        ("the planner section removed", {PAGE: page[:sec_start] + page[sec_end:]}, "S2"),
        ("the script loaded before its element", {PAGE: page.replace('<script src="/solar-planner.js"></script>', "", 1)
                                                  .replace("<div data-wh-solar-planner>", '<script src="/solar-planner.js"></script><div data-wh-solar-planner>', 1)}, "S2"),
        ("the chip back to formula-only", {PAGE: page.replace("the planner calculates on your device from what you enter",
                                                                "Static · formula-only", 1)}, "S3"),
        ("the generator without the planner", {GEN: gen.replace('"tool": {"id": "planner"', '"toolx": {"id": "planner"', 1)}, "S4"),
        ("the generator's template without the tool slot", {GEN: gen.replace("{tool_html}", "", 1)}, "S4"),
        ("lead-acid at 80% depth of discharge", {JS: js.replace("dod: 0.5, eff: 0.85", "dod: 0.8, eff: 0.85", 1)}, "S5"),
        ("no share link", {JS: js.replace("'#plan=' + encode(state)", "'#' + encode(state)", 1)}, "S5"),
        ("no printed sheet", {JS: js.replace("window.addEventListener('beforeprint'", "window.addEventListener('xbeforeprint'", 1)}, "S5"),
        ("no stated losses", {JS: js.replace("WIRE_EFF = 0.97", "WIRE_EFF = 1", 1)}, "S5"),
        ("a sheet a host's print rule hides", {JS: js.replace("wh-sp-sheet *{visibility:visible !important}", "wh-sp-sheet *{}", 1)}, "S5"),
        ("the sizing chain failing a case", {TEST + "::result": (1, "  FAIL home: panels: got 4, want 3")}, "S1"),
        ("the suite as it was before the build", {ED: ed_before}, "S6"),
        ("the suite's plan not carried into its calculation", {ED: ed.replace("set('f-pv-energy', kwh);", "", 1)}, "S6"),
        ("the suite's share link opening the page, not the calculator", {ED: ed.replace("'?calc=solar-pv-system'", "''", 1)}, "S6"),
    ]
    if not before or "<html" not in before:
        fails.append(f"could not read the page as it was before the build ({BEFORE_BUILD}:{PAGE})")
    for name, files, want in mutants:
        f = dict(files)
        f.setdefault(TEST + "::result", ok_test)
        got = check(f)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' was not caught (got {got[:2]})")
    print(f"  {len(mutants)} mutants")
    return fails


def main() -> int:
    if "--self-test" in sys.argv:
        fails = self_test()
        print("SELF-TEST PASS (every mutant caught; the clean run is green)" if not fails else "SELF-TEST FAIL\n  " + "\n  ".join(fails))
        return 1 if fails else 0
    issues = check()
    print("Solar power-station planner (ENH-S): built once, carried by the calculator and its generator")
    if issues:
        for i in issues:
            print("  [FAIL]", i)
        print(f"  FAIL - {len(issues)} problem(s)")
        return 1
    print(f"  PASS - the sizing chain holds its hand-worked cases; {PAGE} carries the planner (drawn during the parse), "
          f"its chip is true, the generator keeps it, and all {len(CAPS)} capability mechanisms are in {JS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
