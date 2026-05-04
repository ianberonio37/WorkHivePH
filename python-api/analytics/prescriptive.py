"""
Prescriptive Analytics — Phase 4 of the WorkHive Analytics Engine
Standard: ISO 55000:2014 Asset Management, SAE JA1011 RCM, SMRP Metrics

5 deterministic functions (Groq synthesis handled by the Edge Function):
  1. Priority Maintenance Ranking  — ISO 55001 risk framework
  2. PM Interval Optimization       — SAE JA1011 §7
  3. Technician Assignment          — SMRP workforce metrics
  4. Parts Reorder Recommendation   — Inventory management cross-reference
  5. Training Gap Recommendation    — logbook MTTR × skill_badges cross-reference

Input contract:
  - logbook_entries:   list[dict]
  - pm_completions:    list[dict]
  - pm_scope_items:    list[dict]
  - inventory_items:   list[dict]
  - inv_transactions:  list[dict]
  - skill_badges:      list[dict]
  - pm_assets:         list[dict]  (includes criticality field)
  - period_days:       int
"""

import pandas as pd
import numpy as np


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


CRITICALITY_WEIGHT = {
    # Platform canonical labels (pm-scheduler.html dropdown)
    "Critical": 4, "High": 3, "Medium": 2, "Low": 1,
    # Legacy/seeder aliases — Major ≈ High, Minor ≈ Medium. Keeps old data
    # interpretable until reseed picks up the canonical labels.
    "Major": 3, "Minor": 2,
}
FREQ_DAYS = {"Monthly": 30, "Quarterly": 90, "Semi-Annual": 180, "Yearly": 365}


# ── 1. Priority Maintenance Ranking — ISO 55001 ───────────────────────────────
# Risk Score = Criticality Weight × Failure Frequency × Avg Downtime
# Ranks all assets so maintenance team knows where to focus first.

def calc_priority_ranking(
    logbook_entries: list[dict],
    pm_assets: list[dict],
    period_days: int = 90
) -> dict:
    log    = _to_df(logbook_entries)
    assets = _to_df(pm_assets)

    if log.empty:
        return {"ranking": [], "standard": "ISO 55001 risk-based prioritisation"}

    log    = _parse_dates(log, "created_at")
    log    = _corrective_only(log)
    cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=period_days)
    recent = log[log["created_at"] >= cutoff]

    # Failure stats per machine
    failure_stats = recent.groupby("machine").agg(
        failure_count=("machine", "size"),
        total_downtime=("downtime_hours", lambda x: pd.to_numeric(x, errors="coerce").sum())
    ).reset_index()

    # Build criticality map from pm_assets, keyed by the HUMAN asset code (tag_id).
    # logbook.machine stores that same code (post-PRODUCTION_FIXES #17 alignment),
    # so we can join the two cleanly. Previously this keyed on asset_name and
    # never matched, so every asset got the default "Medium" weight.
    crit_map: dict = {}
    asset_name_map: dict = {}    # human code → readable name (for display)
    if not assets.empty and "criticality" in assets.columns:
        for _, row in assets.iterrows():
            tag = str(row.get("tag_id", "") or "").strip().lower()
            crit = str(row.get("criticality", "") or "").strip() or "Medium"
            name = str(row.get("asset_name", "") or "").strip()
            if tag:
                crit_map[tag] = crit
                asset_name_map[tag] = name

    ranking = []
    for _, row in failure_stats.iterrows():
        machine     = row["machine"]
        freq        = int(row["failure_count"])
        downtime    = float(row["total_downtime"] or 0)
        avg_dt      = round(downtime / freq, 1) if freq > 0 else 0

        # Match by the human asset code (logbook.machine == pm_assets.tag_id)
        crit_key    = str(machine).lower()
        crit        = crit_map.get(crit_key, "Medium")
        crit_weight = CRITICALITY_WEIGHT.get(crit, 2)

        # Risk score: higher = needs attention sooner
        risk_score  = round(crit_weight * freq * max(avg_dt, 1), 1)

        ranking.append({
            "machine":      machine,
            "criticality":  crit,
            "failure_count": freq,
            "avg_downtime_h": avg_dt,
            "total_downtime_h": round(downtime, 1),
            "risk_score":   risk_score,
            # Tier thresholds calibrated for 90-day windows.
            # Formula = crit (1-4) × failure_count × avg_downtime_hours.
            # A typical Medium asset with 5 failures averaging 3h downtime
            # scores ~30 (P3). A Critical asset with 12 failures × 5h = 240 (P1).
            # Thresholds are deliberately loose so users see the long tail too.
            "priority":     "P1" if risk_score >= 150 else "P2" if risk_score >= 60 else "P3",
        })

    ranking.sort(key=lambda x: -x["risk_score"])

    return {
        "ranking":       ranking,
        "p1_count":      sum(1 for r in ranking if r["priority"] == "P1"),
        "p2_count":      sum(1 for r in ranking if r["priority"] == "P2"),
        "top_priority":  ranking[0]["machine"] if ranking else None,
        "standard":      "ISO 55001 risk framework — Criticality × Frequency × Downtime",
    }


