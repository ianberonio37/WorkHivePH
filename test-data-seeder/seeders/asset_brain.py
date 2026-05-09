"""Seed asset_nodes from existing seeded assets.

Asset Brain Phase 0 schema is empty by default in fresh test envs, which leaves
asset-hub.html showing a "no assets yet" state even though pm-scheduler and
logbook show plenty of activity. This seeder mirrors each ctx['assets'] row
into asset_nodes (level='equipment') so the hub renders immediately.

Edges are intentionally skipped — the hierarchy is best derived by the
20260508000010_asset_brain_backfill.sql migration which knows the production
mapping rules. We just create the leaf-level nodes here.
"""
from .utils import batch_insert


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
