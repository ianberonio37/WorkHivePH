"""
Engineering Calc Python API — Phase 0 Foundation
FastAPI microservice that handles engineering calculations with proper
Python libraries. Called by the Supabase Edge Function as a proxy;
returns { not_implemented: true } for calc types not yet migrated so
the Edge Function falls back to its TypeScript handlers.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
import traceback

app = FastAPI(
    title="Engineering Calc Python API",
    description="Standards-grade engineering calculations for WorkHive Engineering Design",
    version="0.1.0",
)

# CORS — allow the Supabase Edge Function and Netlify frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # locked down per-origin once deployed
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class CalcRequest(BaseModel):
    calc_type: str
    inputs: dict[str, Any]


class AnalyticsRequest(BaseModel):
    phase: str                          # "descriptive" | "diagnostic" | "predictive" | "prescriptive"
    inputs: dict[str, Any]             # phase-specific payload (data arrays + params)


class DiagramRequest(BaseModel):
    diagram_type: str
    inputs: dict[str, Any]
    results: dict[str, Any] = {}


# ─── Handler registry ─────────────────────────────────────────────────────────
# Each phase adds entries here. Key = exact calc_type string used by the
# frontend. Value = a callable that takes (inputs: dict) -> dict.
# Phases 1-9 will import from calcs/ sub-modules and register here.

def _load_handlers() -> dict[str, Any]:
    handlers: dict[str, Any] = {}

    # Phase 1 — Fluid Mechanics (Pump + Pipe + Compressed Air)
    from calcs.pump_tdh      import calculate as pump_tdh_calc
    from calcs.pipe_sizing   import calculate as pipe_sizing_calc
    from calcs.compressed_air import calculate as compressed_air_calc
    handlers["Pump Sizing (TDH)"] = pump_tdh_calc
    handlers["Pipe Sizing"]       = pipe_sizing_calc
    handlers["Compressed Air"]    = compressed_air_calc

    # Phase 2 — HVAC / Psychrometrics
    from calcs.hvac_cooling_load  import calculate as hvac_calc
    from calcs.ahu_sizing         import calculate as ahu_calc
    from calcs.cooling_tower      import calculate as cooling_tower_calc
    from calcs.duct_sizing        import calculate as duct_calc
    handlers["HVAC Cooling Load"]      = hvac_calc
    handlers["AHU Sizing"]             = ahu_calc
    handlers["Cooling Tower Sizing"]   = cooling_tower_calc
    handlers["Duct Sizing"]            = duct_calc

    # Phase 3 — Refrigeration
    from calcs.refrigerant_pipe  import calculate as refrig_pipe_calc
    from calcs.fcu_selection     import calculate as fcu_calc
    from calcs.chiller           import calculate as chiller_calc
    handlers["Refrigerant Pipe Sizing"]              = refrig_pipe_calc
    handlers["FCU Selection"]                        = fcu_calc
    handlers["Chiller System — Water Cooled"]        = chiller_calc
    handlers["Chiller System — Air Cooled"]          = chiller_calc

    # Phase 4 — Electrical
    from calcs.wire_sizing         import calculate as wire_calc
    from calcs.short_circuit       import calculate as sc_calc
    from calcs.load_schedule       import calculate as load_sched_calc
    # from calcs.generator_sizing    import calculate as gen_calc
    # from calcs.solar_pv            import calculate as solar_calc
    handlers["Wire Sizing"]        = wire_calc
    handlers["Short Circuit"]      = sc_calc
    handlers["Load Schedule"]      = load_sched_calc
    from calcs.generator_sizing    import calculate as gen_calc
    from calcs.ups_sizing          import calculate as ups_calc
    from calcs.solar_pv            import calculate as solar_calc
    handlers["Generator Sizing"]   = gen_calc
    handlers["UPS Sizing"]         = ups_calc
    handlers["Solar PV System"]    = solar_calc

    # Phase 5 — Fire Protection
    from calcs.fire_sprinkler  import calculate as sprinkler_calc
    from calcs.fire_pump       import calculate as fire_pump_calc
    handlers["Fire Sprinkler Hydraulic"] = sprinkler_calc
    handlers["Fire Pump Sizing"]         = fire_pump_calc

    # Phase 6 — Plumbing / Water
    from calcs.domestic_water  import calculate as domestic_water_calc
    from calcs.sewer_drainage  import calculate as sewer_drainage_calc
    handlers["Domestic Water System"] = domestic_water_calc
    handlers["Sewer / Drainage"]      = sewer_drainage_calc

    # Phase 7 — Structural / Lighting / LPS
    from calcs.beam_column          import calculate as beam_column_calc
    from calcs.lighting_design      import calculate as lighting_calc
    from calcs.lightning_protection import calculate as lps_calc
    handlers["Beam / Column Design"]       = beam_column_calc
    handlers["Lighting Design"]            = lighting_calc
    handlers["Lightning Protection (LPS)"] = lps_calc

    # Phase 8 — Machine Design
    from calcs.shaft_design    import calculate as shaft_calc
    from calcs.gear_belt_drive import calculate as gear_calc
    from calcs.pressure_vessel import calculate as pv_calc
    from calcs.heat_exchanger  import calculate as hx_calc
    handlers["Shaft Design"]         = shaft_calc
    handlers["Gear / Belt Drive"]    = gear_calc
    handlers["Pressure Vessel"]      = pv_calc
    handlers["Heat Exchanger"]       = hx_calc

    # Phase 9 — Remaining calcs
    from calcs.vibration_analysis import calculate as vibration_calc
    from calcs.fluid_power        import calculate as fluid_power_calc
    from calcs.noise_acoustics    import calculate as noise_calc
    from calcs.boiler_steam       import calculate as boiler_calc
    handlers["Vibration Analysis"]    = vibration_calc
    handlers["Fluid Power"]           = fluid_power_calc
    handlers["Noise / Acoustics"]     = noise_calc
    handlers["Boiler / Steam System"] = boiler_calc

    # ── Frontend name aliases ─────────────────────────────────────────────────
    # Only alias calc types where the frontend input field schema matches what
    # the Python handler expects. Mismatched schemas (Load Estimation, Boiler
    # System, Water Supply Pipe Sizing, Drainage Pipe Sizing) are intentionally
    # NOT aliased — they fall through to the TypeScript handlers which already
    # work correctly for those input shapes.
    handlers["Duct Sizing (Equal Friction)"]       = handlers["Duct Sizing"]
    handlers["Lightning Protection System (LPS)"]  = handlers["Lightning Protection (LPS)"]
    handlers["V-Belt Drive Design"]                = handlers["Gear / Belt Drive"]
    handlers["Short Circuit Analysis"]             = handlers["Short Circuit"]

    return handlers


HANDLERS: dict[str, Any] = _load_handlers()


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check — called by the Edge Function before every request to
    detect cold-start. Returns the list of currently implemented calc types."""
    return {
        "status": "ok",
        "version": "0.1.0",
        "implemented_calcs": sorted(HANDLERS.keys()),
        "total_implemented": len(HANDLERS),
    }


