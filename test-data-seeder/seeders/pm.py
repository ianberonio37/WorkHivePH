"""Seed PM (preventive maintenance) — pm_assets, pm_scope_items, pm_completions."""
import random
from datetime import timedelta, date

from .utils import random_timestamp_in_last_n_days, to_iso

PM_FREQUENCIES = ["Weekly", "Monthly", "Quarterly", "Semi-annual", "Annual"]
FREQ_DAYS = {
    "Daily": 1,  # entered the live vocabulary with the Vehicles PM templates (daily walk-around, 2026-09-02)
    "Weekly": 7,
    "Monthly": 30,
    "Quarterly": 90,
    "Semi-annual": 180,
    "Annual": 365,
}

SCOPE_ITEMS_BY_CATEGORY = {
    "Genset": [
        ("Visual inspection, exhaust check", "Weekly"),
        ("Battery voltage and electrolyte level", "Weekly"),
        ("Oil level and quality, top-up if needed", "Monthly"),
        ("Coolant level, hose condition", "Monthly"),
        ("Load test 30 min at 75% load", "Quarterly"),
        ("Replace primary fuel filter", "Semi-annual"),
        ("Replace oil and oil filter", "Semi-annual"),
        ("Air filter inspection / replacement", "Annual"),
    ],
    "Centrifugal Pump": [
        ("Vibration trend reading at DE/NDE", "Weekly"),
        ("Mechanical seal leak check", "Weekly"),
        ("Bearing temperature reading", "Monthly"),
        ("Coupling alignment verification", "Quarterly"),
        ("Lubricate motor bearings", "Quarterly"),
        ("Performance test against curve", "Annual"),
    ],
    "AC Motor": [
        ("Visual + amp draw check", "Weekly"),
        ("Vibration ISO 10816 reading", "Monthly"),
        ("Bearing greasing per IEC schedule", "Quarterly"),
        ("Insulation resistance test (Megger)", "Semi-annual"),
        ("Cooling fan inspection", "Annual"),
    ],
    "Air Compressor": [
        ("Discharge pressure log", "Weekly"),
        ("Auto-drain function check", "Weekly"),
        ("Oil level top-up", "Monthly"),
        ("Replace oil filter and air filter", "Quarterly"),
        ("Replace separator element", "Semi-annual"),
        ("Replace oil and full service", "Annual"),
    ],
    "Chiller": [
        ("Refrigerant pressures log", "Weekly"),
        ("Approach temperature check", "Monthly"),
        ("Eddy current tube inspection", "Annual"),
        ("Oil sample analysis", "Quarterly"),
        ("Condenser tube cleaning", "Annual"),
    ],
    "VFD": [
        ("Visual + cooling fan check", "Monthly"),
        ("Capacitor inspection", "Quarterly"),
        ("Re-torque power terminals", "Annual"),
    ],
    "UPS": [
        ("Battery voltage per cell log", "Monthly"),
        ("Self-test and bypass verification", "Quarterly"),
        ("Capacity discharge test", "Annual"),
    ],
}
GENERIC_SCOPE = [
    ("General visual + cleanliness", "Weekly"),
    ("Lubricate per OEM spec", "Monthly"),
    ("Tighten loose fasteners", "Quarterly"),
    ("Annual functional test", "Annual"),
]


def _scope_for(category: str):
    return SCOPE_ITEMS_BY_CATEGORY.get(category, GENERIC_SCOPE)


# A completion's status and its note have to agree, or the state is fiction. Drawing them
# independently produced 78 'skipped' rows carrying notes like "All readings nominal" — and a skip
# is the one PM state whose whole value is the REASON it was not done. Walked 2026-07-28 (PM9): the
# numbers already treat a skip honestly (it credits no compliance and does not move next_due_date),
# so the only thing standing between "skipped" and a testable state was a coherent fixture.
_DONE_NOTES = [
    "Completed as scheduled",
    "Within spec",
    "Minor adjustment made",
    "All readings nominal",
    "",
]
_SKIP_REASONS = [
    "Line still running, could not isolate",
    "Deferred: no spare gasket in stores",
    "Access blocked by stacked pallets",
    "Rescheduled with production for next window",
    "Machine already down for corrective work",
]


