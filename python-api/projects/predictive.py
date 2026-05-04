"""
Project Manager — Predictive Phase
Estimate at Completion (EAC), Estimate to Complete (ETC), forecast finish date.

Standards:
    PMBOK 7th ed. — EVM forecasting formulas (chapter on Performance Domain).
    AACE 80R-13 §4.6 — Forecasting cost and schedule at completion.

Formulas:
    EAC  = AC + (BAC - EV) / CPI                Estimate at Completion (cost-performance basis)
    EAC' = AC + (BAC - EV) / (CPI × SPI)        Combined index (more pessimistic)
    ETC  = EAC - AC                              Estimate to Complete
    VAC  = BAC - EAC                             Variance at Completion

For schedule forecast we fit an OLS line on the daily progress logs and
project the finish date as the date when the trend hits 100%. statsmodels
provides confidence-interval bounds (used as a P50/P80 proxy until a full
Monte Carlo lands in Phase 5).
"""

from datetime import datetime, timezone, timedelta


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def calculate(inputs: dict) -> dict:
    project = inputs.get("project") or {}
    items   = inputs.get("items")   or []
    logs    = inputs.get("logs")    or []

    # Need budget + start date for cost forecast; need progress logs for schedule forecast.
    BAC = float(project.get("budget_php") or 0)
    has_budget_dates = BAC > 0 and project.get("start_date") and project.get("end_date")

    forecasts = {}

    # ── Cost forecast (EVM) ──────────────────────────────────────────────
    if has_budget_dates:
        from .diagnostic import calculate as diag_calc
        diag = diag_calc(inputs)
        if diag.get("available"):
            EV = diag["ev"]
            AC = diag["ac"]
            CPI = diag["cpi"]
            SPI = diag["spi"]
            EAC_cpi = AC + (BAC - EV) / CPI if CPI and CPI > 0 else None
            EAC_combined = AC + (BAC - EV) / (CPI * SPI) if CPI and SPI and CPI > 0 and SPI > 0 else None
            ETC = (EAC_cpi - AC) if EAC_cpi is not None else None
            VAC = (BAC - EAC_cpi) if EAC_cpi is not None else None
            forecasts["cost"] = {
                "eac_cpi":      round(EAC_cpi) if EAC_cpi is not None else None,
                "eac_combined": round(EAC_combined) if EAC_combined is not None else None,
                "etc":          round(ETC) if ETC is not None else None,
                "vac":          round(VAC) if VAC is not None else None,
            }

    # ── Schedule forecast (OLS trend on progress logs) ────────────────────
    if len(logs) >= 3:
        try:
            forecasts["schedule"] = _forecast_finish_date(logs, project)
        except Exception as e:
            forecasts["schedule"] = {"available": False, "reason": f"trend fit failed: {e}"}
    else:
        forecasts["schedule"] = {
            "available": False,
            "reason": f"Need at least 3 progress logs (have {len(logs)})",
        }

    return {"forecasts": forecasts}


def _forecast_finish_date(logs: list[dict], project: dict) -> dict:
    """Fit y = mx + b on (days_since_start, pct_complete) and project to 100."""
    import numpy as np
    try:
        import statsmodels.api as sm
        have_sm = True
    except ImportError:
        have_sm = False

    start = _parse_date(project.get("start_date"))
    if not start:
        return {"available": False, "reason": "Project start_date missing"}

    pts = []
    for l in logs:
        d = _parse_date(l.get("log_date"))
        pct = l.get("pct_complete")
        if d and pct is not None:
            days = (d - start).total_seconds() / 86400
            if days >= 0:
                pts.append((days, float(pct)))

    if len(pts) < 3:
        return {"available": False, "reason": "Insufficient log points after parse"}

    pts.sort()
    xs = np.array([p[0] for p in pts])
    ys = np.array([p[1] for p in pts])

    if have_sm:
        X = sm.add_constant(xs)
        model = sm.OLS(ys, X).fit()
        intercept, slope = model.params
        # Forecast: (100 - intercept) / slope days from start
        if slope > 0:
            days_to_100 = (100 - intercept) / slope
            finish = start + timedelta(days=days_to_100)
            # P80 confidence: predict_mean_se gives standard error; use ±1.28σ for 80%
            try:
                resid_std = float(np.std(model.resid))
                slope_se = float(model.bse[1])
                # Sensitivity: small variation in slope => earlier/later finish
                if slope_se > 0 and slope > slope_se:
                    p80_late_slope = max(slope - 1.28 * slope_se, slope * 0.5)
                    days_p80_late  = (100 - intercept) / p80_late_slope
                    finish_p80 = start + timedelta(days=days_p80_late)
                else:
                    finish_p80 = None
            except Exception:
                finish_p80 = None
                resid_std = None
            return {
                "available": True,
                "method": "OLS trend (statsmodels)",
                "slope_pct_per_day": round(slope, 3),
                "intercept": round(intercept, 1),
                "finish_p50": finish.date().isoformat(),
                "finish_p80": finish_p80.date().isoformat() if finish_p80 else None,
                "residual_std": round(resid_std, 2) if resid_std else None,
                "logs_used": len(pts),
            }
        else:
            return {
                "available": False,
                "reason": "Progress trend is flat or negative — needs more recent logs to forecast",
            }
    # Fallback: numpy polyfit if statsmodels not installed
    slope, intercept = np.polyfit(xs, ys, 1)
    if slope <= 0:
        return {"available": False, "reason": "Progress trend non-positive"}
    days_to_100 = (100 - intercept) / slope
    finish = start + timedelta(days=days_to_100)
    return {
        "available": True,
        "method": "numpy polyfit",
        "slope_pct_per_day": round(float(slope), 3),
        "finish_p50": finish.date().isoformat(),
        "finish_p80": None,
        "logs_used": len(pts),
    }
