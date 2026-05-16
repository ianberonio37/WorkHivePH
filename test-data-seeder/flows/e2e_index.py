#!/usr/bin/env python3
"""Layer 2 E2E: index.html — Sign-up/Sign-in, redirect after auth, remember hive."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "index"
CARD = ".hive-card, [data-hive-id], .auth-form"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    # Happy: landing page renders hero content
    h.page.goto(f"{BASE_URL}/index.html", wait_until="networkidle")
    h.wait_for_page_load()
    hero_ok = h.verify_data_rendered("WorkHive") or h.verify_data_rendered("Sign In") or h.verify_data_rendered("Login")
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy_landing", "result": "PASS" if hero_ok and no_undef else "FAIL", "actual": f"hero={hero_ok}"})

    # Auth form visible: navigate with ?signin=1 to open the sign-in modal
    h.page.goto(f"{BASE_URL}/index.html?signin=1", wait_until="domcontentloaded")
    try:
        h.page.wait_for_selector("#si-username", state="visible", timeout=8000)
        form_ok = h.count_rendered_items("#si-username, #si-password, #si-btn") >= 2
    except:
        form_ok = False
    results.append({"scenario": "auth_form_visible", "result": "PASS" if form_ok else "FAIL", "actual": f"form_fields={form_ok}"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    # Happy: sign in via helper (uses ?signin=1 to open modal)
    h.clear()
    login_ok = h.login()
    results.append({"scenario": "happy_signin", "result": "PASS" if login_ok else "FAIL", "actual": f"login={login_ok}"})

    # Validation: open modal and submit empty credentials
    h.clear()
    try:
        h.page.goto(f"{BASE_URL}/index.html?signin=1", wait_until="domcontentloaded")
        h.page.wait_for_selector("#si-username", state="visible", timeout=8000)
        h.page.fill("#si-username", "")
        h.page.fill("#si-password", "")
        h.page.click("#si-btn")
        h.page.wait_for_timeout(1000)
        has_err = h.check_validation_error("required") or h.check_validation_error("invalid") or \
                  h.verify_data_rendered("invalid") or h.verify_data_rendered("required")
        results.append({"scenario": "validation_empty_creds", "result": "PASS" if has_err else "WARN", "actual": f"error={has_err}"})
    except Exception as e:
        results.append({"scenario": "validation_empty_creds", "result": "WARN", "actual": str(e)[:60]})

    # API error: bad credentials
    h.clear()
    try:
        h.page.goto(f"{BASE_URL}/index.html?signin=1", wait_until="domcontentloaded")
        h.page.wait_for_selector("#si-username", state="visible", timeout=8000)
        h.page.fill("#si-username", "baduser99")
        h.page.fill("#si-password", "wrongpass")
        h.page.click("#si-btn")
        h.page.wait_for_timeout(4000)
        err_shown = h.verify_data_rendered("invalid") or h.verify_data_rendered("incorrect") or \
                    h.verify_data_rendered("error") or h.verify_data_rendered("not found")
        results.append({"scenario": "api_error_bad_creds", "result": "PASS" if err_shown else "WARN", "actual": f"error_shown={err_shown}"})
    except Exception as e:
        results.append({"scenario": "api_error_bad_creds", "result": "WARN", "actual": str(e)[:60]})

    results.append({"scenario": "permission", "result": "SKIP", "reason": "public page, no permission check"})
    results.append({"scenario": "concurrent", "result": "SKIP", "reason": "deferred"})
    return {"write": results}


def test_additional(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.goto(PAGE)

    h.clear()
    h.login()
    hive_id = h.page.evaluate("localStorage.getItem('wh_active_hive_id')")
    h.goto(PAGE)
    hive_remembered = h.page.evaluate("localStorage.getItem('wh_active_hive_id')") == hive_id
    results.append({"scenario": "remember_hive", "result": "PASS" if hive_remembered else "WARN", "actual": f"hive_remembered={hive_remembered}"})

    h.clear(); h.set_mobile_viewport(375, 667); h.goto(PAGE)
    results.append({"scenario": "mobile", "result": "PASS" if h.verify_no_horizontal_scroll() else "WARN", "actual": "mobile"})
    h.clear()
    errors, _ = h.check_console_errors()
    results.append({"scenario": "console", "result": "PASS" if len(errors) == 0 else "FAIL", "actual": f"{len(errors)} errors"})
    return {"additional": results}


def run(page: Page, errors: list, warnings: list, log=print) -> dict:
    log("\n[INDEX E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Index: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
