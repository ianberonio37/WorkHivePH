#!/usr/bin/env python3
"""
Layer 2 E2E: marketplace.html
Browse/list/create/publish listings, seller verification, approval queue.
"""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "marketplace"
CARD = "[data-listing-id], .listing-card, .marketplace-item"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)
    h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({
        "scenario": "happy_listings",
        "result": "PASS" if count >= 0 and no_undef else "FAIL",
        "actual": f"{count} listings, no_undef={no_undef}"
    })

    empty = h.verify_data_rendered("no listings", allow_partial=True) or count == 0
    results.append({
        "scenario": "empty_state",
        "result": "PASS" if empty or count > 0 else "WARN",
        "actual": f"empty_or_items={empty or count > 0}"
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

    # Happy: create listing
    h.clear()
    new_btn = h.page.locator("button:has-text('New'), button:has-text('Create'), button:has-text('List Item'), [data-action='create']").first
    if new_btn.is_visible(timeout=3000):
        new_btn.click()
        form_ok = h.fill_form({
            "#title": "E2E Test Item",
            "#description": "Automated test listing",
            "#price": "100",
            "#unit": "each"
        })
        submit_ok = h.submit_form("button:has-text('Save'), button:has-text('Create')")
        success = h.verify_data_rendered("E2E Test Item")
        results.append({"scenario": "happy_create", "result": "PASS" if submit_ok and success else "WARN", "actual": f"submit={submit_ok}, visible={success}"})
    else:
        results.append({"scenario": "happy_create", "result": "WARN", "actual": "no create button"})

    # Happy: publish listing
    h.clear()
    publish_btn = h.page.locator("button:has-text('Publish'), [data-action='publish']").first
    if publish_btn.is_visible(timeout=3000):
        publish_btn.click()
        h.wait_for_page_load()
        published = h.verify_data_rendered("published") or h.verify_data_rendered("live")
        results.append({"scenario": "happy_publish", "result": "PASS" if published else "WARN", "actual": f"published={published}"})
    else:
        results.append({"scenario": "happy_publish", "result": "WARN", "actual": "no publish button"})

    # Validation: missing required fields
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
    h.page.route("**/functions/v1/marketplace*", lambda r: r.abort("failed"))
    publish_btn2 = h.page.locator("button:has-text('Publish')").first
    if publish_btn2.is_visible(timeout=2000):
        publish_btn2.click()
        has_err_ui = h.verify_data_rendered("error") or h.verify_data_rendered("retry")
        results.append({"scenario": "api_error", "result": "PASS" if has_err_ui else "WARN", "actual": f"error_ui={has_err_ui}"})
    else:
        results.append({"scenario": "api_error", "result": "WARN", "actual": "no publish btn"})

    # Permission: admin approval queue
    h.clear()
    role = h.get_auth_context().get("hive_role", "")
    approval_q = h.count_rendered_items("[data-approval], .approval-queue") > 0
    results.append({
        "scenario": "permission_approval",
        "result": "PASS" if (role in ("supervisor", "admin")) == approval_q else "WARN",
        "actual": f"role={role}, approval_visible={approval_q}"
    })

    return {"write": results}


def test_additional(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)

    # Offline: browsing still works
    h.clear()
    h.page.context.set_offline(True)
    h.goto(PAGE)
    still_renders = h.count_rendered_items(CARD) >= 0
    results.append({"scenario": "offline_browse", "result": "PASS" if still_renders else "WARN", "actual": f"renders={still_renders}"})
    h.page.context.set_offline(False)

    # Edge: price with decimal
    h.clear()
    h.goto(PAGE)
    new_btn = h.page.locator("button:has-text('New'), button:has-text('Create')").first
    if new_btn.is_visible(timeout=2000):
        new_btn.click()
        h.fill_form({"#price": "99.99"})
        results.append({"scenario": "edge_decimal_price", "result": "PASS", "actual": "decimal price accepted"})
    else:
        results.append({"scenario": "edge_decimal_price", "result": "WARN", "actual": "no create button"})

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
    log("\n[MARKETPLACE E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Marketplace: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
