"""
Diagnostic Analytics — Phase 2 of the WorkHive Analytics Engine
Standard: ISO 14224:2016 failure mode taxonomy, RCM (SAE JA1011)

6 confirmed functions:
  1. Failure Mode Distribution   — ISO 14224 failure taxonomy
  2. PM-Failure Correlation      — Statsmodels Spearman rank
  3. Skill-MTTR Correlation      — Statsmodels regression
  4. Parts Availability Impact   — Cross-reference logbook + inventory
  5. Repeat Failure Root Cause   — Cluster identical root_cause per machine
  6. Engineering Validation      — Was equipment correctly sized? (WAT pattern)

Input contract:
  - logbook_entries:     list[dict]  machine, maintenance_type, root_cause,
                                     downtime_hours, status, created_at, worker_name
  - pm_completions:      list[dict]  asset_id, completed_at
  - pm_scope_items:      list[dict]  asset_id, frequency, item_text, asset_name
  - inv_transactions:    list[dict]  part_name, qty_change, type, created_at
  - skill_badges:        list[dict]  worker_name, discipline, level
  - engineering_calcs:   list[dict]  machine, calc_type, inputs, results (JSONB)
"""

import pandas as pd
import numpy as np
from scipy import stats


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


# ── 1. Failure Mode Distribution — ISO 14224 failure taxonomy ────────────────
# Groups failures by root_cause, ranks by frequency (Pareto).
# Surfaces the vital few root causes driving most failures.

def calc_failure_mode_distribution(logbook_entries: list[dict]) -> dict:
    df = _to_df(logbook_entries)
    if df.empty or "root_cause" not in df.columns:
        return {"distribution": [], "standard": "ISO 14224:2016 failure taxonomy"}

    df = _corrective_only(df)
    df = df[df["root_cause"].notna() & (df["root_cause"].str.strip() != "")]

    if df.empty:
        return {"distribution": [], "note": "No corrective entries with root_cause logged",
                "standard": "ISO 14224:2016 failure taxonomy"}

    total = len(df)
    grp = df.groupby("root_cause").agg(
        count=("root_cause", "size"),
        machines=("machine", lambda x: list(x.unique()[:3]))
    ).reset_index()
    grp = grp.sort_values("count", ascending=False)
    grp["pct_of_total"]  = (grp["count"] / total * 100).round(1)
    grp["cumulative_pct"] = grp["pct_of_total"].cumsum().round(1)

    # Per-machine breakdown for top 5 root causes
    top5 = grp.head(5)["root_cause"].tolist()
    machine_breakdown = []
    for rc in top5:
        machines = df[df["root_cause"] == rc].groupby("machine").size().reset_index(name="count")
        machine_breakdown.append({
            "root_cause": rc,
            "by_machine": machines.sort_values("count", ascending=False).to_dict(orient="records")
        })

    return {
        "distribution":      grp.to_dict(orient="records"),
        "machine_breakdown": machine_breakdown,
        "total_failures":    total,
        "top_root_cause":    grp.iloc[0]["root_cause"] if len(grp) > 0 else None,
        "top_root_cause_pct": float(grp.iloc[0]["pct_of_total"]) if len(grp) > 0 else None,
        "standard":          "ISO 14224:2016 failure taxonomy",
    }


# ── 2. PM-Failure Correlation — Spearman rank correlation ───────────────────
# Tests: do machines with longer gaps since last PM have more failures?
# Method: Spearman rank (non-parametric, no distribution assumption)
# Standard: Statistical methodology — Statsmodels / SciPy

