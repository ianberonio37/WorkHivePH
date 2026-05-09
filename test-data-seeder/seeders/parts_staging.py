"""Seed one pending parts_staging_recommendation per hive.

Without this, Asset Hub's Recommended Parts to Stage panel and Alert Hub's
Staging filter chip have no data after seed_all -- the staging UI surfaces
look broken in test mode even though the schema and edge fn are healthy.

The recommendation is attached to the highest-risk asset that already has
a risk score >= 0.7 (from risk_scores.py), and picks 2-3 parts from the
hive's approved inventory so the in_stock numbers shown in the UI are real.
"""
import datetime, json, random
from .utils import batch_insert


def seed_parts_staging(client, log, ctx: dict) -> dict:
    log("Seeding 1 pending parts_staging_recommendation per hive...")
    hives = ctx.get("hives") or []
    if not hives:
        log("  no hives in ctx -- parts_staging skipped")
        return {"parts_staging_recs_count": 0}

    now = datetime.datetime.utcnow()
    rows = []
    for hive in hives:
        hive_id = hive["id"]

        # Pick the highest-risk asset (score >= 0.7) seeded by risk_scores.py
        risk_rows = client.table("asset_risk_scores") \
            .select("asset_name, risk_score") \
            .eq("hive_id", hive_id) \
            .gte("risk_score", 0.7) \
            .order("risk_score", desc=True) \
            .limit(1) \
            .execute().data or []
        if not risk_rows:
            log(f"  hive {hive_id}: no high-risk asset to attach a recommendation to (skip)")
            continue
        asset = risk_rows[0]

        # Pick 2-3 approved inventory items for this hive
        inv = client.table("inventory_items") \
            .select("id, part_name, qty_on_hand") \
            .eq("hive_id", hive_id) \
            .eq("status", "approved") \
            .limit(8) \
            .execute().data or []
        if not inv:
            log(f"  hive {hive_id}: no approved inventory items -- recommendation skipped")
            continue
        picked = random.sample(inv, min(3, len(inv)))

        parts = [
            {
                "item_id":    item["id"],
                "part_name":  item.get("part_name") or "Unnamed",
                "qty_avg":    1,
                "confidence": round(random.uniform(0.55, 0.85), 2),
                "in_stock":   int(item.get("qty_on_hand") or 0),
            }
            for item in picked
        ]
        overall_conf = round(sum(p["confidence"] for p in parts) / len(parts), 2)

        rows.append({
            "hive_id":       hive_id,
            "asset_name":    asset["asset_name"],
            "risk_score":    asset["risk_score"],
            "failure_mode":  "Repeat bearing failure pattern",
            "parts":         json.dumps(parts),
            "rationale":     (
                f"Risk score {asset['risk_score']:.2f} on {asset['asset_name']}. "
                f"{len(parts)} parts appear in 55%+ of past corrective fixes "
                "for this asset. Stage now to prevent unplanned downtime."
            ),
            "confidence":    overall_conf,
            "status":        "pending",
            "generated_at":  now.isoformat() + "Z",
            "expires_at":    (now + datetime.timedelta(days=7)).isoformat() + "Z",
            "model_version": "rules-v1",
        })

    if not rows:
        return {"parts_staging_recs_count": 0}

    inserted = batch_insert(client, "parts_staging_recommendations", rows, chunk=200)
    log(f"  inserted {inserted} parts_staging_recommendations")
    return {"parts_staging_recs_count": inserted}
