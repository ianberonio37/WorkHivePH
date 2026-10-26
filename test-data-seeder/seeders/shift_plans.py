"""Seed one shift_plans row per hive so shift-brain.html renders out of the box.

Schema CHECK constraint: shift_window IN ('06-14','14-22','22-06').
We pick the current shift window based on local time so the displayed plan
matches what the supervisor would expect to see right now.
"""
import datetime, json
from .utils import batch_insert


def _current_shift_window() -> str:
    """Return the canonical shift label for the current Manila hour."""
    h = datetime.datetime.utcnow().hour + 8  # rough Manila offset (no DST)
    h %= 24
    if 6 <= h < 14:  return "06-14"
    if 14 <= h < 22: return "14-22"
    return "22-06"


def seed_shift_plans(client, log, ctx: dict) -> dict:
    log("Seeding one draft shift_plan per hive...")
    hives = ctx.get("hives") or []
    assets_by_hive = ctx.get("assets_by_hive") or {}
    if not hives:
        log("  no hives in ctx — shift_plans skipped")
        return {"shift_plans_count": 0}

    shift_window = _current_shift_window()
    today = datetime.date.today().isoformat()

    # ★THE CARRY LIST IS THE HIVE'S OWN OPEN WORK, AS THE PLANNER SELECTS IT (2026-10-27). An empty list over a hive with
    # 9-25 open entries is a plan that silently dropped them, and shift-brain counts this array - the probe
    # shift-brain__carry_count_true read every seeded plan as truncated. Same query as shift-planner-orchestrator's
    # fetchCarryForward: Open, older than 8 hours, oldest first, at most 30, with the cap flag saying when it is full.
    CARRY_FWD_LIMIT = 30
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=8)).isoformat()

    rows = []
    for hive in hives:
        hive_assets = assets_by_hive.get(hive["id"]) or []
        risk_top = [
            {"asset_name": a.get("asset_id") or a.get("name"), "risk_score": 0.78}
            for a in hive_assets[:3]
        ]
        carry = (client.table("logbook")
                 .select("id, machine, problem, maintenance_type, status, created_at, worker_name, downtime_hours, "
                         "loto_applied, permit_reference")
                 .eq("hive_id", hive["id"]).eq("status", "Open").lt("created_at", cutoff)
                 .order("created_at").limit(CARRY_FWD_LIMIT).execute().data or [])
        payload = {
            "risk_top":       risk_top,
            "pms_due":        [],   # populated by orchestrator in real runs
            "carry_forward":  carry,
            "caps":           {"carry_forward": len(carry) >= CARRY_FWD_LIMIT},
            "parts_prestage": [],
            "assignments":    [],
            "projects_today": [],
        }
        rows.append({
            "hive_id":      hive["id"],
            "shift_window": shift_window,
            "shift_date":   today,
            "status":       "draft",
            "generated_by": "shift-planner-orchestrator",
            "briefing":     "Demo shift plan seeded for tester. "
                            f"Top {len(risk_top)} risk assets carry over from yesterday's runtime. "
                            "Supervisor: review, edit, then publish to crew.",
            # jsonb column: pass the dict directly. json.dumps() double-encodes it into a
            # jsonb *string* scalar, which shift-brain's payload.<field> reads render as empty
            # (same class as parts_staging_recommendations.parts F1). The real orchestrator
            # (shift-planner-orchestrator) upserts payload as an object.
            "payload":      payload,
        })

    inserted = batch_insert(client, "shift_plans", rows, chunk=500)
    log(f"  inserted {inserted} shift_plans (window={shift_window}, date={today})")
    return {"shift_plans_count": inserted}
