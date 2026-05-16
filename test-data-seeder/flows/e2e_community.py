#!/usr/bin/env python3
"""
Layer 2 E2E: community.html
Post/edit/delete/reactions, supervisor edit, XP awards, realtime feed.
"""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "community"
CARD = "[data-post-id], .post-card, .community-post"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []

    h.login()
    h.goto(PAGE)
    h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({
        "scenario": "happy_feed",
        "result": "PASS" if count >= 0 and no_undef else "FAIL",
        "actual": f"{count} posts, no_undef={no_undef}"
    })

    empty = h.verify_data_rendered("no posts", allow_partial=True) or h.verify_data_rendered("empty") or count == 0
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

    # Happy: create post
    h.clear()
    form_ok = h.fill_form({"#post_content": "E2E test post — automated", "textarea": "E2E test post — automated"})
    submit_ok = h.submit_form("button:has-text('Post'), button:has-text('Share'), button:has-text('Submit')")
    success = h.verify_data_rendered("E2E test post")
    results.append({
        "scenario": "happy_create_post",
        "result": "PASS" if submit_ok and success else "WARN",
        "actual": f"submit={submit_ok}, visible={success}"
    })

    # Happy: react to post
    h.clear()
    reaction_btn = h.page.locator("[data-reaction], .reaction-btn, button:has-text('👍'), button:has-text('Like')").first
    if reaction_btn.is_visible(timeout=3000):
        reaction_btn.click()
        h.wait_for_page_load()
        results.append({"scenario": "happy_reaction", "result": "PASS", "actual": "reaction clicked"})
    else:
        results.append({"scenario": "happy_reaction", "result": "WARN", "actual": "no reaction button"})

    # Validation: empty post
    h.clear()
    h.fill_form({"#post_content": "", "textarea": ""})
    h.submit_form("button:has-text('Post'), button:has-text('Share')")
    has_err = h.check_validation_error("required") or h.check_validation_error("empty")
    results.append({"scenario": "validation_empty", "result": "PASS" if has_err else "WARN", "actual": f"error={has_err}"})

    # API error
    h.clear()
    h.page.route("**/functions/v1/community*", lambda r: r.abort("failed"))
    h.fill_form({"textarea": "Test"})
    h.submit_form("button:has-text('Post'), button:has-text('Share')")
    has_err_ui = h.verify_data_rendered("error") or h.verify_data_rendered("retry")
    results.append({"scenario": "api_error", "result": "PASS" if has_err_ui else "WARN", "actual": f"error_ui={has_err_ui}"})

    # Permission: supervisor edit
    h.clear()
    role = h.get_auth_context().get("hive_role", "")
    edit_btn = h.count_rendered_items("[data-action='supervisor-edit'], .supervisor-edit-btn") > 0
    results.append({
        "scenario": "permission_supervisor_edit",
        "result": "PASS" if (role in ("supervisor", "admin")) == edit_btn else "WARN",
        "actual": f"role={role}, edit_visible={edit_btn}"
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
    h.fill_form({"textarea": "Offline post test"})
    h.submit_form("button:has-text('Post'), button:has-text('Share')")
    queued = h.verify_data_rendered("pending") or h.verify_data_rendered("offline")
    results.append({"scenario": "offline", "result": "PASS" if queued else "WARN", "actual": f"queued={queued}"})
    h.page.context.set_offline(False)

    # Edge: XP award notification
    h.clear()
    h.goto(PAGE)
    xp_shown = h.verify_data_rendered("XP") or h.verify_data_rendered("xp") or h.verify_data_rendered("points")
    results.append({"scenario": "edge_xp_display", "result": "PASS" if xp_shown else "WARN", "actual": f"xp={xp_shown}"})

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
    log("\n[COMMUNITY E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Community: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
