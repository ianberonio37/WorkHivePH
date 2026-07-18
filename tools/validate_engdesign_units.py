#!/usr/bin/env python3
"""
Validator: Engineering-Design SCOPED SI/IP units toggle (deep-arc P6 / A-6).

The units toggle converts ONLY unambiguous dimensional units (length/area/temp/pressure/mass/flow)
and leaves universal (V/A/kW/RPM), dimensionless (%/persons), and ambiguous (kW) units alone — a
blind universal toggle would produce WRONG conversions on electrical calcs. The engine always
receives SI: runCalculation() normalizes Imperial inputs back to SI for the submit. This gate locks
the wiring so the safety property (engine gets SI; only dimensional fields convert) can't regress.

Live-verified 2026-07-08: 100 m² -> 1076.39 ft², 35°C -> 95°F, persons(count) untouched; running
the calc in Imperial mode yielded the SAME 16.8 kW / 4.78 TR as the 100 m² SI calc.

Static + hermetic. Run: python tools/validate_engdesign_units.py   Self-test: --self-test
"""
import os
import re
import sys

try:
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "engineering-design.js")
HTML = os.path.join(ROOT, "engineering-design.html")


def _called_in(js, fn, caller):
    m = re.search(r"function\s+" + re.escape(caller) + r"\s*\([^)]*\)\s*\{", js)
    if not m:
        return False
    i = js.index("{", m.start()); depth = 0; j = i
    while j < len(js):
        if js[j] == "{": depth += 1
        elif js[j] == "}":
            depth -= 1
            if depth == 0: break
        j += 1
    return (fn + "(") in js[i:j + 1]


def run():
    js = open(JS, encoding="utf-8").read()
    html = open(HTML, encoding="utf-8").read()
    problems = []

    if "const UNIT_CONV" not in js:
        problems.append("A-6: UNIT_CONV conversion map missing")
    for fn in ("toggleUnitSystem", "applyUnitSystem", "_toSIForSubmit"):
        if f"function {fn}(" not in js:
            problems.append(f"A-6: {fn}() missing")

    # engine must get SI: runCalculation normalizes before collectInputs
    if not _called_in(js, "_toSIForSubmit", "runCalculation"):
        problems.append("A-6: runCalculation() does not call _toSIForSubmit() — engine could get Imperial values")
    # a freshly-rendered form re-applies IP display
    if not _called_in(js, "applyUnitSystem", "selectCalcType"):
        problems.append("A-6: selectCalcType() does not call applyUnitSystem()")

    # SAFETY: the map must NOT include universal/ambiguous units (kW/V/A/RPM/%), which would mis-convert
    m = re.search(r"const UNIT_CONV\s*=\s*\{(.*?)\n\};", js, re.S)
    if m:
        body = m.group(1)
        for bad in ("'kW'", "'V'", "'A'", "'RPM'", "'%'", "'kVA'"):
            if re.search(re.escape(bad) + r"\s*:", body):
                problems.append(f"A-6 SAFETY: UNIT_CONV must NOT map {bad} (universal/ambiguous — blind conversion is wrong)")

    # toggle button wired in the HTML
    if 'onclick="toggleUnitSystem()"' not in html:
        problems.append("A-6: units toggle button not wired in engineering-design.html")

    print("=" * 60)
    print("Engineering-Design scoped SI/IP units toggle gate (deep-arc A-6)")
    print("=" * 60)
    if problems:
        print(f"FAIL — {len(problems)} problem(s):")
        for p in problems:
            print("  x", p)
        return 1
    print("PASS — scoped toggle wired; engine normalized to SI; universal/ambiguous units excluded.")
    return 0


def self_test():
    ok = True
    js = "const UNIT_CONV = {\n 'm': {},\n};\nfunction runCalculation(){ const r=_toSIForSubmit(); }"
    if not _called_in(js, "_toSIForSubmit", "runCalculation"):
        print("self-test: _called_in broke"); ok = False
    # a map containing kW must be catchable
    body = " 'm': {}, 'kW': {},"
    if not re.search(r"'kW'\s*:", body):
        print("self-test: safety regex broke"); ok = False
    print("SELF-TEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    sys.exit(run())