@app.post("/calculate")
def calculate(req: CalcRequest):
    """
    Main calculation endpoint.
    - If a Python handler exists for req.calc_type: run it and return results.
    - If not: return { not_implemented: true } so the Deno Edge Function
      falls back to its TypeScript handler for this calc type.
    """
    handler = HANDLERS.get(req.calc_type)

    if handler is None:
        # Signal the Deno proxy to fall through to TypeScript
        return {
            "not_implemented": True,
            "calc_type": req.calc_type,
        }

    try:
        results = handler(req.inputs)
        return {"results": results}
    except ValueError as e:
        # Input validation errors — surface as 422 so the Edge Function
        # can include the message in the error response to the frontend
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # Unexpected errors — log the trace, return 500
        print(f"ERROR in {req.calc_type}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@app.post("/diagram")
def diagram(req: DiagramRequest):
    """
    Diagram generation endpoint.
    Returns { svg: "..." } for supported diagram types,
    or { not_implemented: true } so the frontend can hide the button.
    """
    from diagrams import pump_curve, psychrometric_chart, duct_chart

    DIAGRAM_HANDLERS = {
        "Pump Sizing (TDH)":          pump_curve.generate,
        "AHU Sizing":                  psychrometric_chart.generate,
        "Duct Sizing":                 duct_chart.generate,
        "Duct Sizing (Equal Friction)": duct_chart.generate,
    }

    handler = DIAGRAM_HANDLERS.get(req.diagram_type)
    if handler is None:
        return {"not_implemented": True, "diagram_type": req.diagram_type}

    try:
        svg = handler(req.inputs, req.results)
        return {"svg": svg, "diagram_type": req.diagram_type}
    except Exception as e:
        print(f"DIAGRAM ERROR {req.diagram_type}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Diagram error: {str(e)}")


@app.get("/calcs")
def list_calcs():
    """Returns the list of calc types currently handled by Python (useful for
    the frontend to know which calcs have been upgraded)."""
    return {
        "python_calcs": sorted(HANDLERS.keys()),
        "count": len(HANDLERS),
    }


# ─── Analytics Engine Routes (Stage 3) ───────────────────────────────────────

ANALYTICS_PHASES = {
    "descriptive": None,  # lazy-loaded on first call
}

@app.post("/analytics")
def analytics(req: AnalyticsRequest):
    """
    Stage 3 Analytics Engine endpoint.
    Routes by req.phase to the appropriate analytics module.

    Phase 1 — descriptive: ISO 14224:2016 + SMRP
      inputs: { logbook_entries, pm_completions, pm_scope_items,
                inv_transactions, period_days }

    Returns structured analytics results for the frontend dashboard.
    """
    phase = req.phase.lower().strip()

    if phase == "descriptive":
        from analytics.descriptive import calculate
        try:
            return calculate(req.inputs)
        except Exception as e:
            print(f"ANALYTICS ERROR [descriptive]: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

    if phase == "diagnostic":
        from analytics.diagnostic import calculate
        try:
            return calculate(req.inputs)
        except Exception as e:
            print(f"ANALYTICS ERROR [diagnostic]: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

    if phase == "predictive":
        from analytics.predictive import calculate
        try:
            return calculate(req.inputs)
        except Exception as e:
            print(f"ANALYTICS ERROR [predictive]: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

    # Phase 4 will be added here
    raise HTTPException(
        status_code=404,
        detail=f"Analytics phase '{phase}' not yet implemented. Available: descriptive, diagnostic, predictive"
    )


@app.get("/analytics/health")
def analytics_health():
    """Returns available analytics phases and their status."""
    return {
        "available_phases": ["descriptive", "diagnostic"],
        "coming_soon": ["predictive", "prescriptive"],
        "standards": ["ISO 14224:2016", "ISO 13381-1:2015", "ISO 55000:2014", "SMRP Metrics"],
    }
