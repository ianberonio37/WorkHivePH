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
import importlib

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
    # from calcs.chiller           import calculate as chiller_calc
    handlers["Refrigerant Pipe Sizing"]         = refrig_pipe_calc
    handlers["FCU Selection"]                   = fcu_calc
    # handlers["FCU Selection"]                   = fcu_calc
    # handlers["Chiller System — Water Cooled"]   = chiller_calc
    # handlers["Chiller System — Air Cooled"]     = chiller_calc

    # Phase 4 — Electrical
    # from calcs.wire_sizing         import calculate as wire_calc
    # from calcs.short_circuit       import calculate as sc_calc
    # from calcs.generator_sizing    import calculate as gen_calc
    # from calcs.solar_pv            import calculate as solar_calc
    # handlers["Wire Sizing"]        = wire_calc
    # handlers["Short Circuit"]      = sc_calc
    # handlers["Generator Sizing"]   = gen_calc
    # handlers["Solar PV System"]    = solar_calc

    # Phase 5 — Fire Protection
    # from calcs.fire_sprinkler  import calculate as sprinkler_calc
    # from calcs.fire_pump       import calculate as fire_pump_calc
    # handlers["Fire Sprinkler Hydraulic"] = sprinkler_calc
    # handlers["Fire Pump Sizing"]         = fire_pump_calc

    # Phase 6 — Plumbing / Water
    # Phase 7 — Structural / Lighting / LPS
    # Phase 8 — Diagrams + PDF
    # Phase 9 — Machine Design + Remaining

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


@app.get("/calcs")
def list_calcs():
    """Returns the list of calc types currently handled by Python (useful for
    the frontend to know which calcs have been upgraded)."""
    return {
        "python_calcs": sorted(HANDLERS.keys()),
        "count": len(HANDLERS),
    }
