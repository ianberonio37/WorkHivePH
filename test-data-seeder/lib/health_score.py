"""Unified health score — Formula C (locked 2026-05-04).

  Start 100.
  Each CRITICAL FAIL (static or data layer):  -10
  Each STANDARD FAIL (ui, ai, visual, perf):  -3
  Each WARN (anywhere):                       -0.3
  Stale (>24h since last run):                -10
  Floor at 0.

Color tiers:
  >=95  Healthy
  >=80  Drift
  >=60  Concerning
   <60  Broken

Streak rule: consecutive DAYS with at least one PASS run. Resets on any FAIL
or 24h+ gap with no run.
"""
from datetime import date as DateType
from datetime import datetime, timezone

CRITICAL_LAYERS = {"static", "data"}

PENALTY_CRITICAL = 10
PENALTY_STANDARD = 3
PENALTY_WARN     = 0.3
PENALTY_STALE    = 10

TIER_CUTOFFS = [(95, "Healthy"), (80, "Drift"), (60, "Concerning"), (0, "Broken")]


def tier_for(score: int) -> str:
    for cutoff, name in TIER_CUTOFFS:
        if score >= cutoff:
            return name
    return "Broken"


def compute_score(layers: dict, last_run_iso: str | None = None) -> dict:
    """Compute the score from layer summaries and an optional last-run timestamp.

    layers shape:
      { "static": {"pass": 54, "fail": 0, "warn": 0}, ... }
    """
    score = 100.0
    breakdown = []

    for layer_name, summary in layers.items():
        fails = summary.get("fail", 0) or 0
        warns = summary.get("warn", 0) or 0
        per_fail = PENALTY_CRITICAL if layer_name in CRITICAL_LAYERS else PENALTY_STANDARD
        fail_penalty = fails * per_fail
        warn_penalty = warns * PENALTY_WARN
        score -= fail_penalty + warn_penalty
        breakdown.append({
            "layer": layer_name,
            "passes": summary.get("pass", 0) or 0,
            "fails": fails,
            "warns": warns,
            "fail_penalty": fail_penalty,
            "warn_penalty": round(warn_penalty, 1),
            "is_critical_layer": layer_name in CRITICAL_LAYERS,
        })

    stale = False
    if last_run_iso:
        try:
            last_run = datetime.fromisoformat(last_run_iso.replace("Z", "+00:00"))
            hours_since = (datetime.now(timezone.utc) - last_run).total_seconds() / 3600
            if hours_since > 24:
                score -= PENALTY_STALE
                stale = True
        except Exception:
            pass

    score = max(0, round(score))
    return {
        "score": score,
        "tier": tier_for(score),
        "stale": stale,
        "breakdown": breakdown,
    }


def update_streak(streak: dict, verdict: str, run_date_str: str, commit: str | None = None) -> dict:
    """Update streak based on a new run. run_date_str is YYYY-MM-DD."""
    today = DateType.fromisoformat(run_date_str)
    current = int(streak.get("current_streak", 0) or 0)
    best = int(streak.get("best_streak", 0) or 0)
    last_green = streak.get("last_green_date")

    if verdict == "PASS":
        if last_green:
            last = DateType.fromisoformat(last_green)
            delta = (today - last).days
            if delta == 0:
                pass  # same day, streak unchanged
            elif delta == 1:
                current += 1
            else:
                current = 1  # gap broke the streak, restart
        else:
            current = 1
        streak["current_streak"] = current
        streak["last_green_date"] = run_date_str
        if commit:
            streak["last_green_commit"] = commit
        if current > best:
            streak["best_streak"] = current
    else:
        # Any non-PASS verdict resets streak
        if current > 0:
            streak["broken_at"] = run_date_str
            streak["broken_after_days"] = current
        streak["current_streak"] = 0

    streak["last_run_date"] = run_date_str
    streak["last_run_verdict"] = verdict
    return streak
