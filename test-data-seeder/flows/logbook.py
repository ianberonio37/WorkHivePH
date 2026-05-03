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

    return {"results": results}
