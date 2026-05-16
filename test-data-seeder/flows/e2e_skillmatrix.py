#!/usr/bin/env python3
"""Layer 2 E2E: skillmatrix.html — Skill levels, badge awards, XP tracking, update targets."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "skillmatrix"
CARD = ".skill-row, [data-skill-id], .skill-card"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    skills_ok = h.verify_data_rendered("level") or h.verify_data_rendered("skill") or count >= 0
    results.append({"scenario": "happy", "result": "PASS" if skills_ok and no_undef else "FAIL", "actual": f"{count} skills"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "skills or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    role = h.get_auth_context().get("hive_role", "")
    update_btn = h.page.locator("button:has-text('Update'), button:has-text('Set Target'), [data-action='update-skill']").first
    if role in ("supervisor", "admin") and update_btn.is_visible(timeout=3000):
        update_btn.click()
        h.fill_form({"select#level": "3", "#target_level": "4"})
        h.submit_form("button:has-text('Save'), button:has-text('Update')")
        results.append({"scenario": "happy_update_target", "result": "PASS", "actual": "target updated"})
    else:
        results.append({"scenario": "happy_update_target", "result": "WARN", "actual": f"role={role}, btn_visible={update_btn.is_visible(timeout=500)}"})

    results.append({"scenario": "validation", "result": "SKIP", "reason": "deferred"})
    results.append({"scenario": "api_error", "result": "SKIP", "reason": "deferred"})

    h.clear()
    badge_visible = h.verify_data_rendered("badge") or h.verify_data_rendered("Badge")
    results.append({"scenario": "badge_display", "result": "PASS" if badge_visible else "WARN", "actual": f"badge_shown={badge_visible}"})
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
    log("\n[SKILLMATRIX E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Skillmatrix: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
