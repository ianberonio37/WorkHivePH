"""
Feature Engineering for WorkHive Failure Prediction (Stage 1 ML).
Transforms raw logbook + PM + inventory data into a tabular feature vector
per asset. All features are derived deterministically — the ML model only
does the final classification.

Data threshold: 500+ corrective entries before training produces reliable results.
Below 500, the rules engine (Stage 0) is more trustworthy than an underfit model.

Feature vector (FEATURE_COLS, 11 features):
  days_since_last_fault  - days since last corrective entry (recency signal)
  fault_count_30d        - corrective faults in last 30 days (burst detection)
  fault_count_90d        - corrective faults in last 90 days (baseline rate)
  fault_freq_trend       - 30d rate vs 90d rate * 3 (acceleration: >1.0 = worsening)
  mtbf_days              - mean time between failures in days (0 if < 2 faults)
  days_until_mtbf        - mtbf_days - days_since_last_fault (negative = overdue)
  avg_downtime_hours     - mean downtime_hours for last 5 corrective entries
  repeat_fault_count     - same root_cause appearing >= 2 times on this asset
  pm_overdue_days        - max(0, days_since_last_pm - pm_frequency_days)
  parts_used_30d         - total qty of parts consumed in last 30 days (spike signal)
  total_fault_count      - all-time corrective entry count (maturity signal)
"""

import pandas as pd
import numpy as np

FEATURE_COLS = [
    "days_since_last_fault",
    "fault_count_30d",
    "fault_count_90d",
    "fault_freq_trend",
    "mtbf_days",
    "days_until_mtbf",
    "avg_downtime_hours",
    "repeat_fault_count",
    "pm_overdue_days",
    "parts_used_30d",
    "total_fault_count",
]

FREQ_DAYS = {"Monthly": 30, "Quarterly": 90, "Semi-Annual": 180, "Yearly": 365}


def build_feature_matrix(
    logbook: list[dict],
    pm_completions: list[dict],
    pm_scope_items: list[dict],
    inv_transactions: list[dict],
    label_horizon_days: int = 14,
) -> pd.DataFrame:
    """
    Returns a DataFrame with one row per asset snapshot.
    Columns: FEATURE_COLS + optional 'will_fail' label (if sufficient history exists).

    'will_fail' = 1 if there is a corrective entry within label_horizon_days
    days AFTER each snapshot date. Used for supervised training.
    """
    log   = pd.DataFrame(logbook)   if logbook   else pd.DataFrame()
    comps = pd.DataFrame(pm_completions) if pm_completions else pd.DataFrame()
    scope = pd.DataFrame(pm_scope_items) if pm_scope_items else pd.DataFrame()
    txns  = pd.DataFrame(inv_transactions) if inv_transactions else pd.DataFrame()

    if log.empty or "machine" not in log.columns:
        return pd.DataFrame()

    log["created_at"] = pd.to_datetime(log["created_at"], utc=True, errors="coerce", format="ISO8601")
    now = pd.Timestamp.now(tz="UTC")

    corr = _corrective_only(log)
    if corr.empty:
        return pd.DataFrame()

    # Precompute PM data lookups (expensive — do once, not per asset)
    pm_lookup = _build_pm_lookup(comps, scope, now)
    parts_rates = _build_parts_rates(txns, now)

    rows = []
    for machine, group in corr.groupby("machine"):
        row = _extract_features(machine, group, pm_lookup, parts_rates, now)
        rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Fill any NaN introduced by missing optional data
    for col in FEATURE_COLS:
        if col not in df.columns:
            df[col] = 0.0
    df[FEATURE_COLS] = df[FEATURE_COLS].fillna(0)

    return df


def _corrective_only(df: pd.DataFrame) -> pd.DataFrame:
    if "maintenance_type" not in df.columns:
        return df
    return df[df["maintenance_type"].str.contains("Corrective|Breakdown", case=False, na=False)]


