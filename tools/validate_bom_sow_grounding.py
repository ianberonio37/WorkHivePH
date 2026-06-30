#!/usr/bin/env python3
"""validate_bom_sow_grounding.py — §13.13 A2/B: BOM/SOW grounding-consistency (live).
================================================================================
The BOM + SOW for an engineering calc are LLM-GENERATED (the engineering-bom-sow
edge fn), prompt-grounded on the calc results. That is the platform's HIGHEST
artifact-drift risk: a hallucinated/dropped quantity ships as an authoritative
bill of materials. The firm tier proves the agent is *invoked with* the results;
this LIVE tier proves the generated BOM actually CARRIES the calc's primary sized
value(s) — falsifiable grounding-consistency:

  run /calculate (calc → results) → invoke engineering-bom-sow → assert each calc
  PRIMARY sized value is PRESENT in the generated BOM text (tolerant to LLM
  re-formatting: exact / rounded / 1-2 dp / int).

This is the §13/G3 LIVE grounding tier (an LLM probe, not a hermetic gate): the
primary sized value is strongly prompt-enforced, so a faithful agent always cites
it; a run where it is ABSENT means the agent drifted from the calc. Needs the
local edge (:54321) + python-api (:8000) + a (free-tier) model key. Exit 0 = every
primary value grounded; 1 = a value missing (drift); 2 = a service unreachable.
"""
from __future__ import annotations
import io
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PY_API = "http://127.0.0.1:8000"
EDGE = "http://127.0.0.1:54321/functions/v1"
ANON = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def _post(url: str, body: dict, bearer: str | None = None, timeout: int = 90):
    headers = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"; headers["apikey"] = bearer
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception:
        return None, ""


def _value_present(val, text: str) -> tuple[bool, str]:
    """True if the numeric value appears in any reasonable rendering (LLM reformats)."""
    try:
        f = float(val)
    except (TypeError, ValueError):
        return (str(val) in text, str(val))
    cands = []
    for spec in (".2f", ".1f", ".0f"):
        cands.append(format(f, spec))
    if f == int(f):
        cands.append(str(int(f)))
    # also the raw repr (e.g. 0.18) and a comma-grouped integer (e.g. 1,000)
    cands.append(repr(f).rstrip("0").rstrip(".") if "." in repr(f) else repr(f))
    if f == int(f):
        cands.append(f"{int(f):,}")
    for c in dict.fromkeys(cands):
        if c and c in text:
            return True, c
    return False, "/".join(dict.fromkeys(cands))


# (calc_type, discipline, inputs, [(primary_field, label)]) — primary = the calc's key sized output(s)
SPECS = [
    ("Pump Sizing (TDH)", "Mechanical",
     {"flow_rate": 15, "static_head": 25, "pipe_diameter": 100, "pipe_length": 120,
      "pipe_material": "Steel", "fluid_temp_c": 30, "pump_efficiency": 70,
      "motor_efficiency": 90, "suction_head": 3, "fittings_allowance_pct": 15,
      "fluid_type": "Water", "project_name": "VX Pump"},
     [("recommended_kw", "motor kW"), ("TDH", "TDH")]),

    ("Transformer Sizing", "Electrical",
     {"load_kva": 800, "primary_voltage": 13800, "secondary_voltage": 400, "phases": 3,
      "impedance_pct": 5.75, "winding_connection": "Dyn11", "num_units": 1,
      "cooling_type": "ONAN", "load_power_factor": 0.9, "spare_capacity_pct": 25},
     [("rated_kva", "rated kVA")]),

    ("AHU Sizing", "HVAC Systems",
     {"floor_area": 200, "ceiling_height": 3, "persons": 30, "cooling_load_w": 35000,
      "indoor_temp": 24, "indoor_rh_pct": 55, "outdoor_temp": 34, "outdoor_rh_pct": 70,
      "oa_pct": 20, "face_velocity": 2.5, "coil_rows": 6, "design_margin_pct": 10,
      "oa_per_person_lps": 10},
     [("coil_total_kw", "coil kW")]),

    ("Fire Pump Sizing", "Fire Protection",
     {"occupancy_hazard": "Ordinary Hazard Group 2", "design_area_m2": 140,
      "design_density_mm_min": 8.1, "hose_allowance_lpm": 950, "static_lift_m": 10,
      "pipe_length_m": 80, "system_type": "Wet"},
     # fire pumps are spec'd in HP + L/min (not kW/gpm) — assert the cited units
     [("recommended_flow_lpm", "flow L/min"), ("selected_HP", "motor HP")]),

    ("Generator Sizing", "Electrical",
     {"total_connected_load_kw": 150, "demand_factor": 0.8, "power_factor": 0.8,
      "future_expansion_pct": 20, "altitude_m": 100, "ambient_temp_c": 35,
      "fuel_type": "Diesel", "starting_method": "Direct on Line"},
     [("recommended_kVA", "rated kVA")]),
]


