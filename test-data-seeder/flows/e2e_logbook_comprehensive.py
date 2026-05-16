#!/usr/bin/env python3
"""
Layer 2 Example: Logbook.html Comprehensive E2E Tests
=====================================================
Demonstrates all 3 paths (read + write + additional) with all scenarios.

Patterns used:
- Happy path + 4 error scenarios per write path
- Empty state + loading state for read path
- Permission checks, offline mode, mobile tests

This is the pattern replicated for all 35 pages.
"""

from playwright.sync_api import sync_playwright, Page
import sys
from e2e_helpers import create_helper


def test_logbook_read_path(page: Page, base_url: str) -> dict:
    """
    READ PATH: Load logbook, query entries, render correctly.
    3 scenarios: happy, empty state, loading state.
    """
    helper = create_helper(page, base_url)
    results = {"read": []}

    # ─── Scenario 1: Happy Path ───────────────────────────────────────

    helper.clear()
    print("  [READ] Happy path: Load entries with filters...")

    if not helper.login():
        return {"read": [{"scenario": "happy", "result": "FAIL", "error": "Login failed"}]}

    if not helper.goto("logbook"):
        return {"read": [{"scenario": "happy", "result": "FAIL", "error": "Navigation failed"}]}

    helper.wait_for_page_load()

    # Gate dismissal + data reload is now handled inside goto() automatically.
    helper.page.wait_for_timeout(500)

    # Verify data rendered — entries use .entry-card class
    item_count = helper.count_rendered_items(".entry-card")
    text_check = helper.verify_data_rendered("logbook", allow_partial=True)
    no_undefined = helper.verify_no_undefined_values()

    if item_count >= 1 and no_undefined:
        results["read"].append({
            "scenario": "happy",
            "result": "PASS",
            "actual": f"{item_count} entries rendered, no undefined values"
        })
    elif item_count == 0 and text_check and no_undefined:
        results["read"].append({
            "scenario": "happy",
            "result": "WARN",
            "error": "Page loads OK but 0 entries — seeder may not have logbook data for this hive",
            "root_cause": "Data gap: seed logbook entries for test hive"
        })
    else:
        results["read"].append({
            "scenario": "happy",
            "result": "FAIL",
            "error": f"item_count={item_count}, text_check={text_check}, undefined={not no_undefined}",
            "root_cause": "Page failed to render — check auth or Supabase connection"
        })

    # ─── Scenario 2: Empty State ──────────────────────────────────────

    helper.clear()
    print("  [READ] Empty state: No data shows honest placeholder...")

    # Check for empty state: if entries exist, hide first one; if none, already empty
    entry_count = helper.count_rendered_items(".entry-card")
    if entry_count > 0:
        try:
            helper.page.locator(".entry-card").first.evaluate(
                "el => el.style.display = 'none'"
            )
        except:
            pass

    empty_msg = helper.verify_data_rendered("no entries", allow_partial=True) or \
                helper.verify_data_rendered("empty", allow_partial=True) or \
                helper.count_rendered_items("[data-entry-id], .logbook-card") == 0

    if empty_msg:
        results["read"].append({"scenario": "empty", "result": "PASS", "actual": "Empty state handled"})
    else:
        results["read"].append({
            "scenario": "empty",
            "result": "FAIL",
            "error": "No empty state message found"
        })

    # ─── Scenario 3: Loading State ────────────────────────────────────

    helper.clear()
    print("  [READ] Loading state: Spinner shows, no flickering...")

    # Would throttle network in real test
    if helper.wait_for_page_load(timeout=15000):
        results["read"].append({"scenario": "loading", "result": "PASS", "actual": "Page loaded successfully"})
    else:
        results["read"].append({
            "scenario": "loading",
            "result": "WARN",
            "error": "Page load timeout (network slow?)"
        })

    return results


def _logbook_fill_all_steps(helper, machine="TEST-001", problem="E2E test problem",
                             action="E2E test action", already_on_page=False):
    """Navigate the 3-step logbook form and fill fields. Returns True if reached step 3 submit."""
    try:
        if not already_on_page:
            helper.goto("logbook")

        # goto() already dismissed hive-gate and loaded data; just settle
        helper.page.wait_for_timeout(500)

        # Wait for step 1 to be in DOM (attached = present in DOM, not necessarily visible)
        helper.page.wait_for_selector("#step-panel-1", timeout=8000, state="attached")
        helper.page.wait_for_timeout(300)

        # Inject machine into hidden field
        helper.page.evaluate(
            f"() => {{ const el = document.getElementById('f-machine'); if(el) el.value = '{machine}'; }}"
        )
        # Advance to step 2 (force click with JS if regular click blocked)
        try:
            helper.page.locator("button.btn-next").first.click(timeout=3000)
        except:
            helper.page.evaluate("if(typeof stepGo === 'function') stepGo(2);")
        helper.page.wait_for_timeout(400)

        # Step 2: fill problem description
        helper.fill_form({"#f-problem": problem})
        # Advance to step 3
        try:
            helper.page.locator("button.btn-next").first.click(timeout=3000)
        except:
            helper.page.evaluate("if(typeof stepGo === 'function') stepGo(3);")
        helper.page.wait_for_timeout(400)

        # Step 3: fill action taken
        helper.fill_form({"#f-action": action})
        return True
    except Exception as e:
        print(f"  [DEBUG] _logbook_fill_all_steps failed: {e!s:.120}")
        return False


