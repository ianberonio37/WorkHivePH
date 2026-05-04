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


class PdfRequest(BaseModel):
    html: str                       # full innerHTML of the report panel
    filename: str = "report.pdf"   # suggested download filename


class ProjectRequest(BaseModel):
    project: dict[str, Any]                    # the projects row
    items: list[dict[str, Any]] = []           # project_items rows
    links: list[dict[str, Any]] = []           # project_links rows
    logs:  list[dict[str, Any]] = []           # project_progress_logs rows (last ~30)
    labor_rate_php_per_hour: float | None = None  # optional override; default 200


# ─── Handler registry ─────────────────────────────────────────────────────────
# Each phase adds entries here. Key = exact calc_type string used by the
# frontend. Value = a callable that takes (inputs: dict) -> dict.
# Phases 1-9 will import from calcs/ sub-modules and register here.

def _load_handlers() -> dict[str, Any]:
    handlers: dict[str, Any] = {}

    # Mechanical — Ventilation / ACH + Boiler System (frontend schema)
    from calcs.ventilation_ach import calculate as vent_ach_calc
    from calcs.boiler_system   import calculate as boiler_system_calc
    handlers["Ventilation / ACH"] = vent_ach_calc
    handlers["Boiler System"]     = boiler_system_calc

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
    from calcs.expansion_tank    import calculate as expansion_tank_calc
    handlers["Refrigerant Pipe Sizing"]              = refrig_pipe_calc
    handlers["FCU Selection"]                        = fcu_calc
    handlers["Chiller System — Water Cooled"]        = chiller_calc
    handlers["Chiller System — Air Cooled"]          = chiller_calc
    handlers["Expansion Tank Sizing"]                = expansion_tank_calc

    # Phase 4 — Electrical
    from calcs.voltage_drop             import calculate as vd_calc
    from calcs.power_factor_correction  import calculate as pfc_calc
    from calcs.cable_tray_sizing        import calculate as cable_tray_calc
    from calcs.wire_sizing              import calculate as wire_calc
    from calcs.short_circuit       import calculate as sc_calc
    from calcs.load_schedule       import calculate as load_sched_calc
    # from calcs.generator_sizing    import calculate as gen_calc
    # from calcs.solar_pv            import calculate as solar_calc
    from calcs.load_estimation      import calculate as load_est_calc
    from calcs.transformer_sizing   import calculate as xfmr_calc
    from calcs.harmonic_distortion  import calculate as harmonic_calc
    handlers["Load Estimation"]         = load_est_calc
    handlers["Transformer Sizing"]      = xfmr_calc
    handlers["Harmonic Distortion"]     = harmonic_calc
    handlers["Voltage Drop"]            = vd_calc
    handlers["Power Factor Correction"] = pfc_calc
    handlers["Cable Tray Sizing"]       = cable_tray_calc
    handlers["Wire Sizing"]             = wire_calc
    handlers["Short Circuit"]      = sc_calc
    handlers["Load Schedule"]      = load_sched_calc
    from calcs.generator_sizing    import calculate as gen_calc
    from calcs.ups_sizing          import calculate as ups_calc
    from calcs.solar_pv            import calculate as solar_calc
    handlers["Generator Sizing"]   = gen_calc
    handlers["UPS Sizing"]         = ups_calc
    handlers["Solar PV System"]    = solar_calc

    # Phase 5 — Fire Protection
    from calcs.fire_sprinkler              import calculate as sprinkler_calc
    from calcs.fire_pump                   import calculate as fire_pump_calc
    from calcs.stairwell_pressurization    import calculate as stairwell_calc
    from calcs.fire_alarm_battery          import calculate as fab_calc
    from calcs.clean_agent_suppression import calculate as clean_agent_calc
    handlers["Fire Sprinkler Hydraulic"]   = sprinkler_calc
    handlers["Fire Pump Sizing"]           = fire_pump_calc
    handlers["Clean Agent Suppression"]    = clean_agent_calc
    handlers["Stairwell Pressurization"]   = stairwell_calc
    handlers["Fire Alarm Battery"]         = fab_calc

    # Phase 6 — Plumbing / Water
    from calcs.domestic_water      import calculate as domestic_water_calc
    from calcs.sewer_drainage      import calculate as sewer_drainage_calc
    from calcs.water_supply_pipe   import calculate as water_supply_calc
    handlers["Domestic Water System"]      = domestic_water_calc
    handlers["Sewer / Drainage"]           = sewer_drainage_calc
    handlers["Water Supply Pipe Sizing"]   = water_supply_calc
    from calcs.septic_tank         import calculate as septic_calc
    handlers["Septic Tank Sizing"]         = septic_calc
    from calcs.grease_trap   import calculate as grease_trap_calc
    from calcs.roof_drain    import calculate as roof_drain_calc
    from calcs.storm_drain   import calculate as storm_drain_calc
    handlers["Grease Trap Sizing"]         = grease_trap_calc
    handlers["Roof Drain Sizing"]          = roof_drain_calc
    handlers["Storm Drain / Stormwater"]   = storm_drain_calc
    from calcs.water_softener  import calculate as water_softener_calc
    from calcs.water_treatment import calculate as water_treatment_calc
    handlers["Water Softener Sizing"]      = water_softener_calc
    handlers["Water Treatment System"]     = water_treatment_calc
    from calcs.wastewater_stp  import calculate as stp_calc
    handlers["Wastewater Treatment (STP)"] = stp_calc

    # Phase 7 — Structural / Lighting / LPS
    from calcs.beam_column          import calculate as beam_column_calc
    from calcs.lighting_design      import calculate as lighting_calc
    from calcs.lightning_protection import calculate as lps_calc
    handlers["Beam / Column Design"]       = beam_column_calc
    handlers["Lighting Design"]            = lighting_calc
    handlers["Lightning Protection (LPS)"] = lps_calc
    from calcs.earthing_grounding    import calculate as earthing_calc
    from calcs.hot_water_demand      import calculate as hw_demand_calc
    from calcs.drainage_pipe_sizing  import calculate as drainage_calc
    handlers["Earthing / Grounding System"] = earthing_calc
    handlers["Hot Water Demand"]            = hw_demand_calc
    handlers["Drainage Pipe Sizing"]        = drainage_calc

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
    handlers["Boiler / Steam System"]  = boiler_calc
    from calcs.bearing_life    import calculate as bearing_calc
    from calcs.bolt_torque     import calculate as bolt_calc
    from calcs.hoist_capacity  import calculate as hoist_calc
    from calcs.elevator_traffic import calculate as elevator_calc
    handlers["Bearing Life (L10)"]     = bearing_calc
    handlers["Bolt Torque & Preload"]  = bolt_calc
    handlers["Hoist Capacity"]         = hoist_calc
    handlers["Elevator Traffic Analysis"] = elevator_calc

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
    from diagrams import pump_curve, psychrometric_chart, duct_chart, harmonic_spectrum
    from diagrams import transformer_sld

    DIAGRAM_HANDLERS = {
        "Pump Sizing (TDH)":          pump_curve.generate,
        "AHU Sizing":                  psychrometric_chart.generate,
        "Duct Sizing":                 duct_chart.generate,
        "Duct Sizing (Equal Friction)": duct_chart.generate,
        "Harmonic Distortion":         harmonic_spectrum.generate,
        "Transformer Sizing":          transformer_sld.generate,   # schemdraw IEC 60617
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


@app.post("/pdf")
def generate_pdf(req: PdfRequest):
    """
    Phase 8d — Server-side vector PDF via weasyprint.
    Accepts the report HTML string, returns a true vector PDF (not a rasterised
    screenshot). Text is selectable and searchable; SVGs remain vector.

    The frontend strips contenteditable spans and no-print elements before
    POSTing, and falls back to html2pdf.js if this endpoint is unavailable.
    """
    from fastapi.responses import Response as FastAPIResponse
    try:
        from weasyprint import HTML, CSS
    except ImportError:
        raise HTTPException(status_code=503, detail="weasyprint not available on this deployment")

    # Base CSS: A4 page, Liberation Sans (installed via fonts-liberation Debian pkg),
    # print-friendly table borders, page numbers in footer via CSS Paged Media.
    base_css = CSS(string="""
        @page {
            size: A4;
            margin: 14mm 14mm 20mm 14mm;
            @bottom-center {
                content: "Page " counter(page) " of " counter(pages);
                font-family: 'Liberation Sans', Arial, sans-serif;
                font-size: 8pt;
                color: #888;
            }
        }
        body {
            font-family: 'Liberation Sans', Arial, Helvetica, sans-serif;
            font-size: 9pt;
            color: #1a1a1a;
            background: #fff;
            margin: 0;
            padding: 0;
        }
        table {
            border-collapse: collapse;
            width: 100%;
            page-break-inside: auto;
        }
        tr  { page-break-inside: avoid; }
        th, td {
            border: 1px solid #ccc;
            padding: 4px 6px;
            font-size: 8.5pt;
        }
        h1  { font-size: 14pt; margin: 0 0 4px 0; }
        h2  { font-size: 11pt; margin: 10px 0 4px 0; page-break-after: avoid; }
        h3  { font-size: 10pt; margin: 8px 0 3px 0;  page-break-after: avoid; }
        .no-print { display: none !important; }
        .editable-field { border-bottom: none !important; text-decoration: none; }
        .result-highlight, .sig-block, .narrative-block {
            page-break-inside: avoid;
        }
    """)

    try:
        pdf_bytes = HTML(string=req.html, base_url=None).write_pdf(stylesheets=[base_css])
    except Exception as e:
        print(f"weasyprint error: {e}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

    # Sanitise filename: keep alphanumeric, hyphens, underscores, dots
    safe_name = "".join(c if c.isalnum() or c in "-_." else "_" for c in req.filename)
    if not safe_name.endswith(".pdf"):
        safe_name += ".pdf"

    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


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

    if phase == "prescriptive":
        from analytics.prescriptive import calculate
        try:
            return calculate(req.inputs)
        except Exception as e:
            print(f"ANALYTICS ERROR [prescriptive]: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

    raise HTTPException(
        status_code=404,
        detail=f"Analytics phase '{phase}' not yet implemented. Available: descriptive, diagnostic, predictive, prescriptive"
    )


@app.get("/analytics/health")
def analytics_health():
    """Returns available analytics phases and their status."""
    return {
        "available_phases": ["descriptive", "diagnostic"],
        "coming_soon": ["predictive", "prescriptive"],
        "standards": ["ISO 14224:2016", "ISO 13381-1:2015", "ISO 55000:2014", "SMRP Metrics"],
    }


# ─── Project Manager Routes (Stage 4) ────────────────────────────────────────
# Mirrors the analytics 4-phase pattern: one endpoint runs all 4 phases and
# returns a combined payload so the front-end makes a single round-trip.
# Standards: PMBOK 7th ed., AACE 17R-97, IDCON 6-Phase, ISO 21500.

@app.post("/project/progress")
def project_progress(req: ProjectRequest):
    """
    Aggregates all 4 project phases into one response.
    Body: { project, items, links, logs, labor_rate_php_per_hour? }
    Returns: { rollup, earned_value, forecast, prescriptive, latest_logs }

    Front-end (project-manager.html) and the edge function `project-progress`
    both call this endpoint. Edge function is a thin proxy that adds CORS +
    auth + Supabase data fetch.
    """
    inputs = {
        "project": req.project,
        "items":   req.items,
        "links":   req.links,
        "logs":    req.logs,
        "labor_rate_php_per_hour": req.labor_rate_php_per_hour,
    }

    out: dict[str, Any] = {}
    try:
        from projects.descriptive import calculate as desc_calc
        out["rollup"] = desc_calc(inputs)
    except Exception as e:
        print(f"PROJECT ERROR [descriptive]: {traceback.format_exc()}")
        out["rollup"] = {"error": str(e)}

    try:
        from projects.diagnostic import calculate as diag_calc
        out["earned_value"] = diag_calc(inputs)
    except Exception as e:
        print(f"PROJECT ERROR [diagnostic]: {traceback.format_exc()}")
        out["earned_value"] = {"available": False, "reason": str(e)}

    try:
        from projects.predictive import calculate as pred_calc
        out["forecast"] = pred_calc(inputs)
    except Exception as e:
        print(f"PROJECT ERROR [predictive]: {traceback.format_exc()}")
        out["forecast"] = {"forecasts": {}, "error": str(e)}

    try:
        from projects.prescriptive import calculate as presc_calc
        presc = presc_calc(inputs)
        # Flatten the prescriptive payload so the front-end can read
        # critical_path / blockers / cycle_warning at the top level
        # (matches the client-side fallback shape — single contract).
        out["critical_path"]         = presc.get("critical_path", {"item_ids": [], "total_days": 0, "slack_per_item": {}})
        out["fast_track_candidates"] = presc.get("fast_track_candidates", [])
        out["blockers"]              = presc.get("blockers", [])
        out["cycle_warning"]         = presc.get("cycle_warning")
    except Exception as e:
        print(f"PROJECT ERROR [prescriptive]: {traceback.format_exc()}")
        out["critical_path"]         = {"item_ids": [], "total_days": 0, "slack_per_item": {}}
        out["fast_track_candidates"] = []
        out["blockers"]              = []
        out["cycle_warning"]         = {"message": str(e)}

    out["latest_logs"] = (req.logs or [])[:10]
    return out


@app.get("/project/health")
def project_health():
    """Returns Project Manager backend status."""
    try:
        import networkx
        nx_status = f"available ({networkx.__version__})"
    except ImportError:
        nx_status = "missing — install via pip"
    return {
        "endpoints": ["/project/progress"],
        "phases": ["descriptive", "diagnostic", "predictive", "prescriptive"],
        "networkx": nx_status,
        "standards": ["PMBOK 7th ed.", "AACE 17R-97", "IDCON 6-Phase", "ISO 21500"],
    }