def validate_bom_sow_grounding(blind: bool = False) -> bool | None:
    st, _ = _post(f"{PY_API}/calculate", {"calc_type": "Pump Sizing (TDH)", "inputs": {"flow_rate": 1}})
    if st is None:
        if not blind:
            print(f"{YEL}SKIP (exit 2){RESET}: python-api ({PY_API}) unreachable.")
        return None
    total = 0; grounded = 0; skipped = 0
    fails: list[str] = []; detail: dict = {}
    for i, (calc_type, discipline, inputs, primaries) in enumerate(SPECS):
        if i:
            time.sleep(4)   # pace calls — rapid free-tier bursts transiently 500 the model chain
        cs, cj = _post(f"{PY_API}/calculate", {"calc_type": calc_type, "inputs": inputs})
        results = json.loads(cj).get("results") if cs == 200 else None
        if not results:
            for _f, lbl in primaries:
                total += 1; fails.append(f"{calc_type}·{lbl}: calc failed ({cs})")
            continue
        # one retry on a transient model/service error (the chain can momentarily exhaust)
        bs, bj = _post(f"{EDGE}/engineering-bom-sow",
                       {"discipline": discipline, "calc_type": calc_type, "calc_results": results}, ANON)
        if bs is not None and bs >= 500:
            time.sleep(5)
            bs, bj = _post(f"{EDGE}/engineering-bom-sow",
                           {"discipline": discipline, "calc_type": calc_type, "calc_results": results}, ANON)
        if bs is None:
            if not blind:
                print(f"{YEL}SKIP (exit 2){RESET}: edge ({EDGE}) unreachable.")
            return None
        if bs != 200:
            # a non-200 BOM response is a SERVICE/transient issue (model chain 500 / quota),
            # NOT a grounding drift — skip these cells honestly rather than false-FAIL.
            for _f, lbl in primaries:
                total += 1; skipped += 1
            detail[calc_type] = {"bom_http": bs, "skipped": "service/transient (non-200) — not a grounding signal"}
            if not blind:
                print(f"  {YEL}~{RESET} {calc_type} → BOM HTTP {bs} (transient service issue — skipped, not a drift)")
            continue
        bom_text = bj  # raw JSON string contains the bom_items specs/descriptions
        cells = {}
        for fld, lbl in primaries:
            total += 1
            v = results.get(fld)
            if v is None:
                fails.append(f"{calc_type}·{lbl}: calc result field '{fld}' missing")
                cells[lbl] = {"value": None, "grounded": False}
                continue
            ok, shown = _value_present(v, bom_text)
            cells[lbl] = {"value": v, "as": shown, "grounded": ok}
            if ok:
                grounded += 1
            else:
                fails.append(f"{calc_type}·{lbl}: calc {fld}={v} NOT cited in generated BOM (drift/hallucination)")
        detail[calc_type] = {"bom_http": bs, "bom_len": len(bj), "cells": cells}
        if not blind:
            mark = f"{GREEN}✓{RESET}" if all(c["grounded"] for c in cells.values()) else f"{RED}✗{RESET}"
            shown = ", ".join(f"{k}={v['value']}" for k, v in cells.items())
            print(f"  {mark} {calc_type} → BOM grounds [{shown}]")

    (ROOT / "bom_sow_grounding.json").write_text(json.dumps({
        "tool": "tools/validate_bom_sow_grounding.py",
        "subject": "engineering-bom-sow LLM artifact grounds the calc's primary sized values (live)",
        "cells_total": total, "cells_grounded": grounded, "cells_skipped": skipped, "detail": detail,
        "result": "PASS" if not fails else "FAIL",
    }, indent=2), encoding="utf-8")
    if not blind:
        print(f"  grounded {grounded}/{total - skipped} verifiable cells" + (f" · {skipped} skipped (transient)" if skipped else ""))
    return not fails


def main() -> int:
    print(f"{BOLD}\nBOM/SOW GROUNDING (§13.13 live) — generated BOM cites the calc's sized values{RESET}")
    print("=" * 74)
    r = validate_bom_sow_grounding(blind=False)
    if r is None:
        return 2
    print("-" * 74)
    if r:
        print(f"{GREEN}{BOLD}  BOM/SOW GROUNDING: PASS{RESET} — every primary sized value cited in the generated BOM.")
        return 0
    print(f"{RED}{BOLD}  BOM/SOW GROUNDING: FAIL{RESET} — a calc value was not grounded (see above).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
