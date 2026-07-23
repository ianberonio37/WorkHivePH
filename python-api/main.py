"""
Engineering Calc Python API — Phase 0 Foundation
FastAPI microservice that handles engineering calculations with proper
Python libraries. Called by the Supabase Edge Function as a proxy;
returns { not_implemented: true } for calc types not yet migrated so
the Edge Function falls back to its TypeScript handlers.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any
import traceback
import logging
import os
import time

from _auth import require_api_key, api_key_configured

# ─── Structured logging (B1: replaces print()-only error logging) ─────────────
# main.py previously had zero structured logging — every error path used print(),
# which on Railway/Render lands in stdout untagged and unfilterable. Configure a
# real logger so 5xx, auth failures, and slow requests are queryable, and add a
# request-context access log below. Level via LOG_LEVEL env (default INFO).
logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("engcalc-api")

# B1 keystone: warn loudly at startup when the edge↔python shared secret is unset,
# so an unauthenticated compute API is never silently shipped. Enforcement itself
# lives in _auth.require_api_key (applied to every compute route below).
if not api_key_configured():
    logger.warning(
        "PYTHON_API_KEY unset — compute routes are UNAUTHENTICATED. Set PYTHON_API_KEY "
        "on the python service AND in the edge functions to enforce the edge↔python gate."
    )

# numpy is pulled in transitively by the psychrometrics calcs (e.g. HVAC Cooling
# Load). A handler that returns a numpy scalar will 500 /calculate because
# FastAPI's JSON encoder cannot serialize numpy.bool_ (numpy.float64 happens to
# subclass float and is safe, but numpy.bool_ does NOT subclass bool). The 500
# is silent to the user: the Edge Function treats it as "Python unavailable" and
# falls back to its TypeScript handler, so the worker silently gets the
# UNVALIDATED TS value instead of the migrated Python one. Coerce numpy types to
# native at the API boundary so the validated Python engine actually reaches the
# browser. Guarded so the API still loads if numpy is ever absent.
try:
    import numpy as _np
    _NP_SCALARS = (_np.bool_, _np.integer, _np.floating)
except Exception:  # pragma: no cover - numpy is a transitive dep, not guaranteed
    _np = None
    _NP_SCALARS = ()


def _to_jsonable(obj):
    """Recursively coerce numpy scalars/arrays in a calc result to JSON-native
    Python types. No-op for plain dicts/lists/primitives, so it is cheap and safe
    to apply to every handler result before returning it."""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if _np is not None:
        if isinstance(obj, _np.bool_):
            return bool(obj)
        if isinstance(obj, _np.integer):
            return int(obj)
        if isinstance(obj, _np.floating):
            return float(obj)
        if isinstance(obj, _np.ndarray):
            return _to_jsonable(obj.tolist())
    return obj

from fastapi.responses import JSONResponse as _BaseJSONResponse


class SafeJSONResponse(_BaseJSONResponse):
    """Sanitize NaN/Infinity at the response boundary. FastAPI runs jsonable_encoder BEFORE this
    (so numpy floats/arrays are already native by now), then Starlette's json.dumps uses
    allow_nan=False — a single div-by-zero KPI (MTBF on a 0-failure asset, OEE on 0 units) otherwise
    500s the WHOLE analytics response and hangs analytics-orchestrator (no Action Brief renders).
    Replacing NaN/Inf with null here means one edge-case asset never blocks the dashboard."""
    def render(self, content) -> bytes:
        return super().render(_json_safe(content))


app = FastAPI(
    title="Engineering Calc Python API",
    description="Standards-grade engineering calculations for WorkHive Engineering Design",
    version="0.1.0",
    default_response_class=SafeJSONResponse,
)

# CORS — locked to known production origins (B1: was allow_origins=["*"]).
# Mirrors supabase/functions/_shared/cors.ts: apex + www production, plus a
# comma-separated ALLOWED_ORIGIN env for staging/preview, plus localhost/127.*
# (any port) for local dev via regex. Server-to-server edge calls send no Origin
# header so are unaffected; this only constrains browser-origin requests
# (the direct /pdf and /tts/* frontend calls).
_PROD_ORIGINS = ["https://workhiveph.com", "https://www.workhiveph.com"]
_EXTRA_ORIGINS = [o.strip() for o in os.environ.get("ALLOWED_ORIGIN", "").split(",") if o.strip()]
ALLOWED_ORIGINS = _PROD_ORIGINS + _EXTRA_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    """Per-request structured access log: method, path, status, latency. 5xx logs
    at ERROR (queryable failures); slow/normal at INFO. Replaces the silent void
    where main.py had no request observability at all (B1, I5/I6)."""
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("unhandled error %s %s", request.method, request.url.path)
        raise
    dur_ms = (time.monotonic() - start) * 1000
    level = logging.ERROR if response.status_code >= 500 else logging.INFO
    logger.log(level, "%s %s -> %s (%.1fms)", request.method, request.url.path,
               response.status_code, dur_ms)
    return response


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


class ZScoreRequest(BaseModel):
    values: list[float]                         # the reading window (most-recent first)
    latest: float | None = None                 # defaults to values[0]
    z_anomaly: float | None = None              # override the 3-sigma anomaly threshold
    z_warning: float | None = None              # override the 2-sigma warning threshold


class ProjectRequest(BaseModel):
    project: dict[str, Any]                    # the projects row
    items: list[dict[str, Any]] = []           # project_items rows
    links: list[dict[str, Any]] = []           # project_links rows
    logs:  list[dict[str, Any]] = []           # project_progress_logs rows (last ~30)
    roles: list[dict[str, Any]] = []           # project_roles rows (Phase 5B)
    change_orders: list[dict[str, Any]] = []   # project_change_orders rows (Phase 5D)
    labor_rate_php_per_hour: float | None = None  # optional override; default 200
    daily_hours: int | None = None              # for resource leveling; default 8


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
def calculate(req: CalcRequest, _auth: None = Depends(require_api_key)):
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
        return {"results": _to_jsonable(results)}
    except ValueError as e:
        # Input validation errors — surface as 422 so the Edge Function
        # can include the message in the error response to the frontend
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # Unexpected errors — log the trace, return 500
        logger.error(f"ERROR in {req.calc_type}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Calculation error: {str(e)}")


@app.post("/diagram")
def diagram(req: DiagramRequest):
    # NOTE: intentionally NOT api-key-gated — /diagram is called BROWSER-DIRECT
    # (engineering-design.html -> onrender.com/diagram), same class as /pdf and
    # /tts/*. A browser cannot hold a server secret, so these are controlled by
    # the CORS origin lockdown above, not the edge↔python shared-secret gate.
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
        logger.error(f"DIAGRAM ERROR {req.diagram_type}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Diagram error: {str(e)}")


@app.post("/sensors/zscore")
def sensors_zscore(req: ZScoreRequest):
    # NOTE: intentionally NOT api-key-gated — pure stateless compute (no DB, no secret), same
    # browser-direct class as /diagram and /tts. Access is controlled by the CORS origin lockdown.
    """
    Pure-compute 3-sigma Z-score anomaly check on a caller-supplied reading window.
    The plant-side anomaly handler fetches readings from the DB then runs this same math;
    this route exposes the deterministic core so a client can check its own array (no DB).
    Returns { n, mean, std, latest, z, anomaly, warning, diagnostic }.
    """
    from sensors.anomaly import zscore_compute
    try:
        return _to_jsonable(zscore_compute(req.values, req.latest, req.z_anomaly, req.z_warning))
    except Exception as e:
        logger.error(f"ZSCORE ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=f"zscore error: {str(e)}")


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
        logger.error(f"weasyprint error: {e}")
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

def _json_safe(obj):
    """Recursively replace NaN / Infinity floats with None. Starlette's JSONResponse serializes
    with allow_nan=False, so a single div-by-zero KPI (MTBF on a 0-failure asset, OEE on 0 units)
    raised 'Out of range float values are not JSON compliant' — 500-ing the WHOLE analytics call and
    hanging analytics-orchestrator (no Action Brief). Sanitize at the API boundary so one edge-case
    asset never blocks the dashboard."""
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


@app.post("/analytics")
def analytics(req: AnalyticsRequest, _auth: None = Depends(require_api_key)):
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
            return _json_safe(calculate(req.inputs))
        except Exception as e:
            logger.error(f"ANALYTICS ERROR [descriptive]: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

    if phase == "diagnostic":
        from analytics.diagnostic import calculate
        try:
            return _json_safe(calculate(req.inputs))
        except Exception as e:
            logger.error(f"ANALYTICS ERROR [diagnostic]: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

    if phase == "predictive":
        from analytics.predictive import calculate
        try:
            return _json_safe(calculate(req.inputs))
        except Exception as e:
            logger.error(f"ANALYTICS ERROR [predictive]: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

    if phase == "prescriptive":
        from analytics.prescriptive import calculate
        try:
            return _json_safe(calculate(req.inputs))
        except Exception as e:
            logger.error(f"ANALYTICS ERROR [prescriptive]: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Analytics error: {str(e)}")

    raise HTTPException(
        status_code=404,
        detail=f"Analytics phase '{phase}' not yet implemented. Available: descriptive, diagnostic, predictive, prescriptive"
    )


# ─── Reliability Engineering Workbench (Phase R.5) ───────────────────────────
# Standards: IEC 61649 (Weibull analysis), MIL-HDBK-189C, SAE JA1011/JA1012.
# The edge fn weibull-fitter posts a list of failure durations and right-censored
# survivals; we proxy to lifelines.WeibullFitter and return the v_weibull_truth shape.

class WeibullRequest(BaseModel):
    failures: list[float] = []     # days-to-failure (one per observed failure)
    censored: list[float] = []     # days-survived for right-censored assets


@app.post("/reliability/weibull")
def reliability_weibull(req: WeibullRequest, _auth: None = Depends(require_api_key)):
    """Fit a 2-parameter Weibull from failure + censored durations.

    Returns the v_weibull_truth contract (beta, eta_days, failure_pattern,
    n_failures, n_censored, log_likelihood, fit_method, diagnostic).
    Insufficient-data cases return failure_pattern='insufficient_data' with
    a 200 (the orchestrator persists this so the UI can warn the user).
    """
    try:
        from reliability.weibull import fit_weibull
        return fit_weibull(req.failures, req.censored)
    except Exception as e:
        logger.error(f"WEIBULL ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Weibull fit error: {str(e)}")


class PFRequest(BaseModel):
    readings:        list[dict[str, Any]] = []   # [{ts, value}, ...]
    p_threshold:     float
    f_threshold:     float
    direction:       str = "above"               # "above" | "below"
    safety_critical: bool = False


@app.post("/reliability/pf-interval")
def reliability_pf_interval(req: PFRequest, _auth: None = Depends(require_api_key)):
    """Compute P-F interval + recommended inspection cadence per RCM rule.

    Returns the pf_intervals row shape (pf_days, recommended_interval_days,
    basis, n_pairs, pairs, diagnostic). When no pair is detectable the
    edge fn does NOT persist (pf_intervals.pf_days has CHECK > 0); the UI
    surfaces the diagnostic instead.
    """
    try:
        from reliability.pf_interval import calculate_pf
        return calculate_pf(
            readings=req.readings,
            p_threshold=req.p_threshold,
            f_threshold=req.f_threshold,
            direction=req.direction,
            safety_critical=req.safety_critical,
        )
    except Exception as e:
        logger.error(f"PF ERROR: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"P-F interval error: {str(e)}")


@app.get("/reliability/health")
def reliability_health():
    """Returns Reliability Workbench backend status."""
    try:
        import lifelines
        ll_status = f"available ({lifelines.__version__})"
    except ImportError:
        ll_status = "missing — install lifelines via pip"
    return {
        "endpoints":  ["/reliability/weibull", "/reliability/pf-interval"],
        "lifelines":  ll_status,
        "standards":  ["IEC 61649", "MIL-HDBK-189C", "SAE JA1011", "SAE JA1012"],
    }


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
def project_progress(req: ProjectRequest, _auth: None = Depends(require_api_key)):
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
        "roles":   req.roles,
        "change_orders": req.change_orders,
        "labor_rate_php_per_hour": req.labor_rate_php_per_hour,
        "daily_hours": req.daily_hours or 8,
    }

    out: dict[str, Any] = {}
    try:
        from projects.descriptive import calculate as desc_calc
        out["rollup"] = desc_calc(inputs)
    except Exception as e:
        logger.error(f"PROJECT ERROR [descriptive]: {traceback.format_exc()}")
        out["rollup"] = {"error": str(e)}

    try:
        from projects.diagnostic import calculate as diag_calc
        out["earned_value"] = diag_calc(inputs)
    except Exception as e:
        logger.error(f"PROJECT ERROR [diagnostic]: {traceback.format_exc()}")
        out["earned_value"] = {"available": False, "reason": str(e)}

    try:
        from projects.predictive import calculate as pred_calc
        out["forecast"] = pred_calc(inputs)
    except Exception as e:
        logger.error(f"PROJECT ERROR [predictive]: {traceback.format_exc()}")
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
        logger.error(f"PROJECT ERROR [prescriptive]: {traceback.format_exc()}")
        out["critical_path"]         = {"item_ids": [], "total_days": 0, "slack_per_item": {}}
        out["fast_track_candidates"] = []
        out["blockers"]              = []
        out["cycle_warning"]         = {"message": str(e)}

    # Phase 5A — Resource histogram + overload flags
    try:
        from projects.resources import calculate as res_calc
        out["resources"] = res_calc(inputs)
    except Exception as e:
        logger.error(f"PROJECT ERROR [resources]: {traceback.format_exc()}")
        out["resources"] = {"error": str(e)}

    # Phase 5B/5D pass-through — roles and change_orders are loaded by the
    # edge fn and surfaced here so the front-end can render them.
    out["roles"]         = req.roles or []
    out["change_orders"] = req.change_orders or []

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


# ─── ML Endpoints (Stage 1: GBM Failure Classifier) ──────────────────────────

class MLTrainRequest(BaseModel):
    inputs: dict[str, Any]  # logbook_entries, pm_completions, pm_scope_items, inv_transactions


class MLPredictRequest(BaseModel):
    features: dict[str, Any]  # FEATURE_COLS dict for single-asset prediction


@app.post("/ml/train")
def ml_train(req: MLTrainRequest, _auth: None = Depends(require_api_key)):
    """
    Triggered weekly by pg_cron -> trigger-ml-retrain edge function.
    Builds feature matrix from all hive logbook data and retrains GBM.
    Returns training report including recall, n_samples, and data_warning.
    """
    try:
        from ml.feature_engineering import build_feature_matrix
        from ml.trainer import train

        df = build_feature_matrix(
            logbook=req.inputs.get("logbook_entries", []),
            pm_completions=req.inputs.get("pm_completions", []),
            pm_scope_items=req.inputs.get("pm_scope_items", []),
            inv_transactions=req.inputs.get("inv_transactions", []),
        )
        result = train(df)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML train error: {traceback.format_exc()}")


@app.post("/ml/predict")
def ml_predict(req: MLPredictRequest, _auth: None = Depends(require_api_key)):
    """
    Single-asset risk prediction. Called by batch-risk-scoring edge function.
    Returns risk_score (0-1), risk_level, model_version, recall, data_warning.
    Falls back to rules-v1 scoring when GBM artifact does not yet exist.
    """
    try:
        from ml.trainer import predict
        return predict(req.features)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ML predict error: {traceback.format_exc()}")


@app.get("/ml/status")
def ml_status():
    """Returns current model version, training metadata, and feature list."""
    try:
        from ml.trainer import get_model_meta
        from ml.feature_engineering import FEATURE_COLS
        meta = get_model_meta()
        return {**meta, "feature_cols": FEATURE_COLS}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# ─── TTS — Edge TTS (free, natural Microsoft Neural voices) ───────────────────
# Same pattern as video_marketing_app/app.py. The Edge TTS catalog includes
# en-PH-JamesNeural + en-PH-RosaNeural (Microsoft's voice catalog names —
# unrelated to WorkHive's persona labels after the 2026-05-20 rename to
# hezekiah/zaniah). These voices DO NOT exist in the Azure Speech API
# en-PH catalog. No auth, no subscription, just a websocket call to
# Microsoft's Edge browser TTS.
#
# Cache: sha256(voice::text) keys a local MP3 file under .tmp/wh_tts_cache/.
# Repeat narration hits the disk cache instantly. Cache survives across
# python-api restarts.

import hashlib
import os
import re as _re
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
from pathlib import Path as _Path

from fastapi.responses import FileResponse

_TTS_CACHE_DIR = _Path(__file__).parent.parent / ".tmp" / "wh_tts_cache"
_TTS_VOICES = {
    "hezekiah": "en-PH-JamesNeural",  # WorkHive persona key → Microsoft voice
    "zaniah":   "en-PH-RosaNeural",
}
# Legacy aliases: pre-rename clients send 'james'/'rosa'; map silently so
# in-flight requests during the 30-day cache-cycle window don't 400.
_TTS_LEGACY_ALIASES = {
    "james": "hezekiah",
    "rosa":  "zaniah",
}
_MAX_TTS_CHARS  = 1500
_EDGE_TIMEOUT_S = 60

def _find_edge_tts_exe() -> str | None:
    """Locate the edge-tts CLI. Prefers the venv's Scripts dir, then PATH.
    Mirrors tools/tts_engine.py without the cross-directory import."""
    cli = _shutil.which("edge-tts")
    if cli:
        return cli
    scripts_dir = _Path(_sys.executable).parent / "Scripts"
    candidate = scripts_dir / "edge-tts.exe"
    if candidate.exists():
        return str(candidate)
    return None

def _generate_tts_edge(text: str, voice_id: str, out_path: _Path) -> None:
    """One subprocess call to Microsoft Edge TTS. Raises on failure."""
    edge_exe = _find_edge_tts_exe()
    if not edge_exe:
        raise RuntimeError("edge-tts CLI not installed (pip install edge-tts)")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        try: out_path.unlink()
        except OSError: pass
    cmd = [edge_exe, "--voice", voice_id, "--text", text, "--write-media", str(out_path)]
    try:
        result = _subprocess.run(cmd, capture_output=True, text=True, timeout=_EDGE_TIMEOUT_S)
    except _subprocess.TimeoutExpired:
        raise RuntimeError(f"edge-tts timed out after {_EDGE_TIMEOUT_S}s")
    if result.returncode != 0:
        raise RuntimeError(f"edge-tts rc={result.returncode}: {(result.stderr or '').strip()[-200:]}")
    if not out_path.exists() or out_path.stat().st_size <= 1000:
        raise RuntimeError("edge-tts produced empty / truncated MP3")


class TtsRequest(BaseModel):
    text:    str
    persona: str = "zaniah"


@app.post("/tts/speak")
def tts_speak(req: TtsRequest):
    """Generate (or serve from cache) an Edge-TTS MP3 for the given text +
    persona. Returns the cache key — the frontend then fetches the MP3
    bytes from /tts/audio/{key}.mp3 (or pulls the JSON URL pattern that
    tts-speak edge function expects)."""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    if len(text) > _MAX_TTS_CHARS:
        raise HTTPException(
            status_code=413,
            detail=f"text too long (max {_MAX_TTS_CHARS} chars)",
        )
    persona_key = (req.persona or "zaniah").strip().lower()
    persona_key = _TTS_LEGACY_ALIASES.get(persona_key, persona_key)
    if persona_key not in _TTS_VOICES:
        persona_key = "zaniah"
    voice_id = _TTS_VOICES[persona_key]

    _TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(f"{voice_id}::{text}".encode("utf-8")).hexdigest()
    mp3_path  = _TTS_CACHE_DIR / f"{cache_key}.mp3"

    cached = mp3_path.exists() and mp3_path.stat().st_size > 1000
    if not cached:
        try:
            _generate_tts_edge(text, voice_id, mp3_path)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Edge TTS failed: {exc}")

    return {
        "cache_key": cache_key,
        "voice":     voice_id,
        "persona":   persona_key,
        "cached":    cached,
        "url":       f"/tts/audio/{cache_key}.mp3",
    }


@app.get("/tts/audio/{filename}")
def tts_audio(filename: str):
    """Serve a previously-generated MP3. Filename is the sha256 cache key
    plus .mp3 — anything else 404s."""
    # Defence-in-depth: reject filenames that don't look like our cache keys.
    if not _re.fullmatch(r"[a-f0-9]{64}\.mp3", filename):
        raise HTTPException(status_code=404, detail="not found")
    mp3_path = _TTS_CACHE_DIR / filename
    if not mp3_path.exists():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(
        path=str(mp3_path),
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.get("/tts/health")
def tts_health():
    """Sanity check — confirms edge-tts CLI is installed and the cache dir
    is writable. Frontend can poll this before showing 'Voice On' state."""
    edge_exe = _find_edge_tts_exe()
    _TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return {
        "status":         "ok" if edge_exe else "degraded",
        "edge_tts":       bool(edge_exe),
        "cache_dir":      str(_TTS_CACHE_DIR),
        "cached_files":   sum(1 for _ in _TTS_CACHE_DIR.glob("*.mp3")) if _TTS_CACHE_DIR.exists() else 0,
        "voices":         _TTS_VOICES,
    }
