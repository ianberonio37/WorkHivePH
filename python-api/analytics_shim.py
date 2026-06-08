"""
analytics_shim.py — minimal local stand-in for main.py's /analytics endpoint.

WHY THIS EXISTS (local dev only): main.py imports the full engineering-calc
stack (fluids, iapws, psychrolib, schemdraw, matplotlib …) at module load, which
stalls/hangs on first import (matplotlib font cache + heavy native libs) and is
entirely unrelated to the Stage-3 Analytics Engine. The /analytics route only
needs the four pure-python+numpy/scipy modules in analytics/. This shim exposes
ONLY /analytics (+ health) so the populated analytics sweep can run locally
without standing up the whole calc microservice.

Run:  python -m uvicorn analytics_shim:app --host 0.0.0.0 --port 8002
The edge fn analytics-orchestrator reaches it via PYTHON_API_URL=host.docker.internal:8002.
NOT for prod — prod uses the real main.py on Render.
"""
import traceback
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="WorkHive Analytics Shim", version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


class AnalyticsRequest(BaseModel):
    phase: str
    inputs: dict[str, Any]


_PHASES = {"descriptive", "diagnostic", "predictive", "prescriptive"}


@app.get("/health")
def health():
    return {"ok": True, "service": "analytics-shim", "phases": sorted(_PHASES)}


@app.get("/analytics/health")
def analytics_health():
    return {"available_phases": sorted(_PHASES), "shim": True}


@app.post("/analytics")
def analytics(req: AnalyticsRequest):
    phase = req.phase.lower().strip()
    if phase not in _PHASES:
        raise HTTPException(status_code=404, detail=f"Unknown phase '{phase}'")
    try:
        mod = __import__(f"analytics.{phase}", fromlist=["calculate"])
        return mod.calculate(req.inputs)
    except Exception as e:  # noqa: BLE001 — surface the traceback to the edge fn log
        print(f"ANALYTICS ERROR [{phase}]: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Analytics error: {e}")
