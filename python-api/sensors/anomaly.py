"""Rule-based Z-score anomaly detection over sensor_readings.

Per the predictive-analytics skill: start with rules, move to ML when data
is sufficient. Z-score is the simplest defensible anomaly signal and gives
maintenance engineers a number they can interpret. ML (IsolationForest) is
deferred until each hive has 30+ days of stable readings per parameter,
which prevents cold-start false positives.

The endpoint is consumed by:
  - asset-hub.html Live Telemetry tile (per-asset, per-parameter)
  - batch-risk-scoring edge fn (folds sensor_anomaly_score into v_risk_truth
    top_factors as the 7th factor in the Phase 5b composite model)

Wire into python-api/main.py with:

    from sensors.anomaly import handle_zscore
    elif path == "/sensors/anomaly-z":
        return handle_zscore(payload, supabase)

Skills consulted: predictive-analytics (Z-score over recent window is the
canonical baseline; >3-sigma classic threshold), data-engineer (narrow
select, hive-scoped, n >= min_n guard before reporting), security (no PII
in response, hive isolation at the SQL layer not the application).
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any


DEFAULT_WINDOW_DAYS = 30
DEFAULT_MIN_N       = 20         # need at least this many readings to be defensible
Z_ANOMALY_THRESHOLD = 3.0        # classic 3-sigma rule
Z_WARNING_THRESHOLD = 2.0        # heads-up but not "anomaly"

PARAMETER_RE_PY = r"^[a-z][a-z0-9_]{0,40}$"


def _validate_params(payload: dict[str, Any]) -> tuple[str, str, str, int, int]:
    """Pull and sanity-check the inputs. Raises ValueError on bad input."""
    import re as _re

    hive_id   = str(payload.get("hive_id") or "").strip()
    asset_id  = str(payload.get("asset_id") or "").strip()
    parameter = str(payload.get("parameter") or "").strip().lower()
    if not hive_id or not asset_id:
        raise ValueError("hive_id and asset_id are required")
    if not parameter or not _re.match(PARAMETER_RE_PY, parameter):
        raise ValueError("parameter is required and must match ^[a-z][a-z0-9_]{0,40}$")

    window_days = int(payload.get("window_days") or DEFAULT_WINDOW_DAYS)
    if window_days < 1 or window_days > 365:
        raise ValueError("window_days must be between 1 and 365")

    min_n = int(payload.get("min_n") or DEFAULT_MIN_N)
    if min_n < 3:
        raise ValueError("min_n must be at least 3")

    return hive_id, asset_id, parameter, window_days, min_n


def handle_zscore(payload: dict[str, Any], supabase: Any) -> dict[str, Any]:
    """POST /sensors/anomaly-z handler.

    Input:
      { hive_id, asset_id, parameter, window_days?: 30, min_n?: 20 }

    Output (on success):
      {
        n:                 int,        # readings in window
        mean:              float,
        std:               float,
        latest_value:      float,
        latest_recorded_at: ISO string,
        z:                 float,
        anomaly:           bool,       # z >= Z_ANOMALY_THRESHOLD
        warning:           bool,       # Z_WARNING_THRESHOLD <= z < Z_ANOMALY_THRESHOLD
        diagnostic:        str
      }

    On insufficient data: returns { n, diagnostic, anomaly: false, warning: false }
    and the caller should hide the anomaly chip on the Live Telemetry tile.
    """
    try:
        hive_id, asset_id, parameter, window_days, min_n = _validate_params(payload)
    except ValueError as e:
        return {"error": str(e), "status": 400}

    since_iso = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()

    # Narrow select - we only need (value, recorded_at). Hive-scoped at the
    # SQL layer because RLS is enabled and the python-api uses the service
    # role; we add the explicit eq() anyway as defense-in-depth.
    res = (
        supabase.table("sensor_readings")
        .select("value, recorded_at")
        .eq("hive_id",   hive_id)
        .eq("asset_id",  asset_id)
        .eq("parameter", parameter)
        .gte("recorded_at", since_iso)
        .order("recorded_at", desc=True)
        .limit(2000)
        .execute()
    )
    rows = res.data or []

    n = len(rows)
    if n < min_n:
        return {
            "n":                 n,
            "mean":              None,
            "std":               None,
            "latest_value":      rows[0]["value"] if rows else None,
            "latest_recorded_at": rows[0]["recorded_at"] if rows else None,
            "z":                 None,
            "anomaly":           False,
            "warning":           False,
            "diagnostic": (
                f"Insufficient data: need at least {min_n} readings in the last "
                f"{window_days} days (have {n}). Once the plant bridge has been "
                f"running for a couple of days, this will populate."
            ),
        }

    values = [float(r["value"]) for r in rows if r.get("value") is not None]
    if len(values) < min_n:
        return {
            "n":                 len(values),
            "diagnostic":        "Some rows had null value; filtered them out, n now under min_n.",
            "anomaly":           False,
            "warning":           False,
        }

    mean = sum(values) / len(values)
    var  = sum((v - mean) ** 2 for v in values) / max(1, len(values) - 1)
    std  = math.sqrt(var)

    latest      = values[0]
    latest_ts   = rows[0]["recorded_at"]
    if std <= 0:
        # Degenerate case: every reading is identical. Treat latest deviation
        # of 0 as not-an-anomaly.
        return {
            "n":                 len(values),
            "mean":              mean,
            "std":               0.0,
            "latest_value":      latest,
            "latest_recorded_at": latest_ts,
            "z":                 0.0,
            "anomaly":           False,
            "warning":           False,
            "diagnostic":        "Zero variance in window - sensor may be stuck or value is constant.",
        }

    z = abs(latest - mean) / std
    is_anom = z >= Z_ANOMALY_THRESHOLD
    is_warn = (z >= Z_WARNING_THRESHOLD) and not is_anom

    sign = "above" if latest > mean else "below"
    diag = (
        f"Latest value {latest:.4g} is {z:.2f} sigma {sign} the {len(values)}-reading "
        f"window mean of {mean:.4g} (std {std:.4g})."
    )

    return {
        "n":                 len(values),
        "mean":              mean,
        "std":               std,
        "latest_value":      latest,
        "latest_recorded_at": latest_ts,
        "z":                 z,
        "anomaly":           is_anom,
        "warning":           is_warn,
        "diagnostic":        diag,
    }


def zscore_compute(
    values: list,
    latest: float | None = None,
    z_anomaly: float | None = None,
    z_warning: float | None = None,
) -> dict[str, Any]:
    """Pure-compute 3-sigma Z-score anomaly check on a caller-supplied values array — NO DB.

    handle_zscore() above fetches `sensor_readings` then runs exactly this math; exposing the
    pure core as a stateless compute route (/sensors/zscore) lets a client (or the plant bridge
    in test) check anomalies on its own window without a Supabase round-trip. Same 3-sigma rule,
    same warning band — deterministic given the input (UFAI P7 F1 value-oracle + A4 statelessness).

    `latest` defaults to values[0] (handle_zscore treats the most-recent reading as the latest).
    """
    za = Z_ANOMALY_THRESHOLD if z_anomaly is None else float(z_anomaly)
    zw = Z_WARNING_THRESHOLD if z_warning is None else float(z_warning)
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    if n < 2:
        return {"n": n, "mean": None, "std": None, "z": None,
                "anomaly": False, "warning": False,
                "diagnostic": "Insufficient data: need at least 2 values."}
    latest = vals[0] if latest is None else float(latest)
    mean = sum(vals) / n
    var = sum((v - mean) ** 2 for v in vals) / max(1, n - 1)
    std = math.sqrt(var)
    if std <= 0:
        return {"n": n, "mean": mean, "std": 0.0, "latest": latest, "z": 0.0,
                "anomaly": False, "warning": False,
                "diagnostic": "Zero variance in window — sensor may be stuck or value is constant."}
    z = abs(latest - mean) / std
    is_anom = z >= za
    is_warn = (z >= zw) and not is_anom
    sign = "above" if latest > mean else "below"
    return {
        "n": n, "mean": mean, "std": std, "latest": latest, "z": z,
        "anomaly": is_anom, "warning": is_warn,
        "diagnostic": f"Latest value {latest:.4g} is {z:.2f} sigma {sign} the {n}-reading "
                      f"window mean of {mean:.4g} (std {std:.4g}).",
    }
