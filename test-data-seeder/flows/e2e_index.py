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
    h.goto(PAGE)
    h.wait_for_page_load()

    hero_ok = h.verify_data_rendered("WorkHive") or h.verify_data_rendered("Sign in") or h.verify_data_rendered("Login")
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy_landing", "result": "PASS" if hero_ok and no_undef else "FAIL", "actual": f"hero={hero_ok}"})
    results.append({"scenario": "auth_form_visible", "result": "PASS" if h.count_rendered_items("input[type='password']") > 0 else "FAIL", "actual": "auth form present"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.goto(PAGE)

    h.clear()
    login_ok = h.login()
    results.append({"scenario": "happy_signin", "result": "PASS" if login_ok else "FAIL", "actual": f"login={login_ok}"})

    h.clear()
    h.goto(PAGE)
    h.page.fill('input[placeholder*="username"], input[name="username"]', "")
    h.page.fill('input[type="password"]', "")
    h.page.click('button:has-text("Sign in")')
    has_err = h.check_validation_error("required") or h.check_validation_error("invalid")
    results.append({"scenario": "validation_empty_creds", "result": "PASS" if has_err else "WARN", "actual": f"error={has_err}"})

    h.clear()
    h.goto(PAGE)
    h.page.fill('input[placeholder*="username"]', "wronguser")
    h.page.fill('input[type="password"]', "wrongpass")
    h.page.click('button:has-text("Sign in")')
    h.wait_for_page_load()
    err_shown = h.verify_data_rendered("invalid") or h.verify_data_rendered("incorrect") or h.verify_data_rendered("error")
    results.append({"scenario": "api_error_bad_creds", "result": "PASS" if err_shown else "WARN", "actual": f"error_shown={err_shown}"})

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
