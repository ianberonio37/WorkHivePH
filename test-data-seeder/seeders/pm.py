"""Seed PM (preventive maintenance) — pm_assets, pm_scope_items, pm_completions."""
import random
from datetime import timedelta, date

from .utils import random_timestamp_in_last_n_days, to_iso

PM_FREQUENCIES = ["Weekly", "Monthly", "Quarterly", "Semi-annual", "Annual"]
FREQ_DAYS = {
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
            completion_rows.append({
                "asset_id": scope["asset_id"],
                "scope_item_id": scope["id"],
                "hive_id": scope["hive_id"],
                "worker_name": worker["worker_name"],
                "status": random.choices(["done", "skipped"], weights=[95, 5])[0],
                "notes": random.choice([
                    "Completed as scheduled",
                    "Within spec",
                    "Minor adjustment made",
                    "All readings nominal",
                    "",
                ]),
                "completed_at": to_iso(ts),
                "auth_uid": worker.get("auth_uid"),
            })

    if completion_rows:
        from .utils import batch_insert
        inserted = batch_insert(client, "pm_completions", completion_rows, chunk=500)
        log(f"  inserted {inserted} pm_completions")
    else:
        inserted = 0

    return {
        "pm_assets_count": len(pm_assets_inserted),
        "pm_scope_count": len(scope_items_inserted),
        "pm_completions_count": inserted,
    }
