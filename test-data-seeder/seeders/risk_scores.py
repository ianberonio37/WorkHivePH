"""Seed asset_risk_scores so the predictive page, asset hub risk panel, and
alert hub risk feed all show data without waiting for the daily 13:00 PHT
batch-risk-scoring cron.

For each hive: pick 5 assets and assign a spread of risk levels:
  - 1 critical (score 0.90)
  - 1 high     (score 0.78)
  - 2 medium   (score 0.55, 0.50)
  - 1 low      (score 0.20)
"""
import random
from .utils import batch_insert


def seed_risk_scores(client, log, ctx: dict) -> dict:
    log("Seeding asset_risk_scores spread per hive...")
    assets_by_hive = ctx.get("assets_by_hive") or {}
    if not assets_by_hive:
        log("  no assets in ctx — risk scores skipped")
        return {"risk_scores_count": 0}

    spread = [
        ("critical", 0.90, ["pm_overdue", "repeat_fault", "high_fault_freq"], 12.0),
        ("high",     0.78, ["high_fault_freq", "mtbf_approaching"],          22.0),
        ("medium",   0.55, ["pm_overdue"],                                   45.0),
        ("medium",   0.50, ["mtbf_approaching"],                             52.0),
        ("low",      0.20, [],                                              140.0),
    ]

    rows = []
    for hive_id, assets in assets_by_hive.items():
        if not assets:
            continue
        chosen = random.sample(assets, min(len(spread), len(assets)))
        for asset, (level, score, factors, mtbf) in zip(chosen, spread):
            rows.append({
                "hive_id":            hive_id,
                "asset_name":         asset.get("asset_id") or asset.get("name") or "Unnamed",
                "risk_score":         score,
                "risk_level":         level,
                "health_score":       round((1.0 - score) * 100, 1),
                "mtbf_days":          mtbf,
                "days_until_failure": round(mtbf * (1.0 - score), 1),
                "top_factors":        factors,
                "components":         {"pm_score": 50, "fault_score": 60, "time_score": 70, "repeat_score": 80},
                "model_version":      "rules-v1",
            })

    if not rows:
        return {"risk_scores_count": 0}

    inserted = batch_insert(client, "asset_risk_scores", rows, chunk=500)
    log(f"  inserted {inserted} asset_risk_scores")
    return {"risk_scores_count": inserted}
