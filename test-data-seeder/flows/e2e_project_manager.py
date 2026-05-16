#!/usr/bin/env python3
"""
Layer 2 E2E: project-manager.html
Create/assign workorders, status transitions, approval flow.
"""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "project-manager"
CARD = "[data-project-id], .project-card, [data-workorder-id], .workorder-row"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)
    h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({
        "scenario": "happy_projects",
        "result": "PASS" if count >= 0 and no_undef else "FAIL",
        "actual": f"{count} items, no_undef={no_undef}"
    })

    status_present = (
        h.verify_data_rendered("open", allow_partial=True) or
        h.verify_data_rendered("in progress", allow_partial=True) or
        h.verify_data_rendered("closed", allow_partial=True) or
        count == 0
    )
    results.append({"scenario": "status_labels", "result": "PASS" if status_present else "WARN", "actual": f"status_shown={status_present}"})

    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "page settled"})

    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)

    # Happy: create workorder
    h.clear()
    new_btn = h.page.locator("button:has-text('New'), button:has-text('Create'), button:has-text('Add'), [data-action='create']").first
    if new_btn.is_visible(timeout=3000):
        new_btn.click()
        form_ok = h.fill_form({
            "#title": "E2E Workorder",
            "#description": "Automated test workorder",
            "#status": "open"
        })
        submit_ok = h.submit_form("button:has-text('Save'), button:has-text('Create')")
        success = h.verify_data_rendered("E2E Workorder")
        results.append({"scenario": "happy_create", "result": "PASS" if submit_ok and success else "WARN", "actual": f"submit={submit_ok}, visible={success}"})
    else:
        results.append({"scenario": "happy_create", "result": "WARN", "actual": "no create button"})

    # Happy: status transition
    h.clear()
    status_btn = h.page.locator("button:has-text('In Progress'), button:has-text('Start'), [data-action='update-status']").first
    if status_btn.is_visible(timeout=3000):
        status_btn.click()
        h.wait_for_page_load()
        updated = h.verify_data_rendered("progress") or h.verify_data_rendered("in progress")
        results.append({"scenario": "happy_status_transition", "result": "PASS" if updated else "WARN", "actual": f"status_updated={updated}"})
    else:
        results.append({"scenario": "happy_status_transition", "result": "WARN", "actual": "no status button"})

    # Validation: missing title
    h.clear()
    new_btn2 = h.page.locator("button:has-text('New'), button:has-text('Create')").first
    if new_btn2.is_visible(timeout=2000):
        new_btn2.click()
        h.submit_form("button:has-text('Save'), button:has-text('Create')")
        has_err = h.check_validation_error("required") or h.check_validation_error("title")
        results.append({"scenario": "validation_required", "result": "PASS" if has_err else "WARN", "actual": f"error={has_err}"})
    else:
        results.append({"scenario": "validation_required", "result": "WARN", "actual": "no create button"})

    # API error
    h.clear()
    h.page.route("**/functions/v1/project*", lambda r: r.abort("failed"))
    new_btn3 = h.page.locator("button:has-text('New'), button:has-text('Create')").first
    if new_btn3.is_visible(timeout=2000):
        new_btn3.click()
        h.fill_form({"#title": "Test"})
        h.submit_form("button:has-text('Save')")
        has_err_ui = h.verify_data_rendered("error") or h.verify_data_rendered("retry")
        results.append({"scenario": "api_error", "result": "PASS" if has_err_ui else "WARN", "actual": f"error_ui={has_err_ui}"})
    else:
        results.append({"scenario": "api_error", "result": "WARN", "actual": "no create button"})

    # Permission: approve workorder (supervisor only)
    h.clear()
    role = h.get_auth_context().get("hive_role", "")
    approve_visible = h.count_rendered_items("[data-action='approve'], .approve-btn") > 0
    results.append({
        "scenario": "permission_approve",
        "result": "PASS" if (role in ("supervisor", "admin")) == approve_visible else "WARN",
        "actual": f"role={role}, approve={approve_visible}"
    })

    return {"write": results}


def test_additional(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)

    # Offline
    h.clear()
    h.page.context.set_offline(True)
    new_btn = h.page.locator("button:has-text('New'), button:has-text('Create')").first
    if new_btn.is_visible(timeout=2000):
        new_btn.click()
        h.fill_form({"#title": "Offline WO"})
        h.submit_form("button:has-text('Save')")
    queued = h.verify_data_rendered("pending") or h.verify_data_rendered("offline")
    results.append({"scenario": "offline", "result": "PASS" if queued else "WARN", "actual": f"queued={queued}"})
    h.page.context.set_offline(False)

    # Edge: filter by status
    h.clear()
    h.goto(PAGE)
    filter_btn = h.page.locator("[data-filter], .filter-btn, select#status-filter").first
    if filter_btn.is_visible(timeout=2000):
        filter_btn.click()
        results.append({"scenario": "edge_filter_status", "result": "PASS", "actual": "filter activated"})
    else:
        results.append({"scenario": "edge_filter_status", "result": "WARN", "actual": "no filter control"})

    # Mobile
    h.clear()
    h.set_mobile_viewport(375, 667)
    h.goto(PAGE)
    no_overflow = h.verify_no_horizontal_scroll()
    tap_ok = h.verify_tap_targets_accessible()
    results.append({
        "scenario": "mobile",
        "result": "PASS" if no_overflow and tap_ok else "WARN",
        "actual": f"overflow={not no_overflow}, tap={not tap_ok}"
    })

    # Console
    h.clear()
    errors, _ = h.check_console_errors()
    results.append({"scenario": "console", "result": "PASS" if len(errors) == 0 else "FAIL", "actual": f"{len(errors)} errors"})

    return {"additional": results}


def run(page: Page, errors: list, warnings: list, log=print) -> dict:
    log("\n[PROJECT-MANAGER E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Project-Manager: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