# ── 2. PM Interval Optimization — SAE JA1011 §7 ──────────────────────────────
# If MTBF < PM interval → PM is not frequent enough → recommend shortening
# If MTBF >> PM interval → PM may be over-maintained → flag for review

def calc_pm_interval_optimization(
    logbook_entries: list[dict],
    pm_scope_items: list[dict],
    pm_assets: list[dict]
) -> dict:
    log   = _to_df(logbook_entries)
    scope = _to_df(pm_scope_items)

    if log.empty or scope.empty:
        return {"recommendations": [], "standard": "SAE JA1011 §7 RCM interval optimisation"}

    log = _parse_dates(log, "created_at")
    log = _corrective_only(log)

    # Guard: log may be empty after corrective filter; empty df has no columns.
    if log.empty or "machine" not in log.columns:
        return {
            "recommendations": [], "count": 0,
            "compared_count": 0, "skipped_count": 0,
            "scope_asset_count": int(scope["asset_name"].nunique()) if "asset_name" in scope.columns else 0,
            "note": "No corrective failures logged in this period — no MTBF to compare against.",
            "standard": "SAE JA1011 §7 RCM interval optimisation",
        }

    # MTBF per machine (logbook.machine == human asset code, e.g. "PMP-001")
    mtbf_map: dict = {}
    for machine, group in log.groupby("machine"):
        dates = group["created_at"].dropna().sort_values()
        if len(dates) >= 2:
            intervals = dates.diff().dropna().dt.total_seconds() / 86400
            mtbf_map[str(machine).lower()] = float(intervals.mean())

    # Build machine_code → criticality map. The orchestrator passes pm_assets
    # rows which now include `tag_id` (the human code matching logbook.machine).
    crit_map: dict = {}
    assets_df = _to_df(pm_assets)
    if not assets_df.empty and "tag_id" in assets_df.columns:
        for _, row in assets_df.iterrows():
            code = str(row.get("tag_id", "") or "").lower()
            crit = str(row.get("criticality", "Medium") or "Medium")
            if code:
                crit_map[code] = crit

    # Scope items must carry machine_code (orchestrator enrichment, PRODUCTION_FIXES #17)
    if "machine_code" not in scope.columns:
        return {"recommendations": [], "note": "Orchestrator did not provide machine_code on pm_scope_items — needs redeploy.",
                "standard": "SAE JA1011 §7 RCM interval optimisation"}

    # Track how many assets actually had MTBF data to compare so the UI can
    # render an honest empty state (PRODUCTION_FIXES #19).
    compared_count = 0
    skipped_no_failure_history = 0
    recommendations = []

    for machine_code, s_group in scope[scope["machine_code"] != ""].groupby("machine_code"):
        code_lower = str(machine_code).lower()
        mtbf = mtbf_map.get(code_lower)
        if mtbf is None:
            skipped_no_failure_history += 1
            continue  # no failure history to compare against
        compared_count += 1
        # Pull a display-friendly name from the scope row (orchestrator added asset_name too)
        asset_name = s_group.iloc[0].get("asset_name") or machine_code

        crit = crit_map.get(code_lower, "Medium")

        # Aggregate scope items into ONE recommendation per asset. Comparing
        # MTBF to every individual scope frequency produces N cards per asset
        # all saying the same thing. Instead, evaluate against the binding
        # constraints: the TIGHTEST current interval (most frequent task)
        # for "increase" decisions, and the LOOSEST for "reduce" decisions.
        scope_intervals = []
        for _, item in s_group.iterrows():
            freq = item.get("frequency", "Monthly")
            scope_intervals.append((freq, FREQ_DAYS.get(freq, 30)))
        if not scope_intervals:
            continue

        scope_intervals.sort(key=lambda x: x[1])  # by days ascending
        tightest_freq, tightest_days = scope_intervals[0]   # most frequent
        loosest_freq,  loosest_days  = scope_intervals[-1]  # least frequent
        scope_count = len(scope_intervals)

        if mtbf < tightest_days * 0.8:
            # MTBF is shorter than even the tightest current interval.
            action      = "INCREASE FREQUENCY"
            recommended = max(7, int(mtbf * 0.5))
            reason      = (f"MTBF ({round(mtbf,0)}d) is shorter than the tightest current "
                           f"PM interval ({tightest_freq.lower()} = {tightest_days}d). "
                           f"Failures are slipping past even the most frequent inspection.")
        elif mtbf > loosest_days * 5 and crit not in ("Critical", "High"):
            # MTBF much longer than even the loosest current interval — over-maintained.
            action      = "REVIEW — MAY REDUCE"
            recommended = int(loosest_days * 2)
            reason      = (f"MTBF ({round(mtbf,0)}d) is much longer than the loosest current "
                           f"interval ({loosest_freq.lower()} = {loosest_days}d). "
                           f"This asset may be over-maintained.")
        else:
            continue  # current intervals are appropriate

        recommendations.append({
                "asset_name":         asset_name,
                "machine_code":       str(machine_code),
                "scope_items_count":  scope_count,
                "current_frequency":  tightest_freq,
                "current_interval_d": tightest_days,
                "mtbf_days":          round(mtbf, 1),
                "action":             action,
                "recommended_days":   recommended,
                "reason":             reason,
            })

    return {
        "recommendations":  recommendations,
        "count":            len(recommendations),
        "compared_count":   compared_count,
        "skipped_count":    skipped_no_failure_history,
        "scope_asset_count": int(scope["asset_name"].nunique()) if "asset_name" in scope.columns else 0,
        "standard":         "SAE JA1011 §7 RCM — interval set by failure history, not arbitrary schedule",
    }


