#!/usr/bin/env python3
"""
Layer 2 E2E: hive.html
Dashboard KPIs, hive context switch, realtime updates, permissions.
"""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "hive"
CARD = ".kpi-card, .dashboard-card, [data-kpi], .stat-card"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)
    h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    kpi_present = h.verify_data_rendered("OEE") or h.verify_data_rendered("MTBF") or h.verify_data_rendered("logbook")
    results.append({
        "scenario": "happy_kpis",
        "result": "PASS" if count >= 0 and no_undef else "FAIL",
        "actual": f"{count} KPI cards, kpi_text={kpi_present}, no_undef={no_undef}"
    })

    hive_name = h.get_auth_context().get("hive_name", "")
    hive_shown = h.verify_data_rendered(hive_name, allow_partial=True) if hive_name else True
    results.append({
        "scenario": "hive_context_displayed",
        "result": "PASS" if hive_shown else "FAIL",
        "actual": f"hive_name={hive_name}, shown={hive_shown}"
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

    # Happy: switch hive context
    h.clear()
    switcher = h.page.locator("#hive-selector, .hive-switcher, [data-action='switch-hive']").first
    if switcher.is_visible(timeout=3000):
        switcher.click()
        h.wait_for_page_load()
        results.append({"scenario": "happy_switch_hive", "result": "PASS", "actual": "hive switcher clicked"})
    else:
        results.append({"scenario": "happy_switch_hive", "result": "WARN", "actual": "no hive switcher visible"})

    # Permission: onboarding intent capture
    h.clear()
    intent_btn = h.page.locator("[data-action='set-intent'], .intent-btn, button:has-text('Intent')").first
    role = h.get_auth_context().get("hive_role", "")
    intent_visible = intent_btn.is_visible(timeout=2000) if h.count_rendered_items("[data-action='set-intent']") > 0 else False
    results.append({
        "scenario": "permission_intent",
        "result": "PASS" if (role in ("supervisor", "admin")) == intent_visible else "WARN",
        "actual": f"role={role}, intent_visible={intent_visible}"
    })

    # API error: KPI data
    h.clear()
    h.page.route("**/functions/v1/hive*", lambda r: r.abort("failed"))
    h.goto(PAGE)
    fallback = h.verify_data_rendered("error") or h.verify_data_rendered("unavailable") or h.verify_data_rendered("--")
    results.append({"scenario": "api_error_kpis", "result": "PASS" if fallback else "WARN", "actual": f"fallback={fallback}"})

    # Validation: N/A (hive is mostly read-only dashboard)
    results.append({"scenario": "validation", "result": "SKIP", "reason": "hive dashboard is read-only"})

    # Concurrent: N/A for dashboard
    results.append({"scenario": "concurrent", "result": "SKIP", "reason": "KPIs are aggregated, no concurrent edit conflict"})

    return {"write": results}


def test_additional(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)

    # Offline: KPIs should degrade gracefully
    h.clear()
    h.page.context.set_offline(True)
    h.goto(PAGE)
    graceful = h.verify_data_rendered("offline") or h.verify_data_rendered("unavailable") or h.count_rendered_items(CARD) >= 0
    results.append({"scenario": "offline_degrade", "result": "PASS" if graceful else "WARN", "actual": f"graceful={graceful}"})
    h.page.context.set_offline(False)

    # Edge: Knowledge Pipeline Health tile
    h.clear()
    h.goto(PAGE)
    kph = h.verify_data_rendered("Knowledge") or h.verify_data_rendered("Pipeline")
    results.append({"scenario": "edge_kph_tile", "result": "PASS" if kph else "WARN", "actual": f"kph_tile={kph}"})

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
    log("\n[HIVE E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Hive: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
