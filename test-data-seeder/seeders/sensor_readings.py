"""Seed sensor_readings - 30 days of plant telemetry per asset.

Without this, the asset-hub.html Live Telemetry tile is empty on every
fresh seed, and the Z-score anomaly chip never fires. We synthesize a
realistic time-series per asset: 3 parameters (vibration, temperature,
current_draw) at 10-minute intervals, with an occasional anomaly burst
so the analytics layer has something to detect.

We deliberately use source='sensor_test' so production dashboards can
filter test data out (matches the production sensor-readings-ingest enum).
The external_key trigger in the DB fills the dedup key on insert; we
don't need to compute it client-side.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone


# Parameter profiles - realistic ranges + noise model + unit
PARAMS = {
    "vibration": {
        "baseline": 2.4, "noise": 0.4, "unit": "mm/s",
        "sensor_type": "analog",
        "anomaly_burst": (8.0, 14.0),     # 3-5 sigma burst when anomaly fires
    },
    "temperature": {
        "baseline": 62.0, "noise": 3.0, "unit": "celsius",
        "sensor_type": "analog",
        "anomaly_burst": (85.0, 95.0),
    },
    "current_draw": {
        "baseline": 14.0, "noise": 1.2, "unit": "ampere",
        "sensor_type": "analog",
        "anomaly_burst": (22.0, 28.0),
    },
}

# Realistic plant interval is 10s-1min; for 30 days of 3 params per asset
# at every minute that's 30*24*60*3 = 129,600 rows per asset, which blows
# up the seed. We use 30-min intervals -> 30*48*3 = 4320 rows per asset,
# which is enough for the Live Telemetry tile + Z-score chip to render.
INTERVAL_MINUTES = 30
DAYS = 30
ASSETS_PER_HIVE = 6   # seed top N assets per hive to keep total bounded


def _anomaly_pattern(day_idx: int, total_days: int) -> bool:
    """Return True if this minute should be inside an anomaly burst.

    Anomalies are clustered (a burst lasts ~2 hours then subsides) and
    concentrated in the last 10 days so the trend chart shows
    degradation over time, mirroring real bearing/seal failure modes.
    """
    if day_idx < total_days * 0.66:
        return random.random() < 0.005    # rare baseline noise
    return random.random() < 0.05         # ~5% of late-period readings


def seed_sensor_readings(client, log, ctx: dict) -> dict:
    log(f"Seeding sensor_readings ({DAYS} days x 3 params x top {ASSETS_PER_HIVE} assets/hive)...")

    hives = client.table("hives").select("id, name").execute().data or []
    if not hives:
        log("  no hives - sensor_readings skipped")
        return {"sensor_readings_count": 0}

    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(days=DAYS)

    total_inserted = 0
    for h in hives:
        hive_id = h["id"]
        assets = client.table("asset_nodes").select("id, name").eq(
            "hive_id", hive_id,
        ).limit(ASSETS_PER_HIVE).execute().data or []
        if not assets:
            continue

        rows = []
        for a in assets:
            asset_id = a["id"]
            for param_name, prof in PARAMS.items():
                t = start
                day_idx = 0
                while t <= now:
                    day_idx = (t - start).days
                    if _anomaly_pattern(day_idx, DAYS):
                        lo, hi = prof["anomaly_burst"]
                        v = random.uniform(lo, hi)
                        quality = "uncertain"
                    else:
                        # Smooth seasonal-ish curve so the chart isn't pure noise
                        seasonal = math.sin((t.hour * 60 + t.minute) / 1440 * 2 * math.pi) * prof["noise"] * 0.4
                        v = prof["baseline"] + seasonal + random.gauss(0, prof["noise"])
                        quality = "good"
                    rows.append({
                        "hive_id":      hive_id,
                        "asset_id":     asset_id,
                        "parameter":    param_name,
                        "sensor_type":  prof["sensor_type"],
                        "unit":         prof["unit"],
                        "quality_flag": quality,
                        "value":        round(float(v), 3),
                        "recorded_at":  t.isoformat(),
                        "source":       "sensor_test",
                        # external_key is filled by the BEFORE-INSERT trigger
                        # (sensor_readings_set_external_key). For seeds we
                        # still need a non-null value to satisfy the NOT NULL
                        # constraint if the trigger is somehow disabled, so
                        # we supply a deterministic seed-side key.
                        "external_key": f"seed:{asset_id}:{param_name}:{t.isoformat()}",
                    })
                    t = t + timedelta(minutes=INTERVAL_MINUTES)

        # Insert in chunks; ON CONFLICT (external_key) DO NOTHING is implicit
        # via the UNIQUE index - duplicates from a re-seed (without reset) are
        # silently rejected by the unique constraint.
        from .utils import batch_insert
        try:
            inserted = batch_insert(client, "sensor_readings", rows, chunk=800)
        except Exception as e:
            log(f"  hive {h.get('name', hive_id)[:30]}: insert failed: {e}")
            continue
        total_inserted += inserted
        log(f"  hive {h.get('name', hive_id)[:30]}: {inserted} readings across {len(assets)} assets")

    log(f"  total sensor_readings: {total_inserted}")
    return {"sensor_readings_count": total_inserted}
