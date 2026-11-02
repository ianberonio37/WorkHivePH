#!/usr/bin/env python3
"""census_form_option_reach.py - does every CHOICE a calculator form offers reach its engine as that choice?
(Wave ED, 2026-11-02)

census_calc_input_reach.py proves each KEY the form sends is read. It cannot see a VALUE the engine does not know: the
vibration form's isolator toggle sent "Steel spring (medium)" and the engine read the key - but the stiffness came from a
payload default, so every isolator computed as a rubber mount; the door pages sent "Spring", "SPB", "Factory / Workshop"
and the lookups fell back silently. This asks the question per option.

For every calculator in tools/fixtures/ed_default_payloads.json, every payload key the form fills from a toggle group
(`key: getToggle('tg-x')` in collectInputs) and every option that group offers (`toggle('tg-x','Value')`): run the served
handler (python-api main.HANDLERS) on the form's default payload with the key set to that option, and again with it set to
a garbage string. An option whose result is identical to garbage's (the echoed value masked) and that is not a literal in
the module's code is a choice the person makes that the engine never sees.

    python tools/census_form_option_reach.py            # list them
    python tools/census_form_option_reach.py --gate     # exit 1 when any option is unrecognised (outside RECORDED)
"""
from __future__ import annotations

import importlib
import io
import json
import re
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python-api"))
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

JS = ROOT / "engineering-design.js"
GARBAGE = "zz-not-a-choice-zz"
# options an engine accepts by a rule rather than a table key, or that are recorded-only by decision - each with a reason
RECORDED: dict[tuple[str, str, str], str] = {
    ("Chiller System — Water Cooled", "chiller_type", "Centrifugal"):
        "chiller reads positive-displacement keywords (screw, scroll, reciprocating); everything else is centrifugal",
    ("Transformer Sizing", "winding_connection", "Star-Star (Yyn0)"):
        "the vector group is a label on the report and drawing; it does not change the kVA sizing",
    ("Transformer Sizing", "winding_connection", "Delta-Delta (Dd0)"):
        "the vector group is a label on the report and drawing; it does not change the kVA sizing",
    ("Wire Sizing", "conduit_fill", "1-3"):
        "1-3 current-carrying conductors is the 1.00 adjustment factor, the engine's base case",
    ("Voltage Drop", "circuit_type", "Feeder"):
        "voltage_drop echoes the circuit type; its limit is the form's own VD-limit field",
    ("Lightning Protection System (LPS)", "air_term_method", "Protection Angle"):
        "not modelled: the terminal count is estimated as for the rolling sphere, and air_method_note says so",
    ("Earthing / Grounding System", "electrode_type", "Ring"):
        "the engine's else-branch is the ring (IEEE 142 Dwight ring formula)",
    ("Lighting Design", "fixture_type", "LED Panel 600x600"):
        "the fixture toggle fills lumens_per_fix and watts_per_fix, which the engine reads; the name is the label",
    ("Lighting Design", "fixture_type", "LED Batten 1200mm"):
        "the fixture toggle fills lumens_per_fix and watts_per_fix, which the engine reads; the name is the label",
    ("Lighting Design", "fixture_type", "Fluorescent T8 2x36W"):
        "the fixture toggle fills lumens_per_fix and watts_per_fix, which the engine reads; the name is the label",
    ("Water Treatment System", "intended_use", "Process / Industrial"):
        "softening and RO are added only for boiler and cooling-tower makeup; process water takes the potable train",
    ("Stairwell Pressurization", "building_type", "Non-Sprinklered"):
        "the engine tests for 'Sprinklered'; anything else is the unsprinklered 50 Pa design, which this is",
    ("Shaft Design", "keyway", "No"):
        "the engine tests keyway == 'Yes'; 'No' is the plain-shaft branch",
    ("Wastewater Treatment (STP)", "disinfection", "None"):
        "anything neither chlorination nor UV sizes no disinfection, and disinfection_note names the coliform limit",
    ("Beam / Column Design", "member_type", "RC Column"):
        "the engine routes by 'Steel' and 'Beam' in the type; neither present is the RC column",
}


def _code_only(src: str) -> str:
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    return re.sub(r"#[^\n]*", "", src)


def _strip(r):
    if isinstance(r, dict):
        return {k: _strip(v) for k, v in r.items() if k not in ("inputs_used", "code_notes", "calculation_source")}
    if isinstance(r, list):
        return [_strip(x) for x in r]
    return r


def toggle_keys(js: str) -> dict[str, dict[str, str]]:
    """{calc_type: {payload_key: tg_id}} from collectInputs()'s per-calculator return blocks."""
    out = {}
    for m in re.finditer(r"if \(_calcType === '([^']+)'\) \{\s*(?:[^{}]|\{[^{}]*\})*?return \{([\s\S]*?)\n\s*\};", js):
        calc, body = m.group(1), m.group(2)
        pairs = dict(re.findall(r"(\w+)\s*:\s*getToggle\('([\w-]+)'\)", body))
        if pairs:
            out.setdefault(calc, {}).update(pairs)
    return out


def toggle_options(js: str) -> dict[str, list[str]]:
    opts: dict[str, list[str]] = {}
    for tg, val in re.findall(r"toggle\('([\w-]+)',\s*'([^'$]+)'\)", js):
        if val not in opts.setdefault(tg, []):
            opts[tg].append(val)
    return opts


def census() -> list[dict]:
    warnings.filterwarnings("ignore")
    import logging
    logging.disable(logging.WARNING)
    import census_calc_served_engine as cse
    import main as api
    js = JS.read_text(encoding="utf-8")
    keys, opts = toggle_keys(js), toggle_options(js)
    payloads = json.loads(cse.FIXTURE.read_text(encoding="utf-8"))["payloads"]
    rows = []
    for calc, p in payloads.items():
        handler = api.HANDLERS.get(calc)
        if handler is None or calc not in keys:
            continue
        src = _code_only(Path(importlib.import_module(handler.__module__).__file__).read_text(encoding="utf-8"))
        base = dict(p)
        for k, v in cse.FILL.items():
            if k in base and base[k] in (0, "", None):
                base[k] = v
        for key, tg in keys[calc].items():
            try:
                g = json.dumps(_strip(api._to_jsonable(handler({**base, key: GARBAGE}))), sort_keys=True, default=str)
            except Exception:  # noqa: BLE001 - the engine refuses an unknown value: that is recognition, not a fallback
                continue
            for val in opts.get(tg, []):
                if (calc, key, val) in RECORDED or f'"{val}"' in src or f"'{val}'" in src:
                    continue
                try:
                    a = json.dumps(_strip(api._to_jsonable(handler({**base, key: val}))), sort_keys=True, default=str)
                except Exception:  # noqa: BLE001
                    continue
                if a.replace(json.dumps(val)[1:-1], "@") == g.replace(GARBAGE, "@"):
                    rows.append({"calc": calc, "key": key, "toggle": tg, "option": val})
    return rows


def main() -> int:
    rows = census()
    for r in rows:
        print(f"  UNSEEN  {r['calc']}: {r['key']} = {r['option']!r} (toggle {r['toggle']}) computes exactly as an unknown value")
    gate = "--gate" in sys.argv
    print(f"{'FAIL' if gate and rows else 'PASS' if not rows else 'INFO'} form-option-reach: {len(rows)} form choice(s) "
          f"the engine never recognises" + ("" if rows else " - every toggle option reaches its engine as that choice"))
    return 1 if gate and rows else 0


if __name__ == "__main__":
    sys.exit(main())