# ── 3. Technician Assignment — SMRP workforce metrics ─────────────────────────
# Matches open/recent jobs to best-qualified technician by discipline and level

def calc_technician_assignment(
    logbook_entries: list[dict],
    skill_badges: list[dict]
) -> dict:
    log    = _to_df(logbook_entries)
    badges = _to_df(skill_badges)

    if log.empty or badges.empty:
        return {"assignments": [], "skill_gaps": [],
                "standard": "SMRP workforce metrics — skill level × discipline match"}

    log = _corrective_only(log)
    log = log[log.get("status", pd.Series(dtype=str)).isin(["Open"])] if "status" in log.columns else log

    if log.empty:
        return {"assignments": [], "skill_gaps": [],
                "note": "No open corrective jobs to assign.",
                "standard": "SMRP workforce metrics"}

    # Ranked list of qualified techs per discipline (sorted by level DESC).
    # Used for workload-balanced assignment: each worker gets capped at
    # MAX_CONCURRENT_JOBS, then we drop down to the next-best tech.
    ranked_by_disc: dict = {}
    if not badges.empty and "discipline" in badges.columns:
        top = badges.groupby(["discipline", "worker_name"])["level"].max().reset_index()
        for disc, group in top.groupby("discipline"):
            ranked_by_disc[disc] = [
                {"worker_name": str(row["worker_name"]), "level": int(row["level"])}
                for _, row in group.sort_values("level", ascending=False).iterrows()
            ]

    # Logbook category → canonical skill discipline mapping.
    # Logbook offers 7 categories (logbook.html), skill matrix has 5 canonical
    # disciplines (skill-content.js). This map bridges them. Anything not listed
    # falls back to "Mechanical" for safe defaulting.
    CAT_TO_DISC = {
        "Mechanical":      "Mechanical",
        "Electrical":      "Electrical",
        "Instrumentation": "Instrumentation",
        "Hydraulic":       "Mechanical",   # rotating-equipment subdomain
        "Pneumatic":       "Mechanical",   # rotating-equipment subdomain
        "Lubrication":     "Mechanical",   # mech-maintenance subdomain
        "Other":           "Mechanical",
        # Legacy aliases (handle plurals + retired categories without breaking)
        "Hydraulics":      "Mechanical",
        "Pneumatics":      "Mechanical",
        "HVAC":            "Facilities Management",
        "Civil":           "Facilities Management",
    }

    # Workload cap — once a worker has this many open assignments, the next
    # job in their discipline goes to the next-best tech instead of piling
    # everything on the highest-skilled one.
    MAX_CONCURRENT_JOBS = 3
    load: dict = {}   # worker_name → current assignment count

    def _pick_next_best(disc: str):
        """Return the highest-level worker in `disc` whose load is below cap.
        If everyone is at cap, return the worker with the smallest load
        (skill ties broken by level). Returns None if discipline has no techs."""
        candidates = ranked_by_disc.get(disc) or []
        if not candidates:
            return None
        # Prefer skill order while load < cap
        for c in candidates:
            if load.get(c["worker_name"], 0) < MAX_CONCURRENT_JOBS:
                return c
        # Everyone capped — give it to whoever has the smallest load
        return min(candidates, key=lambda c: (load.get(c["worker_name"], 0), -c["level"]))

    assignments = []
    skill_gaps  = []

    for _, job in log.head(10).iterrows():
        machine  = job.get("machine", "Unknown")
        category = str(job.get("category", "") or "Mechanical")
        problem  = str(job.get("problem", "") or "")
        disc     = CAT_TO_DISC.get(category, "Mechanical")
        best     = _pick_next_best(disc)

        if best:
            current_load = load.get(best["worker_name"], 0)
            load[best["worker_name"]] = current_load + 1
            # Make the reason explain WHY this person (skill + load context)
            if current_load == 0:
                reason = f"Highest Level {best['level']} {disc} tech, no current open jobs."
            elif current_load < MAX_CONCURRENT_JOBS:
                reason = f"Best available Level {best['level']} {disc} tech (currently has {current_load} other open job{'s' if current_load != 1 else ''})."
            else:
                reason = f"All {disc} techs at workload cap; fewest-loaded wins (Level {best['level']}, {current_load} open)."
            assignments.append({
                "machine":         machine,
                "problem":         problem[:60],
                "required_discipline": disc,
                "assigned_to":     best["worker_name"],
                "skill_level":     best["level"],
                "reason":          reason,
            })
        else:
            skill_gaps.append({
                "machine":     machine,
                "discipline":  disc,
                "gap":         f"No qualified {disc} technician found in the team.",
            })

    return {
        "assignments":   assignments,
        "skill_gaps":    skill_gaps,
        "open_job_count": len(log),
        "standard":      "SMRP workforce metrics — highest skill level per discipline",
    }


