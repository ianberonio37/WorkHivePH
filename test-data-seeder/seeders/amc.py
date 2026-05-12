"""Seed amc_briefings - Autonomous Maintenance Crew daily briefs.

Without this, alert-hub.html shows "no brief yet" on every fresh seed and
the AMC card cannot be visually verified or interaction-tested. We generate
a realistic brief per hive for the last 14 shift_dates, with a sensible mix
of statuses (most approved, a few pending, occasional rejected).

The brief JSONB shape mirrors what amc-orchestrator writes in production
(5 sub-agent outputs: top_assets, pm_due, parts_to_stage, crew_match,
narrative). We don't run the LLM in seeder - the narrative is a templated
string drawn from real asset/PM rows. This is enough for UI + flow tests.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone


# Templated narrative chunks - vary so the same brief doesn't keep looking
# identical across hives in the seeded data. Tone matches the production
# Briefing-Composer prompt (concise, Filipino plant supervisor voice).
NARRATIVE_TEMPLATES = [
    "Day starts with {asset_count} high-risk assets and {pm_count} PMs due. Stage parts before 0700 to avoid the 1400 line stop. Watch {asset1} closely - {issue1}.",
    "Priority today: {asset1} ({issue1}). Crew available: {crew_count} workers. {pm_count} PMs need closing this shift. {parts_count} parts to pre-stage.",
    "{asset1} is the morning critical-path - {issue1}. Defer non-urgent PM {pm1} if needed. Inventory shows {parts_count} fast-movers below reorder.",
    "Calm shift expected, {asset_count} watchlist items. Use the window to close overdue PMs ({pm_count} pending). Stage {parts_count} parts during early break.",
    "{asset1} flagged overnight - {issue1}. Assign {crew_count}-worker team at 0700. PM {pm1} can run in parallel. Verify spares before line start.",
]

ISSUE_SAMPLES = [
    "vibration trend up 12% over 7d", "thermal hotspot at bearing #2",
    "current draw +8% vs baseline", "oil sample shows Cu wear particles",
    "predictive-analytics flagged failure mode V-belt slip",
    "MTBF dropped from 86d to 71d this month",
    "two unplanned stops in last 14d", "PF interval halved per recent fits",
]


def _build_brief(assets: list, pms: list, parts: list, workers: list) -> dict:
    """Compose one realistic brief JSONB. Inputs are already hive-filtered."""
    top_assets = []
    for a in assets[:3]:
        top_assets.append({
            "asset_id":     a.get("id"),
            "name":         a.get("name") or a.get("tag") or "unnamed",
            "risk_score":   round(random.uniform(0.55, 0.95), 2),
            "top_factor":   random.choice([
                "MTBF declining", "vibration trend", "thermal anomaly",
                "predictive model failure mode", "overdue PM",
            ]),
        })

    pm_due = []
    for p in pms[:5]:
        pm_due.append({
            "pm_scope_id": p.get("id"),
            "asset_name":  p.get("asset_name") or "unknown",
            "title":       p.get("title") or "monthly inspection",
            "due_in_days": random.choice([-1, 0, 0, 1, 2]),
        })

    parts_to_stage = []
    for pt in parts[:5]:
        parts_to_stage.append({
            "part_number": pt.get("part_number") or "P-XXX",
            "qty_needed":  random.randint(1, 5),
            "asset_name":  pt.get("asset_name") or "",
            "reason":      random.choice(["PM-driven", "predictive-flagged", "low-stock"]),
        })

    crew_match = []
    for w in workers[:4]:
        crew_match.append({
            "worker_name":     w.get("display_name") or w.get("worker_name") or "Worker",
            "discipline":      random.choice(["Mechanical", "Electrical", "Instrumentation"]),
            "level":           random.choice([2, 3, 3, 4]),
            "available_today": True,
        })

    a1 = top_assets[0]["name"] if top_assets else "Asset A"
    p1 = pm_due[0]["title"] if pm_due else "monthly inspection"
    narrative = random.choice(NARRATIVE_TEMPLATES).format(
        asset_count=len(top_assets),
        pm_count=len(pm_due),
        parts_count=len(parts_to_stage),
        crew_count=len(crew_match),
        asset1=a1, pm1=p1,
        issue1=random.choice(ISSUE_SAMPLES),
    )

    return {
        "top_assets":     top_assets,
        "pm_due":         pm_due,
        "parts_to_stage": parts_to_stage,
        "crew_match":     crew_match,
        "narrative":      narrative,
    }


def seed_amc(client, log, ctx: dict) -> dict:
    log("Seeding amc_briefings (14 days x hive, mixed statuses)...")

    hives = client.table("hives").select("id, name").execute().data or []
    if not hives:
        log("  no hives - amc skipped")
        return {"amc_briefings_count": 0}

    rows = []
    today = datetime.now(timezone.utc).date()

    for h in hives:
        hive_id = h["id"]

        # Pull real per-hive context so each brief references actual rows
        assets = client.table("asset_nodes").select("id, name, tag").eq(
            "hive_id", hive_id,
        ).limit(20).execute().data or []
        pms = client.table("pm_scope").select(
            "id, title, asset_name",
        ).eq("hive_id", hive_id).limit(10).execute().data or []
        parts = client.table("inventory_items").select(
            "id, part_number, name",
        ).eq("hive_id", hive_id).limit(10).execute().data or []
        # asset_name passthrough for the parts brief
        for pt in parts:
            pt["asset_name"] = ""
        workers = client.table("worker_profiles").select(
            "username, display_name",
        ).limit(8).execute().data or []
        # Filter to hive members
        hive_members = client.table("hive_members").select(
            "worker_name",
        ).eq("hive_id", hive_id).eq("status", "active").execute().data or []
        hive_worker_names = {hm["worker_name"] for hm in hive_members}
        workers = [w for w in workers if w.get("display_name") in hive_worker_names] or workers

        if not (assets or pms):
            log(f"  hive {h.get('name', hive_id)[:30]}: no asset / pm context, skipped")
            continue

        for d in range(14):
            shift_date = today - timedelta(days=d)
            # Mix: today usually pending, yesterday-ish approved, sprinkle a reject
            if d == 0:
                status = random.choice(["pending", "pending", "approved"])
            elif d <= 2:
                status = random.choice(["approved", "approved", "pending"])
            elif d <= 4:
                status = random.choice(["approved", "approved", "approved", "rejected"])
            else:
                status = random.choice(["approved", "approved", "approved", "expired"])

            generated_at = datetime(
                shift_date.year, shift_date.month, shift_date.day,
                6, random.randint(0, 9), tzinfo=timezone.utc,
            )

            row = {
                "hive_id":       hive_id,
                "generated_at":  generated_at.isoformat(),
                "shift_date":    shift_date.isoformat(),
                "status":        status,
                "brief":         _build_brief(assets, pms, parts, workers),
                "model_version": "amc-v1-seed",
                "expires_at":    (generated_at + timedelta(hours=36)).isoformat(),
            }
            if status in ("approved", "rejected"):
                approver = random.choice(workers).get("display_name") if workers else "Supervisor"
                row["approved_by"]    = approver
                row["approved_at"]    = (generated_at + timedelta(minutes=random.randint(15, 240))).isoformat()
                row["approved_notes"] = random.choice([
                    "", "looks good", "stage parts at 0645",
                    "watch unit 2 closely", "swap PM order, electrical first",
                ])
            rows.append(row)

    if not rows:
        return {"amc_briefings_count": 0}

    from .utils import batch_insert
    # ON CONFLICT (hive_id, shift_date) - upsert silently. Use insert and
    # let the unique index reject dupes; we wipe via reset.py before seed.
    try:
        inserted = batch_insert(client, "amc_briefings", rows, chunk=300)
    except Exception as e:
        log(f"  amc insert failed (likely UNIQUE collision on rerun without reset): {e}")
        return {"amc_briefings_count": 0}
    log(f"  inserted {inserted} amc_briefings rows across {len(hives)} hives")
    return {"amc_briefings_count": inserted}
