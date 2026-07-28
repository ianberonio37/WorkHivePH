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
import random

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


# AHK3 (Asset Hub deepwalk, 2026-07-28): a workflow state with no rows is a state nobody has walked.
# asset_nodes has a real review lifecycle — submit -> pending -> approved | rejected -> restore — and
# the fixture only ever contained the terminal one, so every affordance built for the other states
# (the pending queue, the rejection reason, the restore path) was unreachable and untested.
#
# The status and its companion fields are generated TOGETHER so they cannot disagree. Drawing them
# independently is what produced the logbook arc's 78 "skipped" PMs carrying completion notes: a
# pending row with an approver, or a rejected row with an approved_at, is fiction that would make any
# walk against it meaningless.
_REJECTION_REASONS = [
    "Duplicate of an existing tag - please check the fleet list first.",
    "Criticality looks wrong for this line; confirm with the shift supervisor.",
    "Missing location - which building is this in?",
    "Photo unreadable, cannot verify the nameplate.",
]


def _governance_state(a: dict):
    """(status, approved_by, approved_at, rejection_reason) — internally consistent by construction.

    approved -> reviewed and signed off      (approver + timestamp, no reason)
    pending  -> submitted, NOT yet reviewed  (no approver, no timestamp, no reason)
    rejected -> reviewed and refused         (a REASON, and no approval timestamp)
    """
    roll = random.random()
    if roll < 0.82:
        return "approved", a.get("approved_by"), a.get("approved_at"), None
    if roll < 0.94:
        # Awaiting a supervisor. Nothing may claim it was reviewed.
        return "pending", None, None, None
    # A rejection must SAY WHY — the submitter has to learn something from it (AH3).
    return "rejected", None, None, random.choice(_REJECTION_REASONS)


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

    # Bridge each node to its PM program (pm_assets) by tag, so asset-hub's 360
    # "PM completed" tile + PM timeline light up. seed_pm runs before this seeder,
    # so pm_assets already exist; match (hive_id, lower(tag_id)). Without this the
    # bridge is NULL platform-wide and pm_completions.eq('asset_id', pm_asset_id)
    # silently returns 0 for every asset (STREAMLINE_ROADMAP P9).
    pm_by_tag: dict = {}
    try:
        pm_rows = client.table("pm_assets").select("id, hive_id, tag_id").execute().data or []
        for pm in pm_rows:
            if pm.get("tag_id"):
                pm_by_tag[(pm["hive_id"], str(pm["tag_id"]).strip().lower())] = pm["id"]
    except Exception as e:  # pragma: no cover — degrade to unlinked, never crash the seed
        log(f"  WARN: could not load pm_assets for bridge ({e}); nodes will be unlinked")

    rows = []
    linked = 0
    for a in assets:
        tag = a.get("asset_id") or a.get("name") or "untagged"
        pm_asset_id = pm_by_tag.get((a["hive_id"], str(tag).strip().lower()))
        if pm_asset_id:
            linked += 1
        # AH2/AH3/AHK3 (Asset Hub deepwalk, 2026-07-28): this hand-off used to drop `auth_uid` and
        # hardcode status="approved", and those two omissions made the page's ENTIRE governance
        # workflow untestable. Measured before the fix: 95 asset_nodes, 0 with auth_uid, 0 pending,
        # 0 rejected, 0 authored by any worker or supervisor.
        #   * auth_uid: assets.py computes it from the submitter and asset_brain never carried it,
        #     so no row was provably authored by anyone — which also made the OWNERSHIP half of
        #     asset_nodes_write (`auth_uid = auth.uid()`) impossible to exercise.
        #   * status: with only the terminal state present, submit -> review -> approve/reject ->
        #     restore had no data to walk. That is why the PDDA arc's F21 (a worker's Pending-assets
        #     tile always reads 0) sat undiagnosed — there had never been a pending asset to see.
        # The seeder decides what can be tested, and under-generating a STATE is the quiet failure
        # because nothing looks broken (LB13/LB17 in a new place).
        status, approver, approved_at, reject_reason = _governance_state(a)
        rows.append({
            "hive_id":         a["hive_id"],
            "worker_name":     a.get("worker_name") or a.get("submitted_by"),
            "level":           "equipment",
            "tag":             tag,
            "name":            a.get("name") or a.get("asset_id") or "Unnamed",
            "iso_class":       _classify_iso(a.get("type")),
            "criticality":     crit_map.get(a.get("criticality") or "Medium", "medium"),
            "location":        a.get("location"),
            "legacy_asset_id": a["id"],
            "pm_asset_id":     pm_asset_id,
            # Attribution FK. Without it the row has a submitter NAME and no identity behind it.
            "auth_uid":        a.get("auth_uid"),
            "status":          status,
            "submitted_by":    a.get("submitted_by"),
            "approved_by":     approver,
            "approved_at":     approved_at,
            "rejection_reason": reject_reason,
        })

    inserted = batch_insert(client, "asset_nodes", rows, chunk=500)
    log(f"  inserted {inserted} asset_nodes ({linked} bridged to a PM program by tag)")
    return {"asset_nodes_count": inserted, "asset_nodes_pm_linked": linked}