# ── 4. Parts Reorder Recommendation ──────────────────────────────────────────
# Cross-references: parts below reorder point AND needed for upcoming PMs

def calc_parts_reorder(
    inventory_items: list[dict],
    inv_transactions: list[dict],
    pm_scope_items: list[dict],
    period_days: int = 90
) -> dict:
    items  = _to_df(inventory_items)
    txns   = _to_df(inv_transactions)
    scope  = _to_df(pm_scope_items)

    if items.empty:
        return {"reorder": [], "standard": "Inventory management × PM scope cross-reference"}

    items["qty_on_hand"]  = pd.to_numeric(items.get("qty_on_hand",  pd.Series()), errors="coerce").fillna(0)
    items["reorder_point"] = pd.to_numeric(items.get("reorder_point", pd.Series()), errors="coerce").fillna(0)

    # Average daily consumption
    consumption: dict = {}
    if not txns.empty and "part_name" in txns.columns:
        txns = _parse_dates(txns, "created_at")
        use  = txns[txns.get("type", pd.Series(dtype=str)) == "use"] if "type" in txns.columns else txns
        if not use.empty:
            use = use.copy()
            use["qty_change"] = pd.to_numeric(use.get("qty_change", pd.Series()), errors="coerce").abs()
            grp = use.groupby("part_name")["qty_change"].sum()
            for part, total in grp.items():
                consumption[part] = total / period_days

    # PM scope keywords (for cross-reference)
    pm_keywords = set()
    if not scope.empty and "item_text" in scope.columns:
        for text in scope["item_text"].dropna():
            for word in str(text).lower().split():
                if len(word) > 3:
                    pm_keywords.add(word)

    reorder = []
    for _, item in items.iterrows():
        part_name     = str(item.get("part_name", "") or "")
        qty           = float(item["qty_on_hand"])
        reorder_pt    = float(item["reorder_point"])
        daily         = consumption.get(part_name, 0)

        if qty > reorder_pt and reorder_pt > 0:
            continue  # healthy stock

        # Check if this part is mentioned in PM scope
        part_lower  = part_name.lower()
        pm_relevant = any(kw in part_lower or part_lower in kw for kw in pm_keywords)

        urgency = "CRITICAL" if qty <= 0 else "HIGH" if qty <= reorder_pt else "MEDIUM"
        suggested_qty = max(int(reorder_pt * 2), int(daily * 30)) if daily > 0 else int(reorder_pt * 2)

        reorder.append({
            "part_name":       part_name,
            "qty_on_hand":     round(qty, 1),
            "reorder_point":   round(reorder_pt, 1),
            "daily_usage":     round(daily, 3),
            "urgency":         urgency,
            "pm_relevant":     pm_relevant,
            "suggested_order": max(suggested_qty, 1),
            "action":          f"Order {max(suggested_qty,1)} units immediately." if urgency == "CRITICAL" else f"Reorder {max(suggested_qty,1)} units.",
        })

    reorder.sort(key=lambda x: (0 if x["urgency"]=="CRITICAL" else 1 if x["urgency"]=="HIGH" else 2, -x["pm_relevant"]))

    return {
        "reorder":       reorder,
        "critical_count": sum(1 for r in reorder if r["urgency"] == "CRITICAL"),
        "pm_linked_count": sum(1 for r in reorder if r["pm_relevant"]),
        "standard":      "Inventory management × PM scope cross-reference",
    }