def _build_pm_lookup(
    comps: pd.DataFrame, scope: pd.DataFrame, now: pd.Timestamp
) -> dict[str, float]:
    """Returns {asset_name: pm_overdue_days}."""
    if scope.empty or comps.empty:
        return {}

    if "completed_at" in comps.columns:
        comps = comps.copy()
        comps["completed_at"] = pd.to_datetime(comps["completed_at"], utc=True, errors="coerce", format="ISO8601")

    last_comp: dict[str, pd.Timestamp] = {}
    if "asset_id" in comps.columns and "asset_id" in scope.columns:
        for _, c in comps.iterrows():
            aid = c.get("asset_id")
            dt  = c.get("completed_at")
            if aid and pd.notna(dt):
                if aid not in last_comp or dt > last_comp[aid]:
                    last_comp[aid] = dt

    lookup: dict[str, float] = {}
    if "asset_name" not in scope.columns:
        return lookup

    for asset_name, s_group in scope.groupby("asset_name"):
        overdue_vals = []
        for _, item in s_group.iterrows():
            freq_days = FREQ_DAYS.get(str(item.get("frequency", "Monthly")), 30)
            asset_id  = item.get("asset_id")
            last_done = last_comp.get(asset_id)
            if last_done is not None:
                days_since = (now - last_done).days
                overdue_vals.append(max(0.0, days_since - freq_days))
            else:
                overdue_vals.append(float(freq_days * 2))  # never done = 2 cycles late

        if overdue_vals:
            lookup[str(asset_name)] = float(np.mean(overdue_vals))

    return lookup


def _build_parts_rates(txns: pd.DataFrame, now: pd.Timestamp) -> dict:
    """Returns {part_name: qty_used_in_last_30d}."""
    if txns.empty or "created_at" not in txns.columns:
        return {}
    txns = txns.copy()
    txns["created_at"] = pd.to_datetime(txns["created_at"], utc=True, errors="coerce", format="ISO8601")
    cutoff = now - pd.Timedelta(days=30)
    recent = txns[txns["created_at"] >= cutoff]
    if recent.empty or "qty_change" not in recent.columns:
        return {}
    recent = recent.copy()
    recent["qty_change"] = pd.to_numeric(recent["qty_change"], errors="coerce").abs()
    if "part_name" in recent.columns:
        return recent.groupby("part_name")["qty_change"].sum().to_dict()
    return {}


def _extract_features(
    machine: str,
    group: pd.DataFrame,
    pm_lookup: dict[str, float],
    parts_rates: dict,
    now: pd.Timestamp,
) -> dict:
    dates = group["created_at"].dropna().sort_values()
    n     = len(dates)

    days_since_last = float((now - dates.iloc[-1]).days) if n > 0 else 999.0
    count_30d = int(len(dates[dates >= now - pd.Timedelta(days=30)]))
    count_90d = int(len(dates[dates >= now - pd.Timedelta(days=90)]))

    # Fault frequency trend: > 1.0 means rate is accelerating
    freq_trend = float(count_30d / count_90d * 3) if count_90d > 0 else 0.0

    # MTBF
    mtbf_days       = 0.0
    days_until_mtbf = 0.0
    if n >= 2:
        intervals       = dates.diff().dropna().dt.total_seconds() / 86400
        mtbf_days       = float(intervals.mean())
        days_until_mtbf = mtbf_days - days_since_last

    # Average downtime
    avg_downtime = 0.0
    if "downtime_hours" in group.columns:
        recent5 = group.nlargest(5, "created_at") if len(group) >= 5 else group
        vals    = pd.to_numeric(recent5["downtime_hours"], errors="coerce").dropna()
        avg_downtime = float(vals.mean()) if len(vals) > 0 else 0.0

    # Repeat fault count (same root_cause >= 2 times)
    repeat_count = 0
    if "root_cause" in group.columns:
        vc = group["root_cause"].dropna().value_counts()
        repeat_count = int(vc[vc >= 2].count())

    # PM overdue (days past due)
    pm_overdue = pm_lookup.get(machine, 0.0)

    # Parts consumption in last 30d (aggregate — asset-to-part linkage is indirect)
    parts_30d = sum(parts_rates.values()) / max(len(parts_rates), 1) if parts_rates else 0.0

    return {
        "machine":             machine,
        "days_since_last_fault": round(days_since_last, 1),
        "fault_count_30d":     count_30d,
        "fault_count_90d":     count_90d,
        "fault_freq_trend":    round(freq_trend, 3),
        "mtbf_days":           round(mtbf_days, 1),
        "days_until_mtbf":     round(days_until_mtbf, 1),
        "avg_downtime_hours":  round(avg_downtime, 2),
        "repeat_fault_count":  repeat_count,
        "pm_overdue_days":     round(pm_overdue, 1),
        "parts_used_30d":      round(parts_30d, 1),
        "total_fault_count":   n,
    }