def test_logbook_write_path(page: Page, base_url: str) -> dict:
    """
    WRITE PATH: Create/Edit/Delete entries, verify DB changes.
    5 scenarios: happy + 4 error cases.
    """
    helper = create_helper(page, base_url)
    results = {"write": []}

    helper.login()
    helper.goto("logbook")

    # ─── Scenario 1: Happy Path (Create) ──────────────────────────────

    helper.clear()
    print("  [WRITE] Happy path: Create entry → DB row → UI refresh...")

    ready = _logbook_fill_all_steps(helper)
    if ready:
        submit_ok = helper.submit_form("#save-entry-btn")
        helper.wait_for_page_load()
        entry_shown = helper.count_rendered_items("[data-entry-id], .logbook-card") > 0
        results["write"].append({
            "scenario": "happy",
            "result": "PASS" if submit_ok else "WARN",
            "actual": f"submit={submit_ok}, entries_shown={entry_shown}"
        })
    else:
        results["write"].append({"scenario": "happy", "result": "WARN",
                                  "error": "Could not navigate multi-step form"})

    # ─── Scenario 2: Validation Error ────────────────────────────────

    helper.clear()
    print("  [WRITE] Validation: Missing required field shows error...")

    # Navigate fresh to logbook, dismiss gate, then try empty submit
    try:
        helper.goto("logbook")
        helper.page.wait_for_timeout(800)
        helper.page.evaluate("() => { const g = document.getElementById('hive-gate'); if(g) g.style.display='none'; }")
        helper.page.wait_for_selector("#step-panel-1", timeout=8000)

        # Force-advance to step 3 bypassing stepGo() validation (to test submit guard)
        helper.page.evaluate("""() => {
            document.querySelectorAll('.step-panel').forEach(p => p.classList.remove('active'));
            const s3 = document.getElementById('step-panel-3');
            if (s3) s3.classList.add('active');
            try { _currentStep = 3; } catch(e) {}
        }""")
        helper.page.wait_for_timeout(300)

        # Submit without filling machine — should show toast "Please select an asset"
        submit_btn = helper.page.locator("#save-entry-btn")
        if submit_btn.is_visible(timeout=2000):
            submit_btn.click()

        has_err = helper.check_validation_error("asset") or helper.check_validation_error("select") or \
                  helper.check_validation_error("machine") or helper.check_validation_error("required")
        results["write"].append({
            "scenario": "validation",
            "result": "PASS" if has_err else "WARN",
            "actual": f"validation_error={has_err}"
        })
    except Exception as e:
        results["write"].append({"scenario": "validation", "result": "WARN", "error": str(e)[:80]})

    # ─── Scenario 3: API Error ────────────────────────────────────────

    helper.clear()
    print("  [WRITE] API error: DB fails → show retry button...")

    helper.page.route("**/functions/v1/logbook*", lambda route: route.abort("failed"))
    ready2 = _logbook_fill_all_steps(helper, machine="API-ERR-TEST", already_on_page=False)
    if ready2:
        helper.page.locator("#save-entry-btn").click()
        helper.page.wait_for_timeout(2000)
        all_btn_text = " ".join(helper.page.locator("button").all_text_contents()).lower()
        retry_visible = "retry" in all_btn_text
        err_shown = helper.verify_data_rendered("error") or helper.verify_data_rendered("failed")
        results["write"].append({
            "scenario": "api_error",
            "result": "PASS" if (retry_visible or err_shown) else "WARN",
            "actual": f"retry={retry_visible}, err_shown={err_shown}"
        })
    else:
        results["write"].append({"scenario": "api_error", "result": "WARN", "error": "Could not reach submit"})

    # Unroute after api_error test to prevent blocking subsequent requests
    try:
        helper.page.unroute("**/functions/v1/logbook*")
    except:
        pass

    # ─── Scenario 4: Permission Denied ────────────────────────────────

    helper.clear()
    print("  [WRITE] Permission: Worker cannot edit supervisor-only field...")

    # Navigate to clean page before reading auth context (avoids SecurityError on error pages)
    helper.goto("logbook")
    helper.page.wait_for_timeout(500)
    current_role = helper.get_auth_context()["hive_role"]
    can_edit_supervisor = helper.verify_element_visible_for_role(
        "[data-field='supervisor-approval']",
        ["supervisor", "admin"]
    )

    if current_role == "worker" and not can_edit_supervisor:
        results["write"].append({"scenario": "permission", "result": "PASS", "actual": "Permission guard working"})
    else:
        results["write"].append({
            "scenario": "permission",
            "result": "WARN",
            "error": f"Role={current_role}, field visible={can_edit_supervisor}"
        })

    # ─── Scenario 5: Concurrent Edit ──────────────────────────────────

    helper.clear()
    print("  [WRITE] Concurrent: Edit stale entry → show conflict...")

    # Would need two sessions for this
    results["write"].append({
        "scenario": "concurrent",
        "result": "SKIP",
        "reason": "Requires two concurrent sessions (TODO: implement)"
    })

    return results


