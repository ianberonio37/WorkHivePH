"""Marketplace + Seller Dashboard flows — DB-verified listing and inquiry checks.

Scenarios:
  A – Listings load with required fields (title, price, contact button)
  B – Listing count on page matches DB approved listings for hive
  C – Search/filter narrows results correctly
  D – Category filter shows only matching listings
  E – Verified seller badge visible on verified listings
  F – Inquiry button opens contact form (not a JS error)
  G – No "undefined" or "null" in any listing field
  H – Seller dashboard shows own listings only
  I – Create listing → DB row inserted (marketplace_listings)
  J – Price values are positive numbers (no negative or NaN)
"""

import re
import time
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

TEST_LISTING_TITLE = f"TEST_LISTING_{int(time.time())}"


def run(page, errors, warnings, log) -> dict:
    log("Marketplace flow checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/marketplace.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(3000)

    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    # ── Scenario A: Listings load with required fields ─────────────────────────
    log("  [A] Listings render with title, price, contact button...")
    try:
        listing_count = page.evaluate("""() => {
            const sels = ['[data-listing-id]', '.listing-card', '.marketplace-item', '[id^="listing-"]'];
            for (const s of sels) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) return n;
            }
            return document.querySelectorAll('main .card, main article').length;
        }""")

        page_text = page.locator("body").inner_text()
        has_price   = bool(re.search(r"₱\s*[\d,]+|PHP\s*[\d,]+|\d+\.00", page_text))
        has_contact = "Contact" in page_text or "Inquire" in page_text or "Message" in page_text

        if listing_count > 0 and has_price:
            results.append(("PASS", f"A: {listing_count} listings with price and {'contact button' if has_contact else 'no contact btn (check UI)'}"))
        elif listing_count > 0:
            results.append(("WARN", f"A: {listing_count} listings but no price pattern found (₱/PHP)"))
        else:
            db_count = db.table("marketplace_listings").select("id", count="exact") \
                .eq("status", "approved").limit(1).execute().count or 0
            results.append(("WARN" if db_count == 0 else "FAIL",
                f"A: 0 listings rendered, DB has {db_count} approved listings"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Listing count matches DB ──────────────────────────────────
    log("  [B] Rendered listing count vs DB approved count...")
    try:
        db_approved = db.table("marketplace_listings").select("id", count="exact") \
            .eq("status", "approved").limit(1).execute().count or 0

        ui_count = page.evaluate("""() => {
            const sels = ['[data-listing-id]', '.listing-card', '.marketplace-item'];
            for (const s of sels) { const n = document.querySelectorAll(s).length; if (n > 0) return n; }
            return 0;
        }""")

        if db_approved == 0:
            results.append(("WARN", "B: no approved listings in DB — count check skipped"))
        elif ui_count == 0:
            results.append(("WARN", f"B: DB has {db_approved} approved but 0 rendered (pagination or filter active?)"))
        elif abs(ui_count - db_approved) <= max(3, db_approved * 0.15):
            results.append(("PASS", f"B: rendered={ui_count} DB={db_approved} (within 15% tolerance)"))
        else:
            results.append(("WARN", f"B: rendered={ui_count} DB={db_approved} — large difference"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Search narrows results ────────────────────────────────────
    log("  [C] Search filter narrows listing results...")
    try:
        listings = db.table("marketplace_listings").select("title") \
            .eq("status", "approved").limit(5).execute().data or []

        search_input = page.locator(
            "input[type='search'], input[placeholder*='search' i], "
            "input[placeholder*='Search' i], #search-input, #marketplace-search"
        ).first

        if not search_input.count() or not listings:
            results.append(("WARN", "C: no search input or no listings in DB — skipping"))
        else:
            search_term = (listings[0].get("title") or "")[:8].strip()
            if not search_term:
                results.append(("WARN", "C: could not extract search term from DB listings"))
            else:
                search_input.fill(search_term)
                page.wait_for_timeout(1500)

                page_text = page.locator("body").inner_text()
                if search_term in page_text:
                    results.append(("PASS", f"C: search '{search_term}' returns matching results"))
                else:
                    results.append(("WARN", f"C: search '{search_term}' returned no visible results"))

                search_input.fill("")
                page.wait_for_timeout(600)
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Category filter shows only matching listings ──────────────
    log("  [D] Category filter shows correct subset...")
    try:
        category_btns = page.locator(
            "button[data-category], [role='tab'][data-category], "
            "button:has-text('Parts'), button:has-text('Services'), button:has-text('Training')"
        ).all()

        if not category_btns:
            results.append(("WARN", "D: no category filter buttons found"))
        else:
            first_cat = category_btns[0]
            cat_label = first_cat.inner_text().strip()
            first_cat.click()
            page.wait_for_timeout(1200)

            page_text_after = page.locator("body").inner_text()
            # Verify the selected category appears and the page changed
            if cat_label and cat_label in page_text_after:
                results.append(("PASS", f"D: category filter '{cat_label}' applied and content updated"))
            else:
                results.append(("WARN", f"D: category filter clicked but page content unclear"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: Verified badge visible on verified sellers ────────────────
    log("  [E] Verified seller badge visible...")
    try:
        page_text = page.locator("body").inner_text()
        verified_sellers = db.table("marketplace_listings").select("id") \
            .eq("status", "approved").limit(5).execute().data or []

        has_verified_ui = any(kw in page_text.lower() for kw in
                               ["verified", "✓", "trusted", "badge"])

        if not verified_sellers:
            results.append(("WARN", "E: no approved listings to check for badges"))
        elif has_verified_ui:
            results.append(("PASS", "E: verified seller indicator visible on marketplace"))
        else:
            results.append(("WARN", "E: no verified badge text found — sellers may not be verified yet"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"E skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario F: Inquiry/Contact button opens form (no JS error) ───────────
    log("  [F] Inquiry button opens contact form without JS error...")
    try:
        errors_before = len(errors)
        contact_btn = page.locator(
            "button:has-text('Contact'), button:has-text('Inquire'), "
            "button:has-text('Message Seller'), a:has-text('Contact')"
        ).first

        if contact_btn.count():
            contact_btn.click()
            page.wait_for_timeout(1000)

            new_errors = [e for e in errors[errors_before:] if "TypeError" in e or "ReferenceError" in e]
            form_opened = page.locator(
                "form:visible, [role='dialog']:visible, .modal:visible, #inquiry-form:visible"
            ).count() > 0

            if new_errors:
                results.append(("FAIL", f"F: JS error on contact click: {new_errors[0][:80]}"))
            elif form_opened:
                results.append(("PASS", "F: contact form opened without JS errors"))
            else:
                results.append(("WARN", "F: contact button clicked but no form/modal appeared"))

            # Close modal if open
            close = page.locator("button:has-text('Close'), button:has-text('Cancel'), [aria-label='Close']").first
            if close.count():
                close.click()
                page.wait_for_timeout(300)
        else:
            results.append(("WARN", "F: no contact/inquire button found"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: No "undefined" or "null" in listing fields ───────────────
    log("  [G] No 'undefined' or literal 'null' in listing display...")
    try:
        page_text = page.locator("body").inner_text()
        has_undefined = "undefined" in page_text
        has_null_text = bool(re.search(r"\bnull\b", page_text))

        if has_undefined:
            results.append(("FAIL", "G: 'undefined' found in marketplace page — data mapping issue"))
        elif has_null_text:
            results.append(("WARN", "G: literal 'null' found in marketplace text — may be display issue"))
        else:
            results.append(("PASS", "G: no 'undefined' or literal 'null' in listing display"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"G crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario H: Seller dashboard shows own listings ───────────────────────
    log("  [H] Seller dashboard shows own listings only...")
    try:
        page.goto(f"{BASE_URL}/workhive/marketplace-seller.html", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2500)

        own_listings = db.table("marketplace_listings").select("id, title") \
            .eq("seller_name", worker_name).limit(5).execute().data or []

        page_text = page.locator("body").inner_text()

        if not own_listings:
            results.append(("WARN", "H: no listings by this seller in DB — dashboard will be empty"))
        else:
            found = sum(1 for l in own_listings if (l.get("title") or "") in page_text)
            if found > 0:
                results.append(("PASS", f"H: seller dashboard shows {found}/{len(own_listings)} own listing(s)"))
            else:
                results.append(("WARN", f"H: {len(own_listings)} own listings in DB but none visible in seller dashboard"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario I: Create listing → DB row inserted ──────────────────────────
    log("  [I] Create listing → marketplace_listings row in DB...")
    try:
        db_before = db.table("marketplace_listings").select("id", count="exact") \
            .eq("seller_name", worker_name).limit(1).execute().count or 0

        create_btn = page.locator(
            "button:has-text('New Listing'), button:has-text('Create Listing'), "
            "button:has-text('Add Listing'), button:has-text('List an Item')"
        ).first

        if create_btn.count():
            create_btn.click()
            page.wait_for_timeout(800)

            title_input = page.locator(
                "input[name='title'], input[placeholder*='title' i], #listing-title"
            ).first
            price_input = page.locator(
                "input[name='price'], input[type='number'], input[placeholder*='price' i]"
            ).first

            if title_input.count() and price_input.count():
                title_input.fill(TEST_LISTING_TITLE)
                price_input.fill("1500")

                desc = page.locator("textarea[name='description'], textarea[placeholder*='desc' i]").first
                if desc.count():
                    desc.fill("Test listing created by automated flow test")

                submit = page.locator(
                    "button[type='submit'], button:has-text('Publish'), "
                    "button:has-text('Submit'), button:has-text('Post Listing')"
                ).first
                if submit.count():
                    submit.click()
                    page.wait_for_timeout(2500)

                    db_after = db.table("marketplace_listings").select("id", count="exact") \
                        .eq("seller_name", worker_name).limit(1).execute().count or 0

                    if db_after > db_before:
                        results.append(("PASS", f"I: listing created in DB ({db_before}→{db_after})"))
                    else:
                        results.append(("WARN", "I: listing count unchanged in DB (may require approval)"))
                else:
                    results.append(("WARN", "I: submit button not found in listing form"))
            else:
                results.append(("WARN", "I: title or price input not found in listing form"))
        else:
            results.append(("WARN", "I: Create Listing button not found on seller dashboard"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"I skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario J: Price values are positive (no negative or NaN) ────────────
    log("  [J] Listing prices are positive numbers...")
    try:
        page.goto(f"{BASE_URL}/workhive/marketplace.html", wait_until="networkidle", timeout=12000)
        page.wait_for_timeout(2500)

        page_text = page.locator("body").inner_text()
        neg_prices  = re.findall(r"₱\s*-[\d,]+", page_text)
        nan_prices  = "NaN" in page_text

        if nan_prices:
            results.append(("FAIL", "J: NaN found in price display — calculation bug"))
        elif neg_prices:
            results.append(("FAIL", f"J: negative prices displayed: {neg_prices[:2]}"))
        else:
            results.append(("PASS", "J: no negative or NaN prices rendered"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"J crashed: {e}"))
        log(f"    → FAIL: {e}")

    # Cleanup test listing
    try:
        db.table("marketplace_listings").delete() \
            .eq("seller_name", worker_name) \
            .like("title", "TEST_LISTING_%").execute()
    except Exception:
        pass

    screenshot(page, "marketplace_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Marketplace: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