def _completion_status_and_note() -> dict:
    """Status plus a note that matches it. Kept together so the two cannot drift apart again."""
    status = random.choices(["done", "skipped"], weights=[95, 5])[0]
    return {
        "status": status,
        "notes": random.choice(_DONE_NOTES if status == "done" else _SKIP_REASONS),
    }


def seed_pm(client, log, ctx: dict) -> dict:
    """ctx must include 'workers' and 'assets'."""
    workers = ctx["workers"]
    assets = ctx["assets"]
    workers_by_hive: dict = {}
    for w in workers:
        workers_by_hive.setdefault(w["hive_id"], []).append(w)

    log(f"Seeding PM assets, scope items, and completions for {len(assets)} assets...")

    pm_asset_rows = []
    asset_to_pm_id_map = {}
    for a in assets:
        pm_id_local = None  # filled after insert
        anchor = (random_timestamp_in_last_n_days(90)).date()
        worker = random.choice(workers_by_hive.get(a["hive_id"], [{"worker_name": "seed.admin"}]))
        pm_asset_rows.append({
            "hive_id": a["hive_id"],
            "worker_name": worker["worker_name"],
            "asset_name": a["name"],
            "tag_id": a["asset_id"],
            "location": a["location"],
            "category": a["type"] or "General",
            "criticality": a["criticality"] or "Major",
            "last_anchor_date": anchor.isoformat(),
            "auth_uid": worker.get("auth_uid"),
        })

    res = client.table("pm_assets").insert(pm_asset_rows).execute()
    pm_assets_inserted = res.data
    log(f"  inserted {len(pm_assets_inserted)} pm_assets")

    # Build map from text asset_id -> pm_asset row uuid using order (insert order preserved)
    for asset_row, pm_row in zip(assets, pm_assets_inserted):
        asset_to_pm_id_map[asset_row["id"]] = pm_row["id"]

    # Scope items — based on equipment category
    scope_rows = []
    pm_id_to_category = {}
    for asset_row, pm_row in zip(assets, pm_assets_inserted):
        scope_for = _scope_for(asset_row["type"])
        pm_id_to_category[pm_row["id"]] = asset_row["type"]
        for item_text, freq in scope_for:
            scope_rows.append({
                "asset_id": pm_row["id"],
                "hive_id": asset_row["hive_id"],
                "item_text": item_text,
                "frequency": freq,
                "anchor_date": pm_row["last_anchor_date"],
                "is_custom": False,
            })

    res = client.table("pm_scope_items").insert(scope_rows).execute()
    scope_items_inserted = res.data
    log(f"  inserted {len(scope_items_inserted)} pm_scope_items")

    # Completions — generate historical PM completions over 90 days
    log("  generating PM completions over 90 days based on frequency...")
    completion_rows = []
    # pm_completions carries a UNIQUE (scope_item_id, worker_name, completed_at::date) dedup
    # index. The same worker can be randomly picked for two completions of ONE scope item on
    # the SAME day -> a deterministic 23505 under the fixed RNG seed (aborts /api/seed/all).
    # Track the key and skip a would-be duplicate (a lost filler completion is harmless).
    seen_completion_keys: set = set()
    for scope in scope_items_inserted:
        freq_days = FREQ_DAYS.get(scope["frequency"], 30)
        # Number of completions = 90 / freq_days, plus a bit of jitter
        n_completions = max(0, 90 // freq_days)
        for i in range(n_completions):
            ts = random_timestamp_in_last_n_days(90 - i * freq_days // max(1, 1) - random.randint(0, 5))
            asset_workers = workers_by_hive.get(scope["hive_id"], [])
            if not asset_workers:
                continue
            worker = random.choice(asset_workers)
            dedup_key = (scope["id"], worker["worker_name"], to_iso(ts)[:10])  # date mirrors the uidx
            if dedup_key in seen_completion_keys:
                continue
            seen_completion_keys.add(dedup_key)
            completion_rows.append({
                "asset_id": scope["asset_id"],
                "scope_item_id": scope["id"],
                "hive_id": scope["hive_id"],
                "worker_name": worker["worker_name"],
                # PM9 (PM deepwalk, 2026-07-28): the status and the note used to be drawn
                # INDEPENDENTLY, so a 'skipped' row carried a completion note — 78 skips in the
                # database said things like "All readings nominal", which is incoherent: if the
                # readings were nominal the PM was done, not skipped. A skip needs a skip REASON, or
                # the whole state is untestable fiction (the seeder decides what can be tested).
                **_completion_status_and_note(),
                "completed_at": to_iso(ts),
                "auth_uid": worker.get("auth_uid"),
            })

    if completion_rows:
        from .utils import batch_insert
        inserted = batch_insert(client, "pm_completions", completion_rows, chunk=500)
        log(f"  inserted {inserted} pm_completions")
    else:
        inserted = 0

    # LOGBOOK deepwalk LB13 (2026-07-28): mirror a sample of completions into the logbook.
    #
    # pm-scheduler.html mirrors a completed PM into the logbook (its #sheet-log-toggle is checked by
    # default) and the PDDA arc fixed that mirror's asset lineage and gated it as #27. But the seed
    # never produced a single linked row -- 0 of 1,591 completions carried a pm_completion_id -- so
    # the provenance the gate protects was undemonstrable, and the journey that walks it was
    # unwalkable by construction. That is the HK2 lesson from the hive arc in a new place: the
    # seeder decides what can be tested, and under-generating a RELATIONSHIP is the quiet failure
    # because nothing looks broken.
    #
    # Mirrors a sample rather than all of them, because in reality not every PM gets logged: the
    # toggle can be unchecked. A sample keeps both branches of that reality present in the data.
    try:
        done = [c for c in (client.table("pm_completions")
                            .select("id,hive_id,asset_id,worker_name,completed_at,notes")
                            .eq("status", "done").limit(40).execute().data or [])]
        if done:
            pm_asset_ids = list({c["asset_id"] for c in done if c.get("asset_id")})
            pa = (client.table("pm_assets").select("id,asset_name,tag_id")
                  .in_("id", pm_asset_ids).execute().data or [])
            by_pm_asset = {r["id"]: r for r in pa}
            # The canonical node is resolved from asset_nodes.pm_asset_id, NOT from a column on
            # pm_assets (there isn't one). Same resolution the live mirror and embed-entry use --
            # feeding a pm_assets id straight into an asset_nodes FK is exactly what silently
            # starved pm_knowledge to 0 rows (reference_pm_knowledge_fk_100pct_broken).
            nodes = (client.table("asset_nodes").select("id,pm_asset_id")
                     .in_("pm_asset_id", pm_asset_ids).execute().data or [])
            node_by_pm_asset = {n["pm_asset_id"]: n["id"] for n in nodes if n.get("pm_asset_id")}
            mirror_rows = []
            for c in done:
                a = by_pm_asset.get(c.get("asset_id")) or {}
                tag = a.get("tag_id") or a.get("asset_name")
                if not tag:
                    continue
                mirror_rows.append({
                    "id":                f"pmlog-{c['id'][:12]}",
                    "hive_id":           c["hive_id"],
                    "worker_name":       c["worker_name"],
                    "date":              c["completed_at"],
                    "machine":           tag,                      # the TAG, not the display name
                    "asset_node_id":     node_by_pm_asset.get(c.get("asset_id")),  # canonical lineage, gate #27
                    "maintenance_type":  "Preventive Maintenance",
                    "category":          "Mechanical",
                    "problem":           "Scheduled PM",
                    "action":            (c.get("notes") or "Completed as scheduled"),
                    "status":            "Closed",
                    "closed_at":         c["completed_at"],
                    "pm_completion_id":  c["id"],
                })
            if mirror_rows:
                from .utils import batch_insert
                n = batch_insert(client, "logbook", mirror_rows, chunk=200)
                log(f"  mirrored {n} PM completions into the logbook (pm_completion_id lineage)")
    except Exception as e:                                   # seeding must not die on the sample step
        log(f"  WARN pm->logbook mirror sample skipped: {e}")

    return {
        "pm_assets_count": len(pm_assets_inserted),
        "pm_scope_count": len(scope_items_inserted),
        "pm_completions_count": inserted,
    }
