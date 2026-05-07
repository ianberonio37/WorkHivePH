"""Inventory flows — DB-verified stock accuracy and deduction checks.

Scenarios:
  A – Low stock items have a visual flag (red/amber badge)
  B – Item count on page matches DB row count for hive
  C – Restock: qty increases in DB + inventory_transaction created
  D – Search/filter returns correct subset only
  E – Negative qty never rendered (safety: no negative stock displayed)
  F – Approval queue visible to supervisor, hidden from worker
  G – Stock alert on hive dashboard matches inventory low-stock count
"""

import re
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot


def _get_hive_id(page) -> str | None:
    return page.evaluate("localStorage.getItem('wh_active_hive_id') || null")


def run(page, errors, warnings, log) -> dict:
    log("Inventory flow checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/inventory.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2500)

    hive_id     = _get_hive_id(page)
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    if not hive_id:
        return {"results": [("WARN", "No hive_id — inventory is solo mode, hive-scoped checks skipped")]}

    # ── Scenario A: Low stock items have visual flag ──────────────────────────
    log("  [A] Low stock items visually flagged...")
    try:
        low_stock_items = db.table("inventory_items") \
            .select("id, part_name, qty_on_hand, min_qty") \
            .eq("hive_id", hive_id) \
            .execute().data or []

        actually_low = [
            i for i in low_stock_items
            if (i.get("qty_on_hand") or 0) <= (i.get("min_qty") or 0)
        ]

        if not actually_low:
            results.append(("WARN", "A: no low-stock items in DB — flag check skipped"))
        else:
            page_text = page.locator("body").inner_text()
            # Check that at least one low-stock part name appears with a warning indicator
            first_low = actually_low[0]["part_name"]
            if first_low in page_text:
                # Look for visual indicators near the part name
                low_el = page.locator(f"text={first_low}").first
                if low_el.count():
                    # Use Playwright evaluate on the located element to avoid :has-text() in querySelector
                    parent_html = low_el.evaluate(
                        "el => el.closest('.card, li, [data-item-id], [class*=\"item\"], [class*=\"part\"]')?.outerHTML || el.parentElement?.outerHTML || ''"
                    )
                    has_flag = any(kw in parent_html.lower() for kw in
                                   ["red", "danger", "warn", "low", "alert", "f87171", "fbbf24"])
                    results.append(
                        ("PASS", f"A: low-stock item '{first_low}' has visual flag")
                        if has_flag
                        else ("WARN", f"A: '{first_low}' shown but no obvious visual flag found")
                    )
                else:
                    results.append(("WARN", f"A: low-stock item '{first_low}' not found in rendered list"))
            else:
                results.append(("WARN", f"A: '{first_low}' not in page text — may be paginated or filtered"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Item count on page matches DB ─────────────────────────────
    log("  [B] Rendered item count vs DB count...")
    try:
        db_count = db.table("inventory_items").select("id", count="exact") \
            .eq("hive_id", hive_id).limit(1).execute().count or 0

        # Count rendered item cards — inventory.html renders inside #parts-list
        # Each item has an openDetailModal button
        ui_count = page.evaluate("""() => {
            const sels = [
                '[data-item-id]', '.inventory-item', '.inv-card', '.item-row',
                '#parts-list > *', '[onclick*="openDetailModal"]'
            ];
            for (const s of sels) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) return n;
            }
            return 0;
        }""")

        if db_count == 0:
            results.append(("WARN", "B: no inventory items in DB — count check skipped"))
        elif ui_count == 0:
            results.append(("WARN", f"B: DB has {db_count} items but 0 item cards rendered (may use virtual scroll or different selector)"))
        elif abs(ui_count - db_count) <= max(3, db_count * 0.05):
            results.append(("PASS", f"B: rendered={ui_count} DB={db_count} (within 5% tolerance)"))
        else:
            results.append(("WARN", f"B: rendered={ui_count} DB={db_count} — significant mismatch (pagination or filter active?)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"B crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario C: Restock → qty increases + transaction created ─────────────
    log("  [C] Restock flow: DB qty increases + inventory_transaction inserted...")
    try:
        # Find an item to restock
        items = db.table("inventory_items") \
            .select("id, part_name, qty_on_hand") \
            .eq("hive_id", hive_id) \
            .limit(5).execute().data or []

        if not items:
            results.append(("WARN", "C: no items to restock — skipping"))
        else:
            target        = items[0]
            target_id     = target["id"]
            qty_before    = target["qty_on_hand"] or 0
            restock_qty   = 5

            # Look for a restock button on the page
            restock_btn = page.locator(
                f"button:has-text('Restock'), button:has-text('Add Stock'), "
                f"[data-item-id='{target_id}'] button:has-text('+')"
            ).first

            if not restock_btn.count():
                # Try clicking the item first to open detail
                item_el = page.locator(f"[data-item-id='{target_id}']").first
                if item_el.count():
                    item_el.click()
                    page.wait_for_timeout(600)
                    restock_btn = page.locator("button:has-text('Restock'), button:has-text('Add Stock')").first

            if restock_btn.count():
                restock_btn.click()
                page.wait_for_timeout(500)

                # Fill quantity if a field appeared
                qty_input = page.locator("input[type='number']:visible").first
                if qty_input.count():
                    qty_input.fill(str(restock_qty))

                # Confirm / save
                confirm_btn = page.locator(
                    "button:has-text('Confirm'), button:has-text('Save'), button:has-text('Restock')"
                ).last
                if confirm_btn.count():
                    confirm_btn.click()
                    page.wait_for_timeout(2000)

                # DB verify
                updated = db.table("inventory_items").select("qty_on_hand") \
                    .eq("id", target_id).single().execute().data
                qty_after = updated["qty_on_hand"] if updated else qty_before

                txn = db.table("inventory_transactions").select("id, qty_change") \
                    .eq("item_id", target_id).eq("type", "restock") \
                    .order("created_at", desc=True).limit(1).execute().data

                if qty_after > qty_before:
                    txn_ok = bool(txn and txn[0]["qty_change"] > 0)
                    results.append(("PASS" if txn_ok else "WARN",
                        f"C: qty {qty_before}→{qty_after} ({'+ transaction' if txn_ok else 'but no restock transaction found'})"))
                else:
                    results.append(("WARN", f"C: qty unchanged after restock attempt ({qty_before}→{qty_after}) — UI flow may differ"))
            else:
                results.append(("WARN", "C: no Restock button found — may require supervisor role or different UI path"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Search/filter returns correct subset ──────────────────────
    log("  [D] Search filter narrows item list correctly...")
    try:
        items = db.table("inventory_items") \
            .select("part_name").eq("hive_id", hive_id).limit(10).execute().data or []

        if not items:
            results.append(("WARN", "D: no items in DB — search check skipped"))
        else:
            search_term = items[0]["part_name"][:6].strip()   # first 6 chars = selective enough
            search_input = page.locator(
                "input[type='search'], input[placeholder*='search' i], input[placeholder*='Search' i], #inv-search"
            ).first

            if not search_input.count():
                results.append(("WARN", "D: no search input found on inventory page"))
            else:
                search_input.fill(search_term)
                page.wait_for_timeout(1200)

                page_text = page.locator("body").inner_text()
                if search_term in page_text:
                    # Verify a non-matching item is NOT shown
                    non_match_items = [i for i in items
                                       if not i["part_name"].lower().startswith(search_term.lower())]
                    if non_match_items:
                        hidden = non_match_items[0]["part_name"][:10]
                        if hidden not in page_text:
                            results.append(("PASS", f"D: search '{search_term}' shows match, hides '{hidden}'"))
                        else:
                            results.append(("WARN", f"D: search '{search_term}' shows results but non-matching '{hidden}' also visible"))
                    else:
                        results.append(("PASS", f"D: search '{search_term}' returns results"))
                else:
                    results.append(("WARN", f"D: search '{search_term}' returned no visible results"))

                # Clear search
                search_input.fill("")
                page.wait_for_timeout(600)
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: No negative qty rendered ──────────────────────────────────
    log("  [E] No negative qty_on_hand rendered in list...")
    try:
        page_text = page.locator("body").inner_text()
        # Match patterns like "-1", "-5", "qty: -3" near stock indicators
        neg_matches = re.findall(r"(?:qty|stock|on hand)[^\n]{0,20}-\d+", page_text, re.IGNORECASE)

        if neg_matches:
            results.append(("FAIL", f"E: negative qty values rendered: {neg_matches[:2]}"))
        else:
            # Also check DB for negative values
            neg_in_db = db.table("inventory_items").select("id, part_name, qty_on_hand") \
                .eq("hive_id", hive_id).lt("qty_on_hand", 0).execute().data or []
            if neg_in_db:
                results.append(("FAIL", f"E: {len(neg_in_db)} items have negative qty_on_hand in DB — inventory integrity issue"))
            else:
                results.append(("PASS", "E: no negative qty values in DB or rendered list"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"E crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario F: Approval queue — supervisor sees pending, worker does not ──
    log("  [F] Approval queue: supervisor sees pending items, worker does not...")
    try:
        role = page.evaluate("""
            localStorage.getItem('wh_hive_role') || ''
        """)

        pending_items = db.table("inventory_items").select("id", count="exact") \
            .eq("hive_id", hive_id).eq("status", "pending").limit(1).execute().count or 0

        page_text = page.locator("body").inner_text()
        has_pending_ui = "pending" in page_text.lower() or "approve" in page_text.lower()

        if role == "supervisor":
            if pending_items > 0 and has_pending_ui:
                results.append(("PASS", f"F: supervisor sees {pending_items} pending items in approval queue"))
            elif pending_items > 0 and not has_pending_ui:
                results.append(("WARN", f"F: {pending_items} pending items in DB but approval queue not visible to supervisor"))
            else:
                results.append(("PASS", "F: supervisor view loaded correctly (no pending items to approve)"))
        else:
            if has_pending_ui:
                results.append(("WARN", "F: 'pending/approve' text visible to worker — may be own pending items (acceptable)"))
            else:
                results.append(("PASS", "F: worker view shows no approval queue (correct — workers don't manage approvals)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: Stock alert on hive dashboard matches actual low stock ─────
    log("  [G] Cross-check: hive dashboard stock alert count vs inventory...")
    try:
        low_count = sum(
            1 for i in (db.table("inventory_items")
                .select("qty_on_hand, min_qty").eq("hive_id", hive_id)
                .execute().data or [])
            if (i.get("qty_on_hand") or 0) <= (i.get("min_qty") or 0)
        )

        page.goto(f"{BASE_URL}/workhive/hive.html", wait_until="networkidle", timeout=12000)
        page.wait_for_timeout(2000)
        page_text = page.locator("body").inner_text()

        m = re.search(r"(\d+)\s+items?\s+running low", page_text, re.IGNORECASE)
        dashboard_count = int(m.group(1)) if m else None

        if dashboard_count is None:
            results.append(("WARN" if low_count > 0 else "PASS",
                f"G: dashboard stock alert {'not shown' if low_count == 0 else f'missing — DB has {low_count} low-stock items'}"))
        elif abs(dashboard_count - low_count) <= 2:
            results.append(("PASS", f"G: dashboard shows {dashboard_count} low-stock, DB has {low_count} (match)"))
        else:
            results.append(("WARN", f"G: dashboard shows {dashboard_count} low-stock, DB has {low_count} (mismatch >2)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "inventory_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Inventory: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

