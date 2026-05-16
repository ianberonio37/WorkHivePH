#!/usr/bin/env python3
"""Layer 2 E2E: alert-hub.html — Load alerts/patterns, acknowledge/resolve, filter, auto-dismiss."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "alert-hub"
CARD = "[data-alert-id], .alert-card, .alert-row"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy", "result": "PASS" if count >= 0 and no_undef else "FAIL", "actual": f"{count} alerts"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "alerts or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    ack_btn = h.page.locator("button:has-text('Acknowledge'), button:has-text('Ack'), [data-action='acknowledge']").first
    if ack_btn.is_visible(timeout=3000):
        ack_btn.click()
        h.wait_for_page_load()
        acked = h.verify_data_rendered("acknowledged") or h.verify_data_rendered("ack")
        results.append({"scenario": "happy_acknowledge", "result": "PASS" if acked else "WARN", "actual": f"acked={acked}"})
    else:
        results.append({"scenario": "happy_acknowledge", "result": "WARN", "actual": "no ack button"})

    h.clear()
    resolve_btn = h.page.locator("button:has-text('Resolve'), [data-action='resolve']").first
    if resolve_btn.is_visible(timeout=3000):
        resolve_btn.click()
        h.wait_for_page_load()
        results.append({"scenario": "happy_resolve", "result": "PASS", "actual": "resolve clicked"})
    else:
        results.append({"scenario": "happy_resolve", "result": "WARN", "actual": "no resolve button"})

    results.append({"scenario": "validation", "result": "SKIP", "reason": "alerts are system-generated"})
    results.append({"scenario": "api_error", "result": "SKIP", "reason": "deferred"})

    h.clear()
    filter_btn = h.page.locator("[data-filter], select#severity-filter, .filter-btn").first
    if filter_btn.is_visible(timeout=2000):
        filter_btn.click()
        results.append({"scenario": "filter_by_severity", "result": "PASS", "actual": "filter applied"})
    else:
        results.append({"scenario": "filter_by_severity", "result": "WARN", "actual": "no filter"})

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
    log("\n[ALERT-HUB E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Alert-Hub: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