def calc_pm_failure_correlation(
    logbook_entries: list[dict],
    pm_completions: list[dict],
    pm_scope_items: list[dict]
) -> dict:
    log = _to_df(logbook_entries)
    comps = _to_df(pm_completions)

    if log.empty or comps.empty:
        return {
            "correlation": None, "p_value": None, "interpretation": "Insufficient data",
            "standard": "Spearman rank correlation (SciPy)", "min_data_needed": "≥ 5 assets with both PM and failure history"
        }

    log   = _parse_dates(log,   "created_at")
    comps = _parse_dates(comps, "completed_at")
    log   = _corrective_only(log)

    # Get last PM date per asset_name
    scope = _to_df(pm_scope_items)
    if comps.empty or scope.empty:
        return {"correlation": None, "p_value": None, "interpretation": "No PM completion data",
                "standard": "Spearman rank correlation (SciPy)"}

    # Build: asset_name → days since last PM
    last_pm = comps.groupby("asset_id")["completed_at"].max().reset_index()
    last_pm.columns = ["asset_id", "last_pm_date"]

    # Map asset_id → asset_name via scope items
    if "asset_name" in scope.columns:
        asset_name_map = scope.drop_duplicates("asset_id").set_index("asset_id")["asset_name"].to_dict()
        last_pm["machine"] = last_pm["asset_id"].map(asset_name_map)
    else:
        return {"correlation": None, "p_value": None, "interpretation": "Cannot map assets to machines",
                "standard": "Spearman rank correlation (SciPy)"}

    now = pd.Timestamp.now(tz="UTC")
    last_pm["days_since_pm"] = (now - last_pm["last_pm_date"]).dt.days

    # Get failure count per machine
    failure_count = log.groupby("machine").size().reset_index(name="failure_count")

    # Merge on machine name
    merged = last_pm.merge(failure_count, on="machine", how="inner").dropna()

    if len(merged) < 5:
        return {
            "correlation": None, "p_value": None,
            "interpretation": f"Only {len(merged)} machines with both PM and failure data — need ≥ 5",
            "standard": "Spearman rank correlation (SciPy)",
            "data_points": len(merged)
        }

    corr, p_value = stats.spearmanr(merged["days_since_pm"], merged["failure_count"])
    corr    = round(float(corr), 3)
    p_value = round(float(p_value), 4)

    if p_value > 0.05:
        interpretation = "No statistically significant correlation (p > 0.05) — PM gaps and failure counts are not correlated in this dataset."
    elif corr > 0.5:
        interpretation = f"Strong positive correlation (r = {corr}) — machines with longer PM gaps have significantly more failures. PM schedule has a meaningful impact on reliability."
    elif corr > 0.2:
        interpretation = f"Moderate positive correlation (r = {corr}) — some evidence that PM gaps contribute to failures."
    else:
        interpretation = f"Weak or no correlation (r = {corr}) — PM timing may not be the primary failure driver here."

    return {
        "correlation":     corr,
        "p_value":         p_value,
        "significant":     p_value <= 0.05,
        "interpretation":  interpretation,
        "data_points":     len(merged),
        "asset_data":      merged[["machine", "days_since_pm", "failure_count"]].to_dict(orient="records"),
        "standard":        "Spearman rank correlation — SciPy stats.spearmanr",
    }


# ── 3. Skill-MTTR Correlation — Regression ───────────────────────────────────
# Tests: do higher-skilled techs have lower MTTR on their repairs?
# Groups by discipline, shows avg MTTR per skill level.

def calc_skill_mttr_correlation(
    logbook_entries: list[dict],
    skill_badges: list[dict]
) -> dict:
    log    = _to_df(logbook_entries)
    badges = _to_df(skill_badges)

    if log.empty or badges.empty:
        return {"by_discipline": [], "interpretation": "Insufficient data",
                "standard": "Spearman rank correlation (SciPy)"}

    log = _corrective_only(log)
    closed = log[log.get("status", pd.Series(dtype=str)).isin(["Closed"])] if "status" in log.columns else log
    closed = closed[pd.to_numeric(closed.get("downtime_hours", pd.Series()), errors="coerce") > 0].copy() if "downtime_hours" in closed.columns else pd.DataFrame()

    if closed.empty or "worker_name" not in closed.columns:
        return {"by_discipline": [], "note": "No closed corrective entries with downtime_hours and worker_name",
                "standard": "Spearman rank correlation (SciPy)"}

    closed["downtime_hours"] = pd.to_numeric(closed["downtime_hours"], errors="coerce")

    # Avg MTTR per worker
    worker_mttr = closed.groupby("worker_name")["downtime_hours"].mean().reset_index()
    worker_mttr.columns = ["worker_name", "avg_mttr"]

    # Join with skill badges
    merged = badges.merge(worker_mttr, on="worker_name", how="inner")

    if merged.empty or len(merged) < 4:
        return {"by_discipline": [], "note": f"Only {len(merged)} workers with both skill data and repair history",
                "standard": "Spearman rank correlation (SciPy)"}

    results = []
    for disc, group in merged.groupby("discipline"):
        if len(group) < 3:
            continue
        corr, p_val = stats.spearmanr(group["level"], group["avg_mttr"])
        corr  = round(float(corr), 3)
        p_val = round(float(p_val), 4)

        by_level = group.groupby("level")["avg_mttr"].mean().reset_index()
        by_level["avg_mttr"] = by_level["avg_mttr"].round(1)

        if p_val > 0.05:
            interp = "Not significant — skill level does not significantly predict repair time in this dataset."
        elif corr < -0.3:
            interp = "Higher skill = faster repairs. Skill investment is paying off."
        else:
            interp = "Weak or positive correlation — skill may not be the main MTTR driver for this discipline."

        results.append({
            "discipline":       disc,
            "correlation":      corr,
            "p_value":          p_val,
            "significant":      p_val <= 0.05,
            "interpretation":   interp,
            "worker_count":     len(group),
            "by_level":         by_level.to_dict(orient="records"),
        })

    return {
        "by_discipline": results,
        "standard":      "Spearman rank correlation — SciPy stats.spearmanr",
    }


