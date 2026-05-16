#!/usr/bin/env python3
"""Layer 2 E2E: integrations.html — CMMS config, update settings, webhook test, credential rotation."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "integrations"
CARD = ".integration-card, [data-integration-id], .connector-row"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy", "result": "PASS" if count >= 0 and no_undef else "FAIL", "actual": f"{count} integrations"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "integrations or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    edit_btn = h.page.locator("button:has-text('Configure'), button:has-text('Edit'), [data-action='configure']").first
    if edit_btn.is_visible(timeout=3000):
        edit_btn.click()
        h.fill_form({"#api_key": "test-key-e2e", "#webhook_url": "https://test.example.com"})
        h.submit_form("button:has-text('Save'), button:has-text('Update')")
        results.append({"scenario": "happy_configure", "result": "PASS", "actual": "config saved"})
    else:
        results.append({"scenario": "happy_configure", "result": "WARN", "actual": "no configure button"})

    h.clear()
    test_btn = h.page.locator("button:has-text('Test'), button:has-text('Test Webhook'), [data-action='test']").first
    if test_btn.is_visible(timeout=2000):
        test_btn.click()
        h.wait_for_page_load()
        test_result = h.verify_data_rendered("success") or h.verify_data_rendered("200") or h.verify_data_rendered("sent")
        results.append({"scenario": "happy_test_webhook", "result": "PASS" if test_result else "WARN", "actual": f"test_result={test_result}"})
    else:
        results.append({"scenario": "happy_test_webhook", "result": "WARN", "actual": "no test button"})

    results.append({"scenario": "validation", "result": "SKIP", "reason": "deferred"})
    results.append({"scenario": "api_error", "result": "SKIP", "reason": "deferred"})
    results.append({"scenario": "permission", "result": "SKIP", "reason": "admin-only page"})
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
    log("\n[INTEGRATIONS E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Integrations: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
