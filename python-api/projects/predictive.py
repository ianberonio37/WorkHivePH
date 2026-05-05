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
    # ── Schedule risk via Monte Carlo (Phase 5C) ──────────────────────
    # Triangular distribution per item:
    #   optimistic   = 0.7 × planned duration
    #   most_likely  = planned duration
    #   pessimistic  = 1.5 × planned duration
    # Propagate through the DAG 1000 times; report P50/P80/P95 finish.
    if len(items) > 0:
        try:
            forecasts["schedule_risk"] = _monte_carlo_schedule(items)
        except Exception as e:
            forecasts["schedule_risk"] = {"available": False, "reason": f"Monte Carlo failed: {e}"}


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


def _monte_carlo_schedule(items: list[dict], n_runs: int = 1000) -> dict:
    """
    Phase 5C — Schedule risk via Monte Carlo.

    For each scope item:
      - optimistic  = 0.7 × planned duration
      - most_likely = planned duration
      - pessimistic = 1.5 × planned duration

    Each run samples a duration from numpy's triangular() per item, propagates
    through the DAG (max of predecessor finishes), and returns the project
    finish day. From 1000 runs we extract P50/P80/P95 percentiles.

    Standards: PMI Practice Standard for Scheduling §6 (schedule risk),
    AACE 65R-11 (Risk Analysis and Contingency Determination).
    """
    try:
        import numpy as np
    except ImportError:
        return {"available": False, "reason": "numpy not installed"}

    by_id = {it.get("id"): it for it in items if it.get("id")}
    if not by_id:
        return {"available": False, "reason": "No items with ids"}

    def _dur(it):
        ds, de = _parse_date(it.get("planned_start")), _parse_date(it.get("planned_end"))
        if ds and de:
            return max(1, (de - ds).days + 1)
        if it.get("estimated_hours"):
            from math import ceil
            return max(1, ceil(float(it["estimated_hours"]) / 8))
        return 1

    # Topological order via predecessors.
    # Simple Kahn's algorithm; cycles fall back to file order (CPM module
    # already surfaces cycle warnings via prescriptive.py).
    in_degree = {iid: 0 for iid in by_id}
    for it in items:
        for p in (it.get("predecessors") or []):
            if p in by_id and it.get("id") in in_degree:
                in_degree[it.get("id")] += 1
    queue = [iid for iid, d in in_degree.items() if d == 0]
    topo: list[str] = []
    visited: set[str] = set()
    while queue:
        n = queue.pop(0)
        if n in visited:
            continue
        visited.add(n)
        topo.append(n)
        for m_iid, m_it in by_id.items():
            if n in (m_it.get("predecessors") or []) and m_iid not in visited:
                in_degree[m_iid] -= 1
                if in_degree[m_iid] <= 0:
                    queue.append(m_iid)
    # If cycle, fallback to original order
    for iid in by_id:
        if iid not in visited:
            topo.append(iid)

    finishes = []
    for _ in range(n_runs):
        ef: dict[str, float] = {}
        for iid in topo:
            it = by_id[iid]
            d = _dur(it)
            sampled = float(np.random.triangular(0.7 * d, float(d), 1.5 * d))
            preds = [p for p in (it.get("predecessors") or []) if p in by_id]
            es = max((ef[p] for p in preds), default=0.0)
            ef[iid] = es + sampled
        finishes.append(max(ef.values()) if ef else 0)

    arr = np.array(finishes)
    return {
        "available": True,
        "method": "Monte Carlo (1000 runs, triangular 0.7×/1.0×/1.5× planned)",
        "n_runs": n_runs,
        "p50_days": round(float(np.percentile(arr, 50)), 1),
        "p80_days": round(float(np.percentile(arr, 80)), 1),
        "p95_days": round(float(np.percentile(arr, 95)), 1),
        "min_days": round(float(arr.min()), 1),
        "max_days": round(float(arr.max()), 1),
        "mean_days": round(float(arr.mean()), 1),
        "std_days": round(float(arr.std()), 1),
    }


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
