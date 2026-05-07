"""CMMS Demo Mode Analytics -- Phase 7.

Computes an intelligence report from a CMMSDataset without any AI API calls.
All analysis is deterministic, instant, and derived purely from the dataset.

This is the sales demo engine: "Your data was already in SAP.
WorkHive found these patterns in under 2 seconds."
"""

from collections import Counter, defaultdict
from datetime import datetime, timezone

from data.cmms_templates import HISTORY_DAYS, INDUSTRY_PROFILES


# ---------------------------------------------------------------------------
# Risk keywords for parts-PM cross-reference
# ---------------------------------------------------------------------------

_PART_KEYWORDS = [
    "bearing", "seal", "gasket", "belt", "filter", "valve", "relay",
    "fan", "oil", "grease", "coolant", "refrigerant", "pump", "motor",
]


def _keyword_match(text_a: str, text_b: str) -> bool:
    a, b = text_a.lower(), text_b.lower()
    return any(kw in a and kw in b for kw in _PART_KEYWORDS)


# ---------------------------------------------------------------------------
# Core analytics
# ---------------------------------------------------------------------------

def compute_demo_report(ds) -> dict:
    """Compute intelligence report from a CMMSDataset.

    Returns a structured dict ready to render in the UI.
    """
    started = datetime.now(timezone.utc)
    profile = INDUSTRY_PROFILES.get(ds.industry, {})
    history_days = HISTORY_DAYS.get(ds.size, 365)

    # ── 1. Breakdown counts per machine ─────────────────────────────────────
    breakdown_counts: Counter = Counter()
    downtime_by_machine: dict[str, float] = defaultdict(float)

    for entry in ds.expected_logbook:
        if entry.get("maintenance_type") == "Breakdown / Corrective":
            machine = entry.get("machine", "UNKNOWN")
            breakdown_counts[machine] += 1
            downtime_by_machine[machine] += float(entry.get("downtime_hours") or 0)

    # ── 2. MTBF per machine (days between failures) ─────────────────────────
    mtbf_by_machine: dict[str, float] = {}
    for machine, count in breakdown_counts.items():
        if count > 0:
            mtbf_by_machine[machine] = round(history_days / count, 1)

    # ── 3. Overdue PM schedules ─────────────────────────────────────────────
    overdue_pm = [p for p in ds.expected_pm if p.get("is_overdue")]

    # ── 4. Low-stock parts ──────────────────────────────────────────────────
    low_stock = [i for i in ds.expected_inventory if i.get("is_low_stock")]

    # ── 5. Cross-reference: low stock vs overdue PM ─────────────────────────
    parts_blocking_pm: list[dict] = []
    for part in low_stock:
        part_name = part.get("name", "")
        for pm in overdue_pm:
            task = pm.get("task", "")
            if _keyword_match(part_name, task):
                parts_blocking_pm.append({
                    "part":    part_name,
                    "pm_task": task,
                    "asset":   pm.get("asset_tag", ""),
                })
                break  # one match per part is enough

    # ── 6. Risk scoring per asset ────────────────────────────────────────────
    # breakdown_count × 3 + overdue_pm × 2 + parts_blocking × 1
    overdue_by_asset = Counter(p.get("asset_tag", "") for p in overdue_pm)
    blocking_by_asset = Counter(p.get("asset", "") for p in parts_blocking_pm)

    all_assets = {e.get("machine", "") for e in ds.expected_logbook}
    all_assets |= {p.get("asset_tag", "") for p in ds.expected_pm}

    risk_scores: list[dict] = []
    for asset in all_assets:
        if not asset:
            continue
        b_count  = breakdown_counts.get(asset, 0)
        pm_count = overdue_by_asset.get(asset, 0)
        pt_count = blocking_by_asset.get(asset, 0)
        score    = b_count * 3 + pm_count * 2 + pt_count

        if score == 0:
            continue

        mtbf = mtbf_by_machine.get(asset)
        risk_scores.append({
            "asset":        asset,
            "breakdowns":   b_count,
            "overdue_pm":   pm_count,
            "parts_at_risk": pt_count,
            "downtime_hrs": round(downtime_by_machine.get(asset, 0), 1),
            "mtbf_days":    mtbf,
            "score":        score,
            "risk_level":   (
                "critical" if score >= 10
                else "high"   if score >= 5
                else "medium" if score >= 2
                else "low"
            ),
        })

    risk_scores.sort(key=lambda x: x["score"], reverse=True)
    top_risk = risk_scores[:5]

    # ── 7. Repeat-failure machines (>= 3 breakdowns) ────────────────────────
    repeat_machines = [m for m, c in breakdown_counts.items() if c >= 3]

    # ── 8. Recommendations (plain language) ─────────────────────────────────
    recommendations: list[str] = []

    if top_risk:
        top = top_risk[0]
        mtbf_str = f"MTBF = {top['mtbf_days']:.0f} days" if top["mtbf_days"] else "MTBF unknown"
        recommendations.append(
            f"CRITICAL: {top['asset']} -- {top['breakdowns']} breakdowns "
            f"in {history_days} days ({mtbf_str}). "
            f"Escalate to full overhaul."
        )

    if overdue_pm:
        assets_str = ", ".join({p.get("asset_tag", "") for p in overdue_pm[:3]})
        recommendations.append(
            f"OVERDUE PM: {len(overdue_pm)} maintenance tasks past due date "
            f"on {assets_str}{'...' if len(overdue_pm) > 3 else ''}. "
            f"Schedule immediately."
        )

    if low_stock:
        recommendations.append(
            f"PARTS RISK: {len(low_stock)} critical spares below reorder point. "
            f"Raise purchase orders before next breakdown window."
        )

    if parts_blocking_pm:
        ex = parts_blocking_pm[0]
        recommendations.append(
            f"BLOCKED WORK: {ex['part']} needed for '{ex['pm_task']}' "
            f"on {ex['asset']} but stock is critically low."
        )

    if repeat_machines:
        top_repeats = repeat_machines[:3]
        recommendations.append(
            f"REPEAT FAILURES: {len(repeat_machines)} assets have 3+ breakdowns "
            f"({', '.join(top_repeats)}). Review root cause and PM strategy."
        )

    # ── 9. Summary statistics ────────────────────────────────────────────────
    critical_count  = sum(1 for r in risk_scores if r["risk_level"] == "critical")
    high_count      = sum(1 for r in risk_scores if r["risk_level"] == "high")
    total_downtime  = round(sum(downtime_by_machine.values()), 1)
    total_breakdowns = sum(breakdown_counts.values())

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()

    return {
        "generated_at":    started.isoformat(),
        "elapsed_seconds": round(elapsed, 3),
        "industry":        profile.get("label", ds.industry),
        "company":         profile.get("company", ""),
        "cmms_type":       ds.cmms_type,
        "size":            ds.size,
        "seed":            ds.seed,
        "history_days":    history_days,
        "dataset": {
            "assets":       len(ds.assets),
            "work_orders":  len(ds.work_orders),
            "pm_schedules": len(ds.pm_schedules),
            "parts":        len(ds.inventory),
        },
        "summary": {
            "total_breakdowns":    total_breakdowns,
            "total_downtime_hrs":  total_downtime,
            "assets_at_risk":      len(risk_scores),
            "critical_assets":     critical_count,
            "high_risk_assets":    high_count,
            "overdue_pm_count":    len(overdue_pm),
            "low_stock_count":     len(low_stock),
            "parts_blocking_pm":   len(parts_blocking_pm),
            "repeat_machines":     len(repeat_machines),
        },
        "top_risk_assets": top_risk,
        "overdue_pm":      overdue_pm[:5],
        "low_stock":       low_stock[:5],
        "parts_blocking_pm": parts_blocking_pm[:3],
        "recommendations": recommendations,
    }
