"""
Descriptive Analytics — Phase 1 of the WorkHive Analytics Engine
Standard: ISO 14224:2016, SMRP Metrics Standard

All 8 confirmed functions:
  1. MTBF per asset          — ISO 14224 §9.3
  2. MTTR per asset          — ISO 14224 §9.4
  3. Availability %          — ISO 14224 §9.2
  4. PM Compliance Rate      — SMRP Metric 2.1.1
  5. Failure frequency       — ISO 14224
  6. Downtime Pareto         — General analytics (80/20)
  7. Parts consumption rate  — SMRP
  8. Repeat failure count    — ISO 14224

Input contract (all lists of dicts from Supabase queries):
  - logbook_entries: machine, maintenance_type, category, root_cause,
                     downtime_hours, status, created_at, closed_at, worker_name
  - pm_completions:  asset_id, completed_at, asset_name
  - pm_scope_items:  asset_id, frequency, item_text
  - inv_transactions: part_name, qty_change, type, created_at
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone


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
    """ISO 14224 §9.3 — MTBF uses Breakdown/Corrective entries only."""
    if df.empty or "maintenance_type" not in df.columns:
        return df
    return df[df["maintenance_type"].str.contains("Corrective|Breakdown", case=False, na=False)]


# ── 1. MTBF per asset — ISO 14224 §9.3 ──────────────────────────────────────
# MTBF = Mean Time Between Failures
# Formula: sum of intervals between consecutive failures / (n_failures - 1)
# Requires: ≥ 2 failures per machine to calculate an interval

def calc_mtbf(logbook_entries: list[dict]) -> dict:
    df = _to_df(logbook_entries)
    if df.empty:
        return {"mtbf_by_asset": [], "unit": "days", "standard": "ISO 14224:2016 §9.3"}

    df = _parse_dates(df, "created_at")
    df = _corrective_only(df)

    if df.empty:
        return {"mtbf_by_asset": [], "unit": "days", "standard": "ISO 14224:2016 §9.3"}

    results = []
    for machine, group in df.groupby("machine"):
        dates = group["created_at"].dropna().sort_values()
        n = len(dates)
        if n < 2:
            results.append({
                "machine": machine,
                "failure_count": n,
                "mtbf_days": None,
                "note": "Need ≥ 2 failures to calculate MTBF"
            })
            continue

        intervals = dates.diff().dropna().dt.total_seconds() / 86400
        mtbf = float(intervals.mean())
        results.append({
            "machine": machine,
            "failure_count": n,
            "mtbf_days": round(mtbf, 1),
            "min_interval_days": round(float(intervals.min()), 1),
            "max_interval_days": round(float(intervals.max()), 1),
        })

    results.sort(key=lambda x: (x["mtbf_days"] or 9999))
    return {"mtbf_by_asset": results, "unit": "days", "standard": "ISO 14224:2016 §9.3"}


# ── 2. MTTR per asset — ISO 14224 §9.4 ──────────────────────────────────────
# MTTR = Mean Time To Repair
# Formula: sum(downtime_hours) / count(repairs)
# Uses worker-logged downtime_hours (preferred over clock time per data-engineer skill)

def calc_mttr(logbook_entries: list[dict]) -> dict:
    df = _to_df(logbook_entries)
    if df.empty:
        return {"mttr_by_asset": [], "unit": "hours", "standard": "ISO 14224:2016 §9.4"}

    df = _corrective_only(df)
    closed = df[df.get("status", pd.Series(dtype=str)) == "Closed"] if "status" in df.columns else df
    has_downtime = closed[pd.to_numeric(closed.get("downtime_hours", pd.Series()), errors="coerce") > 0] if "downtime_hours" in closed.columns else pd.DataFrame()

    if has_downtime.empty:
        return {"mttr_by_asset": [], "unit": "hours", "standard": "ISO 14224:2016 §9.4",
                "note": "No closed corrective entries with logged downtime_hours found"}

    has_downtime = has_downtime.copy()
    has_downtime["downtime_hours"] = pd.to_numeric(has_downtime["downtime_hours"], errors="coerce")

    results = []
    for machine, group in has_downtime.groupby("machine"):
        total_h = float(group["downtime_hours"].sum())
        count   = len(group)
        mttr    = total_h / count
        results.append({
            "machine": machine,
            "repair_count": count,
            "total_downtime_h": round(total_h, 1),
            "mttr_hours": round(mttr, 1),
        })

    results.sort(key=lambda x: -x["mttr_hours"])
    return {"mttr_by_asset": results, "unit": "hours", "standard": "ISO 14224:2016 §9.4"}


# ── 3. Availability % — ISO 14224 §9.2 ───────────────────────────────────────
# Availability = MTBF / (MTBF + MTTR) × 100
# Inherent availability — does not account for logistics or admin delays

def calc_availability(logbook_entries: list[dict]) -> dict:
    mtbf_result = calc_mtbf(logbook_entries)
    mttr_result = calc_mttr(logbook_entries)

    mtbf_map = {r["machine"]: r["mtbf_days"] for r in mtbf_result["mtbf_by_asset"] if r["mtbf_days"]}
    mttr_map = {r["machine"]: r["mttr_hours"] / 24 for r in mttr_result["mttr_by_asset"]}  # convert h → days

    machines = set(mtbf_map) | set(mttr_map)
    results = []
    for machine in machines:
        mtbf = mtbf_map.get(machine)
        mttr = mttr_map.get(machine, 0)
        if mtbf is None:
            continue
        availability = (mtbf / (mtbf + mttr)) * 100 if (mtbf + mttr) > 0 else None
        results.append({
            "machine": machine,
            "mtbf_days": mtbf,
            "mttr_days": round(mttr, 2),
            "availability_pct": round(availability, 1) if availability is not None else None,
        })

    results.sort(key=lambda x: (x["availability_pct"] or 0))
    return {
        "availability_by_asset": results,
        "unit": "%",
        "standard": "ISO 14224:2016 §9.2",
        "formula": "MTBF / (MTBF + MTTR) × 100"
    }


# ── 4. PM Compliance Rate — SMRP Metric 2.1.1 ────────────────────────────────
# PM Compliance = Completed PMs / Scheduled PMs × 100
# Scheduled PMs = scope items whose due date has passed within the period

def calc_pm_compliance(pm_completions: list[dict], pm_scope_items: list[dict], period_days: int = 90) -> dict:
    comps = _to_df(pm_completions)
    scope = _to_df(pm_scope_items)

    if scope.empty:
        return {"compliance_by_asset": [], "overall_pct": None,
                "standard": "SMRP Metric 2.1.1", "note": "No PM scope items found"}

    comps = _parse_dates(comps, "completed_at")
    now    = pd.Timestamp.now(tz="UTC")
    cutoff = now - pd.Timedelta(days=period_days)  # only count completions within the period

    # Frequency string → days mapping
    freq_days = {
        "Monthly": 30, "Quarterly": 90,
        "Semi-Annual": 180, "Yearly": 365,
    }

    results = []
    for asset_id, s_group in scope.groupby("asset_id"):
        asset_name = s_group.iloc[0].get("asset_name", asset_id)
        c_group    = comps[comps["asset_id"] == asset_id] if not comps.empty else pd.DataFrame()

        # Filter completions to within the analysis period
        if not c_group.empty and "completed_at" in c_group.columns:
            c_group = c_group[c_group["completed_at"] >= cutoff]

        scheduled = 0
        completed = 0

        for _, item in s_group.iterrows():
            freq   = item.get("frequency", "Monthly")
            days   = freq_days.get(freq, 30)
            comp_for_item = c_group[c_group["scope_item_id"] == item.get("id")] if not c_group.empty and "scope_item_id" in c_group.columns else pd.DataFrame()

            # How many times was this task due in the period?
            # e.g. Monthly (30d) in 90-day period = 3 times due
            due_count = max(1, int(period_days / days))
            scheduled += due_count

            # Count completions within expected window
            done = len(comp_for_item) if not comp_for_item.empty else 0
            completed += min(done, due_count)

        compliance = (completed / scheduled * 100) if scheduled > 0 else 0
        results.append({
            "asset_name": asset_name,
            "asset_id": asset_id,
            "scheduled": scheduled,
            "completed": completed,
            "compliance_pct": round(compliance, 1),
        })

    overall = float(np.mean([r["compliance_pct"] for r in results])) if results else 0
    results.sort(key=lambda x: x["compliance_pct"])
    return {
        "compliance_by_asset": results,
        "overall_pct": round(overall, 1),
        "standard": "SMRP Metric 2.1.1",
    }


# ── 5. Failure Frequency — ISO 14224 ─────────────────────────────────────────
# Count of corrective failures per machine per period

def calc_failure_frequency(logbook_entries: list[dict], period_days: int = 90) -> dict:
    df = _to_df(logbook_entries)
    if df.empty:
        return {"failure_frequency": [], "period_days": period_days, "standard": "ISO 14224:2016"}

    df = _parse_dates(df, "created_at")
    df = _corrective_only(df)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=period_days)
    df     = df[df["created_at"] >= cutoff]

    if df.empty:
        return {"failure_frequency": [], "period_days": period_days,
                "note": f"No corrective failures in the last {period_days} days"}

    freq = df.groupby("machine").size().reset_index(name="failure_count")
    freq = freq.sort_values("failure_count", ascending=False)

    return {
        "failure_frequency": freq.to_dict(orient="records"),
        "period_days": period_days,
        "total_failures": int(freq["failure_count"].sum()),
        "standard": "ISO 14224:2016",
    }


# ── 6. Downtime Pareto — 80/20 Rule ──────────────────────────────────────────
# Ranked downtime by machine — identifies the vital few causing most downtime

def calc_downtime_pareto(logbook_entries: list[dict]) -> dict:
    df = _to_df(logbook_entries)
    if df.empty or "downtime_hours" not in df.columns:
        return {"pareto": [], "note": "No downtime data found"}

    df = _corrective_only(df)
    df["downtime_hours"] = pd.to_numeric(df["downtime_hours"], errors="coerce").fillna(0)
    pareto = df.groupby("machine")["downtime_hours"].sum().reset_index()
    pareto = pareto[pareto["downtime_hours"] > 0].sort_values("downtime_hours", ascending=False)

    if pareto.empty:
        return {"pareto": [], "note": "No downtime_hours logged in corrective entries"}

    total = float(pareto["downtime_hours"].sum())
    pareto["cumulative_pct"] = (pareto["downtime_hours"].cumsum() / total * 100).round(1)
    pareto["downtime_hours"] = pareto["downtime_hours"].round(1)
    pareto["pct_of_total"]   = (pareto["downtime_hours"] / total * 100).round(1)

    return {
        "pareto": pareto.to_dict(orient="records"),
        "total_downtime_hours": round(total, 1),
        "top_machine": pareto.iloc[0]["machine"] if len(pareto) > 0 else None,
        "top_machine_pct": float(pareto.iloc[0]["pct_of_total"]) if len(pareto) > 0 else None,
    }


# ── 7. Parts Consumption Rate — SMRP ─────────────────────────────────────────
# Units consumed per week/month per part — from inventory_transactions

def calc_parts_consumption(inv_transactions: list[dict], period_days: int = 90) -> dict:
    df = _to_df(inv_transactions)
    if df.empty:
        return {"consumption": [], "period_days": period_days, "standard": "SMRP"}

    df = _parse_dates(df, "created_at")
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=period_days)
    df     = df[df["created_at"] >= cutoff]

    # Only 'use' transactions (not 'add' or 'adjust')
    if "type" in df.columns:
        df = df[df["type"] == "use"]

    if df.empty or "part_name" not in df.columns:
        return {"consumption": [], "period_days": period_days,
                "note": "No parts usage transactions found in period"}

    df["qty_change"] = pd.to_numeric(df.get("qty_change", pd.Series(dtype=float)), errors="coerce").abs()
    grp = df.groupby("part_name").agg(
        total_used=("qty_change", "sum"),
        transaction_count=("qty_change", "count")
    ).reset_index()

    grp["per_week"]  = (grp["total_used"] / period_days * 7).round(2)
    grp["per_month"] = (grp["total_used"] / period_days * 30).round(2)
    grp = grp.sort_values("total_used", ascending=False)

    return {
        "consumption": grp.to_dict(orient="records"),
        "period_days": period_days,
        "standard": "SMRP",
    }


# ── 8. Repeat Failure Count — ISO 14224 ──────────────────────────────────────
# Same root_cause on same machine ≥ 2 times = repeat failure
# Indicates ineffective repair or systemic issue

def calc_repeat_failures(logbook_entries: list[dict]) -> dict:
    df = _to_df(logbook_entries)
    if df.empty or "root_cause" not in df.columns:
        return {"repeats": [], "standard": "ISO 14224:2016"}

    df = _corrective_only(df)
    df = df[df["root_cause"].notna() & (df["root_cause"].str.strip() != "")]

    if df.empty:
        return {"repeats": [], "note": "No corrective entries with root_cause logged"}

    grp = df.groupby(["machine", "root_cause"]).size().reset_index(name="occurrences")
    repeats = grp[grp["occurrences"] >= 2].sort_values("occurrences", ascending=False)

    return {
        "repeats": repeats.to_dict(orient="records"),
        "repeat_pair_count": len(repeats),
        "standard": "ISO 14224:2016",
        "note": "Same root_cause on same machine ≥ 2 times indicates ineffective repair",
    }


# ── 9. OEE — Overall Equipment Effectiveness — ISO 22400-2 ───────────────────
# OEE = Availability × Quality (Performance requires planned rate — excluded)
# Availability: from MTBF/MTTR already calculated
# Quality: from production_output.quality_pct in logbook entries
# Note: Performance remains flagged (needs planned production rate input)

def calc_oee(logbook_entries: list[dict], period_days: int = 90) -> dict:
    df = _to_df(logbook_entries)
    if df.empty:
        return {"oee_by_asset": [], "standard": "ISO 22400-2:2014 (partial — Availability × Quality)",
                "note": "No logbook data found"}

    df = _parse_dates(df, "created_at")
    df = _corrective_only(df)

    # Availability component — from downtime vs period hours
    # Assume 8h shift × period_days as total available time
    total_hours = period_days * 8.0
    downtime_by_machine = {}
    if "downtime_hours" in df.columns:
        dh = df.copy()
        dh["downtime_hours"] = pd.to_numeric(dh["downtime_hours"], errors="coerce").fillna(0)
        downtime_by_machine = dh.groupby("machine")["downtime_hours"].sum().to_dict()

    # Quality component — from production_output field
    quality_data: dict[str, list] = {}
    if "production_output" in df.columns:
        for _, row in df.iterrows():
            po = row.get("production_output")
            if not po or not isinstance(po, dict):
                continue
            machine = row.get("machine", "Unknown")
            q_pct   = po.get("quality_pct")
            if q_pct is not None:
                quality_data.setdefault(machine, []).append(float(q_pct))

    all_machines = set(downtime_by_machine) | set(quality_data)
    if not all_machines:
        return {"oee_by_asset": [], "standard": "ISO 22400-2:2014",
                "note": "No downtime or production_output data recorded yet"}

    results = []
    for machine in all_machines:
        downtime      = downtime_by_machine.get(machine, 0)
        avail_pct     = max(0, min(100, (total_hours - downtime) / total_hours * 100)) if total_hours > 0 else None
        qual_readings = quality_data.get(machine, [])
        quality_pct   = round(float(np.mean(qual_readings)), 1) if qual_readings else None

        # OEE = Availability × Quality (Performance excluded — needs planned rate)
        if avail_pct is not None and quality_pct is not None:
            oee = round(avail_pct / 100 * quality_pct / 100 * 100, 1)
        else:
            oee = None

        results.append({
            "machine":        machine,
            "availability_pct": round(avail_pct, 1) if avail_pct is not None else None,
            "quality_pct":    quality_pct,
            "oee_pct":        oee,
            "quality_readings": len(qual_readings),
            "note":           "Performance dimension excluded — needs planned production rate" if oee else "Insufficient data",
        })

    results.sort(key=lambda x: (x["oee_pct"] or 0))
    return {
        "oee_by_asset":  results,
        "assets_tracked": len(results),
        "standard":      "ISO 22400-2:2014 — Availability × Quality (partial OEE)",
        "note":          "Performance dimension will activate when planned production rate is configured.",
    }


# ── Master function — runs all 8 and returns combined result ─────────────────

def calculate(inputs: dict) -> dict:
    """
    Entry point called by /analytics/descriptive endpoint.
    inputs keys:
      - logbook_entries      list[dict]
      - pm_completions       list[dict]
      - pm_scope_items       list[dict]
      - inv_transactions     list[dict]
      - period_days          int (optional, default 90)
    """
    logbook   = inputs.get("logbook_entries", [])
    comps     = inputs.get("pm_completions", [])
    scope     = inputs.get("pm_scope_items", [])
    txns      = inputs.get("inv_transactions", [])
    period    = int(inputs.get("period_days", 90))

    return {
        "phase": "descriptive",
        "standard": "ISO 14224:2016, SMRP Metrics, ISO 22400-2",
        "period_days": period,
        "mtbf":              calc_mtbf(logbook),
        "mttr":              calc_mttr(logbook),
        "availability":      calc_availability(logbook),
        "oee":               calc_oee(logbook, period),
        "pm_compliance":     calc_pm_compliance(comps, scope, period),
        "failure_frequency": calc_failure_frequency(logbook, period),
        "downtime_pareto":   calc_downtime_pareto(logbook),
        "parts_consumption": calc_parts_consumption(txns, period),
        "repeat_failures":   calc_repeat_failures(logbook),
    }
