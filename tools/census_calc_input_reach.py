#!/usr/bin/env python3
"""census_calc_input_reach.py - does every value the calculator form sends reach its engine? (Wave ED, 2026-10-31)

Reading two guides against their engines found the same defect twice in one day: the form sends a key the engine never
reads, so a value the person typed does nothing. Pipe Sizing sent "Cold Water Supply" where the engine knew "Domestic Cold"
(a value mismatch); Pump Sizing sent pressure_head, fittings_allowance and fluid_density, none of which pump_tdh.py read
(TDH left out the discharge back-pressure). The pipe calculator had had its own fittings_allowance read fixed on
2026-10-09 - the pump beside it kept the bug - so this measures the whole class instead of one engine at a time.

For every calculator: the TOP-LEVEL keys collectInputs() returns for it (engineering-design.js) against the keys its engine
module reads (python-api/main.py's handler map -> calcs/<module>.py: inputs.get("k") / inputs["k"]).
  SENT, NEVER READ   a value the person types or picks that changes nothing (project metadata excepted)
  READ, NEVER SENT   a value the engine takes from its own default every time (reported, not failed: often deliberate)

    python tools/census_calc_input_reach.py            # the table
    python tools/census_calc_input_reach.py --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "engineering-design.js"
MAIN = ROOT / "python-api" / "main.py"
CALCS = ROOT / "python-api" / "calcs"
META = {"project_name", "project", "calc_type", "notes", "units", "unit_system"}

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def _block_after(src: str, i: int) -> str:
    """The brace-balanced body that starts at the first '{' at or after i (strings skipped)."""
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
                return src[j:k + 1]
        k += 1
    return src[j:]


def _top_level_keys(obj: str) -> set[str]:
    """The keys of an object literal's top level - `name: value` AND the shorthand `name,` (2026-11-01: Compressed Air
    sends its tool list as `tools,` and the first parser, which only counted `name:`, never saw it - the engine ignored
    every tool a person listed and the census said nothing)."""
    inner = obj.strip()[1:-1]
    parts, depth, cur, q, k = [], 0, [], None, 0
    while k < len(inner):
        ch = inner[k]
        if q:
            cur.append(ch)
            if ch == "\\" and k + 1 < len(inner):
                cur.append(inner[k + 1])
                k += 2
                continue
            if ch == q:
                q = None
        elif ch == "/" and inner[k + 1:k + 2] == "/":
            nl = inner.find("\n", k)
            k = len(inner) if nl < 0 else nl
            continue
        elif ch in "'\"`":
            q = ch
            cur.append(ch)
        elif ch in "{[(":
            depth += 1
            cur.append(ch)
        elif ch in "}])":
            depth -= 1
            cur.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        k += 1
    parts.append("".join(cur))
    keys = set()
    for part in parts:
        seg = part.strip()
        if not seg or seg.startswith("..."):
            continue
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:", seg)
        if m:
            keys.add(m.group(1))
        elif re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", seg):
            keys.add(seg)
    return keys


def sent_keys(src: str) -> dict[str, set[str]]:
    """calc id -> the top-level keys of the object collectInputs() returns for it."""
    fn = _block_after(src, src.index("function collectInputs("))
    out: dict[str, set[str]] = {}
    for m in re.finditer(r"if \(_calcType === '([^']+)'\) \{", fn):
        body = _block_after(fn, m.start())
        r = body.find("return {")
        if r < 0:
            continue
        obj = _block_after(body, r)
        keys = _top_level_keys(obj)
        out.setdefault(m.group(1), set()).update(keys)
    return out


def engine_modules(main: str) -> dict[str, str]:
    alias = {m.group(2): m.group(1) for m in re.finditer(r"from calcs\.(\w+)\s+import calculate as (\w+)", main)}
    out = {}
    for m in re.finditer(r'handlers\["([^"]+)"\]\s*=\s*(\w+)', main):
        if m.group(2) in alias:
            out[m.group(1)] = alias[m.group(2)]
    # ★A NAME REGISTERED AS ANOTHER NAME (2026-11-02): main.py maps the frontend's longer names with
    # handlers["Lightning Protection System (LPS)"] = handlers["Lightning Protection (LPS)"] - this parser followed only
    # `= <name>_calc`, so four calculators read as "no python handler" and two rows (ED352, ED353) were banked on a
    # fall-through that never happened. Follow the alias to the module it names.
    for m in re.finditer(r'handlers\["([^"]+)"\]\s*=\s*handlers\["([^"]+)"\]', main):
        if m.group(2) in out:
            out[m.group(1)] = out[m.group(2)]
    return out


def read_keys(module: str) -> set[str]:
    p = CALCS / f"{module}.py"
    if not p.exists():
        return set()
    s = p.read_text(encoding="utf-8", errors="ignore")
    return set(re.findall(r"""(?:inputs|inp|data|params)\.get\(\s*["']([A-Za-z_0-9]+)["']""", s)) | \
        set(re.findall(r"""(?:inputs|inp|data|params)\[\s*["']([A-Za-z_0-9]+)["']\s*\]""", s))


