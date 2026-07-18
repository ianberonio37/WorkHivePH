"""validate_inventory_integrity.py — Inventory data quality checks.

Checks:
  1. no_negative_qty    — qty_on_hand must never be negative
  2. txn_item_refs      — every inventory_transaction.item_id references a real item
  3. txn_type_valid     — every transaction has a valid type (use/restock/adjustment)
  4. qty_after_accuracy — spot-check: qty_after in recent transactions approximates
                          current qty_on_hand (catches silent deduction bugs)
  5. min_qty_positive   — min_qty must be > 0 for items that need reorder alerts

Found during walkthrough (May 2026): parts deduction ran even when the
logbook update silently failed (0 rows updated). This can result in
inventory counts that are lower than they should be. This validator detects
the symptom: negative qty or implausible qty_after sequences.
"""

import sys, json
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "test-data-seeder"))
from lib.supabase_client import get_client

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

VALID_TXN_TYPES = {"use", "restock", "adjustment", "add"}  # 'add' = initial stock / manual restock (inventory.html:934, 1028)


def main():
    db = get_client()
    results = []
    total_pass = total_fail = total_warn = 0

    print(f"\n{BOLD}INVENTORY INTEGRITY VALIDATOR{RESET}")
    print("─" * 40)

    items = db.table("inventory_items") \
        .select("id, part_name, part_number, qty_on_hand, min_qty, hive_id, linked_asset_node_ids") \
        .limit(500).execute().data or []

    txns = db.table("inventory_transactions") \
        .select("id, item_id, type, qty_change, qty_after, created_at") \
        .order("created_at", desc=True) \
        .limit(1000).execute().data or []

    item_ids = {i["id"] for i in items}
    print(f"  Items: {len(items)} | Transactions: {len(txns)}")

    # ── Check 1: No negative qty_on_hand ─────────────────────────────────────
    negative = [i for i in items if (i.get("qty_on_hand") or 0) < 0]

    if not negative:
        print(f"  {GREEN}PASS{RESET}  no_negative_qty: all {len(items)} items have qty_on_hand ≥ 0")
        total_pass += 1
        results.append({"check": "no_negative_qty", "status": "PASS", "count": 0})
    else:
        n = len(negative)
        print(f"  {RED}FAIL{RESET}  no_negative_qty: {n} items have negative qty_on_hand")
        for i in negative[:3]:
            print(f"         → {i['part_name']} (#{i['part_number']}): qty={i['qty_on_hand']}")
        total_fail += 1
        results.append({"check": "no_negative_qty", "status": "FAIL", "count": n,
                        "examples": [i["id"] for i in negative[:5]]})

    # ── Check 2: Transaction item_ids reference real items ────────────────────
    orphan_txns = [t for t in txns if t.get("item_id") not in item_ids]

    if not orphan_txns:
        print(f"  {GREEN}PASS{RESET}  txn_item_refs: all {len(txns)} transactions reference valid items")
        total_pass += 1
        results.append({"check": "txn_item_refs", "status": "PASS", "count": 0})
    else:
        n = len(orphan_txns)
        print(f"  {YELLOW}WARN{RESET}  txn_item_refs: {n} transactions reference item_ids not in inventory_items")
        print(f"         (may be from deleted items — not necessarily a bug)")
        total_warn += 1
        results.append({"check": "txn_item_refs", "status": "WARN", "count": n})

    # ── Check 3: Transaction types are valid ──────────────────────────────────
    invalid_types = [t for t in txns if t.get("type") not in VALID_TXN_TYPES]

    if not invalid_types:
        print(f"  {GREEN}PASS{RESET}  txn_type_valid: all transactions use valid type values")
        total_pass += 1
        results.append({"check": "txn_type_valid", "status": "PASS", "count": 0})
    else:
        bad = list({t["type"] for t in invalid_types})
        print(f"  {RED}FAIL{RESET}  txn_type_valid: {len(invalid_types)} transactions with invalid type: {bad}")
        total_fail += 1
        results.append({"check": "txn_type_valid", "status": "FAIL",
                        "count": len(invalid_types), "invalid_types": bad})

    # ── Check 4: qty_after in last transaction approximates current qty ───────
    # Group last transaction per item and compare qty_after to current qty_on_hand
    mismatch_count = 0
    checked = 0
    by_item: dict[str, dict] = {}
    for t in txns:
        if t.get("item_id") and t["item_id"] not in by_item:
            by_item[t["item_id"]] = t

    for item in items[:50]:   # sample
        last = by_item.get(item["id"])
        if not last or last.get("qty_after") is None:
            continue
        checked += 1
        diff = abs((last["qty_after"] or 0) - (item["qty_on_hand"] or 0))
        if diff > 20:   # more than 20 units off = suspicious
            mismatch_count += 1

    if checked == 0:
        print(f"  {YELLOW}WARN{RESET}  qty_after_accuracy: no transactions to compare (no history)")
        total_warn += 1
        results.append({"check": "qty_after_accuracy", "status": "WARN", "reason": "no transactions"})
    elif mismatch_count == 0:
        print(f"  {GREEN}PASS{RESET}  qty_after_accuracy: qty_after in last transactions matches current qty ({checked} checked)")
        total_pass += 1
        results.append({"check": "qty_after_accuracy", "status": "PASS",
                        "checked": checked, "mismatch": 0})
    else:
        print(f"  {YELLOW}WARN{RESET}  qty_after_accuracy: {mismatch_count}/{checked} items have >20 unit gap between last txn and current qty")
        print(f"         (may indicate unrecorded deductions from the silent-failure bug)")
        total_warn += 1
        results.append({"check": "qty_after_accuracy", "status": "WARN",
                        "checked": checked, "mismatch": mismatch_count})

    # ── Check 5: min_qty is positive for items with reorder alerts ────────────
    zero_min = [i for i in items if (i.get("min_qty") or 0) <= 0]

    if not zero_min:
        print(f"  {GREEN}PASS{RESET}  min_qty_positive: all items have min_qty > 0")
        total_pass += 1
        results.append({"check": "min_qty_positive", "status": "PASS", "count": 0})
    else:
        n = len(zero_min)
        print(f"  {YELLOW}WARN{RESET}  min_qty_positive: {n} items have min_qty=0 or null — stock alerts won't fire for them")
        total_warn += 1
        results.append({"check": "min_qty_positive", "status": "WARN", "count": n})

    # ── Check 6: Asset↔part BOM coverage (Inventory PDDA) ─────────────────────
    # linked_asset_node_ids is the spare-parts BOM that drives inventory.html's asset
    # badges + the logbook fault-parts-picker prioritization. WARN (not FAIL) when 0
    # parts are linked — it's a seed-state canary: run tools/backfill_asset_part_bom.py
    # (the seed pipeline's post-seed step wires it automatically on a fresh reseed).
    linked = [i for i in items if i.get("linked_asset_node_ids")]
    if linked:
        print(f"  {GREEN}PASS{RESET}  asset_bom_coverage: {len(linked)}/{len(items)} parts linked to equipment (spare-parts BOM)")
        total_pass += 1
        results.append({"check": "asset_bom_coverage", "status": "PASS", "linked": len(linked), "total": len(items)})
    else:
        print(f"  {YELLOW}WARN{RESET}  asset_bom_coverage: 0/{len(items)} parts linked — run tools/backfill_asset_part_bom.py (BOM unseeded)")
        total_warn += 1
        results.append({"check": "asset_bom_coverage", "status": "WARN", "linked": 0, "total": len(items)})

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n  Summary: {total_pass} pass · {total_warn} warn · {total_fail} fail")

    report = {
        "validator": "inventory_integrity",
        "pass": total_pass, "warn": total_warn, "fail": total_fail,
        "total_items": len(items), "total_txns": len(txns),
        "checks": results,
    }
    out = ROOT / "inventory_integrity_report.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    sys.exit(0 if total_fail == 0 else 1)


if __name__ == "__main__":
    main()
