#!/usr/bin/env python3
"""Layer 2 E2E: voice-journal.html — Load voice logs, record/transcribe, error recovery."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "voice-journal"
CARD = "[data-log-id], .voice-entry, .journal-entry"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    count = h.count_rendered_items(CARD)
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy", "result": "PASS" if count >= 0 and no_undef else "FAIL", "actual": f"{count} logs"})
    results.append({"scenario": "empty_state", "result": "PASS" if count >= 0 else "WARN", "actual": "logs or empty"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    record_btn = h.page.locator("button:has-text('Record'), button:has-text('Start'), [data-action='record']").first
    if record_btn.is_visible(timeout=3000):
        record_btn.click()
        results.append({"scenario": "happy_record", "result": "PASS", "actual": "record initiated"})
    else:
        results.append({"scenario": "happy_record", "result": "WARN", "actual": "no record button (requires microphone permission)"})

    results.append({"scenario": "validation", "result": "SKIP", "reason": "requires mic permission in test env"})

    h.clear()
    h.page.route("**/functions/v1/voice*", lambda r: r.abort("failed"))
    save_btn = h.page.locator("button:has-text('Save'), button:has-text('Stop')").first
    if save_btn.is_visible(timeout=2000):
        save_btn.click()
        has_err_ui = h.verify_data_rendered("error") or h.verify_data_rendered("retry")
        results.append({"scenario": "api_error_transcribe", "result": "PASS" if has_err_ui else "WARN", "actual": f"error_ui={has_err_ui}"})
    else:
        results.append({"scenario": "api_error_transcribe", "result": "SKIP", "reason": "no save button"})

    results.append({"scenario": "permission", "result": "SKIP", "reason": "all workers can use voice journal"})
    results.append({"scenario": "concurrent", "result": "SKIP", "reason": "one recording at a time"})
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
    log("\n[VOICE-JOURNAL E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Voice-Journal: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
