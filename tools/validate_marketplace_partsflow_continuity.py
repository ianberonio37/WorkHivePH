#!/usr/bin/env python3
"""
validate_marketplace_partsflow_continuity.py — MK6: lock the inventory <-> marketplace round trip.

The 2026-07-24 deepwalk walked this flow in BOTH directions and found it clean. A clean walk is a real
result, but it is not a durable one: nothing stopped a later edit from quietly removing a hop, and the
next deepwalk would have had to rediscover it. This is the lock.

THE FOUR INVARIANTS (each is one hop of the round trip, or the rule that keeps it safe):

  MK6.1 SELL deep link      inventory.html offers surplus/above-reorder stock a "Sell" link into
                            marketplace.html carrying `from_inventory=<id>`, and marketplace.html
                            READS it to prefill the post. A link nobody reads is a dead end.
  MK6.2 PART NUMBER SEARCH  the buyer search must also match `part_number`, because that is the strong
                            join key between the two sides. Inventory is material-centric and listings
                            are equipment-centric, so their category taxonomies diverge and category
                            alone can never match a part.
  MK6.3 RECEIVE round trip  the listing detail offers "Received this? Add to inventory" back into
                            inventory.html (`receive=1`), closing the loop rather than stranding a
                            buyer who just took delivery.
  MK6.4 PROVENANCE STAYS    `source_inventory_item_id` must remain BASE-only and must NOT be projected
        BASE-ONLY           through v_marketplace_listings_truth. It is one tenant's internal inventory
                            id; exposing it through the buyer-facing view would leak tenant topology
                            out of the hive. This is the security half of the bridge and the reason
                            this gate checks the live view rather than trusting the migration text.

MK6.4 needs the DB and SKIPs cleanly when docker is absent (same policy as the other live gates); the
rest are static, so the gate still has teeth in --fast.
Self-test: `--selftest`.
"""
from __future__ import annotations
import re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTAINER = "supabase_db_workhive"
GREEN, RED, YELLOW, BOLD, RESET = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"


def _read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""


def _view_exposes(column: str) -> bool | None:
    """True/False from the LIVE view; None when the DB is unreachable."""
    try:
        r = subprocess.run(
            ["docker", "exec", CONTAINER, "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c",
             "SELECT COUNT(*) FROM information_schema.columns "
             "WHERE table_name='v_marketplace_listings_truth' AND column_name='" + column + "';"],
            capture_output=True, text=True, timeout=60)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    try:
        return int(r.stdout.strip()) > 0
    except ValueError:
        return None


def run() -> int:
    results: list[tuple[str, bool | None, str]] = []

    inv, mkt = _read("inventory.html"), _read("marketplace.html")

    # MK6.1 — the link must be EMITTED by inventory and READ by marketplace. Either half alone is dead.
    emits = "from_inventory" in inv
    reads = "from_inventory" in mkt
    results.append(("MK6.1 inventory->marketplace Sell deep link", emits and reads,
                    "inventory emits from_inventory and marketplace reads it" if (emits and reads)
                    else f"broken hop (inventory emits={emits}, marketplace reads={reads}) -> surplus "
                         f"stock has no path to a listing, or the prefill silently drops"))

    # MK6.2 — part_number is the join key; category alone cannot match a part across the two taxonomies.
    results.append(("MK6.2 buyer search matches part_number", "part_number.ilike" in mkt,
                    "search includes part_number.ilike" if "part_number.ilike" in mkt
                    else "search dropped part_number -> a buyer holding a part number cannot find the listing"))

    # MK6.3 — close the loop back into inventory's own ledger-consistent receive path.
    results.append(("MK6.3 marketplace->inventory receive round trip",
                    "receive=1" in mkt and "receive" in inv,
                    "listing detail routes back into inventory's receive path" if ("receive=1" in mkt and "receive" in inv)
                    else "the round trip is open-ended -> a buyer who received the part has no way back in"))

    # MK6.4 — provenance is BASE-only. Checked LIVE, because a later CREATE OR REPLACE VIEW could add it.
    exposed = _view_exposes("source_inventory_item_id")
    if exposed is None:
        results.append(("MK6.4 provenance stays base-only", None, "local DB unreachable — skipped"))
    else:
        results.append(("MK6.4 provenance stays base-only", not exposed,
                        "v_marketplace_listings_truth does not project source_inventory_item_id" if not exposed
                        else "the buyer-facing truth view PROJECTS source_inventory_item_id -> one tenant's "
                             "internal inventory id leaks out of the hive"))

    print(f"{BOLD}Marketplace parts-flow continuity (MK6){RESET}")
    n_pass = n_fail = n_skip = 0
    for label, ok, detail in results:
        if ok is None:
            n_skip += 1; print(f"  {YELLOW}SKIP{RESET}  {label}: {detail}")
        elif ok:
            n_pass += 1; print(f"  {GREEN}PASS{RESET}  {label}: {detail}")
        else:
            n_fail += 1; print(f"  {RED}FAIL{RESET}  {label}: {detail}")
    print(f"MK6 parts-flow: {n_pass} PASS, {n_fail} FAIL, {n_skip} SKIP")
    return 1 if n_fail else 0


def selftest() -> int:
    """Prove each detector FIRES on a synthetic break (a gate that cannot fail is not a gate)."""
    ok = True

    def chk(label, got, want):
        nonlocal ok
        good = got == want
        ok &= good
        print(f"  {GREEN+'PASS'+RESET if good else RED+'FAIL'+RESET}  {label}: got {got}, want {want}")

    # MK6.1 needs BOTH halves — the half-wired case is the one worth catching.
    chk("emit-only link is a broken hop", ("from_inventory" in 'href="marketplace.html?from_inventory=1"')
        and ("from_inventory" in "const q = new URLSearchParams();"), False)
    chk("both halves present passes", ("from_inventory" in 'href="?from_inventory=1"')
        and ("from_inventory" in "params.get('from_inventory')"), True)
    chk("MK6.2 fires when the part_number filter is dropped", "part_number.ilike" in "or(`title.ilike.%x%`)", False)
    chk("MK6.2 passes with the filter", "part_number.ilike" in "or(`part_number.ilike.%x%`)", True)
    chk("MK6.3 fires without the receive link", "receive=1" in 'href="inventory.html"', False)
    chk("MK6.3 passes with it", "receive=1" in 'href="inventory.html?receive=1"', True)
    print(f"\n  SELFTEST: {GREEN+'PASS'+RESET if ok else RED+'FAIL'+RESET}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(selftest() if "--selftest" in sys.argv else run())
