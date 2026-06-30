#!/usr/bin/env python3
"""validate_diagram_value_alignment.py — §13.13 A4: diagram VALUE == calc VALUE (live).
================================================================================
The firm artifact tier (validate_artifact_alignment.py) proves a diagram BUILDER
is wired to consume `results`. It does NOT prove the rendered diagram's dimension
LABELS carry the SAME values the calc computed — an emitter could read the wrong
field, mis-format, or silently drop a value. This is the live A4 tier:

  run /calculate (calc → results) → run /diagram (results → SVG) → assert each
  calc result value is PRESENT in the SVG, formatted exactly as the generator
  formats it.

No hand oracle needed: the calc's own numeric correctness is proven by
validate_calc_formula_accuracy.py (58/58). This tier proves the ARTIFACT faithfully
ECHOES the calc — falsifiable (drop/garble a label → the cell fails). Each
(diagram, field) is one cell. Exit 0 = every cell aligned; 1 = a mismatch;
2 = python-api unreachable.

Standard: the python-api diagram generators (python-api/diagrams/*.py).
"""
from __future__ import annotations
import io
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
API = "http://127.0.0.1:8000"
GREEN = "\033[92m"; RED = "\033[91m"; YEL = "\033[93m"; BOLD = "\033[1m"; RESET = "\033[0m"


def post(path: str, body: dict):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, {"_http_error": e.read().decode()[:160]}
    except Exception as e:
        return None, {"_err": str(e)}


def _get(results: dict, path: str):
    """Resolve 'field' or 'segments.0.diameter_mm' (dotted nested/index) out of results."""
    cur = results
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)] if part.isdigit() and int(part) < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def _fmt(v, spec: str) -> str:
    return format(float(v), spec)


# Each diagram: (calc_type, diagram_type, inputs, [(result_field_path, format_spec)])
# format_spec mirrors the generator's exact label f-string formatting.
SPECS = [
    ("Pump Sizing (TDH)", "Pump Sizing (TDH)",
     {"flow_rate": 15, "static_head": 25, "pipe_diameter": 100, "pipe_length": 120,
      "pipe_material": "Steel", "fluid_temp_c": 30, "pump_efficiency": 70,
      "motor_efficiency": 90, "suction_head": 3, "fittings_allowance_pct": 15,
      "fluid_type": "Water", "project_name": "VX Pump"},
     [("flow_m3hr", ".2f"), ("TDH", ".2f"), ("static_head", ".2f"), ("recommended_kw", ".2f")]),

    ("Harmonic Distortion", "Harmonic Distortion",
     {"system_voltage_v": 480, "fundamental_current_a": 200, "max_demand_current_a": 250,
      "short_circuit_current_a": 10000,
      "harmonics": [{"order": 5, "current_pct": 25}, {"order": 7, "current_pct": 12},
                    {"order": 11, "current_pct": 7}, {"order": 13, "current_pct": 4}]},
     [("THD_I_pct", ".2f"), ("TDD_pct", ".2f"), ("K_factor", ".2f"),
      ("fundamental_current_A", ".1f")]),

    ("Transformer Sizing", "Transformer Sizing",
     {"load_kva": 800, "primary_voltage": 13800, "secondary_voltage": 400, "phases": 3,
      "impedance_pct": 5.75, "winding_connection": "Dyn11", "num_units": 1,
      "cooling_type": "ONAN", "load_power_factor": 0.9, "spare_capacity_pct": 25},
     [("rated_kva", ".0f"), ("I1_full_load_A", ".2f"), ("I2_full_load_A", ".2f"),
      ("voltage_regulation_pct", ".2f"), ("efficiency_fl_pct", ".2f"), ("loading_pct", ".1f")]),

    ("AHU Sizing", "AHU Sizing",
     {"floor_area": 200, "ceiling_height": 3, "persons": 30, "cooling_load_w": 35000,
      "indoor_temp": 24, "indoor_rh_pct": 55, "outdoor_temp": 34, "outdoor_rh_pct": 70,
      "oa_pct": 20, "face_velocity": 2.5, "coil_rows": 6, "design_margin_pct": 10,
      "oa_per_person_lps": 10},
     # AHU diagram now grounds mixed-air in the calc's T_mixed (off-coil/supply are
     # derived from the calc's adp_c/bypass/dT_sa). Assert the clean identity cell.
     [("T_mixed", ".1f")]),

    ("Duct Sizing", "Duct Sizing",
     {"flow_cfm": 2000, "friction_rate_pam": 0.8, "section_type": "round",
      "application": "supply", "duct_length_m": 30,
      "sections": [{"name": "S1", "flow_cfm": 2000}, {"name": "S2", "flow_cfm": 1000}]},
     # calc returns sections[].circular.{D_std_mm, velocity_ms}; diagram now reads them
     [("sections.0.circular.D_std_mm", ".0f"), ("sections.0.circular.velocity_ms", ".1f")]),
]


