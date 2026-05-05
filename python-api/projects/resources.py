"""
Project Manager Phase 5A — Resource Histogram + Leveling Suggestions

Standards: PMBOK 7th ed. (Resource management performance domain),
PMI Practice Standard for Scheduling §5.4 (resource leveling).

For v1 we surface a daily resource histogram (per-worker hour load) and
flag overloaded days where any worker exceeds the daily capacity (8 h
default). A future v2 can add scipy.optimize.linprog to suggest exact
reassignments — but the histogram alone gives the supervisor enough to
make smart decisions manually.

Inputs:
    items: list[dict] of project_items rows with planned_start/planned_end,
           estimated_hours, owner_name
    daily_hours: int, capacity per worker per day (default 8)

Output:
    {
      "histogram":     [ {date, worker, hours, overloaded} ],
      "overloaded_days": [ {date, worker, hours} ],
      "suggestions":  [ {item_id, current_owner, alternative_owner, reason} ]
    }
"""

from datetime import datetime, timedelta
from math import ceil


def _parse_date(s):
    if not s:
        return None
    try:
        from datetime import timezone as _tz
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt
    except Exception:
        return None


def calculate(inputs: dict) -> dict:
    items = inputs.get("items") or []
    daily_hours = int(inputs.get("daily_hours") or 8)

    # ── Build daily-by-worker hour matrix ────────────────────────────────
    by_day_worker: dict[tuple, float] = {}
    for it in items:
        owner = it.get("owner_name")
        if not owner:
            continue
        if it.get("status") in ("done", "skipped", "cancelled"):
            continue
        ds, de = _parse_date(it.get("planned_start")), _parse_date(it.get("planned_end"))
        est_h = float(it.get("estimated_hours") or 0)
        if est_h <= 0:
            continue
        if not ds or not de:
            # Unscheduled item — bucket under "unscheduled"
            key = ("unscheduled", owner)
            by_day_worker[key] = by_day_worker.get(key, 0) + est_h
            continue
        # Spread hours evenly across the date span
        days = max(1, (de - ds).days + 1)
        per_day = est_h / days
        cur = ds
        while cur <= de:
            d_str = cur.date().isoformat()
            key = (d_str, owner)
            by_day_worker[key] = by_day_worker.get(key, 0) + per_day
            cur += timedelta(days=1)

    histogram = []
    overloaded_days = []
    workers_seen: set[str] = set()
    for (d, w), h in sorted(by_day_worker.items()):
        h_round = round(h, 2)
        overloaded = h_round > daily_hours
        histogram.append({"date": d, "worker": w, "hours": h_round, "overloaded": overloaded})
        if overloaded:
            overloaded_days.append({"date": d, "worker": w, "hours": h_round, "over_by": round(h_round - daily_hours, 2)})
        workers_seen.add(w)

    # ── Suggestion heuristic: for each overloaded day, find a worker who
    # has spare capacity that day on the same project. Light-touch v1.
    suggestions = []
    workers = sorted(workers_seen)
    for o in overloaded_days[:10]:  # cap at 10 to avoid noise
        d, overloaded_w = o["date"], o["worker"]
        # find slack workers
        slack = [w for w in workers
                 if w != overloaded_w
                 and by_day_worker.get((d, w), 0) < daily_hours - 2]
        if slack:
            suggestions.append({
                "date": d,
                "from_worker": overloaded_w,
                "to_worker": slack[0],
                "reason": f"{overloaded_w} is at {o['hours']}h on {d}; {slack[0]} has spare capacity.",
            })

    return {
        "histogram": histogram,
        "overloaded_days": overloaded_days,
        "suggestions": suggestions,
        "daily_hours": daily_hours,
        "workers": workers,
    }
