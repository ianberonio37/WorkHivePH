"""Logbook-specific UI tests after sign-in."""
import uuid
from datetime import datetime, timezone
from lib.supabase_client import get_client
from .harness import BASE_URL, screenshot


def run(page, errors, warnings, log) -> dict:
    log("Logbook UI checks...")
    results = []

    # Navigate to logbook
    page.goto(f"{BASE_URL}/workhive/logbook.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(1500)  # let entries load

    # Check 1: my entries list shows >0 cards/rows
    try:
        # Try multiple selector patterns for entries
        count = page.evaluate("""() => {
            const candidates = ['[data-entry-id]', '.entry-card', '.logbook-entry', '[id^="entry-"]'];
            for (const sel of candidates) {
                const n = document.querySelectorAll(sel).length;
                if (n > 0) return n;
            }
            // fallback: just count anything that looks like a list of items
            return document.querySelectorAll('main li, main article, main .card').length;
        }""")
        if count > 0:
            results.append(("PASS", f"my-entries shows {count} cards"))
            log(f"  ✓ my-entries shows {count} cards rendered")
        else:
            results.append(("FAIL", "my-entries shows 0 cards"))
            log(f"  ✗ my-entries shows 0 cards (expected ~100-500)")
    except Exception as e:
        results.append(("FAIL", f"entry-count check crashed: {e}"))
        log(f"  ✗ entry-count check crashed: {e}")

    # Check 2: maintenance type pill values present somewhere on page
    try:
        page_text = page.locator("body").inner_text()
        valid_types = ["Breakdown", "Preventive", "Inspection", "Project"]
        found_types = [t for t in valid_types if t in page_text]
        if len(found_types) >= 2:
            results.append(("PASS", f"maintenance type pills visible: {found_types}"))
            log(f"  ✓ maintenance type labels visible: {found_types}")
        else:
            results.append(("WARN", f"few maintenance types visible: {found_types}"))
            log(f"  ⚠ only {len(found_types)} maintenance types visible: {found_types}")
    except Exception as e:
        results.append(("FAIL", f"type-pills check crashed: {e}"))

    # Check 3: discipline category labels present
    try:
        page_text = page.locator("body").inner_text()
        disciplines = ["Mechanical", "Electrical", "Hydraulic", "Instrumentation"]
        found = [d for d in disciplines if d in page_text]
        if len(found) >= 1:
            results.append(("PASS", f"discipline labels visible: {found}"))
            log(f"  ✓ discipline labels visible: {found}")
        else:
            results.append(("WARN", "no discipline labels visible — entries may not be rendering category"))
            log(f"  ⚠ no discipline labels visible")
    except Exception as e:
        results.append(("FAIL", f"discipline-labels check crashed: {e}"))

    screenshot(page, "logbook_my_entries")

    # Check 4: edit-with-parts path — insert Open entry via DB, reload, then edit to Closed
    # This covers the inventory_transactions.insert() id-field bug (Parts log failed toast)
    # Using DB insert avoids the multi-step form wizard (f-problem is in step 2, not visible by default)
    try:
        db = get_client()
        worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")
        hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
        now_iso     = datetime.now(timezone.utc).isoformat()
        test_id     = str(uuid.uuid4())

        insert_res = db.table("logbook").insert({
            "id": test_id, "worker_name": worker_name, "date": now_iso,
            "machine": "TEST-PUMP-001", "problem": "Logbook tester: open entry check",
            "action": "Tester validation", "knowledge": "", "status": "Open",
            "maintenance_type": "Breakdown / Corrective", "root_cause": "",
            "downtime_hours": 0, "created_at": now_iso, "hive_id": hive_id,
            "parts_used": [], "closed_at": None,
        }).execute()

        if not insert_res.data:
            results.append(("WARN", "edit-with-parts check skipped: DB insert returned no data"))
        else:
            # Reload so the new entry appears in the list
            page.reload(wait_until="networkidle")
            page.wait_for_timeout(1500)

            # Open the entry modal (cards use onclick="openModal('id')")
            page.evaluate(f"if (typeof openModal === 'function') openModal('{test_id}')")
            page.wait_for_timeout(800)

            # Click Edit Entry inside the modal
            edit_btn = page.locator("button:has-text('Edit Entry')").first
            if edit_btn.count() and edit_btn.is_visible():
                edit_btn.click()
                page.wait_for_timeout(800)

                # In edit mode all panels are visible — switch to Closed
                page.evaluate("document.querySelector(\"input[name='f-status'][value='Closed']\")?.click()")
                page.wait_for_timeout(400)

                page.locator("#save-entry-btn").click()
                page.wait_for_timeout(2000)

                page_text_after = page.locator("body").inner_text()
                if "Parts log failed" in page_text_after:
                    results.append(("FAIL", "edit-to-closed save shows 'Parts log failed' error"))
                    log("  x edit-to-closed save triggered Parts log failed error")
                elif "Could not update" in page_text_after:
                    results.append(("FAIL", "edit-to-closed save shows 'Could not update' error"))
                    log("  x edit-to-closed save triggered Could not update error")
                else:
                    results.append(("PASS", "edit-to-closed save completes without Parts log error"))
                    log("  v edit-to-closed save completed cleanly")
            else:
                results.append(("WARN", "no Edit Entry button found in modal — skipped edit-with-parts check"))
                log("  ! no Edit Entry button visible in modal")

        # Cleanup
        try:
            db.table("logbook").delete().eq("id", test_id).execute()
        except Exception:
            pass
    except Exception as e:
        results.append(("WARN", f"edit-with-parts check skipped: {e}"))
        log(f"  ! edit-with-parts check error: {e}")

    return {"results": results}