def read_patterns(module: str) -> list[re.Pattern]:
    """Keys an engine reads through an f-string - storm_drain.py reads inputs.get(f"z{zi}_area") in a loop over zones
    (2026-11-01: the first census could not see them and reported the three zones unread; the engine reads all six)."""
    p = CALCS / f"{module}.py"
    if not p.exists():
        return []
    s = p.read_text(encoding="utf-8", errors="ignore")
    out = []
    for tpl in re.findall(r"""(?:inputs|inp|data|params)\.get\(\s*f["']([^"']+)["']""", s):
        rx = "^" + re.sub(r"\\\{[^}]*\\\}", "[A-Za-z0-9_]+", re.escape(tpl)) + "$"
        out.append(re.compile(rx))
    return out

def census() -> dict:
    src, main = JS.read_text(encoding="utf-8", errors="ignore"), MAIN.read_text(encoding="utf-8", errors="ignore")
    sent, mods = sent_keys(src), engine_modules(main)
    rows = []
    for calc, keys in sorted(sent.items()):
        mod = mods.get(calc)
        if not mod:
            rows.append({"calc": calc, "module": None, "unread": [], "unsent": [], "note": "no python handler"})
            continue
        rk, pats = read_keys(mod), read_patterns(mod)
        unread = sorted(k for k in keys - rk - META if not any(px.match(k) for px in pats))
        rows.append({"calc": calc, "module": mod, "sent": len(keys), "read": len(rk),
                     "unread": unread, "unsent": sorted(rk - keys - META)})
    return {"calculators": len(rows), "with_unread": sum(1 for r in rows if r["unread"]),
            "unread_keys": sum(len(r["unread"]) for r in rows), "rows": rows}


