#!/usr/bin/env python3
"""census_calc_served_engine.py - which engine answers each calculator a person runs? (Wave ED, 2026-10-31)

engineering-design.html sends every calculation to the engineering-calc-agent edge function. That function tries the Python
engine first (python-api /calculate) and, when Python has no handler for the type, or raises (422 / 500), it falls through
SILENTLY to its own TypeScript implementation (supabase/functions/engineering-calc-agent/index.ts). The oracle that pins
every engine to hand-computed, standard-anchored values (tools/validate_calc_formula_accuracy.py) imports the PYTHON
modules - so a calculator whose form payload Python refuses is answered by an engine the oracle never checks.

Found walking Wire Sizing (2026-10-31): the form sends power_w; wire_sizing.py accepts only load_kw / load_kva / load_amps
and raises "Provide load_kw, load_kva, or load_amps." on every form calculation - so every wire size a person has been given
came from the TypeScript fallback, never from the verified engine.

For every built calculator this runs its Python handler on the form's real default payload
(tools/fixtures/ed_default_payloads.json - collectInputs() read in the page; the values a person must fill set by FILL):
  python        the Python engine answers - the oracle-checked engine is the one served
  ts-fallback   Python raises on the form's own payload - the TypeScript fallback answers, unchecked
  ts-only       no Python handler - the TypeScript implementation is the only engine
  none          Python raises and the edge function has no TypeScript branch - the person gets an error

    python tools/census_calc_served_engine.py [--json]
"""
from __future__ import annotations

import argparse
import importlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "python-api"))
import census_calc_input_reach as cir  # noqa: E402

FIXTURE = ROOT / "tools" / "fixtures" / "ed_default_payloads.json"
EDGE = ROOT / "supabase" / "functions" / "engineering-calc-agent" / "index.ts"
# the values a person must type before Calculate - set to an ordinary job so the run is the form's, not an empty one
FILL = {"cooling_load_kW": 50, "flow_rate": 300, "static_head": 15, "pipe_length": 50, "q_rejection_kw": 500,
        "steam_demand_kg_hr": 1000, "floor_area": 100, "roof_area": 500, "required_flow": 1900, "required_pressure": 7,
        "heat_load_kw": 300}

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


def census() -> dict:
    import warnings
    warnings.filterwarnings("ignore")
    payloads = json.loads(FIXTURE.read_text(encoding="utf-8"))["payloads"]
    mods = cir.engine_modules(cir.MAIN.read_text(encoding="utf-8", errors="ignore"))
    edge = EDGE.read_text(encoding="utf-8", errors="ignore")
    ts_types = set(re.findall(r'calc_type === "([^"]+)"', edge))
    rows = []
    for calc, p in payloads.items():
        inputs = dict(p)
        for k, v in FILL.items():
            if k in inputs and inputs[k] in (0, "", None):
                inputs[k] = v
        mod = mods.get(calc)
        has_ts = calc in ts_types
        if not mod:
            rows.append({"calc": calc, "served": "ts-only" if has_ts else "none", "module": None, "why": "no python handler"})
            continue
        try:
            m = importlib.import_module(f"calcs.{mod}")
            r = m.calculate(inputs)
            ok = isinstance(r, dict) and bool(r)
            rows.append({"calc": calc, "served": "python" if ok else ("ts-fallback" if has_ts else "none"),
                         "module": mod, "why": "" if ok else "empty result"})
        except Exception as e:  # what python-api turns into 422 / 500 - the edge function then falls through
            rows.append({"calc": calc, "served": "ts-fallback" if has_ts else "none", "module": mod,
                         "why": f"{type(e).__name__}: {str(e)[:140]}"})
    from collections import Counter
    return {"calculators": len(rows), "by_served": dict(Counter(r["served"] for r in rows)), "rows": rows}


BASELINE = ROOT / "calc_served_engine_baseline.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--gate", action="store_true", help="fail when a calculator Python answered falls back to TypeScript")
    ap.add_argument("--update-baseline", action="store_true", help="record today's Python-served set (only ever grows)")
    ap.add_argument("--teeth", action="store_true", help="plant a Python-served calculator as fallen back; must be caught")
    a = ap.parse_args()
    c = census()
    if a.json:
        print(json.dumps(c, ensure_ascii=False, indent=1))
        return 0
    served = {r["calc"] for r in c["rows"] if r["served"] == "python"}
    base = set(json.loads(BASELINE.read_text(encoding="utf-8"))["python"]) if BASELINE.exists() else set()
    if a.update_baseline:
        BASELINE.write_text(json.dumps({"note": "calculators whose form payload the oracle-verified Python engine answers - "
                                        "one that falls back to the edge function's TypeScript fails the gate",
                                        "python": sorted(base | served)}, indent=1) + "\n", encoding="utf-8")
        base = base | served
    if a.gate or a.teeth:
        now = set(served)
        if a.teeth and now:
            now.discard(sorted(now)[0])
        fell = sorted(base - now)
        for calc in fell:
            why = next((r["why"] for r in c["rows"] if r["calc"] == calc), "")
            print(f"  FELL BACK  {calc}: Python no longer answers the form ({why or 'planted by --teeth'})")
        if a.teeth:
            print("TEETH ok calc-served-engine: a planted fall-back was caught" if fell else "BLUNT calc-served-engine")
            return 0 if fell else 1
        print(f"{'FAIL' if fell else 'PASS'} calc-served-engine: {len(served)}/{c['calculators']} calculators answered by the "
              f"oracle-verified Python engine on the form's own payload · {len(fell)} fell back · "
              f"{c['calculators'] - len(served)} still answered by TypeScript (the ED-E1 rows)")
        return 1 if fell else 0
    for r in c["rows"]:
        if r["served"] != "python":
            print(f"  {r['served']:<12} {r['calc']}: {r['why']}")
    print("served by: " + " · ".join(f"{k} {v}" for k, v in sorted(c["by_served"].items())) + f"  (of {c['calculators']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
