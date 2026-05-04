"""Seed assets — equipment registered to each hive."""
import random

from data.ph_equipment import EQUIPMENT_CATALOG
from .utils import text_id, random_timestamp_in_last_n_days, to_iso

ASSETS_PER_HIVE = 30
LOCATIONS_PER_HIVE = [
    "Production Line A", "Production Line B", "Utility Building",
    "Compressor Room", "Pump Pit 1", "Pump Pit 2", "Substation",
    "Cooling Tower Bay", "Boiler Room", "Workshop", "Warehouse",
    "Yard - North", "Yard - South",
]
# Match platform canonical labels (pm-scheduler.html dropdown).
# Weights here = relative frequency in the seeded distribution (not the
# analytics multiplier — that lives in CRITICALITY_WEIGHT in prescriptive.py).
CRITICALITY_WEIGHTS = [
    ("Critical", 1),   # ~12% of assets — show-stoppers
    ("High",     2),   # ~25% — important but not life-or-death
    ("Medium",   4),   # ~50% — bulk of equipment
    ("Low",      1),   # ~12% — non-critical
]


def _pick_criticality():
    pool = []
    for value, weight in CRITICALITY_WEIGHTS:
        pool.extend([value] * weight)
    return random.choice(pool)


def seed_assets(client, log, ctx: dict) -> dict:
    """ctx must include 'hives' and 'workers'. Returns dict with 'assets'."""
    hives = ctx["hives"]
    workers = ctx["workers"]
    log(f"Seeding {ASSETS_PER_HIVE} assets per hive ({ASSETS_PER_HIVE * len(hives)} total)...")

    rows = []
    for hive in hives:
        hive_workers = [w for w in workers if w["hive_id"] == hive["id"]]
        if not hive_workers:
            continue
        supervisors = [w for w in hive_workers if w["role"] == "supervisor"]
        approver = supervisors[0] if supervisors else hive_workers[0]

        # Use a numbering counter per tag_prefix to keep tag IDs unique inside a hive
        tag_counters: dict[str, int] = {}

        for _ in range(ASSETS_PER_HIVE):
            arch = random.choice(EQUIPMENT_CATALOG)
            tag_prefix = arch["tag_prefix"]
            tag_counters[tag_prefix] = tag_counters.get(tag_prefix, 0) + 1
            tag_num = tag_counters[tag_prefix]
            tag_id = f"{tag_prefix}-{tag_num:03d}"

            registered = random_timestamp_in_last_n_days(120)  # registered before activity window
            submitter = random.choice(hive_workers)

            rows.append({
                "id": text_id("asset"),
                "worker_name": submitter["worker_name"],
                "asset_id": tag_id,
                "name": f"{arch['make']} {arch['model']}",
                "type": arch["category"],
                "location": random.choice(LOCATIONS_PER_HIVE),
                "criticality": _pick_criticality(),
                "registered_at": to_iso(registered),
                "created_at": to_iso(registered),
                "status": "approved",
                "hive_id": hive["id"],
                "submitted_by": submitter["worker_name"],
                "approved_by": approver["worker_name"],
                "approved_at": to_iso(registered),
                "auth_uid": submitter.get("auth_uid"),
            })

    client.table("assets").insert(rows).execute()
    log(f"  inserted {len(rows)} assets")

    # Group by hive for downstream seeders
    by_hive = {}
    for a in rows:
        by_hive.setdefault(a["hive_id"], []).append(a)

    return {"assets": rows, "assets_by_hive": by_hive}