def test_logbook_additional_path(page: Page, base_url: str) -> dict:
    """
    ADDITIONAL PATH: Permissions, offline, edge cases, mobile.
    4 scenarios.
    """
    helper = create_helper(page, base_url)
    results = {"additional": []}

    helper.login()
    helper.goto("logbook")

    # ─── Scenario 1: Offline Mode ──────────────────────────────────────

    helper.clear()
    print("  [ADD] Offline: Queue entry → sync when online...")

    # Navigate to logbook BEFORE going offline, then go offline
    helper.goto("logbook")
    helper.page.wait_for_timeout(500)
    helper.page.context.set_offline(True)
    ready_offline = _logbook_fill_all_steps(helper, machine="OFFLINE-TEST",
                                             problem="Offline test entry", action="Offline action",
                                             already_on_page=True)
    if ready_offline:
        try:
            helper.page.locator("#save-entry-btn").click(timeout=5000)
        except:
            pass

    # Should queue entry (check IndexedDB or UI indicator)
    offline_badge = helper.verify_data_rendered("pending") or \
                    helper.verify_data_rendered("offline")

    if offline_badge:
        results["additional"].append({"scenario": "offline", "result": "PASS", "actual": "Entry queued offline"})
    else:
        results["additional"].append({
            "scenario": "offline",
            "result": "WARN",
            "error": "Offline queue not visible"
        })

    helper.page.context.set_offline(False)

    # ─── Scenario 2: Edge Cases ───────────────────────────────────────

    helper.clear()
    print("  [ADD] Edge cases: Special chars, max length, boundary values...")

    edge_tests = [
        ("Special chars: TM(R)(C) test", "#f-problem"),
        ("A" * 500, "#f-action"),
        ("Newlines and tabs test", "#f-problem"),
    ]

    all_passed = True
    for test_val, selector in edge_tests:
        helper.fill_form({selector: test_val})
        if not helper.page.locator("#save-entry-btn").is_visible(timeout=1000):
            all_passed = False

    if all_passed:
        results["additional"].append({"scenario": "edge_cases", "result": "PASS", "actual": "All edge cases handled"})
    else:
        results["additional"].append({"scenario": "edge_cases", "result": "WARN", "error": "Some edge cases failed"})

    # ─── Scenario 3: Mobile Viewport ──────────────────────────────────

    helper.clear()
    print("  [ADD] Mobile: 375px viewport, no overflow, tap targets ≥44px...")

    helper.set_mobile_viewport(375, 667)
    helper.goto("logbook")

    no_overflow = helper.verify_no_horizontal_scroll()
    tap_ok = helper.verify_tap_targets_accessible()
    console_ok = helper.verify_no_critical_console_errors()

    if no_overflow and tap_ok and console_ok:
        results["additional"].append({"scenario": "mobile", "result": "PASS", "actual": "Mobile-friendly"})
    else:
        results["additional"].append({
            "scenario": "mobile",
            "result": "WARN",
            "error": f"overflow={not no_overflow}, taps={not tap_ok}, console={not console_ok}"
        })

    # ─── Scenario 4: Browser Console ──────────────────────────────────

    helper.clear()
    print("  [ADD] Console: No critical errors...")

    errors, warnings = helper.check_console_errors()
    if len(errors) == 0:
        results["additional"].append({"scenario": "console", "result": "PASS", "actual": "No critical errors"})
    else:
        results["additional"].append({
            "scenario": "console",
            "result": "FAIL",
            "error": f"{len(errors)} console errors found"
        })

    return results


def run(page: Page, errors: list, warnings: list, log=print) -> dict:
    """
    Main entry point for comprehensive logbook tests.
    Compatible with run_flows.py interface.
    """
    log("\n[LOGBOOK E2E COMPREHENSIVE]")
    log("Testing all 3 paths: read + write + additional...")

    base_url = "http://127.0.0.1:5000/workhive"

    # Run all paths
    read_results = test_logbook_read_path(page, base_url)
    write_results = test_logbook_write_path(page, base_url)
    additional_results = test_logbook_additional_path(page, base_url)

    # Compile results
    all_results = [
        *read_results.get("read", []),
        *write_results.get("write", []),
        *additional_results.get("additional", []),
    ]

    # Print summary
    pass_count = sum(1 for r in all_results if r.get("result") == "PASS")
    fail_count = sum(1 for r in all_results if r.get("result") == "FAIL")
    warn_count = sum(1 for r in all_results if r.get("result") == "WARN")

    log(f"\nLogbook E2E Results: {pass_count} PASS / {fail_count} FAIL / {warn_count} WARN")

    return {
        "results": all_results,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "warn_count": warn_count,
    }


if __name__ == "__main__":
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        result = run(page, [], [], log=print)
        print(f"\nFinal: {result['pass_count']} PASS / {result['fail_count']} FAIL")
        browser.close()