def validate_diagram_value_alignment(blind: bool = False) -> bool:
    st, _ = post("/calculate", {"calc_type": "Pump Sizing (TDH)", "inputs": {"flow_rate": 1}})
    if st is None:
        print(f"{YEL}SKIP (exit 2){RESET}: python-api ({API}) unreachable — start it to validate.")
        return None  # caller maps None→skip
    total = 0
    passed = 0
    fails: list[str] = []
    detail: dict = {}
    for calc_type, diagram_type, inputs, checks in SPECS:
        cs, cj = post("/calculate", {"calc_type": calc_type, "inputs": inputs})
        results = (cj or {}).get("results") if isinstance(cj, dict) else None
        if not results:
            for fld, _spec in checks:
                total += 1
                fails.append(f"{diagram_type}·{fld}: calc failed ({cs}: {str(cj)[:80]})")
            detail[diagram_type] = {"calc_error": f"{cs}: {str(cj)[:120]}"}
            continue
        ds, dj = post("/diagram", {"diagram_type": diagram_type, "inputs": inputs, "results": results})
        svg = (dj or {}).get("svg", "") if isinstance(dj, dict) else ""
        cells = {}
        for fld, spec in checks:
            total += 1
            v = _get(results, fld)
            if v is None:
                fails.append(f"{diagram_type}·{fld}: result field missing")
                cells[fld] = {"value": None, "ok": False}
                continue
            s = _fmt(v, spec)
            ok = s in svg
            cells[fld] = {"value": v, "rendered_as": s, "ok": ok}
            if ok:
                passed += 1
            else:
                fails.append(f"{diagram_type}·{fld}: '{s}' (={v}) NOT in SVG (label dropped/garbled)")
        detail[diagram_type] = {"svg_len": len(svg), "not_implemented": isinstance(dj, dict) and dj.get("not_implemented"),
                                "cells": cells}
        mark = f"{GREEN}✓{RESET}" if all(c["ok"] for c in cells.values()) else f"{RED}✗{RESET}"
        if not blind:
            shown = ", ".join(f"{k}={v['rendered_as']}" for k, v in cells.items() if v.get("rendered_as"))
            nok = sum(c["ok"] for c in cells.values())
            print(f"  {mark} {diagram_type}: {nok}/{len(cells)} labels == calc ({shown})")

    (ROOT / "diagram_value_alignment.json").write_text(json.dumps({
        "tool": "tools/validate_diagram_value_alignment.py",
        "subject": "engineering-design diagram dimension labels == calc results (A4 live tier)",
        "cells_total": total, "cells_aligned": passed, "detail": detail,
        "result": "PASS" if not fails else "FAIL",
    }, indent=2), encoding="utf-8")

    if not blind:
        print("-" * 74)
        print(f"  diagram-value cells aligned : {passed}/{total}")
    return not fails


def main() -> int:
    print(f"{BOLD}\nDIAGRAM VALUE ALIGNMENT (A4) — diagram labels == calc results (live){RESET}")
    print("=" * 74)
    r = validate_diagram_value_alignment(blind=False)
    if r is None:
        return 2
    if r:
        print(f"{GREEN}{BOLD}  DIAGRAM VALUE ALIGNMENT: PASS{RESET}")
        return 0
    print(f"{RED}{BOLD}  DIAGRAM VALUE ALIGNMENT: FAIL{RESET}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
