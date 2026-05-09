"""Seed one active parts_staged_reservation per hive.

Without this, Inventory's orange "X reserved" badge never appears in test
mode -- workers viewing inventory.html see no evidence of the Auto-Staging
flow ever happening, even though the migration and edge fn are healthy.

The reservation is attached to the first approved inventory item per hive
and the highest-risk asset_name that has a risk score in the table. Marked
active by leaving consumed_at and released_at NULL.
"""
import datetime
from .utils import batch_insert


def seed_parts_reservations(client, log, ctx: dict) -> dict:
    log("Seeding 1 active parts_staged_reservation per hive...")
    hives = ctx.get("hives") or []
    if not hives:
        log("  no hives in ctx -- parts_reservations skipped")
        return {"parts_reservations_count": 0}

    rows = []
    for hive in hives:
        hive_id = hive["id"]

        inv = client.table("inventory_items") \
            .select("id, part_name") \
            .eq("hive_id", hive_id) \
            .eq("status", "approved") \
            .limit(1) \
            .execute().data or []
        if not inv:
            log(f"  hive {hive_id}: no approved inventory items -- reservation skipped")
            continue

        # Pick a high-risk asset to attribute the reservation to (or fall back to a generic name)
        risk_rows = client.table("asset_risk_scores") \
            .select("asset_name") \
            .eq("hive_id", hive_id) \
            .gte("risk_score", 0.7) \
            .limit(1) \
            .execute().data or []
        asset_name = (risk_rows[0]["asset_name"] if risk_rows else "Demo Asset")

        rows.append({
            "hive_id":      hive_id,
            "asset_name":   asset_name,
            "item_id":      inv[0]["id"],
            "qty_reserved": 1,
            "reserved_by":  "tester-seed",
            "notes":        f"Demo reservation seeded for {inv[0].get('part_name') or 'unnamed part'}",
        })

    if not rows:
        return {"parts_reservations_count": 0}

    inserted = batch_insert(client, "parts_staged_reservations", rows, chunk=100)
    log(f"  inserted {inserted} parts_staged_reservations")
    return {"parts_reservations_count": inserted}
