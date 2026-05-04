"""
Project Manager — Diagnostic Phase
Earned Value Management (EVM) variance decomposition + blocker analysis.

Standards: PMI PMBOK 7th ed. (Performance Domain: Measurement),
AACE International Recommended Practice 80R-13 (Project Performance Measurement).

Formulas:
    PV  = BAC × (days_elapsed / days_total)         Planned Value
    EV  = BAC × (pct_complete / 100)                Earned Value
    AC  = hours_actual × labor_rate_php_per_hour    Actual Cost (proxy)
    SV  = EV - PV                                   Schedule Variance
    CV  = EV - AC                                   Cost Variance
    SPI = EV / PV                                   Schedule Performance Index
    CPI = EV / AC                                   Cost Performance Index

Status thresholds (AACE EV interpretation guidance):
    Green: min(SPI, CPI) >= 0.95
    Amber: 0.85 <= min(SPI, CPI) < 0.95
    Red:   min(SPI, CPI) < 0.85
"""

from datetime import datetime, timezone


# Default proxy labor rate. Phase 5 will pull from worker_profiles.
DEFAULT_LABOR_RATE_PHP_PER_HOUR = 200


def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _days_between(a, b):
    da, db = _parse_date(a), _parse_date(b)
    if not da or not db:
        return 0
    return max(1, int((db - da).total_seconds() // 86400) + 1)


def _ev_status(spi, cpi):
    if spi is None and cpi is None:
        return "unknown"
    m = min(spi if spi is not None else 1, cpi if cpi is not None else 1)
    if m >= 0.95:
        return "green"
    if m >= 0.85:
        return "amber"
    return "red"


def _phase_from_notes(notes: str) -> str:
    import re
    if not notes:
        return ""
    m = re.match(r"phase:\s*([a-z0-9]+)", notes, re.IGNORECASE)
    return m.group(1).lower() if m else ""


def calculate(inputs: dict) -> dict:
    project = inputs.get("project") or {}
    items   = inputs.get("items")   or []
    logs    = inputs.get("logs")    or []
    labor_rate = inputs.get("labor_rate_php_per_hour") or DEFAULT_LABOR_RATE_PHP_PER_HOUR

    # Skip if budget or dates missing — EVM requires all three
    if not project.get("budget_php") or not project.get("start_date") or not project.get("end_date"):
        return {"available": False, "reason": "Requires budget_php + start_date + end_date"}

    BAC = float(project["budget_php"])
    now_iso = datetime.now(timezone.utc).isoformat()
    days_elapsed = _days_between(project["start_date"], now_iso)
    days_total   = _days_between(project["start_date"], project["end_date"])
    planned_pct  = min(1.0, days_elapsed / days_total) if days_total > 0 else 0

    # Weighted pct_complete by estimated_hours
    total_w = sum((it.get("estimated_hours") or 1) for it in items) or 1
    pct_complete = (
        sum((it.get("pct_complete") or 0) * (it.get("estimated_hours") or 1) for it in items) / total_w
        if items else 0
    )

    hours_actual = sum((it.get("actual_hours") or 0) for it in items)

    PV  = BAC * planned_pct
    EV  = BAC * (pct_complete / 100)
    AC  = hours_actual * labor_rate
    SV  = EV - PV
    CV  = EV - AC
    SPI = EV / PV if PV > 0 else None
    CPI = EV / AC if AC > 0 else None

    # ── Per-phase decomposition: which phase is dragging? ─────────────────
    phase_variance = {}
    for it in items:
        p = _phase_from_notes(it.get("notes") or "") or "other"
        h_est  = it.get("estimated_hours") or 0
        h_act  = it.get("actual_hours") or 0
        pct    = (it.get("pct_complete") or 0) / 100
        ev_p   = h_est * pct
        ac_p   = h_act
        if p not in phase_variance:
            phase_variance[p] = {"est_h": 0, "actual_h": 0, "earned_h": 0, "items": 0}
        phase_variance[p]["est_h"]    += h_est
        phase_variance[p]["actual_h"] += h_act
        phase_variance[p]["earned_h"] += ev_p
        phase_variance[p]["items"]    += 1
    for p, v in phase_variance.items():
        v["cv_hours"] = round(v["earned_h"] - v["actual_h"], 1)

    # ── Blocker frequency from progress logs ─────────────────────────────
    blocker_count = sum(1 for l in logs if (l.get("blockers") or "").strip())
    recent_blockers = [
        {"date": l.get("log_date"), "by": l.get("reported_by"), "text": l.get("blockers")}
        for l in logs[:10]
        if (l.get("blockers") or "").strip()
    ]

    return {
        "available": True,
        "bac": round(BAC),
        "pv":  round(PV),
        "ev":  round(EV),
        "ac":  round(AC),
        "sv":  round(SV),
        "cv":  round(CV),
        "spi": round(SPI, 2) if SPI is not None else None,
        "cpi": round(CPI, 2) if CPI is not None else None,
        "status": _ev_status(SPI, CPI),
        "phase_variance": phase_variance,
        "blocker_count_30d": blocker_count,
        "recent_blockers":  recent_blockers,
        "labor_rate_used":  labor_rate,
    }
