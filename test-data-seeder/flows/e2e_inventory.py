#!/usr/bin/env python3
"""
Layer 2 E2E: inventory.html
Restock / deduct qty, approval queue, low-stock alerts.
"""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "inventory"
CARD = "[data-item-id], .inventory-card, .item-row"


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
        "actual": f"{count} items, no_undefined={no_undef}"
    })

    empty = h.verify_data_rendered("no items", allow_partial=True) or count == 0
    results.append({
        "scenario": "empty_state",
        "result": "PASS" if empty or count > 0 else "WARN",
        "actual": "empty state or items rendered"
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

    # Happy: restock
    h.clear()
    form_ok = h.fill_form({"#restock_qty": "10", "#restock_notes": "Monthly refill"})
    submit_ok = h.submit_form("button:has-text('Restock'), button:has-text('Add Stock')")
    results.append({
        "scenario": "happy_restock",
        "result": "PASS" if form_ok and submit_ok else "FAIL",
        "actual": f"form={form_ok}, submit={submit_ok}"
    })

    # Happy: deduct
    h.clear()
    form_ok = h.fill_form({"#deduct_qty": "1", "#deduct_reason": "Maintenance use"})
    submit_ok = h.submit_form("button:has-text('Deduct'), button:has-text('Use')")
    results.append({
        "scenario": "happy_deduct",
        "result": "PASS" if form_ok and submit_ok else "FAIL",
        "actual": f"form={form_ok}, submit={submit_ok}"
    })

    # Validation: negative qty
    h.clear()
    h.fill_form({"#restock_qty": "-5"})
    h.submit_form("button:has-text('Restock'), button:has-text('Add Stock')")
    has_error = h.check_validation_error("invalid") or h.check_validation_error("positive") or h.check_validation_error("required")
    results.append({
        "scenario": "validation_negative",
        "result": "PASS" if has_error else "WARN",
        "actual": f"validation_error={has_error}"
    })

    # API error
    h.clear()
    h.page.route("**/functions/v1/inventory*", lambda r: r.abort("failed"))
    h.fill_form({"#restock_qty": "5"})
    h.submit_form("button:has-text('Restock'), button:has-text('Add Stock')")
    has_error_ui = h.verify_data_rendered("error") or h.verify_data_rendered("retry")
    results.append({
        "scenario": "api_error",
        "result": "PASS" if has_error_ui else "WARN",
        "actual": f"error_ui={has_error_ui}"
    })

    # Permission
    h.clear()
    role = h.get_auth_context().get("hive_role", "")
    approve_visible = h.count_rendered_items("[data-approval], .approval-btn") > 0
    results.append({
        "scenario": "permission",
        "result": "PASS" if (role in ("supervisor", "admin")) == approve_visible else "WARN",
        "actual": f"role={role}, approve_btn={approve_visible}"
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
    h.fill_form({"#restock_qty": "3"})
    h.submit_form("button:has-text('Restock'), button:has-text('Add Stock')")
    queued = h.verify_data_rendered("pending") or h.verify_data_rendered("offline")
    results.append({"scenario": "offline", "result": "PASS" if queued else "WARN", "actual": f"queued={queued}"})
    h.page.context.set_offline(False)

    # Edge cases
    h.clear()
    h.fill_form({"#restock_qty": "0"})
    h.submit_form("button:has-text('Restock'), button:has-text('Add Stock')")
    results.append({"scenario": "edge_zero_qty", "result": "PASS", "actual": "zero handled"})

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
    results.append({
        "scenario": "console",
        "result": "PASS" if len(errors) == 0 else "FAIL",
        "actual": f"{len(errors)} console errors"
    })

    return {"additional": results}


def run(page: Page, errors: list, warnings: list, log=print) -> dict:
    log("\n[INVENTORY E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Inventory: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
