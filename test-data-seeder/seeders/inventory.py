"""Seed inventory_items + inventory_transactions (born ledger-consistent).

ARC DI §10.5 anti-seesaw (2026-07-08): the stock level is ONE truth stored TWO ways --
inventory_items.qty_on_hand (balance) and inventory_transactions.qty_after (ledger). The
old seeder wrote qty_on_hand as an OPENING balance then walked the ledger FORWARD from it
(latest qty_after = opening + net_change != qty_on_hand) AND stamped txns with random,
unsorted created_at (so "latest by created_at" didn't track the running total) -> 25/27
items drifted. This seeder builds each item's ledger FIRST, chronologically, and sets the
stored balance to the ledger's LAST qty_after -> balance == latest qty_after and each
qty_after == prev + qty_change by construction. Co-lands with migration
20260708000001 (reconcile trigger) + gate validate_inventory_ledger_reconciled so the
next reseed cannot re-open the drift (kills the cross-session seesaw).
"""
import random
from datetime import timedelta

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


def _gen_ledger(target_qty: int, low_stock: bool):
    """Build a born-consistent ledger; return (final_balance, txns).

    txns is a CHRONOLOGICAL list of {type, qty_change, qty_after, ts} where each
    qty_after == prev_qty_after + qty_change (cumulative-consistent) and the LAST
    qty_after == final_balance. The caller stores final_balance as qty_on_hand, so
    the balance and the ledger's newest running total agree by construction -- the
    §10.5 anti-seesaw contract. Runs non-negative throughout.
    """
    n_tx = random.randint(3, 8)
    # Distinct, sorted, chronological timestamps so the newest-by-created_at row is
    # the true final movement (the old seeder's random order broke this invariant).
    tstamps = sorted(random_timestamp_in_last_n_days(90) for _ in range(n_tx))
    for k in range(1, len(tstamps)):
        if tstamps[k] <= tstamps[k - 1]:
            tstamps[k] = tstamps[k - 1] + timedelta(seconds=1)
    # Low-stock items use only small use/adjustment movements so the ledger genuinely
    # ends at/below min_qty (deterministic low-stock UI coverage, as before).
    changes = []
    for _ in range(n_tx):
        if low_stock:
            tx_type = random.choices(["use", "adjustment"], weights=[70, 30])[0]
        else:
            tx_type = random.choices(["use", "restock", "adjustment"], weights=[60, 30, 10])[0]
        if tx_type == "use":
            ch = -random.randint(1, 3)
        elif tx_type == "restock":
            ch = random.randint(5, 15)
        else:
            ch = random.randint(-2, 2)
        changes.append((tx_type, ch))
    # Opening chosen so the ledger ENDS exactly at target_qty (clamped non-negative).
    opening = target_qty - sum(ch for _, ch in changes)
    if opening < 0:
        opening = 0  # final becomes sum(changes); still fully cumulative-consistent
    running = opening
    txns = []
    for (tx_type, ch), ts in zip(changes, tstamps):
        running += ch
        if running < 0:            # keep the running total >= 0 AND consistent:
            ch -= running          #   shrink this movement so qty_after lands at 0
            running = 0
        txns.append({"type": tx_type, "qty_change": ch, "qty_after": running, "ts": ts})
    return running, txns


# ── Asset ↔ spare-part BOM (Inventory PDDA, 2026-07-12) ────────────────────────
# linked_asset_node_ids (uuid[] on inventory_items) is the spare-parts BOM: "which
# equipment does this part fit". It was left unseeded (0/N) after the Phase-5b.2 column
# churn, so inventory.html's asset badges + the logbook fault-parts-picker had nothing to
# prioritize. This rule table rebuilds a realistic partial BOM by matching a part to the
# equipment it services (consumables/refrigerant/cleaner intentionally stay unlinked —
# not every part maps to an asset). Pure functions so the standalone backfill tool
# (tools/backfill_asset_part_bom.py) and the seeder share ONE mapping.
def _asset_matches_part(part_number: str, asset: dict) -> bool:
    pn  = (part_number or "").upper()
    tag = (asset.get("tag") or "").upper()
    iso = asset.get("iso_class") or ""
    def tagp(*prefixes): return any(tag.startswith(p) for p in prefixes)
    if pn in ("PUMP-WR-SET", "SEAL-T2100"):                     return tagp("P-", "SUB-")
    if pn.startswith("BRG") or pn.startswith("GREASE"):         return tagp("P-", "SUB-", "GEN-", "AC-", "RC-", "MILL-", "CR-", "BF-")
    if pn in ("FLT-FUEL-P", "FLT-FUEL-S", "FLT-OIL", "OIL-15W40", "BAT-12V100"): return tagp("GEN-")
    if pn == "FLT-AIR":                                         return tagp("AC-", "RC-", "GEN-")
    if pn == "OIL-VG46":                                        return iso == "Hydraulic" or tagp("HPU-")
    if pn == "PT100":                                           return iso == "Instrumentation" or tagp("TT-", "BLR-")
    if pn in ("PSV-SPARE", "GAS-SW-DN50"):                      return tagp("PV-", "BLR-")
    if pn in ("CB-MCCB-160", "CONT-32A", "FUSE-100A", "FUSE-32A", "CABLE-25MM"): return iso == "Electrical" or tagp("UPS-", "PLC-", "WLD-")
    if pn == "VBELT-SPB1700":                                   return tagp("AC-", "BF-")
    if pn == "CHAIN-12B":                                       return tagp("CR-", "FL-")
    return False


