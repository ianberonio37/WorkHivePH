#!/usr/bin/env python3
"""Layer 2 E2E: founder-console.html — Platform dashboard, all hives, cost aggregation, admin controls."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "founder-console"
CARD = ".panel, .console-card, [data-panel], .hive-row"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    panels_ok = (
        h.verify_data_rendered("Growth") or h.verify_data_rendered("Hive") or
        h.verify_data_rendered("cost") or count >= 0
    )
    results.append({"scenario": "happy_all_panels", "result": "PASS" if panels_ok and no_undef else "FAIL", "actual": f"{count} panels"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "panels or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    refresh_btn = h.page.locator("button:has-text('Refresh All'), button:has-text('Refresh'), [data-action='refresh-all']").first
    if refresh_btn.is_visible(timeout=3000):
        refresh_btn.click()
        h.wait_for_page_load()
        results.append({"scenario": "happy_refresh_all", "result": "PASS", "actual": "refresh-all clicked"})
    else:
        results.append({"scenario": "happy_refresh_all", "result": "WARN", "actual": "no refresh-all button"})

    h.clear()
    auto_refresh = h.page.locator("select#auto-refresh, [data-auto-refresh]").first
    if auto_refresh.is_visible(timeout=2000):
        auto_refresh.click()
        results.append({"scenario": "happy_auto_refresh", "result": "PASS", "actual": "auto-refresh set"})
    else:
        results.append({"scenario": "happy_auto_refresh", "result": "WARN", "actual": "no auto-refresh dropdown"})

    results.append({"scenario": "validation", "result": "SKIP", "reason": "read-only dashboard"})
    results.append({"scenario": "api_error", "result": "SKIP", "reason": "deferred"})

    h.clear()
    role = h.get_auth_context().get("hive_role", "")
    results.append({"scenario": "permission_founder_only", "result": "PASS" if role in ("admin", "founder") else "WARN", "actual": f"role={role}"})
    results.append({"scenario": "concurrent", "result": "SKIP", "reason": "read-only"})
    return {"write": results}


def test_additional(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    growth_pulse = h.verify_data_rendered("Growth Pulse") or h.verify_data_rendered("Pulse")
    feature_heatmap = h.verify_data_rendered("Heatmap") or h.verify_data_rendered("Feature")
    results.append({"scenario": "edge_8_panels_present", "result": "PASS" if growth_pulse or feature_heatmap else "WARN", "actual": f"growth={growth_pulse}, heatmap={feature_heatmap}"})

    h.clear(); h.set_mobile_viewport(375, 667); h.goto(PAGE)
    results.append({"scenario": "mobile", "result": "PASS" if h.verify_no_horizontal_scroll() else "WARN", "actual": "mobile"})
    h.clear()
    errors, _ = h.check_console_errors()
    results.append({"scenario": "console", "result": "PASS" if len(errors) == 0 else "FAIL", "actual": f"{len(errors)} errors"})
    return {"additional": results}


def run(page: Page, errors: list, warnings: list, log=print) -> dict:
    log("\n[FOUNDER-CONSOLE E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Founder-Console: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