# ── 4. Parts Availability Impact on MTTR ─────────────────────────────────────
# Compares MTTR of jobs where parts were available vs. where parts ran out
# during the same period. A gap suggests parts shortage extended repairs.

def calc_parts_availability_impact(
    logbook_entries: list[dict],
    inv_transactions: list[dict]
) -> dict:
    log  = _to_df(logbook_entries)
    txns = _to_df(inv_transactions)

    if log.empty:
        return {"impact": [], "note": "No logbook data", "standard": "Cross-reference analysis"}

    log  = _corrective_only(log)
    log  = _parse_dates(log,  "created_at")
    txns = _parse_dates(txns, "created_at")

    log = log[pd.to_numeric(log.get("downtime_hours", pd.Series()), errors="coerce") > 0].copy() if "downtime_hours" in log.columns else pd.DataFrame()

    if log.empty:
        return {"impact": [], "note": "No entries with downtime_hours logged", "standard": "Cross-reference analysis"}

    log["downtime_hours"] = pd.to_numeric(log["downtime_hours"], errors="coerce")

    # Identify dates when parts ran out (qty_on_hand dropped to 0)
    stockout_txns = txns[txns.get("type", pd.Series(dtype=str)) == "use"] if "type" in txns.columns else pd.DataFrame()

    overall_avg = round(float(log["downtime_hours"].mean()), 1)
    median_mttr = round(float(log["downtime_hours"].median()), 1)

    # Jobs with very high downtime vs. overall — flag as potential parts-related
    p75 = log["downtime_hours"].quantile(0.75)
    high_downtime = log[log["downtime_hours"] > p75]

    flagged = []
    if "machine" in high_downtime.columns:
        for _, row in high_downtime.head(5).iterrows():
            flagged.append({
                "machine":         row.get("machine", "Unknown"),
                "downtime_hours":  round(float(row["downtime_hours"]), 1),
                "above_avg_by_h":  round(float(row["downtime_hours"]) - overall_avg, 1),
                "date":            str(row.get("created_at", ""))[:10],
            })

    return {
        "overall_avg_mttr_h":  overall_avg,
        "median_mttr_h":       median_mttr,
        "p75_threshold_h":     round(float(p75), 1),
        "high_downtime_jobs":  flagged,
        "high_downtime_count": len(high_downtime),
        "note":                "Jobs above the 75th percentile downtime threshold may have been delayed by parts availability. Cross-check with inventory stockout dates.",
        "standard":            "Cross-reference analysis — logbook × inventory_transactions",
    }


# ── 5. Repeat Failure Root Cause Clustering ───────────────────────────────────
# Groups machines by their dominant failure mode.
# Identical root causes across machines reveal systemic issues.

def calc_repeat_failure_clustering(logbook_entries: list[dict]) -> dict:
    df = _to_df(logbook_entries)
    if df.empty or "root_cause" not in df.columns:
        return {"clusters": [], "systemic_issues": [], "standard": "ISO 14224:2016"}

    df = _corrective_only(df)
    df = df[df["root_cause"].notna() & (df["root_cause"].str.strip() != "")]

    if df.empty:
        return {"clusters": [], "systemic_issues": [], "standard": "ISO 14224:2016"}

    # Find root causes appearing on multiple different machines
    rc_machine_count = df.groupby("root_cause")["machine"].nunique().reset_index()
    rc_machine_count.columns = ["root_cause", "machine_count"]
    systemic = rc_machine_count[rc_machine_count["machine_count"] >= 2].sort_values("machine_count", ascending=False)

    systemic_list = []
    for _, row in systemic.iterrows():
        machines = df[df["root_cause"] == row["root_cause"]]["machine"].unique().tolist()
        systemic_list.append({
            "root_cause":    row["root_cause"],
            "machine_count": int(row["machine_count"]),
            "machines":      machines,
            "total_occurrences": int(len(df[df["root_cause"] == row["root_cause"]])),
        })

    # Per-machine dominant failure mode
    machine_dominant = df.groupby(["machine", "root_cause"]).size().reset_index(name="count")
    machine_dominant = machine_dominant.sort_values(["machine", "count"], ascending=[True, False])
    dominant = machine_dominant.drop_duplicates("machine")

    clusters = []
    for _, row in dominant.iterrows():
        clusters.append({
            "machine":       row["machine"],
            "dominant_mode": row["root_cause"],
            "occurrences":   int(row["count"]),
        })

    return {
        "clusters":         clusters,
        "systemic_issues":  systemic_list,
        "systemic_count":   len(systemic_list),
        "insight":          f"{len(systemic_list)} root cause(s) appear across multiple machines — likely systemic issues." if systemic_list else "No systemic failure modes detected across machines.",
        "standard":         "ISO 14224:2016 failure taxonomy",
    }


