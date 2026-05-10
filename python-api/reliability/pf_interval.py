"""P-F interval calculator (Phase R.6).

P-F (Potential failure to Functional failure) is the time from the moment a
defect becomes detectable (parameter crosses the P threshold) until the
asset has actually failed (parameter crosses the F threshold). The standard
RCM rule sets the inspection interval to P-F / 2 for normal assets and
P-F / 3 for safety- or environment-critical assets, so the inspection always
catches the defect at least once before failure.

Inputs (from edge fn pf-calculator):
  readings:        [{"ts": iso8601, "value": float}, ...]
  p_threshold:     float   warning level (the alarm trigger)
  f_threshold:     float   functional-failure level
  direction:       'above' | 'below'
                   'above': value rising past threshold means alarm/failure
                            (vibration, temperature, pressure-drop)
                   'below': value falling past threshold means alarm/failure
                            (oil level, insulation resistance, flow)
  safety_critical: bool   when true the basis becomes P-F/3 (more conservative)

Output (matches pf_intervals row shape):
  pf_days:                   float  median observed P-F window (days)
  recommended_interval_days: int    pf_days / divisor (always >= 1)
  basis:                     'P-F/2' | 'P-F/3'
  n_pairs:                   int    how many P-F pairs were detected
  pairs:                     list of {p_ts, f_ts, days_between}
  diagnostic:                str    human-readable note

Insufficient-data rule:
  - fewer than 2 valid readings, or
  - no detectable P-F pair
  -> returns pf_days=None and a diagnostic; the edge fn does NOT persist
     because pf_intervals.pf_days has a CHECK > 0.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime
from statistics import median


def _parse_ts(ts: str) -> float | None:
    """Convert ISO 8601 timestamp to a float (epoch seconds). Returns None on parse failure."""
    if not ts:
        return None
    try:
        # Python 3.11+ tolerates 'Z' via fromisoformat; older versions need replace.
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _exceeds(value: float, threshold: float, direction: str) -> bool:
    if direction == "below":
        return value <= threshold
    return value >= threshold     # 'above' is the default


def _detect_pairs(
    readings: list[dict[str, Any]],
    p_threshold: float,
    f_threshold: float,
    direction: str,
) -> list[dict[str, Any]]:
    """Walk the time-sorted reading series and capture each P→F transition.

    Returns one pair per cycle:
      - record the first reading that crosses the P threshold
      - the next reading that crosses the F threshold seals the pair
      - reset and continue (so a long history with multiple defect cycles
        contributes multiple data points)
    """
    points = []
    for r in readings:
        ts = _parse_ts(r.get("ts"))
        try:
            v = float(r.get("value"))
        except Exception:
            continue
        if ts is None:
            continue
        points.append((ts, v))
    points.sort(key=lambda p: p[0])

    pairs: list[dict[str, Any]] = []
    p_ts: float | None = None

    for ts, v in points:
        crossed_p = _exceeds(v, p_threshold, direction)
        crossed_f = _exceeds(v, f_threshold, direction)
        if p_ts is None and crossed_p and not crossed_f:
            p_ts = ts
        elif p_ts is not None and crossed_f:
            days = (ts - p_ts) / 86_400.0
            if days > 0:
                pairs.append({
                    "p_ts":         datetime.utcfromtimestamp(p_ts).isoformat() + "Z",
                    "f_ts":         datetime.utcfromtimestamp(ts).isoformat() + "Z",
                    "days_between": round(days, 3),
                })
            p_ts = None
    return pairs


def calculate_pf(
    readings: list[dict[str, Any]],
    p_threshold: float,
    f_threshold: float,
    direction: str = "above",
    safety_critical: bool = False,
) -> dict[str, Any]:
    """Public entry point used by main.py /reliability/pf-interval.

    Always returns a JSON-safe dict; never raises for "no data".
    """
    direction = "below" if str(direction).lower() == "below" else "above"

    if direction == "above" and p_threshold >= f_threshold:
        return {
            "pf_days":                   None,
            "recommended_interval_days": None,
            "basis":                     "P-F/3" if safety_critical else "P-F/2",
            "n_pairs":                   0,
            "pairs":                     [],
            "diagnostic": (
                "Invalid thresholds: with direction='above', P (warning) must be lower than F (failure). "
                "Otherwise the alarm fires at the same time the asset has already failed."
            ),
        }
    if direction == "below" and p_threshold <= f_threshold:
        return {
            "pf_days":                   None,
            "recommended_interval_days": None,
            "basis":                     "P-F/3" if safety_critical else "P-F/2",
            "n_pairs":                   0,
            "pairs":                     [],
            "diagnostic": (
                "Invalid thresholds: with direction='below', P (warning) must be higher than F (failure). "
                "Otherwise the alarm fires at the same time the asset has already failed."
            ),
        }

    pairs = _detect_pairs(readings or [], float(p_threshold), float(f_threshold), direction)
    basis_divisor = 3 if safety_critical else 2
    basis_label   = "P-F/3" if safety_critical else "P-F/2"

    if not pairs:
        return {
            "pf_days":                   None,
            "recommended_interval_days": None,
            "basis":                     basis_label,
            "n_pairs":                   0,
            "pairs":                     [],
            "diagnostic": (
                "No P-F pair detected in the supplied readings. Ensure the parameter "
                "actually crosses both thresholds within the observation window."
            ),
        }

    days_list = [p["days_between"] for p in pairs]
    pf_days   = float(median(days_list))
    interval  = max(1, int(round(pf_days / basis_divisor)))

    return {
        "pf_days":                   round(pf_days, 3),
        "recommended_interval_days": interval,
        "basis":                     basis_label,
        "n_pairs":                   len(pairs),
        "pairs":                     pairs,
        "diagnostic": (
            f"Median P-F window {pf_days:.1f}d across {len(pairs)} pair(s). "
            f"Recommended inspection interval = {pf_days:.1f} / {basis_divisor} = {interval}d "
            f"(basis {basis_label}). Inspect at this cadence so the defect is caught at least "
            f"once between P and F."
        ),
    }