# ── 5. Training Gap Recommendation ────────────────────────────────────────────
# High MTTR in a category + low skill level in that discipline = training target

def calc_training_gaps(
    logbook_entries: list[dict],
    skill_badges: list[dict]
) -> dict:
    log    = _to_df(logbook_entries)
    badges = _to_df(skill_badges)

    if log.empty:
        return {"gaps": [], "standard": "logbook MTTR × skill_badges cross-reference"}

    log = _corrective_only(log)
    closed = log[log.get("status", pd.Series(dtype=str)) == "Closed"] if "status" in log.columns else log
    if "downtime_hours" in closed.columns:
        closed = closed.copy()
        closed["downtime_hours"] = pd.to_numeric(closed["downtime_hours"], errors="coerce")
        closed = closed[closed["downtime_hours"] > 0]

    if closed.empty:
        return {"gaps": [], "note": "No closed corrective entries with downtime_hours.",
                "standard": "logbook MTTR × skill_badges cross-reference"}

    # Same bridge as in calc_technician_assignment — keep them in sync.
    CAT_TO_DISC = {
        "Mechanical":      "Mechanical",
        "Electrical":      "Electrical",
        "Instrumentation": "Instrumentation",
        "Hydraulic":       "Mechanical",
        "Pneumatic":       "Mechanical",
        "Lubrication":     "Mechanical",
        "Other":           "Mechanical",
        "Hydraulics":      "Mechanical",
        "Pneumatics":      "Mechanical",
        "HVAC":            "Facilities Management",
        "Civil":           "Facilities Management",
    }

    # Avg MTTR per category
    mttr_by_cat = closed.groupby("category")["downtime_hours"].mean()
    overall_avg = float(closed["downtime_hours"].mean())

    # Max skill level per discipline per worker
    max_level: dict = {}
    if not badges.empty and "discipline" in badges.columns and "worker_name" in badges.columns:
        for _, row in badges.iterrows():
            disc   = str(row.get("discipline", "") or "")
            worker = str(row.get("worker_name", "") or "")
            level  = int(row.get("level", 0) or 0)
            key    = (disc, worker)
            max_level[key] = max(max_level.get(key, 0), level)

    gaps = []
    above_threshold_count = 0   # categories whose MTTR exceeds threshold
    for cat, avg_mttr in mttr_by_cat.items():
        if avg_mttr <= overall_avg * 1.2:
            continue  # not significantly above average
        above_threshold_count += 1

        disc = CAT_TO_DISC.get(cat, cat)

        # Find workers with low skill in this discipline
        disc_workers = {w: lvl for (d, w), lvl in max_level.items() if d == disc}
        low_skill    = {w: lvl for w, lvl in disc_workers.items() if lvl < 3}

        gaps.append({
            "category":        cat,
            "discipline":      disc,
            "avg_mttr_h":      round(float(avg_mttr), 1),
            "overall_avg_h":   round(overall_avg, 1),
            "above_avg_by_h":  round(float(avg_mttr) - overall_avg, 1),
            "low_skill_workers": [{"worker": w, "current_level": lvl} for w, lvl in low_skill.items()],
            "recommendation":  f"Upskill {disc} technicians to Level 3+. Current avg repair time ({round(float(avg_mttr),1)}h) is {round(float(avg_mttr)-overall_avg,1)}h above hive average.",
        })

    gaps.sort(key=lambda x: -x["above_avg_by_h"])

    return {
        "gaps":                  gaps,
        "gap_count":             len(gaps),
        "categories_evaluated":  int(len(mttr_by_cat)),
        "above_threshold_count": int(above_threshold_count),
        "badge_count":           int(len(badges)),
        "standard":    "logbook MTTR × skill_badges cross-reference — SMRP workforce development",
    }


# ── Master function ───────────────────────────────────────────────────────────

def calculate(inputs: dict) -> dict:
    logbook    = inputs.get("logbook_entries", [])
    comps      = inputs.get("pm_completions", [])
    scope      = inputs.get("pm_scope_items", [])
    inv_items  = inputs.get("inventory_items", [])
    txns       = inputs.get("inv_transactions", [])
    badges     = inputs.get("skill_badges", [])
    pm_assets  = inputs.get("pm_assets", [])
    period     = int(inputs.get("period_days", 90))

    return {
        "phase":    "prescriptive",
        "standard": "ISO 55000:2014, SAE JA1011, SMRP Metrics",
        "period_days": period,
        "priority_ranking":        calc_priority_ranking(logbook, pm_assets, period),
        "pm_interval_optimization": calc_pm_interval_optimization(logbook, scope, pm_assets),
        "technician_assignment":   calc_technician_assignment(logbook, badges),
        "parts_reorder":           calc_parts_reorder(inv_items, txns, scope, period),
        "training_gaps":           calc_training_gaps(logbook, badges),
    }
