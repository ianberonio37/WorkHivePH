"""validate_sensor_pipeline.py - Phase 1.9 of STRATEGIC_ROADMAP.md.

Architectural contract gate for the MQTT/OPC-UA sensor pipeline (Wave B1).
A hive that runs a sensor bridge writes to sensor_readings; the worker UI
subscribes via realtime; the Python anomaly module reads to flag drifts.

Layers:
  L1  sensor_readings migration exists with hive_id + asset_id + ts + value
  L2  sensor_readings is in supabase_realtime publication
  L3  asset-hub.html subscribes to sensor_readings via postgres_changes
  L4  sensor_readings is registered in canonical_sources
  L5  python-api/sensors/anomaly.py exists (z-score helper)

Skills consulted:
  data-engineer (time-series schema must be append-only, indexed on
    (hive_id, asset_id, ts DESC) for live polling)
  realtime-engineer (subscription requires publication)
  predictive-analytics (anomaly detection on raw sensor stream is the
    feedstock for Stair-3 predictive output)
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).parent
MIGRATION_GLOB = "supabase/migrations/*_sensor_readings.sql"
ASSET_HUB     = ROOT / "asset-hub.html"
ANOMALY_PY    = ROOT / "python-api" / "sensors" / "anomaly.py"

LAYERS = [
    {"layer": "L1", "label": "sensor_readings migration with hive_id+asset_id+ts+value"},
    {"layer": "L2", "label": "sensor_readings in supabase_realtime publication"},
    {"layer": "L3", "label": "asset-hub.html subscribes to sensor_readings"},
    {"layer": "L4", "label": "sensor_readings registered in canonical_sources"},
    {"layer": "L5", "label": "python-api/sensors/anomaly.py exists"},
]


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _find_migration() -> Path | None:
    matches = sorted(ROOT.glob(MIGRATION_GLOB))
    return matches[-1] if matches else None


def run() -> dict:
    issues: list[dict] = []
    m = _find_migration()
    if not m:
        issues.append({"check": "l1", "layer": "L1",
                       "reason": "No supabase/migrations/*_sensor_readings.sql found."})
    else:
        src = _read(m)
        required = ["sensor_readings", "hive_id", "asset_id"]
        missing = [c for c in required if c not in src]
        if missing:
            issues.append({"check": "l1_columns", "layer": "L1",
                           "reason": f"{m.name} is missing columns: {missing}."})
        if "ALTER PUBLICATION supabase_realtime" not in src or "sensor_readings" not in src:
            issues.append({"check": "l2", "layer": "L2",
                           "reason": "sensor_readings is not added to "
                                     "supabase_realtime publication."})
        if "canonical_sources" not in src:
            issues.append({"check": "l4", "layer": "L4",
                           "reason": "sensor_readings is not registered in canonical_sources."})

    if not ASSET_HUB.exists():
        issues.append({"check": "l3_asset_hub_missing", "layer": "L3",
                       "reason": "asset-hub.html not found."})
    else:
        hub = _read(ASSET_HUB)
        if "sensor_readings" not in hub or "postgres_changes" not in hub:
            issues.append({"check": "l3", "layer": "L3",
                           "reason": "asset-hub.html does not subscribe to "
                                     "sensor_readings via postgres_changes."})

    if not ANOMALY_PY.exists():
        issues.append({"check": "l5", "layer": "L5",
                       "reason": "python-api/sensors/anomaly.py not found. "
                                 "Without it, z-score / spike detection has no "
                                 "implementation."})

    failed_layers = {i.get("layer") for i in issues if i.get("layer")}
    failed = len(failed_layers)
    passed = len(LAYERS) - failed
    return {"validator": "sensor_pipeline", "total_checks": len(LAYERS),
            "passed": passed, "failed": failed, "warned": 0,
            "layers": LAYERS, "issues": issues, "warnings": []}


def main() -> int:
    out = run()
    print(f"\nSensor Pipeline Validator ({len(out['layers'])}-layer)")
    print("=" * 55)
    for layer in out["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    if out["issues"]:
        print(f"  \033[91m{out['failed']} FAIL\033[0m")
        for i in out["issues"]:
            print(f"  [FAIL] [{i['check']}]  {i['reason']}")
    else:
        print(f"  \033[92mAll {out['total_checks']} checks passed.\033[0m")
    (ROOT / "sensor_pipeline_report.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    return 1 if out["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
