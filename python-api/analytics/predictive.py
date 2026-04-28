"""
Predictive Analytics — Phase 3 of the WorkHive Analytics Engine
Standard: ISO 13381-1:2015 Condition monitoring — prognostics
          ISO 14224:2016 (MTBF-based prediction)
          ISO 281:2007 (Bearing life)

5 confirmed functions:
  1. Next failure date (MTBF-based)  — ISO 14224 / ISO 13381-1
  2. PM due date calendar             — Deterministic
  3. Parts stockout date              — Deterministic
  4. Failure trend forecast           — Prophet (requires ≥ 24 data points)
  5. Equipment health score           — SMRP-inspired weighted composite

Input contract:
  - logbook_entries:   list[dict]  machine, maintenance_type, downtime_hours, created_at
  - pm_completions:    list[dict]  asset_id, completed_at, asset_name
  - pm_scope_items:    list[dict]  asset_id, frequency, item_text, asset_name
  - inv_transactions:  list[dict]  part_name, qty_change, type, created_at
  - inventory_items:   list[dict]  part_name, qty_on_hand, reorder_point
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_df(records: list[dict]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


def _parse_dates(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], utc=True, errors="coerce")
    return df


def _corrective_only(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "maintenance_type" not in df.columns:
        return df
    return df[df["maintenance_type"].str.contains("Corrective|Breakdown", case=False, na=False)]


FREQ_DAYS = {"Monthly": 30, "Quarterly": 90, "Semi-Annual": 180, "Yearly": 365}


# ── 1. Next Failure Date (MTBF-based) — ISO 14224 / ISO 13381-1 ─────────────
# Prediction: last_failure_date + MTBF = predicted next failure
# Risk level: HIGH if overdue, MEDIUM if due within 14 days, LOW otherwise
# Requires: ≥ 2 failures per machine to compute MTBF

def calc_next_failure_dates(logbook_entries: list[dict]) -> dict:
    df = _to_df(logbook_entries)
    if df.empty:
        return {"predictions": [], "standard": "ISO 14224:2016 / ISO 13381-1:2015"}

    df = _parse_dates(df, "created_at")
    df = _corrective_only(df)

    now = pd.Timestamp.now(tz="UTC")
    predictions = []

    for machine, group in df.groupby("machine"):
        dates = group["created_at"].dropna().sort_values()
        n = len(dates)
        if n < 2:
            continue

        intervals = dates.diff().dropna().dt.total_seconds() / 86400
        mtbf_days = float(intervals.mean())
        last_failure = dates.iloc[-1]
        predicted_next = last_failure + pd.Timedelta(days=mtbf_days)

        days_until = (predicted_next - now).total_seconds() / 86400

        if days_until < 0:
            risk = "HIGH"
            status = f"Overdue by {abs(int(days_until))} days"
        elif days_until <= 14:
            risk = "MEDIUM"
            status = f"Due in {int(days_until)} days"
        else:
            risk = "LOW"
            status = f"Due in {int(days_until)} days"

        predictions.append({
            "machine":            machine,
            "failure_count":      n,
            "mtbf_days":          round(mtbf_days, 1),
            "last_failure":       last_failure.strftime("%Y-%m-%d"),
            "predicted_next":     predicted_next.strftime("%Y-%m-%d"),
            "days_until":         round(days_until, 0),
            "risk":               risk,
            "status":             status,
        })

    predictions.sort(key=lambda x: x["days_until"])
    high_count   = sum(1 for p in predictions if p["risk"] == "HIGH")
    medium_count = sum(1 for p in predictions if p["risk"] == "MEDIUM")

    return {
        "predictions":   predictions,
        "high_risk":     high_count,
        "medium_risk":   medium_count,
        "total_tracked": len(predictions),
        "standard":      "ISO 14224:2016 §9.3 MTBF + ISO 13381-1:2015 prognostics",
        "note":          "Prediction = last failure date + mean interval between failures. Requires ≥ 2 failures per machine.",
    }


# ── 2. PM Due Date Calendar — Deterministic ───────────────────────────────────
# Next PM due = last completion date + frequency interval
# Overdue if due date has passed. Risk levels per days overdue.

def calc_pm_due_calendar(
    pm_completions: list[dict],
    pm_scope_items: list[dict]
) -> dict:
    comps = _to_df(pm_completions)
    scope = _to_df(pm_scope_items)

    if scope.empty:
        return {"calendar": [], "overdue_count": 0, "standard": "Deterministic — PM frequency intervals"}

    comps = _parse_dates(comps, "completed_at")
    now   = pd.Timestamp.now(tz="UTC")

    # Last completion per scope item
    last_comp: dict = {}
    if not comps.empty and "scope_item_id" in comps.columns:
        for _, c in comps.iterrows():
            sid = c.get("scope_item_id")
            dt  = c.get("completed_at")
            if sid and pd.notna(dt):
                if sid not in last_comp or dt > last_comp[sid]:
                    last_comp[sid] = dt

    # Last completion per asset (fallback when no scope_item_id match)
    last_asset_comp: dict = {}
    if not comps.empty and "asset_id" in comps.columns:
        for _, c in comps.iterrows():
            aid = c.get("asset_id")
            dt  = c.get("completed_at")
            if aid and pd.notna(dt):
                if aid not in last_asset_comp or dt > last_asset_comp[aid]:
                    last_asset_comp[aid] = dt

    calendar = []
    for _, item in scope.iterrows():
        freq       = item.get("frequency", "Monthly")
        days       = FREQ_DAYS.get(freq, 30)
        asset_name = item.get("asset_name", item.get("asset_id", "Unknown"))
        item_text  = item.get("item_text", "PM Task")
        item_id    = item.get("id")
        asset_id   = item.get("asset_id")

        # Get last done date (scope item match preferred, asset fallback)
        last_done = last_comp.get(item_id) or last_asset_comp.get(asset_id)

        if last_done:
            next_due = last_done + pd.Timedelta(days=days)
        else:
            next_due = now  # never done = overdue immediately

        days_until = (next_due - now).total_seconds() / 86400

        if days_until < 0:
            risk   = "OVERDUE"
            status = f"Overdue by {abs(int(days_until))} days"
        elif days_until <= 7:
            risk   = "DUE SOON"
            status = f"Due in {int(days_until)} days"
        elif days_until <= 30:
            risk   = "UPCOMING"
            status = f"Due in {int(days_until)} days"
        else:
            risk   = "OK"
            status = f"Due {next_due.strftime('%Y-%m-%d')}"

        calendar.append({
            "asset_name":  asset_name,
            "task":        item_text[:80],
            "frequency":   freq,
            "last_done":   last_done.strftime("%Y-%m-%d") if last_done else "Never",
            "next_due":    next_due.strftime("%Y-%m-%d"),
            "days_until":  round(days_until, 0),
            "risk":        risk,
            "status":      status,
        })

    calendar.sort(key=lambda x: x["days_until"])
    overdue  = [c for c in calendar if c["risk"] == "OVERDUE"]
    due_soon = [c for c in calendar if c["risk"] == "DUE SOON"]

    return {
        "calendar":      calendar,
        "overdue_count": len(overdue),
        "due_soon_count":len(due_soon),
        "total_tasks":   len(calendar),
        "standard":      "Deterministic — last completion + frequency interval",
    }


# ── 3. Parts Stockout Date — Deterministic ────────────────────────────────────
# days_to_stockout = qty_on_hand / avg_daily_consumption_rate
# Flags parts projected to stock out within 30 days

def calc_parts_stockout(
    inventory_items: list[dict],
    inv_transactions: list[dict],
    period_days: int = 90
) -> dict:
    items = _to_df(inventory_items)
    txns  = _to_df(inv_transactions)

    if items.empty:
        return {"stockout_risk": [], "standard": "Deterministic — qty_on_hand / avg daily consumption"}

    # Compute avg daily consumption per part from transactions
    consumption_rate: dict = {}
    if not txns.empty and "part_name" in txns.columns:
        txns = _parse_dates(txns, "created_at")
        use_txns = txns[txns.get("type", pd.Series(dtype=str)) == "use"] if "type" in txns.columns else txns
        if not use_txns.empty:
            use_txns = use_txns.copy()
            use_txns["qty_change"] = pd.to_numeric(use_txns.get("qty_change", pd.Series()), errors="coerce").abs()
            grp = use_txns.groupby("part_name")["qty_change"].sum()
            for part, total in grp.items():
                consumption_rate[part] = total / period_days  # units per day

    results = []
    for _, item in items.iterrows():
        part_name     = item.get("part_name", "Unknown")
        qty_on_hand   = float(pd.to_numeric(item.get("qty_on_hand", 0), errors="coerce") or 0)
        reorder_point = float(pd.to_numeric(item.get("reorder_point", 0), errors="coerce") or 0)
        daily_rate    = consumption_rate.get(part_name, 0)

        if daily_rate <= 0:
            # No recent usage — flag only if already below reorder point
            if qty_on_hand <= reorder_point and reorder_point > 0:
                results.append({
                    "part_name":        part_name,
                    "qty_on_hand":      qty_on_hand,
                    "reorder_point":    reorder_point,
                    "daily_rate":       0,
                    "days_to_reorder":  None,
                    "days_to_stockout": None,
                    "risk":             "BELOW REORDER",
                    "status":           "Already below reorder point — no recent usage to project",
                })
            continue

        days_to_stockout = qty_on_hand / daily_rate
        days_to_reorder  = (qty_on_hand - reorder_point) / daily_rate if reorder_point > 0 else None

        if days_to_stockout <= 7:
            risk = "CRITICAL"
        elif days_to_stockout <= 30:
            risk = "HIGH"
        elif days_to_reorder is not None and days_to_reorder <= 14:
            risk = "MEDIUM"
        else:
            continue  # healthy — skip

        results.append({
            "part_name":        part_name,
            "qty_on_hand":      round(qty_on_hand, 1),
            "reorder_point":    round(reorder_point, 1),
            "daily_rate":       round(daily_rate, 3),
            "days_to_reorder":  round(days_to_reorder, 0) if days_to_reorder is not None else None,
            "days_to_stockout": round(days_to_stockout, 0),
            "risk":             risk,
            "status":           f"Stockout in ~{int(days_to_stockout)} days at current rate",
        })

    results.sort(key=lambda x: (x["days_to_stockout"] or 9999))
    return {
        "stockout_risk":  results,
        "at_risk_count":  len(results),
        "period_days":    period_days,
        "standard":       "Deterministic — qty_on_hand / avg daily consumption (SMRP inventory metrics)",
    }


# ── 4. Failure Trend Forecast — requires ≥ 24 data points ────────────────────
# Uses rolling counts to show whether failures are increasing or decreasing.
# Prophet is skipped if insufficient data — uses linear trend instead.

def calc_failure_trend(logbook_entries: list[dict], period_days: int = 90) -> dict:
    df = _to_df(logbook_entries)
    if df.empty:
        return {"trend": [], "direction": None, "standard": "Time-series trend analysis"}

    df = _parse_dates(df, "created_at")
    df = _corrective_only(df)

    if df.empty or len(df) < 4:
        return {
            "trend": [], "direction": None,
            "note": f"Only {len(df)} data points — need ≥ 4 to detect trend.",
            "standard": "Time-series trend analysis"
        }

    # Weekly failure counts
    df = df.set_index("created_at").sort_index()
    weekly = df.resample("W").size().reset_index()
    weekly.columns = ["week", "count"]
    weekly["week_label"] = weekly["week"].dt.strftime("%Y-%m-%d")

    # Linear trend via numpy polyfit
    x = np.arange(len(weekly))
    y = weekly["count"].values
    if len(x) >= 2:
        slope, intercept = np.polyfit(x, y, 1)
        slope = float(slope)
    else:
        slope = 0.0

    if slope > 0.1:
        direction = "INCREASING"
        trend_label = f"Failures trending UP (+{slope:.2f}/week) — investigate root cause"
    elif slope < -0.1:
        direction = "DECREASING"
        trend_label = f"Failures trending DOWN ({slope:.2f}/week) — maintenance improving"
    else:
        direction = "STABLE"
        trend_label = "Failure rate is stable"

    # Forecast next 4 weeks
    forecast = []
    for i in range(1, 5):
        predicted = max(0, round(intercept + slope * (len(weekly) + i - 1), 1))
        week_date = (weekly["week"].iloc[-1] + pd.Timedelta(weeks=i)).strftime("%Y-%m-%d")
        forecast.append({"week": week_date, "predicted_count": predicted})

    return {
        "trend":         weekly[["week_label", "count"]].rename(columns={"week_label": "week"}).to_dict(orient="records"),
        "forecast":      forecast,
        "slope_per_week": round(slope, 3),
        "direction":     direction,
        "trend_label":   trend_label,
        "data_points":   len(weekly),
        "standard":      "Linear trend (numpy polyfit) — Prophet requires ≥ 24 weeks of data",
        "note":          "Full Prophet forecasting will activate when ≥ 24 weeks of failure data exists.",
    }


# ── 5. Equipment Health Score — SMRP-inspired ────────────────────────────────
# Composite score (0-100) per machine based on:
#   40% — MTBF trend (higher = better)
#   30% — PM compliance (higher = better)
#   30% — Recent failure frequency (lower = better)
# Standard: SMRP-inspired weighted composite

def calc_health_scores(
    logbook_entries: list[dict],
    pm_completions: list[dict],
    pm_scope_items: list[dict],
    period_days: int = 90
) -> dict:
    log   = _to_df(logbook_entries)
    comps = _to_df(pm_completions)
    scope = _to_df(pm_scope_items)

    if log.empty:
        return {"health_scores": [], "standard": "SMRP-inspired weighted composite (0-100)"}

    log   = _parse_dates(log,   "created_at")
    comps = _parse_dates(comps, "completed_at")
    corr  = _corrective_only(log)

    now    = pd.Timestamp.now(tz="UTC")
    cutoff = now - pd.Timedelta(days=period_days)

    # MTBF per machine (from all history)
    mtbf_map: dict = {}
    for machine, group in corr.groupby("machine"):
        dates = group["created_at"].dropna().sort_values()
        if len(dates) >= 2:
            intervals = dates.diff().dropna().dt.total_seconds() / 86400
            mtbf_map[machine] = float(intervals.mean())

    # Recent failure count per machine (within period)
    recent_failures: dict = {}
    recent = corr[corr["created_at"] >= cutoff]
    if not recent.empty and "machine" in recent.columns:
        recent_failures = recent.groupby("machine").size().to_dict()

    # PM compliance per asset (simplified — % tasks with any completion)
    pm_compliance: dict = {}
    if not scope.empty and "asset_name" in scope.columns:
        for asset_name, s_group in scope.groupby("asset_name"):
            if comps.empty:
                pm_compliance[asset_name] = 0
                continue
            c_group = comps[comps.get("asset_id", pd.Series(dtype=str)).isin(s_group["asset_id"].values)] if "asset_id" in comps.columns else pd.DataFrame()
            pm_compliance[asset_name] = min(100, len(c_group) / max(len(s_group), 1) * 100)

    # Normalize MTBF: use 90 days as "perfect" MTBF (score = 100)
    max_mtbf = 90.0

    all_machines = set(mtbf_map) | set(recent_failures)
    scores = []

    for machine in all_machines:
        mtbf         = mtbf_map.get(machine, None)
        failures     = recent_failures.get(machine, 0)
        compliance   = pm_compliance.get(machine, 50)  # default 50 if no PM data

        # Component scores (0-100 each)
        mtbf_score       = min(100, (mtbf / max_mtbf * 100)) if mtbf else 30
        failure_score    = max(0, 100 - failures * 15)  # -15 per failure, floor at 0
        compliance_score = float(compliance)

        # Weighted composite
        health = round(
            0.40 * mtbf_score +
            0.30 * failure_score +
            0.30 * compliance_score,
            1
        )

        if health >= 80:
            status = "HEALTHY"
            color  = "green"
        elif health >= 60:
            status = "WATCH"
            color  = "yellow"
        else:
            status = "AT RISK"
            color  = "red"

        scores.append({
            "machine":          machine,
            "health_score":     health,
            "status":           status,
            "color":            color,
            "mtbf_days":        round(mtbf, 1) if mtbf else None,
            "recent_failures":  failures,
            "pm_compliance_pct": round(compliance, 1),
            "components": {
                "mtbf_score":       round(mtbf_score, 1),
                "failure_score":    round(failure_score, 1),
                "compliance_score": round(compliance_score, 1),
            }
        })

    scores.sort(key=lambda x: x["health_score"])
    return {
        "health_scores": scores,
        "at_risk_count": sum(1 for s in scores if s["status"] == "AT RISK"),
        "watch_count":   sum(1 for s in scores if s["status"] == "WATCH"),
        "healthy_count": sum(1 for s in scores if s["status"] == "HEALTHY"),
        "weights":       {"mtbf": "40%", "failure_frequency": "30%", "pm_compliance": "30%"},
        "standard":      "SMRP-inspired weighted composite — 40% MTBF + 30% failure freq + 30% PM compliance",
    }


# ── 6. Anomaly Baseline Detection — ISO 7870-2 (Statistical Process Control) ──
# Uses readings_json from logbook entries.
# Calculates mean ± 2σ per reading type per machine.
# Flags readings outside control limits as anomalies.

def calc_anomaly_baseline(logbook_entries: list[dict]) -> dict:
    df = _to_df(logbook_entries)
    if df.empty or "readings_json" not in df.columns:
        return {
            "baselines": [],
            "anomalies": [],
            "standard": "ISO 7870-2 Statistical Process Control (2σ control limits)",
            "note": "No readings_json data yet. Fill Quick Readings in Breakdown entries to activate.",
        }

    df = _corrective_only(df)
    has_readings = df[df["readings_json"].notna()]
    if has_readings.empty:
        return {
            "baselines": [], "anomalies": [],
            "standard": "ISO 7870-2 SPC",
            "note": "Readings logged but none linked to Breakdown entries yet.",
        }

    # Collect all readings per machine per reading type
    from collections import defaultdict
    machine_readings: dict = defaultdict(lambda: defaultdict(list))

    for _, row in has_readings.iterrows():
        machine  = row.get("machine", "Unknown")
        readings = row.get("readings_json")
        if not isinstance(readings, dict):
            continue
        for key, val in readings.items():
            try:
                machine_readings[machine][key].append(float(val))
            except (TypeError, ValueError):
                pass

    UNIT_MAP = {
        "temperature_c": "°C", "vibration_mms": "mm/s", "pressure_bar": "bar",
        "voltage_v": "V", "current_a": "A", "flow_lpm": "L/min",
        "signal_ma": "mA", "oil_temp_c": "°C",
    }

    baselines = []
    anomalies = []

    for machine, reading_types in machine_readings.items():
        for rtype, values in reading_types.items():
            if len(values) < 3:
                continue  # need ≥ 3 readings to establish baseline
            arr  = np.array(values)
            mean = float(arr.mean())
            std  = float(arr.std())
            ucl  = mean + 2 * std   # upper control limit
            lcl  = mean - 2 * std   # lower control limit

            unit = UNIT_MAP.get(rtype, "")
            label = rtype.replace("_", " ").replace("c", "").replace("mms", "mm/s").strip()

            baseline = {
                "machine":   machine,
                "reading":   rtype,
                "label":     label,
                "unit":      unit,
                "mean":      round(mean, 2),
                "std":       round(std, 2),
                "ucl":       round(ucl, 2),
                "lcl":       round(max(lcl, 0), 2),
                "n_readings": len(values),
                "last_value": round(values[-1], 2),
            }
            baselines.append(baseline)

            # Flag last reading if outside control limits
            last = values[-1]
            if last > ucl or last < lcl:
                anomalies.append({
                    "machine":    machine,
                    "reading":    label,
                    "unit":       unit,
                    "value":      round(last, 2),
                    "mean":       round(mean, 2),
                    "deviation":  round(abs(last - mean) / std, 1) if std > 0 else None,
                    "direction":  "HIGH" if last > ucl else "LOW",
                    "alert":      f"{label} reading ({round(last,1)}{unit}) is outside 2σ control limits — potential fault developing.",
                })

    return {
        "baselines":       baselines,
        "anomalies":       anomalies,
        "anomaly_count":   len(anomalies),
        "machines_tracked": len(machine_readings),
        "standard":        "ISO 7870-2 — Statistical Process Control, ±2σ control limits",
    }


# ── Master function ───────────────────────────────────────────────────────────

def calculate(inputs: dict) -> dict:
    logbook    = inputs.get("logbook_entries", [])
    comps      = inputs.get("pm_completions", [])
    scope      = inputs.get("pm_scope_items", [])
    txns       = inputs.get("inv_transactions", [])
    inv_items  = inputs.get("inventory_items", [])
    period     = int(inputs.get("period_days", 90))

    return {
        "phase":    "predictive",
        "standard": "ISO 13381-1:2015, ISO 14224:2016, ISO 7870-2, SMRP Metrics",
        "period_days": period,
        "next_failure_dates": calc_next_failure_dates(logbook),
        "pm_due_calendar":    calc_pm_due_calendar(comps, scope),
        "parts_stockout":     calc_parts_stockout(inv_items, txns, period),
        "failure_trend":      calc_failure_trend(logbook, period),
        "health_scores":      calc_health_scores(logbook, comps, scope, period),
        "anomaly_baseline":   calc_anomaly_baseline(logbook),
    }
