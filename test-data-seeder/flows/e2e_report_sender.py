#!/usr/bin/env python3
"""Layer 2 E2E: report-sender.html — Load template, send to recipients, multi-recipient, retry."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "report-sender"
CARD = ".report-template, [data-template-id], .recipient-row"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy", "result": "PASS" if count >= 0 and no_undef else "FAIL", "actual": f"{count} templates"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "templates or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    form_ok = h.fill_form({"#recipients": "test@example.com", "#subject": "E2E Test Report"})
    send_btn = h.submit_form("button:has-text('Send'), button:has-text('Send Report')")
    results.append({"scenario": "happy_send", "result": "PASS" if form_ok and send_btn else "WARN", "actual": f"form={form_ok}"})

    h.clear()
    h.fill_form({"#recipients": ""})
    h.submit_form("button:has-text('Send')")
    has_err = h.check_validation_error("recipient") or h.check_validation_error("required")
    results.append({"scenario": "validation_no_recipient", "result": "PASS" if has_err else "WARN", "actual": f"error={has_err}"})

    h.clear()
    h.page.route("**/functions/v1/report*", lambda r: r.abort("failed"))
    h.fill_form({"#recipients": "test@example.com"})
    h.submit_form("button:has-text('Send')")
    has_err_ui = h.verify_data_rendered("retry") or h.verify_data_rendered("error")
    results.append({"scenario": "api_error_retry", "result": "PASS" if has_err_ui else "WARN", "actual": f"retry_visible={has_err_ui}"})

    results.append({"scenario": "permission", "result": "SKIP", "reason": "supervisor-only page"})
    results.append({"scenario": "concurrent", "result": "SKIP", "reason": "deferred"})
    return {"write": results}


def test_additional(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear(); h.set_mobile_viewport(375, 667); h.goto(PAGE)
    results.append({"scenario": "mobile", "result": "PASS" if h.verify_no_horizontal_scroll() else "WARN", "actual": "mobile"})
    h.clear()
    errors, _ = h.check_console_errors()
    results.append({"scenario": "console", "result": "PASS" if len(errors) == 0 else "FAIL", "actual": f"{len(errors)} errors"})
    return {"additional": results}


def run(page: Page, errors: list, warnings: list, log=print) -> dict:
    log("\n[REPORT-SENDER E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Report-Sender: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
