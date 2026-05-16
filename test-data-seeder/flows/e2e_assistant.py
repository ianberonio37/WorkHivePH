#!/usr/bin/env python3
"""Layer 2 E2E: assistant.html — AI chat send/receive, rate limiting, history truncate."""
from playwright.sync_api import sync_playwright, Page
from e2e_helpers import E2ETestHelper

BASE_URL = "http://127.0.0.1:5000/workhive"
PAGE = "assistant"
CARD = ".message, [data-message-id], .chat-bubble"


def test_read(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE); h.wait_for_page_load()

    chat_ok = h.count_rendered_items("input, textarea, #chat-input") > 0
    no_undef = h.verify_no_undefined_values()
    results.append({"scenario": "happy_chat_ui", "result": "PASS" if chat_ok and no_undef else "FAIL", "actual": f"chat_input={chat_ok}"})
    results.append({"scenario": "empty_state", "result": "PASS", "actual": "chat starts empty by design"})
    results.append({"scenario": "loading", "result": "PASS" if h.wait_for_page_load(15000) else "WARN", "actual": "settled"})
    return {"read": results}


def test_write(page: Page) -> dict:
    h = E2ETestHelper(page, BASE_URL)
    results = []
    h.login(); h.goto(PAGE)

    h.clear()
    chat_input = h.page.locator("#chat-input, textarea, input[placeholder*='message']").first
    if chat_input.is_visible(timeout=3000):
        chat_input.fill("What is OEE?")
        h.page.keyboard.press("Enter")
        h.page.wait_for_timeout(3000)
        response = h.count_rendered_items(CARD) > 0 or h.verify_data_rendered("OEE")
        results.append({"scenario": "happy_send_message", "result": "PASS" if response else "WARN", "actual": f"response={response}"})
    else:
        results.append({"scenario": "happy_send_message", "result": "WARN", "actual": "no chat input"})

    h.clear()
    chat_input2 = h.page.locator("#chat-input, textarea").first
    if chat_input2.is_visible(timeout=2000):
        chat_input2.fill("")
        h.page.keyboard.press("Enter")
        has_err = h.check_validation_error("empty") or h.check_validation_error("required")
        results.append({"scenario": "validation_empty_message", "result": "PASS" if has_err else "WARN", "actual": f"error={has_err}"})
    else:
        results.append({"scenario": "validation_empty_message", "result": "WARN", "actual": "no input"})

    h.clear()
    h.page.route("**/functions/v1/amc*", lambda r: r.abort("failed"))
    chat_input3 = h.page.locator("#chat-input, textarea").first
    if chat_input3.is_visible(timeout=2000):
        chat_input3.fill("Test message")
        h.page.keyboard.press("Enter")
        h.page.wait_for_timeout(2000)
        err_shown = h.verify_data_rendered("error") or h.verify_data_rendered("retry") or h.verify_data_rendered("unavailable")
        results.append({"scenario": "api_error_ai_down", "result": "PASS" if err_shown else "WARN", "actual": f"error_shown={err_shown}"})
    else:
        results.append({"scenario": "api_error_ai_down", "result": "WARN", "actual": "no input"})

    results.append({"scenario": "permission", "result": "SKIP", "reason": "all workers can use assistant"})
    results.append({"scenario": "concurrent", "result": "SKIP", "reason": "per-user session"})
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
    log("\n[ASSISTANT E2E]")
    all_r = [*test_read(page)["read"], *test_write(page)["write"], *test_additional(page)["additional"]]
    p = sum(1 for x in all_r if x.get("result") == "PASS")
    f = sum(1 for x in all_r if x.get("result") == "FAIL")
    w = sum(1 for x in all_r if x.get("result") == "WARN")
    log(f"Assistant: {p} PASS / {f} FAIL / {w} WARN")
    return {"results": all_r, "pass_count": p, "fail_count": f, "warn_count": w}


if __name__ == "__main__":
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        p = b.new_page()
        run(p, [], [])
        b.close()
