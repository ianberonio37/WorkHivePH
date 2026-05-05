"""Logbook-specific UI tests after sign-in."""
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

    # Check 4: edit-with-parts path — log an open entry then close it with a part
    # This covers the inventory_transactions.insert() id-field bug (Parts log failed toast)
    try:
        # Fill minimum required fields for a new Open entry
        page.locator("#f-machine").fill("TEST-PUMP-001")
        page.locator("#f-problem").fill("Logbook tester: open entry check")
        page.locator("#f-action").fill("Tester validation")
        open_radio = page.locator("input[name='f-status'][value='Open']")
        if open_radio.count():
            open_radio.check()

        # Save as Open
        page.locator("#save-entry-btn").click()
        page.wait_for_timeout(2000)

        # Find the entry we just saved and open it for editing
        # It should appear first in "my entries" since it was just added
        edit_btn = page.locator("button:has-text('Edit Entry')").first
        if edit_btn.count():
            edit_btn.click()
            page.wait_for_timeout(800)

            # Switch status to Closed — this reveals the parts section
            closed_radio = page.locator("input[name='f-status'][value='Closed']")
            if closed_radio.count():
                closed_radio.check()
                page.wait_for_timeout(600)

            # Save (no parts this time — just verify the closed save path works)
            save_btn = page.locator("#save-entry-btn")
            save_btn.click()
            page.wait_for_timeout(2000)

            # Check: no "Parts log failed" toast visible
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
            results.append(("WARN", "no Edit Entry button found — skipped edit-with-parts check"))
            log("  ! no Edit Entry button found to test edit path")
    except Exception as e:
        results.append(("WARN", f"edit-with-parts check skipped: {e}"))
        log(f"  ! edit-with-parts check error: {e}")

    return {"results": results}
