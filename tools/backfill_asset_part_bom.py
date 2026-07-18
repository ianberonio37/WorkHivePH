"""backfill_asset_part_bom.py — populate inventory_items.linked_asset_node_ids (the
spare-parts BOM) from asset_nodes, using the shared rule table in the inventory seeder.

Why: linked_asset_node_ids ("which equipment does this part fit") was left unseeded
(0/N) after the Phase-5b.2 column churn, so inventory.html's asset badges + the logbook
fault-parts-picker's asset prioritization had no data. This is a reproducible, idempotent
backfill (recomputes from scratch), safe to run after any reseed. It only writes
linked_asset_node_ids — the ledger (qty_on_hand / inventory_transactions) is untouched.

Run:  python tools/backfill_asset_part_bom.py [--dry-run]
"""
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "test-data-seeder"))
sys.path.insert(0, str(ROOT / "test-data-seeder" / "seeders"))
from lib.supabase_client import get_client
from seeders.inventory import compute_asset_links

GREEN = "\033[92m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"


def main():
    dry = "--dry-run" in sys.argv
    db = get_client()
    print(f"\n{BOLD}ASSET↔PART BOM BACKFILL{RESET}{'  (dry-run)' if dry else ''}")
    print("─" * 40)

    assets = db.table("asset_nodes").select("id, tag, iso_class, hive_id").limit(5000).execute().data or []
    items  = db.table("inventory_items").select("id, part_number, hive_id").limit(5000).execute().data or []

    assets_by_hive, items_by_hive = {}, {}
    for a in assets:
        assets_by_hive.setdefault(a["hive_id"], []).append(a)
    for it in items:
        items_by_hive.setdefault(it["hive_id"], []).append(it)

    total_linked = total_links = 0
    for hid, hitems in items_by_hive.items():
        hassets = assets_by_hive.get(hid, [])
        links = compute_asset_links(hitems, hassets)
        # Clear-then-set so a re-run is idempotent (parts that no longer match get [] again).
        for it in hitems:
            desired = links.get(it["id"], [])
            if not dry:
                db.table("inventory_items").update({"linked_asset_node_ids": desired or None}).eq("id", it["id"]).execute()
            if desired:
                total_linked += 1
                total_links += len(desired)
        print(f"  hive {hid[:8]}…: {len(links)}/{len(hitems)} parts linked ({sum(len(v) for v in links.values())} edges, {len(hassets)} assets)")

    print(f"\n  {GREEN}{'Would link' if dry else 'Linked'} {total_linked} parts · {total_links} part↔asset edges{RESET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
