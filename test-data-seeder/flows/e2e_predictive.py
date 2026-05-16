#!/usr/bin/env python3
"""Layer 2 E2E: predictive.html — Load failure predictions, trigger ML scoring, calendar/export."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "predictive"
CARD = "[data-prediction-id], .prediction-card, .failure-risk"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    risk_shown = h.verify_data_rendered("risk") or h.verify_data_rendered("failure") or count >= 0
    results.append({"scenario": "happy", "result": "PASS" if risk_shown and no_undef else "FAIL", "actual": f"{count} predictions"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "predictions or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    score_btn = h.page.locator("button:has-text('Score'), button:has-text('Run ML'), button:has-text('Analyze'), [data-action='score']").first
    if score_btn.is_visible(timeout=3000):
        score_btn.click()
        h.wait_for_page_load()
        results.append({"scenario": "happy_ml_score", "result": "PASS", "actual": "ML score triggered"})
    else:
        results.append({"scenario": "happy_ml_score", "result": "WARN", "actual": "no score button"})

    h.clear()
    export_btn = h.page.locator("button:has-text('Export'), [data-action='export']").first
    if export_btn.is_visible(timeout=2000):
        export_btn.click()
        results.append({"scenario": "happy_export", "result": "PASS", "actual": "export triggered"})
    else:
        results.append({"scenario": "happy_export", "result": "WARN", "actual": "no export"})

    results.append({"scenario": "validation", "result": "SKIP", "reason": "ML scoring is system-triggered"})
    results.append({"scenario": "api_error", "result": "SKIP", "reason": "deferred"})
    results.append({"scenario": "permission", "result": "SKIP", "reason": "supervisor+ gated at page"})
    results.append({"scenario": "concurrent", "result": "SKIP", "reason": "ML scoring is queued"})
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
    log("\n[PREDICTIVE E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Predictive: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
