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

    # (level, score, factors, fallback_mtbf). mtbf_days is sourced from the CANONICAL
    # get_mtbf_by_machine engine below when the asset has failure history; the fallback is
    # only used for assets with no failures in the window (those aren't compared to the live
    # engine by validate_reliability_kpi_faithfulness, which inner-joins on the machine).
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
        # Canonical MTBF per machine (the SAME engine batch-risk-scoring uses) so the seeded
        # cache is FAITHFUL to get_mtbf_by_machine. Without this the seeder writes synthetic
        # mtbf_days that diverge from the live engine -> validate_reliability_kpi_faithfulness
        # FAILs on every reseed (the cross-session reliability-KPI seesaw). Runs after logbook
        # is seeded (orchestrator order), so the RPC returns real values.
        mtbf_by_machine: dict = {}
        try:
            rpc = client.rpc("get_mtbf_by_machine",
                             {"p_hive_id": hive_id, "p_worker": None, "p_period_days": 365}
                             ).execute().data or []
            for r in rpc:
                m = (r.get("machine") or "").strip().lower()
                v = r.get("mtbf_days")
                if m and v is not None:
                    mtbf_by_machine[m] = round(float(v), 1)
        except Exception as e:  # RPC unavailable -> fall back (rows just won't be canonical)
            log(f"  get_mtbf_by_machine unavailable ({e}); using fallback mtbf")
        chosen = random.sample(assets, min(len(spread), len(assets)))
        for asset, (level, score, factors, fallback_mtbf) in zip(chosen, spread):
            asset_name = asset.get("asset_id") or asset.get("name") or "Unnamed"
            mtbf = mtbf_by_machine.get(asset_name.strip().lower(), fallback_mtbf)
            rows.append({
                "hive_id":            hive_id,
                "asset_name":         asset_name,
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
