"""
Project Manager — Descriptive Phase
Current-state rollup, hours, days elapsed, status mix.

Standards: PMBOK 7th ed. (Performance Domain: Measurement),
ISO 21500:2021 §4.3.27 (Project status reporting).

Input contract:
    project:  dict with start_date, end_date, budget_php, status
    items:    list[dict] of project_items rows
    links:    list[dict] of project_links rows  (used for linked-counts only)
    logs:     list[dict] of project_progress_logs rows  (last 30)
"""

from datetime import datetime, timezone


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


def _phase_from_notes(notes: str) -> str:
    """Items carry phase as 'phase: X' prefix on the notes column."""
    import re
    if not notes:
        return ""
    m = re.match(r"phase:\s*([a-z0-9]+)", notes, re.IGNORECASE)
    return m.group(1).lower() if m else ""


def calculate(inputs: dict) -> dict:
    project = inputs.get("project") or {}
    items   = inputs.get("items")   or []
    links   = inputs.get("links")   or []
    logs    = inputs.get("logs")    or []

    # ── Weighted percent complete (by estimated_hours) ────────────────────
    total_w = sum((it.get("estimated_hours") or 1) for it in items) or 1
    if items:
        weighted_pct = sum(
            (it.get("pct_complete") or 0) * (it.get("estimated_hours") or 1)
            for it in items
        ) / total_w
        pct_complete = round(weighted_pct)
    else:
        pct_complete = 0

    # ── Counts ────────────────────────────────────────────────────────────
    items_total = len(items)
    items_done  = sum(1 for it in items if it.get("status") == "done")
    items_blocked = sum(1 for it in items if it.get("status") == "blocked")
    hours_estimated = sum((it.get("estimated_hours") or 0) for it in items)
    hours_actual    = sum((it.get("actual_hours") or 0) for it in items)

    # ── Days elapsed / total ──────────────────────────────────────────────
    now_iso = datetime.now(timezone.utc).isoformat()
    days_elapsed = _days_between(project.get("start_date"), now_iso) if project.get("start_date") else 0
    days_total   = _days_between(project.get("start_date"), project.get("end_date")) \
        if project.get("start_date") and project.get("end_date") else 0

    # ── Status mix ────────────────────────────────────────────────────────
    status_mix = {}
    for it in items:
        s = it.get("status") or "pending"
        status_mix[s] = status_mix.get(s, 0) + 1

    # ── Phase mix (PMBOK lifecycle phases) ────────────────────────────────
    phase_mix = {}
    for it in items:
        p = _phase_from_notes(it.get("notes") or "") or "other"
        phase_mix[p] = phase_mix.get(p, 0) + 1

    # ── Linked-work counts ────────────────────────────────────────────────
    link_counts = {}
    for l in links:
        t = l.get("link_type") or "other"
        link_counts[t] = link_counts.get(t, 0) + 1

    return {
        "pct_complete":    pct_complete,
        "items_total":     items_total,
        "items_done":      items_done,
        "items_blocked":   items_blocked,
        "hours_estimated": hours_estimated,
        "hours_actual":    hours_actual,
        "days_elapsed":    days_elapsed,
        "days_total":      days_total,
        "status_mix":      status_mix,
        "phase_mix":       phase_mix,
        "link_counts":     link_counts,
        "log_count_30d":   len(logs),
    }