BASELINE = ROOT / "calc_input_reach_baseline.json"
# a value the engine deliberately does not compute with - it describes the job and is printed on the report. Each needs its
# reason, and the form/guide must say "recorded on the report" for it (decided per key on the ED-I1 walk)
RECORDED: dict[str, dict[str, str]] = {
    "Bearing Life (L10)": {"bearing_no": "the form labels it 'Bearing Number (optional: for report reference)' - a catalog "
                                         "number printed on the report; the life comes from C and P, which are read"},
    "Generator Sizing": {"phase_config": "3-Phase 4-Wire (400V) or 1-Phase is printed on the report; the generator kVA, "
                                         "the motor-start dip and the fuel are computed in kVA and do not depend on it"},
    "Shaft Design": {
        "power_input": "the number the person typed, echoed for the report - the form converts it to power_kW (HP x 0.746) "
                       "before sending, and power_kW is read",
        "power_unit": "kW or HP, echoed for the report - the conversion happens in the form; power_kW is read"},
    # the same echo pair, visible once python-api answered the form's own name (2026-11-02, ED-E1)
    "V-Belt Drive Design": {
        "power_input": "the number the person typed, echoed - the form converts HP to kW (x 0.746) and sends power_kW, "
                       "which the engine reads (oracle: 7.5 kW x SF 1.2 = 9.0 kW design power)",
        "power_unit": "kW or HP, echoed - the conversion happens in the form; power_kW is read"},
    "Earthing / Grounding System": {"system_voltage": "the form labels it 'System Voltage (V L-L, for fault current ref.)' - "
                                                      "printed for reference; the electrode resistance and the GEC size (by "
                                                      "the service conductor) do not depend on it"},
    "Grease Trap Sizing": {"facility_type": "describes the kitchen on the report; the sizing reads the fixtures, the "
                                            "simultaneous-use factor and the meals per day, which are all read"},
    "FCU Selection": {
        "mounting_type": "cassette / concealed / floor-mounted is printed on the schedule; the FCU is chosen by its cooling "
                         "load and CHW flow, which the mounting does not change",
        "pipe_system": "2-pipe or 4-pipe is printed on the schedule; this calculator sizes the cooling coil and CHW flow - a "
                       "4-pipe system's heating coil is not sized here (its guide must say so)"},
    "UPS Sizing": {"phase": "1-Phase 230V or 3-Phase is printed on the report and decides the product line; the UPS kVA "
                            "(load x growth / 80%) and the battery Ah do not depend on it"},
    "HVAC Cooling Load": {"building_type": "the form labels it 'Building Type (for permit documentation: also suggests Room "
                                           "Function)' - it fills the report header and pre-selects Room Function on the "
                                           "page; the load comes from Room Function's values, which are read"},
}


def _unread_pairs(c: dict) -> set[tuple[str, str]]:
    return {(r["calc"], k) for r in c["rows"] for k in r.get("unread", [])
            if k not in RECORDED.get(r["calc"], {})}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true", help="fail on a value sent and never read that the baseline does not hold")
    ap.add_argument("--update-baseline", action="store_true", help="write today's unread set as the ratchet")
    ap.add_argument("--teeth", action="store_true", help="plant an unread key; the gate must catch it")
    a = ap.parse_args()
    c = census()
    if a.teeth:
        c["rows"][0].setdefault("unread", []).append("wh_teeth_planted_key")
    if a.json:
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return 0
    if a.update_baseline:
        BASELINE.write_text(json.dumps({"note": "values a calculator form sends that its engine never reads - each an open "
                                        "ED-I1 row; the gate fails on any pair not listed here", "unread":
                                        sorted([list(p) for p in _unread_pairs(c)])}, indent=1) + "\n", encoding="utf-8")
    if a.gate or a.teeth:
        base = {tuple(p) for p in json.loads(BASELINE.read_text(encoding="utf-8"))["unread"]} if BASELINE.exists() else set()
        new = sorted(_unread_pairs(c) - base)
        for calc, k in new:
            print(f"  NEW   {calc}: the form sends '{k}' and its engine never reads it")
        if a.teeth:
            ok = any(k == "wh_teeth_planted_key" for _, k in new)
            print("TEETH ok calc-input-reach: a planted unread key was caught" if ok else "BLUNT calc-input-reach")
            return 0 if ok else 1
        left = len(_unread_pairs(c))
        print(f"{'FAIL' if new else 'PASS'} calc-input-reach: {len(new)} new value(s) sent and never read · {left} still open "
              f"in {sum(1 for r in c['rows'] if set(r.get('unread', [])) - set(RECORDED.get(r['calc'], {})))} calculator(s) "
              f"(the ED-I1 rows) · {sum(len(v) for v in RECORDED.values())} recorded-only by decision")
        return 1 if new else 0
    for r in c["rows"]:
        if r.get("note"):
            print(f"  --    {r['calc']}: {r['note']}")
        elif r["unread"]:
            print(f"  SENT, NEVER READ  {r['calc']} ({r['module']}): {', '.join(r['unread'])}")
    print(f"{c['with_unread']} of {c['calculators']} calculators send {c['unread_keys']} key(s) their engine never reads")
    return 0


if __name__ == "__main__":
    sys.exit(main())
