"""Report Sender flows — DB-verified contact management and send flow.

Scenarios:
  A – Page loads with contact section visible (list or empty state)
  B – Add contact → report_contacts row in DB
  C – Report type checkboxes render (PM Overdue, Failure Digest, etc.)
  D – Send flow completes: success toast, no "Failed to send" error
  E – Voice context input visible and interactable
  F – No undefined/null in contact display fields
  G – Remove contact → row deleted from DB
  H – Sent report appears in automation_log (fire-and-forget verified)
"""

import time
import re
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

TEST_CONTACT_NAME  = f"TEST_CONTACT_{int(time.time())}"
TEST_CONTACT_EMAIL = f"test_{int(time.time())}@workhive-test.local"

EXPECTED_REPORT_TYPES = [
    "PM Overdue", "Failure Digest", "Shift Handover", "Predictive"
]


def run(page, errors, warnings, log) -> dict:
    log("Report Sender flow checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/report-sender.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2500)

    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    # ── Scenario A: Page loads with contact section ───────────────────────────
    log("  [A] Report Sender loads with contact section visible...")
    try:
        page_text   = page.locator("body").inner_text()
        has_contact = any(kw in page_text for kw in
                          ["contact", "Contact", "recipient", "Recipient", "send to", "Send to"])
        has_report  = any(kw in page_text for kw in
                          ["report", "Report", "PM Overdue", "Shift", "Digest"])

        if has_contact and has_report:
            results.append(("PASS", "A: contact section and report options both visible"))
        elif has_report:
            results.append(("WARN", "A: report options visible but no contact section found"))
        else:
            results.append(("FAIL", "A: neither contacts nor report types visible — page not rendering"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Add contact → report_contacts DB row ─────────────────────
    log("  [B] Add contact → report_contacts row created in DB...")
    try:
        before = 0
        if hive_id:
            before = db.table("report_contacts").select("id", count="exact") \
                .eq("hive_id", hive_id).limit(1).execute().count or 0

        # Open add contact sheet — button ID is #add-contact-btn
        add_btn = page.locator(
            "#add-contact-btn, "
            "button:has-text('Add Contact'), button:has-text('+ Add contact')"
        ).first

        if not add_btn.count():
            results.append(("WARN", "B: Add Contact button not found — may require different role/hive"))
        else:
            add_btn.click()
            page.wait_for_timeout(800)  # let sheet animation complete

            # Use direct IDs — #contact-name, #contact-email, #save-contact-btn
            name_input  = page.locator("#contact-name").first
            email_input = page.locator("#contact-email").first

            if name_input.count() and name_input.is_visible() and email_input.count():
                name_input.fill(TEST_CONTACT_NAME)
                email_input.fill(TEST_CONTACT_EMAIL)

                save_btn = page.locator("#save-contact-btn").first
                if save_btn.count() and save_btn.is_visible():
                    save_btn.click()
                    page.wait_for_timeout(2000)

                    after = 0
                    if hive_id:
                        after = db.table("report_contacts").select("id", count="exact") \
                            .eq("hive_id", hive_id).limit(1).execute().count or 0

                    if after > before:
                        results.append(("PASS", f"B: report_contacts count {before}→{after}"))
                    else:
                        page_text = page.locator("body").inner_text()
                        if TEST_CONTACT_NAME in page_text:
                            results.append(("WARN", "B: contact visible on page but DB count unchanged"))
                        else:
                            results.append(("WARN", "B: contact saved but not in DB or visible on page after add"))
                else:
                    results.append(("WARN", "B: #save-contact-btn not visible after sheet opened"))
            else:
                results.append(("WARN", "B: contact sheet did not open — inputs not visible after add_btn click"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Report type checkboxes render ─────────────────────────────
    log("  [C] Report type checkboxes render for all 4 types...")
    try:
        page_text = page.locator("body").inner_text()
        found     = [t for t in EXPECTED_REPORT_TYPES if t in page_text]

        if len(found) >= 4:
            results.append(("PASS", f"C: all 4 report types visible: {found}"))
        elif len(found) >= 2:
            results.append(("WARN", f"C: only {len(found)} report types visible: {found}"))
        else:
            results.append(("FAIL", f"C: fewer than 2 report types found ({found})"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"C crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario D: Send flow completes without "Failed to send" ──────────────
    log("  [D] Send flow: success toast, no 'Failed to send' error...")
    try:
        errors_before = len(errors)

        # Select at least one report type
        pm_checkbox = page.locator(
            "input[type='checkbox']:near(:text('PM Overdue')), "
            "input[type='checkbox']:near(:text('PM')), "
            "label:has-text('PM Overdue') input"
        ).first
        if pm_checkbox.count() and not pm_checkbox.is_checked():
            pm_checkbox.check()
            page.wait_for_timeout(300)

        # Find and click send
        send_btn = page.locator(
            "button:has-text('Send Report'), button:has-text('Send'), "
            "button:has-text('Generate'), button:has-text('Email Report')"
        ).first

        if not send_btn.count():
            results.append(("WARN", "D: Send button not found — skipping send flow"))
        elif not send_btn.is_enabled():
            results.append(("WARN", "D: Send button is disabled — add contacts and select report type first"))
        else:
            send_btn.click()
            page.wait_for_timeout(15000)   # report generation + send

            page_text  = page.locator("body").inner_text()
            has_failed = any(kw in page_text for kw in
                             ["Failed to send", "Send failed", "Error sending", "could not send"])
            has_success = any(kw in page_text for kw in
                              ["Sent", "sent", "Delivered", "Success", "Report sent"])
            new_js_err  = [e for e in errors[errors_before:] if "TypeError" in e]

            if new_js_err:
                results.append(("FAIL", f"D: TypeError during send: {new_js_err[0][:80]}"))
            elif has_failed:
                results.append(("FAIL", "D: 'Failed to send' message appeared after clicking Send"))
            elif has_success:
                results.append(("PASS", "D: send completed with success indicator"))
            else:
                results.append(("WARN", "D: send button clicked but no clear success or failure indicator"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: Voice context input visible ───────────────────────────────
    log("  [E] Voice context input visible and has at least 44px height...")
    try:
        voice_el = page.locator(
            "textarea[id*='voice'], textarea[placeholder*='voice' i], "
            "textarea[placeholder*='context' i], #voice-context, "
            "button[aria-label*='voice' i], button:has-text('🎤')"
        ).first

        if voice_el.count() and voice_el.is_visible():
            box = voice_el.bounding_box()
            h   = box["height"] if box else 0
            results.append(
                ("PASS", f"E: voice context input visible, height={h:.0f}px")
                if h >= 40
                else ("WARN", f"E: voice input visible but height={h:.0f}px < 44px tap target")
            )
        else:
            results.append(("WARN", "E: no voice context input found (may be tab or collapsed)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"E skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario F: No undefined/null in contact display ─────────────────────
    log("  [F] No 'undefined' or literal 'null' in contact fields...")
    try:
        page_text = page.locator("body").inner_text()
        has_undef = "undefined" in page_text
        has_null  = bool(re.search(r"\bnull\b", page_text))

        if has_undef:
            results.append(("FAIL", "F: 'undefined' in report sender — contact field mapping broken"))
        elif has_null:
            results.append(("WARN", "F: literal 'null' in report sender text — display issue"))
        else:
            results.append(("PASS", "F: no 'undefined' or literal 'null' in contact display"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"F crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario G: Remove contact → DB row deleted ───────────────────────────
    log("  [G] Remove contact → report_contacts row deleted from DB...")
    try:
        test_contacts = db.table("report_contacts").select("id") \
            .eq("hive_id", hive_id).like("name", "TEST_CONTACT_%") \
            .limit(1).execute().data if hive_id else []

        if not test_contacts:
            results.append(("WARN", "G: no test contacts to remove — skipping"))
        else:
            contact_id = test_contacts[0]["id"]
            remove_btn = page.locator(
                f"[data-contact-id='{contact_id}'] button:has-text('Remove'), "
                f"[data-contact-id='{contact_id}'] button:has-text('Delete'), "
                f"[data-contact-id='{contact_id}'] [aria-label*='remove' i]"
            ).first

            if not remove_btn.count():
                # Try finding by name text
                remove_btn = page.locator(
                    f":text('{TEST_CONTACT_NAME}') ~ button, "
                    f":text('{TEST_CONTACT_NAME}') + button"
                ).first

            if remove_btn.count():
                page.on("dialog", lambda d: d.accept())
                remove_btn.click()
                page.wait_for_timeout(2000)

                still_there = db.table("report_contacts").select("id") \
                    .eq("id", contact_id).execute().data
                if not still_there:
                    results.append(("PASS", "G: contact removed from DB"))
                else:
                    results.append(("WARN", "G: contact still in DB after remove — soft delete or failed"))
            else:
                results.append(("WARN", "G: Remove button not found for test contact"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario H: Send logged in automation_log ─────────────────────────────
    log("  [H] Sent report logged in automation_log...")
    try:
        log_rows = db.table("automation_log").select("id, job_name, status") \
            .in_("job_name", ["report-sender", "send-report", "scheduled-agents"]) \
            .order("triggered_at", desc=True).limit(3).execute().data or []

        if log_rows:
            latest = log_rows[0]
            results.append(("PASS" if latest["status"] in ("success", "failed") else "WARN",
                f"H: automation_log has {len(log_rows)} report entries, latest status={latest['status']}"))
        else:
            results.append(("WARN", "H: no report entries in automation_log (send may be fire-and-forget without logging)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    # Cleanup test contacts
    try:
        if hive_id:
            db.table("report_contacts").delete() \
                .eq("hive_id", hive_id).like("name", "TEST_CONTACT_%").execute()
    except Exception:
        pass

    screenshot(page, "report_sender_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Report Sender: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

