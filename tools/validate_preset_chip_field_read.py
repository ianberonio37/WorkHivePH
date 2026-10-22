"""validate_preset_chip_field_read.py - ENH-P (2026-10-23): where a calculator's preset chips fill a number field, the
calculation reads the FIELD, never the chip.

engineering-design.js has 16 chip groups that fill a field (`toggle('tg-x','300');document.getElementById('f-x').value=
'300'`): soil resistivity, runoff coefficient, BOD, salt dose, turbidity and the rest. The field stays on screen and a
person types into it. Fifteen read the field. Earthing read the lit chip unless Custom was lit, so a typed 125 Ohm*m
was computed as the lit "100 (loam)" - the earthing resistance and its PASS/FAIL followed a number nobody entered. The
ENH-P compare walk found it: it changed the field, ran again, and the card said "Scenario A is this calculation".

  P1  every chip-filled field is read by the calculation (v('f-x'), num('f-x') or getElementById('f-x').value);
  P2  no chip group that fills a field is read with getToggle - the field is the one source of the number;
  P3  the scan finds at least 16 groups (a scan that finds none passes nothing).

  python tools/validate_preset_chip_field_read.py
  python tools/validate_preset_chip_field_read.py --self-test   (the file as it is passes; three weakened copies fail)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "engineering-design.js"
PAIR = re.compile(r"toggle\('([\w-]+)','[^']*'\);document\.getElementById\('([\w-]+)'\)\.value=")
MIN_GROUPS = 16


def check(js: str) -> list[str]:
    pairs = sorted(set(PAIR.findall(js)))
    bad = []
    if len(pairs) < MIN_GROUPS:
        bad.append(f"P3 found {len(pairs)} chip groups that fill a field, expected at least {MIN_GROUPS} - the scan lost its anchor")
    for group, field in pairs:
        f = re.escape(field)
        if not re.search(r"\b(?:v|num)\('" + f + r"'\)|getElementById\('" + f + r"'\)\.value(?!\s*=)", js):
            bad.append(f"P1 {field} is filled by the {group} chips but the calculation never reads it - a typed value is lost")
        if re.search(r"getToggle\('" + re.escape(group) + r"'\)", js):
            bad.append(f"P2 the {group} chips are read as the value - a number typed into {field} loses to the lit chip")
    return bad


def main() -> int:
    js = JS.read_text(encoding="utf-8")
    bad = check(js)
    if bad:
        print("FAIL preset-chip-field-read:")
        for b in bad:
            print("  -", b)
        return 1
    print(f"PASS preset-chip-field-read - {len(set(PAIR.findall(js)))} chip groups fill a field, and the calculation "
          "reads each field, never the chip")
    return 0


def self_test() -> int:
    js = JS.read_text(encoding="utf-8")
    fails = []
    if check(js):
        fails.append("the file as it is should PASS: " + "; ".join(check(js)))
    mutants = [
        ("the earthing reader as it was", js.replace(
            "    const soilRho = parseFloat(v('f-eg-rho')) || 100;\n",
            "    const soilToggle = getToggle('tg-eg-soil') || '100';\n"
            "    const soilRho = soilToggle === 'custom' ? (parseFloat(v('f-eg-rho')) || 100) : parseFloat(soilToggle);\n"), "P2"),
        ("a field nobody reads", js.replace("parseFloat(v('f-eg-rho')) || 100", "100"), "P1"),
        ("no chip fills a field", PAIR.sub("toggle('x','y');void(", js), "P3"),
    ]
    for name, mjs, want in mutants:
        if mjs == js:
            fails.append(f"mutant '{name}' did not apply - its anchor moved")
            continue
        got = check(mjs)
        if not any(g.startswith(want) for g in got):
            fails.append(f"mutant '{name}' should fail {want}, got {got[:2]}")
    if fails:
        print("SELF-TEST FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print(f"PASS preset-chip-field-read self-test - the file passes; {len(mutants)} weakened copies fail their check")
    return 0


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    sys.exit(self_test() if "--self-test" in sys.argv else main())