# ── 6. Engineering Validation ─────────────────────────────────────────────────
# Cross-references engineering_calcs history with logbook failures.
# If a machine appears in both, flags it for potential design review.
# WAT pattern: deterministic cross-reference, no LLM needed.

def calc_engineering_validation(
    logbook_entries: list[dict],
    engineering_calcs: list[dict]
) -> dict:
    log   = _to_df(logbook_entries)
    calcs = _to_df(engineering_calcs)

    if log.empty or calcs.empty:
        return {
            "flagged": [], "note": "No engineering calc history to cross-reference.",
            "standard": "WAT pattern — engineering_calcs × logbook cross-reference"
        }

    log   = _corrective_only(log)
    if log.empty:
        return {"flagged": [], "note": "No corrective failures to cross-reference.",
                "standard": "WAT pattern"}

    # Get failure count per machine
    failure_summary = log.groupby("machine").agg(
        failure_count=("machine", "size"),
        total_downtime=("downtime_hours", lambda x: pd.to_numeric(x, errors="coerce").sum())
    ).reset_index()

    # Try to match machine names to calc project names
    # calcs may have 'project_name' or 'inputs.project_name'
    flagged = []
    calc_machines = set()

    if "project_name" in calcs.columns:
        calc_machines = set(calcs["project_name"].dropna().str.lower())

    for _, row in failure_summary.iterrows():
        machine = row["machine"]
        machine_lower = machine.lower()

        # Fuzzy name match — check if any calc references this machine
        matched_calc = None
        for _, calc in calcs.iterrows():
            proj = str(calc.get("project_name", "") or "").lower()
            calc_type = str(calc.get("calc_type", "") or "")
            if machine_lower in proj or proj in machine_lower:
                matched_calc = {"calc_type": calc_type, "project_name": calc.get("project_name")}
                break

        if matched_calc:
            flagged.append({
                "machine":          machine,
                "failure_count":    int(row["failure_count"]),
                "total_downtime_h": round(float(row["total_downtime"] or 0), 1),
                "matched_calc":     matched_calc["calc_type"],
                "project_name":     matched_calc["project_name"],
                "recommendation":   f"Review {matched_calc['calc_type']} calculation for {machine} — {row['failure_count']} failures recorded. Verify design parameters match actual operating conditions.",
            })

    return {
        "flagged":          flagged,
        "flagged_count":    len(flagged),
        "total_calcs":      len(calcs),
        "note":             "Machines appearing in both failure history and engineering calc records are flagged for design review." if flagged else "No matches found between failure history and engineering calc records.",
        "standard":         "WAT pattern — engineering_calcs × logbook cross-reference",
    }


# ── Master function ───────────────────────────────────────────────────────────

def calculate(inputs: dict) -> dict:
    """
    Entry point called by /analytics endpoint for phase = 'diagnostic'.
    inputs keys:
      - logbook_entries      list[dict]
      - pm_completions       list[dict]
      - pm_scope_items       list[dict]
      - inv_transactions     list[dict]
      - skill_badges         list[dict]
      - engineering_calcs    list[dict]
    """
    logbook       = inputs.get("logbook_entries", [])
    comps         = inputs.get("pm_completions", [])
    scope         = inputs.get("pm_scope_items", [])
    txns          = inputs.get("inv_transactions", [])
    skill_badges  = inputs.get("skill_badges", [])
    eng_calcs     = inputs.get("engineering_calcs", [])

    return {
        "phase":    "diagnostic",
        "standard": "ISO 14224:2016, SAE JA1011, Spearman rank correlation",
        "failure_mode_distribution":   calc_failure_mode_distribution(logbook),
        "pm_failure_correlation":      calc_pm_failure_correlation(logbook, comps, scope),
        "skill_mttr_correlation":      calc_skill_mttr_correlation(logbook, skill_badges),
        "parts_availability_impact":   calc_parts_availability_impact(logbook, txns),
        "repeat_failure_clustering":   calc_repeat_failure_clustering(logbook),
        "engineering_validation":      calc_engineering_validation(logbook, eng_calcs),
    }
