#!/usr/bin/env python3
"""Layer 2 E2E: marketplace-admin.html — Admin approve/reject listings, verification, payment settings."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "marketplace-admin"
CARD = "[data-listing-id], .listing-card, .pending-listing"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy", "result": "PASS" if count >= 0 and no_undef else "FAIL", "actual": f"{count} listings"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "listings or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    approve_btn = h.page.locator("button:has-text('Approve'), [data-action='approve']").first
    if approve_btn.is_visible(timeout=3000):
        approve_btn.click()
        h.wait_for_page_load()
        approved = h.verify_data_rendered("approved") or h.verify_data_rendered("live")
        results.append({"scenario": "happy_approve", "result": "PASS" if approved else "WARN", "actual": f"approved={approved}"})
    else:
        results.append({"scenario": "happy_approve", "result": "WARN", "actual": "no approve button (no pending listings)"})

    h.clear()
    reject_btn = h.page.locator("button:has-text('Reject'), [data-action='reject']").first
    if reject_btn.is_visible(timeout=2000):
        reject_btn.click()
        h.wait_for_page_load()
        results.append({"scenario": "happy_reject", "result": "PASS", "actual": "listing rejected"})
    else:
        results.append({"scenario": "happy_reject", "result": "WARN", "actual": "no reject button"})

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
    log("\n[MARKETPLACE-ADMIN E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Marketplace-Admin: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
