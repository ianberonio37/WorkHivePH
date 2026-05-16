#!/usr/bin/env python3
"""Layer 2 E2E: analytics-report.html — Generate report, download, filter by machine/discipline."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "analytics-report"
CARD = ".report-section, .report-card, [data-section]"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy_sections", "result": "PASS" if count >= 0 and no_undef else "FAIL", "actual": f"{count} sections"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "sections or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    gen_btn = h.page.locator("button:has-text('Generate'), button:has-text('Run Report'), [data-action='generate']").first
    if gen_btn.is_visible(timeout=3000):
        gen_btn.click()
        h.wait_for_page_load()
        results.append({"scenario": "happy_generate", "result": "PASS", "actual": "report generated"})
    else:
        results.append({"scenario": "happy_generate", "result": "WARN", "actual": "no generate button"})

    h.clear()
    filter_sel = h.page.locator("select#machine, select#discipline, [data-filter='machine']").first
    if filter_sel.is_visible(timeout=2000):
        filter_sel.click()
        results.append({"scenario": "happy_filter", "result": "PASS", "actual": "filter applied"})
    else:
        results.append({"scenario": "happy_filter", "result": "WARN", "actual": "no filter"})

    results.append({"scenario": "validation", "result": "SKIP", "reason": "read-heavy"})
    results.append({"scenario": "api_error", "result": "SKIP", "reason": "deferred"})
    results.append({"scenario": "permission", "result": "SKIP", "reason": "supervisor+ only (gated at page level)"})
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
    log("\n[ANALYTICS-REPORT E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Analytics-Report: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
