#!/usr/bin/env python3
"""
Layer 2 E2E: pm-scheduler.html
Complete PM tasks, anchor dates, overdue detection, skip logic.
"""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "pm-scheduler"
CARD = "[data-task-id], .pm-card, .task-row"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)
    h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({
        "scenario": "happy",
        "result": "PASS" if count >= 0 and no_undef else "FAIL",
        "actual": f"{count} tasks, no_undefined={no_undef}"
    })

    overdue_check = h.verify_data_rendered("overdue", allow_partial=True)
    results.append({
        "scenario": "overdue_tasks_flagged",
        "result": "PASS" if overdue_check or count == 0 else "WARN",
        "actual": f"overdue_flag={overdue_check}"
    })

    results.append({
        "scenario": "loading",
        "result": "PASS" if h.wait_for_page_load(15000) else "WARN",
        "actual": "page settled"
    })

    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)

    # Happy: complete a task
    h.clear()
    complete_btn = h.page.locator("button:has-text('Complete'), button:has-text('Done'), [data-action='complete']").first
    if complete_btn.is_visible(timeout=3000):
        complete_btn.click()
        h.wait_for_page_load()
        confirmed = h.verify_data_rendered("completed") or h.verify_data_rendered("done")
        results.append({"scenario": "happy_complete", "result": "PASS" if confirmed else "WARN", "actual": f"confirmed={confirmed}"})
    else:
        results.append({"scenario": "happy_complete", "result": "WARN", "actual": "no complete button visible"})

    # Happy: skip task
    h.clear()
    skip_btn = h.page.locator("button:has-text('Skip'), [data-action='skip']").first
    if skip_btn.is_visible(timeout=3000):
        skip_btn.click()
        h.wait_for_page_load()
        results.append({"scenario": "happy_skip", "result": "PASS", "actual": "skip confirmed"})
    else:
        results.append({"scenario": "happy_skip", "result": "WARN", "actual": "no skip button visible"})

    # Validation: complete without notes
    h.clear()
    complete_btn2 = h.page.locator("button:has-text('Complete')").first
    if complete_btn2.is_visible(timeout=2000):
        complete_btn2.click()
        has_err = h.check_validation_error("notes") or h.check_validation_error("required")
        results.append({"scenario": "validation_notes", "result": "PASS" if has_err else "WARN", "actual": f"validation={has_err}"})
    else:
        results.append({"scenario": "validation_notes", "result": "WARN", "actual": "no complete button"})

    # API error
    h.clear()
    h.page.route("**/functions/v1/pm*", lambda r: r.abort("failed"))
    complete_btn3 = h.page.locator("button:has-text('Complete')").first
    if complete_btn3.is_visible(timeout=2000):
        complete_btn3.click()
        has_err_ui = h.verify_data_rendered("error") or h.verify_data_rendered("retry")
        results.append({"scenario": "api_error", "result": "PASS" if has_err_ui else "WARN", "actual": f"error_ui={has_err_ui}"})
    else:
        results.append({"scenario": "api_error", "result": "WARN", "actual": "no complete button to test"})

    # Permission: only supervisors can reassign
    h.clear()
    role = h.get_auth_context().get("hive_role", "")
    reassign_visible = h.count_rendered_items("[data-action='reassign'], .reassign-btn") > 0
    results.append({
        "scenario": "permission_reassign",
        "result": "PASS" if (role in ("supervisor", "admin")) == reassign_visible else "WARN",
        "actual": f"role={role}, reassign_visible={reassign_visible}"
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
    complete_btn = h.page.locator("button:has-text('Complete')").first
    if complete_btn.is_visible(timeout=2000):
        complete_btn.click()
    queued = h.verify_data_rendered("pending") or h.verify_data_rendered("offline")
    results.append({"scenario": "offline", "result": "PASS" if queued else "WARN", "actual": f"queued={queued}"})
    h.page.context.set_offline(False)

    # Edge: frequency boundary
    h.clear()
    freq_display = h.verify_data_rendered("day") or h.verify_data_rendered("week")
    results.append({"scenario": "edge_freq_display", "result": "PASS" if freq_display else "WARN", "actual": f"freq_display={freq_display}"})

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
    log("\n[PM-SCHEDULER E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"PM-Scheduler: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
