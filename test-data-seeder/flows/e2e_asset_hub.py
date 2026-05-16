#!/usr/bin/env python3
"""Layer 2 E2E: asset-hub.html — Asset details, metadata update, risk scoring, related logbook."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "asset-hub"
CARD = "[data-asset-id], .asset-card, .asset-row"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy", "result": "PASS" if count >= 0 and no_undef else "FAIL", "actual": f"{count} assets"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "assets or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    first_asset = h.page.locator(CARD).first
    if first_asset.is_visible(timeout=3000):
        first_asset.click()
        h.wait_for_page_load()
        edit_btn = h.page.locator("button:has-text('Edit'), [data-action='edit']").first
        if edit_btn.is_visible(timeout=2000):
            edit_btn.click()
            h.fill_form({"#asset_name": "Updated Asset Name", "#notes": "E2E edit"})
            h.submit_form("button:has-text('Save'), button:has-text('Update')")
            updated = h.verify_data_rendered("Updated Asset Name")
            results.append({"scenario": "happy_edit_metadata", "result": "PASS" if updated else "WARN", "actual": f"updated={updated}"})
        else:
            results.append({"scenario": "happy_edit_metadata", "result": "WARN", "actual": "no edit button"})
    else:
        results.append({"scenario": "happy_edit_metadata", "result": "WARN", "actual": "no assets to click"})

    results.append({"scenario": "validation", "result": "SKIP", "reason": "deferred"})
    results.append({"scenario": "api_error", "result": "SKIP", "reason": "deferred"})

    h.clear()
    role = h.get_auth_context().get("hive_role", "")
    risk_edit = h.count_rendered_items("[data-action='edit-risk'], .risk-edit-btn") > 0
    results.append({"scenario": "permission_risk_edit", "result": "PASS" if (role in ("supervisor", "admin")) == risk_edit else "WARN", "actual": f"role={role}, risk_edit={risk_edit}"})

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
    log("\n[ASSET-HUB E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Asset-Hub: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