def compute_asset_links(items: list, assets: list, cap: int = 6) -> dict:
    """Return {item_id: [asset_node_id,...]} — up to `cap` matching assets per part,
    picking ONE representative per asset family (tag prefix, e.g. 'P', 'GEN') so a generic
    part (a bearing, grease) spreads across equipment TYPES instead of clustering on the
    early-alphabet tags of a single family. Deterministic (tag-sorted) => idempotent."""
    assets_sorted = sorted(assets, key=lambda a: (a.get("tag") or "", a.get("id") or ""))
    links = {}
    for it in items:
        matched = [a for a in assets_sorted if _asset_matches_part(it.get("part_number", ""), a)]
        seen_fam, chosen = set(), []
        for a in matched:
            fam = (a.get("tag") or "").split("-")[0]
            if fam in seen_fam:
                continue
            seen_fam.add(fam)
            chosen.append(a["id"])
            if len(chosen) >= cap:
                break
        if chosen:
            links[it["id"]] = chosen
    return links


def seed_inventory(client, log, ctx: dict) -> dict:
    """ctx must include 'hives' and 'workers' and 'assets_by_hive'."""
    hives = ctx["hives"]
    workers = ctx["workers"]
    workers_by_hive: dict = {}
    for w in workers:
        workers_by_hive.setdefault(w["hive_id"], []).append(w)

    log(f"Seeding inventory_items per hive ({len(PARTS_CATALOG)} parts x {len(hives)} hives)...")

    item_rows = []
    tx_rows = []

    for hive in hives:
        hive_workers = workers_by_hive.get(hive["id"], [])
        if not hive_workers:
            continue
        supervisors = [w for w in hive_workers if w["role"] == "supervisor"]
        approver = supervisors[0] if supervisors else hive_workers[0]

        for idx, (part_no, part_name, category, unit, init_qty, min_qty) in enumerate(PARTS_CATALOG):
            submitter = random.choice(hive_workers)
            # Force ~10% of parts below min_qty so the low-stock UI gets tested.
            low_stock = (idx % 10 == 0)
            if low_stock:
                target = max(0, min_qty - random.randint(1, max(1, min_qty // 2)))
            else:
                target = max(0, init_qty + random.randint(-3, 5))

            # Build the ledger FIRST so the stored balance == its latest qty_after.
            final_balance, item_txns = _gen_ledger(target, low_stock)
            item_id = text_id("inv")
            item_rows.append({
                "id": item_id,
                "worker_name": submitter["worker_name"],
                "part_number": part_no,
                "part_name": part_name,
                "category": category,
                "unit": unit,
                "qty_on_hand": final_balance,   # reconciled: equals the ledger's last qty_after
                "min_qty": min_qty,
                "bin_location": f"Bin {random.randint(1, 12)}-{random.choice(['A', 'B', 'C'])}",
                # linked_asset_ids was dropped in Phase 5b.2 (2026-05-12) in favour of the
                # parts_records cross-table linkage (association lives on the txn side).
                "notes": "",
                "status": "approved",
                "hive_id": hive["id"],
                "submitted_by": submitter["worker_name"],
                "approved_by": approver["worker_name"],
                "approved_at": to_iso(random_timestamp_in_last_n_days(120)),
                "auth_uid": submitter.get("auth_uid"),
            })
            for t in item_txns:
                worker = random.choice(hive_workers)
                tx_rows.append({
                    "id": text_id("tx"),
                    "worker_name": worker["worker_name"],
                    "item_id": item_id,
                    "type": t["type"],
                    "qty_change": t["qty_change"],
                    "qty_after": t["qty_after"],
                    "note": random.choice(TRANSACTION_NOTES),
                    "job_ref": "",
                    "created_at": to_iso(t["ts"]),
                    "hive_id": hive["id"],
                    "auth_uid": worker.get("auth_uid"),
                })

    client.table("inventory_items").insert(item_rows).execute()
    log(f"  inserted {len(item_rows)} inventory_items")

    log("Generating inventory_transactions (chronological, ledger-consistent)...")
    inserted = batch_insert(client, "inventory_transactions", tx_rows, chunk=500)
    log(f"  inserted {inserted} inventory_transactions (balance == latest qty_after by construction)")

    return {"inventory_items_count": len(item_rows), "inventory_tx_count": inserted}
