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
from datetime import datetime, timedelta, timezone

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


def _external_ids_sample(tag: str | None):
    """CMMS ids for ~20% of assets — the rest stay un-synced, which is the honest cold-start."""
    if random.random() >= 0.20:
        return None
    t = (tag or "X").replace("-", "").upper()
    return {"SAP_PM": f"EQ-{t}", "Fiix": f"FX{random.randint(1, 999999):06d}"}


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
            # AH17/F18 (2026-07-28): the CMMS-id card reads node.external_ids and NOTHING ever wrote
            # it — 0 of 95 nodes had any, so even with the page's select fixed the card had nothing to
            # render. A SAMPLE, not all: a plant that has never run a CMMS import legitimately has
            # none, and both states have to exist for the card to be walkable either way.
            "external_ids":    _external_ids_sample(tag),
            "submitted_by":    a.get("submitted_by"),
            "approved_by":     approver,
            "approved_at":     approved_at,
            "rejection_reason": reject_reason,
        })

    inserted = batch_insert(client, "asset_nodes", rows, chunk=500)
    log(f"  inserted {inserted} asset_nodes ({linked} bridged to a PM program by tag)")

    synced = _seed_external_sync(client, log, rows)
    return {"asset_nodes_count": inserted, "asset_nodes_pm_linked": linked,
            "external_sync_count": synced}


def _seed_external_sync(client, log, rows) -> int:
    """AH6 (Asset Hub deepwalk, 2026-07-28): give the CMMS ids a sync PROVENANCE.

    external_sync held 0 rows platform-wide while asset-hub.html read v_external_sync_truth to
    render "Last synced from SAP PM 3 days ago" under the CMMS-id card. An empty table feeding a
    live UI element is the AHK3 class again: nothing looked broken, the line was simply always
    blank, so an engineer saw ids with no way to tell whether they were current or left over from
    an integration that died months ago.

    NOT every id gets a row, and that is the point — the page now says "No sync on record for
    these ids" when there is none, and both states have to exist for either to be walkable.
    A sample also carries sync_status='error', because a sync that is FAILING is the state a
    maintenance planner most needs to see and the one a happy-path fixture never produces.
    """
    now = datetime.now(timezone.utc)
    ext_rows = []
    for r in rows:
        ext = r.get("external_ids") or {}
        if not ext:
            continue
        # ~75% of the assets that carry ids have actually been synced; the rest were typed in.
        if random.random() >= 0.75:
            continue
        for system_type, external_id in ext.items():
            roll = random.random()
            if roll < 0.12:
                # Failing integration: last contact is old and the status says why it stopped.
                status, days = "error", random.randint(9, 40)
            elif roll < 0.25:
                status, days = "active", random.randint(3, 8)
            else:
                status, days = "active", 0
            ext_rows.append({
                "hive_id":        r["hive_id"],
                "system_type":    system_type,
                "external_id":    str(external_id),
                "entity_type":    "asset",
                "workhive_table": "asset_nodes",
                "sync_status":    status,
                "last_synced_at": (now - timedelta(days=days,
                                                   hours=random.randint(0, 20))).isoformat(),
            })

    if not ext_rows:
        log("  no external_ids to give a sync record")
        return 0

    n = batch_insert(client, "external_sync", ext_rows, chunk=500)
    errs = sum(1 for r in ext_rows if r["sync_status"] == "error")
    log(f"  inserted {n} external_sync rows ({errs} in an error state)")
    return n
