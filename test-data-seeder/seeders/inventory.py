"""Seed inventory_items + inventory_transactions."""
import random

from .utils import text_id, random_timestamp_in_last_n_days, to_iso, batch_insert

PARTS_CATALOG = [
    ("BRG-6310", "Bearing 6310 C3", "Bearings", "pcs", 12, 4),
    ("BRG-6313", "Bearing 6313 C3", "Bearings", "pcs", 8, 3),
    ("SEAL-T2100", "Mech seal Type 2100", "Seals & Gaskets", "pcs", 6, 2),
    ("GAS-SW-DN50", "Spiral wound gasket DN50", "Seals & Gaskets", "pcs", 24, 8),
    ("GREASE-NLGI2", "Grease NLGI 2 (400g)", "Lubricants", "tubes", 30, 10),
    ("OIL-15W40", "SAE 15W-40 engine oil", "Lubricants", "L", 200, 60),
    ("OIL-VG46", "ISO VG46 hydraulic oil", "Lubricants", "L", 160, 40),
    ("FLT-AIR", "Air filter element", "Filters", "pcs", 18, 6),
    ("FLT-OIL", "Oil filter cartridge", "Filters", "pcs", 22, 8),
    ("FLT-FUEL-P", "Primary fuel filter", "Filters", "pcs", 12, 4),
    ("FLT-FUEL-S", "Secondary fuel filter", "Filters", "pcs", 12, 4),
    ("BAT-12V100", "Battery 12V 100Ah", "Electrical", "pcs", 4, 2),
    ("FUSE-100A", "HRC fuse 100A", "Electrical", "pcs", 30, 10),
    ("CB-MCCB-160", "MCCB 160A 3P", "Electrical", "pcs", 4, 1),
    ("CONT-32A", "Contactor 32A 3P", "Electrical", "pcs", 8, 3),
    ("VBELT-SPB1700", "V-belt SPB 1700", "Mechanical", "pcs", 16, 5),
    ("CHAIN-12B", "Chain 12B-1 (5m)", "Mechanical", "rolls", 4, 1),
    ("PUMP-WR-SET", "Wear ring set", "Mechanical", "pcs", 6, 2),
    ("CABLE-25MM", "Cable gland 25mm IP68", "Electrical", "pcs", 20, 6),
    ("PTFE-TAPE", "PTFE thread tape", "Consumables", "rolls", 60, 20),
    ("LOCT-567", "Loctite 567 thread sealant", "Consumables", "tubes", 12, 4),
    ("RAG-SHOP", "Shop rag bundle", "Consumables", "kg", 50, 15),
    ("REFRIG-R134A", "R-134a refrigerant", "Refrigerants", "kg", 40, 10),
    ("CLEAN-CIP100", "CIP-100 alkaline cleaner", "Chemicals", "L", 75, 20),
    ("PSV-SPARE", "PSV spare assembly", "Mechanical", "pcs", 3, 1),
    ("PT100", "Pt100 sensor with thermowell", "Instrumentation", "pcs", 8, 2),
    ("FUSE-32A", "MCB 32A 3P C-curve", "Electrical", "pcs", 24, 8),
]

TRANSACTION_NOTES = [
    "Used on breakdown repair",
    "Issued to PM team",
    "Restocked from supplier",
    "Adjusted after physical count",
    "Returned unused from job",
]


def seed_inventory(client, log, ctx: dict) -> dict:
    """ctx must include 'hives' and 'workers' and 'assets_by_hive'."""
    hives = ctx["hives"]
    workers = ctx["workers"]
    assets_by_hive = ctx["assets_by_hive"]
    workers_by_hive: dict = {}
    for w in workers:
        workers_by_hive.setdefault(w["hive_id"], []).append(w)

    log(f"Seeding inventory_items per hive ({len(PARTS_CATALOG)} parts × {len(hives)} hives)...")

    item_rows = []
    items_by_hive: dict = {}

    for hive in hives:
        hive_assets = assets_by_hive.get(hive["id"], [])
        asset_id_pool = [a["id"] for a in hive_assets]
        hive_workers = workers_by_hive.get(hive["id"], [])
        if not hive_workers:
            continue
        supervisors = [w for w in hive_workers if w["role"] == "supervisor"]
        approver = supervisors[0] if supervisors else hive_workers[0]

        for idx, (part_no, part_name, category, unit, init_qty, min_qty) in enumerate(PARTS_CATALOG):
            submitter = random.choice(hive_workers)
            # Force ~10% of parts to be below min_qty so the low-stock UI gets tested
            if idx % 10 == 0:
                qty = max(0, min_qty - random.randint(1, max(1, min_qty // 2)))
            else:
                qty = init_qty + random.randint(-3, 5)
            linked = random.sample(asset_id_pool, k=min(2, len(asset_id_pool))) if asset_id_pool else []
            row = {
                "id": text_id("inv"),
                "worker_name": submitter["worker_name"],
                "part_number": part_no,
                "part_name": part_name,
                "category": category,
                "unit": unit,
                "qty_on_hand": max(0, qty),
                "min_qty": min_qty,
                "bin_location": f"Bin {random.randint(1, 12)}-{random.choice(['A', 'B', 'C'])}",
                "linked_asset_ids": linked,
                "notes": "",
                "status": "approved",
                "hive_id": hive["id"],
                "submitted_by": submitter["worker_name"],
                "approved_by": approver["worker_name"],
                "approved_at": to_iso(random_timestamp_in_last_n_days(120)),
                "auth_uid": submitter.get("auth_uid"),
            }
            item_rows.append(row)
            items_by_hive.setdefault(hive["id"], []).append(row)

    client.table("inventory_items").insert(item_rows).execute()
    log(f"  inserted {len(item_rows)} inventory_items")

    # Generate transactions — 3-8 per item over 90 days
    log("Generating inventory_transactions over 90 days...")
    tx_rows = []
    for item in item_rows:
        n_tx = random.randint(3, 8)
        running = item["qty_on_hand"]
        for _ in range(n_tx):
            tx_type = random.choices(["use", "restock", "adjustment"], weights=[60, 30, 10])[0]
            if tx_type == "use":
                qty_change = -random.randint(1, 3)
            elif tx_type == "restock":
                qty_change = random.randint(5, 15)
            else:
                qty_change = random.randint(-2, 2)
            running = max(0, running + qty_change)
            ts = random_timestamp_in_last_n_days(90)
            worker = random.choice(workers_by_hive.get(item["hive_id"], []))
            tx_rows.append({
                "id": text_id("tx"),
                "worker_name": worker["worker_name"],
                "item_id": item["id"],
                "type": tx_type,
                "qty_change": qty_change,
                "qty_after": running,
                "note": random.choice(TRANSACTION_NOTES),
                "job_ref": "",
                "created_at": to_iso(ts),
                "hive_id": item["hive_id"],
                "auth_uid": worker.get("auth_uid"),
            })

    inserted = batch_insert(client, "inventory_transactions", tx_rows, chunk=500)
    log(f"  inserted {inserted} inventory_transactions")

    return {"inventory_items_count": len(item_rows), "inventory_tx_count": inserted}
