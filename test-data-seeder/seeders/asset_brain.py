"""Seed asset_nodes from existing seeded assets.

Asset Brain Phase 0 schema is empty by default in fresh test envs, which leaves
asset-hub.html showing a "no assets yet" state even though pm-scheduler and
logbook show plenty of activity. This seeder mirrors each ctx['assets'] row
into asset_nodes (level='equipment') so the hub renders immediately.

Edges are intentionally skipped — the hierarchy is best derived by the
20260508000010_asset_brain_backfill.sql migration which knows the production
mapping rules. We just create the leaf-level nodes here.

iso_class:
  The legacy assets table has a free-text `type` column ("Air Compressor",
  "Centrifugal Pump", "VFD", etc.). asset_nodes.iso_class is the high-level
  ISO 14224 discipline bucket (Mechanical / Electrical / Hydraulic /
  Pneumatic / Instrumentation / Lubrication) used by:
    - asset-hub.html Reliability Report header
    - test-data-seeder/seeders/reliability.py FMEA template selector
    - test-data-seeder asset_hub_flow legacy bridge checks
  We classify by keyword on the type string. Without iso_class set, the
  reliability seeder falls back to "Mechanical" templates everywhere and the
  Print Report shows "ISO 14224 class: --" for every asset.
"""
from .utils import batch_insert


# Substring matchers (case-insensitive). First match wins. Order matters:
# more-specific tokens (transmitter / VFD) come before generic fallbacks.
_ISO_CLASS_RULES = [
    # Instrumentation — sensors and transmitters
    (("transmitter", "sensor", "indicator", "gauge", "meter"), "Instrumentation"),
    # Electrical — switchgear, drives, motors, transformers, control panels
    (("vfd", "ups", "transformer", "switchgear", "plc", "motor", "welder"),
     "Electrical"),
    # Pneumatic — compressed-air machines
    (("compressor", "pneumat"), "Pneumatic"),
    # Hydraulic — hydraulic power units
    (("hydraulic",), "Hydraulic"),
    # Lubrication — explicit lubrication systems
    (("luber", "lube", "lubric"), "Lubrication"),
    # Default Mechanical: pumps, boilers, conveyors, gensets, vessels, HVAC, etc.
]


def _classify_iso(type_str: str | None) -> str:
    s = (type_str or "").strip().lower()
    if not s:
        return "Mechanical"
    for tokens, bucket in _ISO_CLASS_RULES:
        for tok in tokens:
            if tok in s:
                return bucket
    return "Mechanical"


def seed_asset_brain(client, log, ctx: dict) -> dict:
    log("Seeding asset_nodes from seeded assets...")
    assets = ctx.get("assets") or []
    if not assets:
        log("  no assets in ctx — asset_nodes skipped")
        return {"asset_nodes_count": 0}

    crit_map = {"Critical": "critical", "High": "high", "Medium": "medium", "Low": "low"}

    rows = []
    for a in assets:
        rows.append({
            "hive_id":         a["hive_id"],
            "worker_name":     a.get("worker_name") or a.get("submitted_by"),
            "level":           "equipment",
            "tag":             a.get("asset_id") or a.get("name") or "untagged",
            "name":            a.get("name") or a.get("asset_id") or "Unnamed",
            "iso_class":       _classify_iso(a.get("type")),
            "criticality":     crit_map.get(a.get("criticality") or "Medium", "medium"),
            "location":        a.get("location"),
            "legacy_asset_id": a["id"],
            "status":          "approved",
            "submitted_by":    a.get("submitted_by"),
            "approved_by":     a.get("approved_by"),
            "approved_at":     a.get("approved_at"),
        })

    inserted = batch_insert(client, "asset_nodes", rows, chunk=500)
    log(f"  inserted {inserted} asset_nodes")
    return {"asset_nodes_count": inserted}
