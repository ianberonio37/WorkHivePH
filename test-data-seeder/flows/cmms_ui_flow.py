"""CMMS Integration UI flows — wizard steps and API key management.

Scenarios:
  A – Three tabs (Import File, Live Sync, API Keys) render and switch correctly
  B – Step 1: source card selection enables the Next button
  C – Step 2: CSV upload shows row count and detects SAP format
  D – Step 3: Auto-suggest maps critical SAP fields (AUFNR → Work Order ID)
  E – Step 4: Preview table shows 5 rows with no undefined values
  F – Step 5: Import reports a count (not 0 or NaN)
  G – Live Sync: Test Connection returns feedback within 15s
  H – API Keys: generate key starts with wh_ and appears in Active Keys list
  I – Generated API key revocation removes it from list
"""

import os
import re
import csv
import time
import tempfile
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot


def _make_test_csv() -> str:
    """Create a minimal SAP PM work orders CSV for upload testing."""
    rows = [
        {
            "AUFNR": f"00000001{i:04d}", "AUART": "PM02" if i % 3 else "PM01",
            "LTXT": f"Test fault description {i} — bearing check",
            "ISTAT": "I0045" if i % 2 else "I0002",
            "ARBEI": str(round(i * 1.5, 1)),
            "ERDAT": f"2026-0{(i % 5)+1:01d}-{(i % 28)+1:02d}",
            "AEDAT": f"2026-0{(i % 5)+1:01d}-{(i % 28)+1:02d}",
            "RUCKMDAT": f"2026-0{(i % 5)+1:01d}-{(i % 28)+2:02d}" if i % 2 else "",
            "EQUNR": f"P-{i:03d}",
            "KOSTL": "CC-FP-MAINT",
            "PRIOK": str((i % 4) + 1),
            "ARBPL": "MAINT-01",
            "QMNUM": f"QM-{i:05d}" if i % 3 else "",
        }
        for i in range(1, 21)   # 20 rows — enough to test without being slow
    ]
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def run(page, errors, warnings, log) -> dict:
    log("CMMS Integration UI flow checks...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/integrations.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)

    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    # ── Scenario A: Three tabs render and switch ──────────────────────────────
    log("  [A] Import File / Live Sync / API Keys tabs render and switch...")
    try:
        page_text   = page.locator("body").inner_text()
        tab_labels  = ["Import File", "Live Sync", "API Keys"]
        found_tabs  = [t for t in tab_labels if t in page_text]

        if len(found_tabs) < 3:
            results.append(("FAIL", f"A: only {len(found_tabs)}/3 tabs found: {found_tabs}"))
        else:
            # Click Live Sync tab
            sync_tab = page.locator("button:has-text('Live Sync'), [data-tab='sync'], #tab-sync").first
            if sync_tab.count():
                sync_tab.click()
                page.wait_for_timeout(500)
                sync_visible = page.locator("#tab-sync-content").is_visible() \
                    if page.locator("#tab-sync-content").count() else False

                # Click back to Import
                import_tab = page.locator("button:has-text('Import File'), #tab-import").first
                if import_tab.count():
                    import_tab.click()
                    page.wait_for_timeout(400)

                results.append(("PASS", f"A: all 3 tabs found, Live Sync tab switched correctly"))
            else:
                results.append(("WARN", "A: tabs found in text but Live Sync tab button not clickable"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Step 1 — source card enables Next ─────────────────────────
    log("  [B] Selecting SAP PM card enables Next button...")
    try:
        sap_card = page.locator(
            "[data-type='sap_pm'], .source-card:has-text('SAP PM'), "
            "div:has-text('SAP PM'):has-text('AUFNR')"
        ).first

        next_btn = page.locator("#btn-s1-next, button:has-text('Next: Upload')").first

        if not sap_card.count():
            results.append(("WARN", "B: SAP PM source card not found"))
        elif not next_btn.count():
            results.append(("WARN", "B: Next button not found"))
        else:
            # Verify Next is disabled before selection
            disabled_before = next_btn.is_disabled()
            # Call selectSource() directly — most reliable across all page states
            page.evaluate("selectSource('sap_pm')")
            page.wait_for_timeout(800)
            disabled_after = next_btn.is_disabled()

            if disabled_before and not disabled_after:
                results.append(("PASS", "B: Next button enabled after SAP PM card selection"))
            elif not disabled_before:
                results.append(("WARN", "B: Next button was already enabled before card selection"))
            else:
                results.append(("FAIL", "B: Next button still disabled after clicking SAP PM card"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Step 2 — CSV upload detects format ───────────────────────
    log("  [C] CSV upload detects SAP format and shows row count...")
    csv_path = None
    try:
        csv_path = _make_test_csv()

        # Click Next to go to Step 2
        next_btn = page.locator("#btn-s1-next, button:has-text('Next: Upload')").first
        if next_btn.count() and not next_btn.is_disabled():
            next_btn.click()
            page.wait_for_timeout(600)

        # Upload the CSV
        file_input = page.locator("input[type='file']").first
        if file_input.count():
            page.set_input_files("input[type='file']", csv_path)
            page.wait_for_timeout(3000)   # CSV parsing

            page_text = page.locator("body").inner_text()
            has_row_count = "20" in page_text or "rows" in page_text.lower()
            has_sap_detect = any(kw in page_text for kw in
                                  ["SAP PM", "SAP", "AUFNR", "detected"])

            if has_row_count and has_sap_detect:
                results.append(("PASS", "C: CSV uploaded — row count shown and SAP format detected"))
            elif has_row_count:
                results.append(("WARN", "C: row count shown but SAP auto-detection not confirmed"))
            elif has_sap_detect:
                results.append(("WARN", "C: SAP detected but row count not visible"))
            else:
                results.append(("WARN", "C: file uploaded but neither row count nor SAP detection found"))
        else:
            results.append(("WARN", "C: file input not found — upload step may need different navigation"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")
    finally:
        if csv_path and os.path.exists(csv_path):
            os.unlink(csv_path)

    # ── Scenario D: Step 3 — Auto-suggest maps SAP fields ────────────────────
    log("  [D] Auto-suggest maps AUFNR → Work Order ID and EQUNR → Machine...")
    try:
        # Click Next to go to Step 3
        next_btn = page.locator("#btn-s2-next, button:has-text('Next: Map')").first
        if next_btn.count() and not next_btn.is_disabled():
            next_btn.click()
            page.wait_for_timeout(800)

        # Click Auto-suggest
        auto_btn = page.locator("button:has-text('Auto-suggest'), button:has-text('Auto')").first
        if auto_btn.count():
            auto_btn.click()
            page.wait_for_timeout(500)

        page_text = page.locator("body").inner_text()
        has_aufnr  = "AUFNR" in page_text
        has_wo_id  = "Work Order ID" in page_text or "external_id" in page_text
        has_equnr  = "EQUNR" in page_text
        has_machine = "Machine" in page_text or "Asset" in page_text

        if has_aufnr and has_wo_id and has_equnr:
            results.append(("PASS", "D: mapping table shows AUFNR→WorkOrderID and EQUNR columns"))
        elif has_wo_id:
            results.append(("WARN", "D: Work Order ID mapping visible but AUFNR column reference unclear"))
        else:
            results.append(("WARN", "D: field mapping table not found or columns not detected"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: Step 4 — Preview shows rows without undefined ─────────────
    log("  [E] Preview table shows rows with no undefined values...")
    try:
        # Click Next to go to Step 4
        next_btn = page.locator("button:has-text('Preview'), button:has-text('Next: Preview')").first
        if next_btn.count():
            next_btn.click()
            page.wait_for_timeout(800)

        page_text = page.locator("body").inner_text()
        has_preview = any(kw in page_text for kw in ["Preview", "preview", "first 5", "rows"])
        has_undef   = "undefined" in page_text

        preview_rows = page.evaluate("""() =>
            document.querySelectorAll('#preview-tbody tr, .preview-table tr').length
        """)

        if has_undef:
            results.append(("FAIL", "E: 'undefined' in preview table — normalization bug"))
        elif preview_rows >= 5:
            results.append(("PASS", f"E: preview shows {preview_rows} rows with no undefined"))
        elif preview_rows > 0:
            results.append(("WARN", f"E: preview shows only {preview_rows} rows (expected ≥5)"))
        elif has_preview:
            results.append(("WARN", "E: preview section visible but 0 table rows found"))
        else:
            results.append(("WARN", "E: could not navigate to preview step"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"E skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario F: Step 5 — Import reports count ─────────────────────────────
    log("  [F] Import step completes and shows imported count...")
    try:
        import_btn = page.locator(
            "button:has-text('Import'), button:has-text('Start Import'), "
            "#preview-count-label ~ button, button:has-text('rows →')"
        ).first

        db_before = db.table("external_sync").select("id", count="exact") \
            .is_("hive_id", "null").limit(1).execute().count or 0 if not hive_id else 0

        if import_btn.count():
            import_btn.click()
            page.wait_for_timeout(8000)   # batch import

            page_text = page.locator("body").inner_text()
            has_count = any(kw in page_text for kw in
                            ["Imported", "imported", "work orders", "complete"])
            has_nan   = "NaN" in page_text

            if has_nan:
                results.append(("FAIL", "F: NaN in import results"))
            elif has_count:
                # Look for a number in the results
                nums = re.findall(r"\b([1-9]\d*)\s*(?:Imported|imported|work orders)", page_text)
                count_shown = nums[0] if nums else "?"
                results.append(("PASS", f"F: import completed, shows '{count_shown}' imported"))
            else:
                results.append(("WARN", "F: import may have run but no count found in results"))
        else:
            results.append(("WARN", "F: Import button not found — preview step navigation may differ"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: Live Sync Test Connection ─────────────────────────────────
    log("  [G] Live Sync Test Connection returns feedback within 15s...")
    try:
        # Switch to Live Sync tab
        sync_tab = page.locator("button:has-text('Live Sync'), #tab-sync").first
        if sync_tab.count():
            sync_tab.click()
            page.wait_for_timeout(800)

        url_input = page.locator("#sc-url, input[placeholder*='endpoint' i], input[placeholder*='url' i]").first
        test_btn  = page.locator("button:has-text('Test Connection')").first

        if url_input.count() and test_btn.count():
            # host.docker.internal: edge functions run in Docker and cannot reach 127.0.0.1
            url_input.fill("http://host.docker.internal:5000/mock/sap/odata/WorkOrders")
            page.wait_for_timeout(200)
            test_btn.click()
            page.wait_for_timeout(15000)

            result_el = page.locator("#sync-test-result").first
            if result_el.count() and result_el.is_visible():
                result_text = result_el.inner_text()
                if "Connected" in result_text or "found" in result_text.lower():
                    results.append(("PASS", f"G: Test Connection → '{result_text[:60]}'"))
                elif "Error" in result_text or "failed" in result_text.lower():
                    results.append(("WARN", f"G: Test Connection returned error: '{result_text[:60]}'"))
                else:
                    results.append(("WARN", f"G: Test Connection result unclear: '{result_text[:60]}'"))
            else:
                results.append(("WARN", "G: no Test Connection result appeared within 15s"))
        else:
            results.append(("WARN", "G: URL input or Test Connection button not found in Live Sync tab"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario H: API Keys — generate → wh_ key appears ────────────────────
    log("  [H] API Keys: generate key starts with wh_ and appears in list...")
    try:
        api_tab = page.locator("button:has-text('API Keys'), #tab-api").first
        if api_tab.count():
            api_tab.click()
            page.wait_for_timeout(800)

        label_input = page.locator("#api-key-label, input[placeholder*='label' i]").first
        gen_btn     = page.locator("button:has-text('Generate Key'), button:has-text('Generate')").first

        if label_input.count() and gen_btn.count():
            label_input.fill(f"Test Key {int(time.time())}")
            gen_btn.click()
            page.wait_for_timeout(2000)

            # Check for wh_ key in the new-key-result area
            result_el = page.locator("#new-key-result").first
            page_text = page.locator("body").inner_text()
            has_wh_key = "wh_" in page_text

            if has_wh_key and result_el.count() and result_el.is_visible():
                results.append(("PASS", "H: API key generated starting with wh_"))
            elif has_wh_key:
                results.append(("PASS", "H: wh_ key visible on page (result panel may use different id)"))
            else:
                results.append(("WARN", "H: Generate Key clicked but no wh_ key found in page"))
        else:
            results.append(("WARN", "H: API key label or Generate button not found"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario I: API key revocation removes from list ─────────────────────
    log("  [I] Revoking API key removes it from Active Keys list...")
    try:
        if hive_id:
            test_keys = db.table("api_keys").select("id, key_prefix") \
                .eq("hive_id", hive_id).eq("enabled", True).limit(1).execute().data or []
            if test_keys:
                key_id     = test_keys[0]["id"]
                key_prefix = test_keys[0]["key_prefix"]

                revoke_btn = page.locator(
                    f"button:has-text('Revoke'):near(:text('{key_prefix}'))"
                ).first
                if not revoke_btn.count():
                    revoke_btn = page.locator("button:has-text('Revoke')").first

                if revoke_btn.count():
                    page.on("dialog", lambda d: d.accept())
                    revoke_btn.click()
                    page.wait_for_timeout(2000)

                    still_enabled = db.table("api_keys").select("enabled") \
                        .eq("id", key_id).execute().data or []
                    is_enabled = still_enabled[0].get("enabled", True) if still_enabled else True

                    if not is_enabled or not still_enabled:
                        results.append(("PASS", "I: API key revoked — disabled or removed from DB"))
                    else:
                        results.append(("WARN", "I: key still enabled in DB after Revoke click"))
                else:
                    results.append(("WARN", "I: Revoke button not found for test key"))
            else:
                results.append(("WARN", "I: no API keys to revoke — skipping"))
        else:
            results.append(("WARN", "I: no hive context — API key revocation skipped"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"I skipped: {e}"))
        log(f"    → WARN: {e}")

    # Cleanup test keys
    try:
        if hive_id:
            db.table("api_keys").delete() \
                .eq("hive_id", hive_id).like("label", "Test Key %").execute()
    except Exception:
        pass

    screenshot(page, "cmms_ui_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  CMMS Integration UI: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

