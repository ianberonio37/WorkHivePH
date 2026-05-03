"""Sign-up form edge cases — taken username, password mismatch, password too short."""
from .harness import BASE_URL, pick_test_username


def run(page, errors, warnings, log) -> dict:
    log("Sign-up edge case checks...")
    results = []

    # We need to be signed OUT for the sign-up flow. Open in a fresh tab/origin.
    page.context.clear_cookies()
    page.evaluate("() => localStorage.clear()")

    page.goto(f"{BASE_URL}/workhive/index.html?signin=1", wait_until="domcontentloaded")
    page.wait_for_selector("#tab-signup", timeout=10000)

    # Switch to Sign Up tab
    page.click("#tab-signup")
    page.wait_for_selector("#su-username:visible", timeout=5000)

    taken_username = pick_test_username()
    log(f"  using {taken_username} (a seeded user) for taken-name test")

    # Test 1: Taken username — type it, wait for the live availability badge
    page.fill("#su-username", taken_username)
    page.wait_for_timeout(800)  # debounced check (400ms in code)
    status_text = page.locator("#su-username-status").text_content() or ""
    if "taken" in status_text.lower():
        results.append(("PASS", f"taken username detected: '{status_text.strip()}'"))
        log(f"  ✓ taken username detected: '{status_text.strip()}'")
    else:
        results.append(("FAIL", f"taken username NOT detected — status was '{status_text.strip()}'"))
        log(f"  ✗ taken username NOT detected: '{status_text.strip()}'")

    # Test 2: Available username — should show ✓
    page.fill("#su-username", "brandnewseeduser_xyz123")
    page.wait_for_timeout(800)
    status_text = page.locator("#su-username-status").text_content() or ""
    if "available" in status_text.lower() or "✓" in status_text:
        results.append(("PASS", f"available username shows OK: '{status_text.strip()}'"))
        log(f"  ✓ available username detected")
    else:
        results.append(("WARN", f"available username status unclear: '{status_text.strip()}'"))

    # Test 3: Password too short
    page.fill("#su-username", "testshortpw_abc")
    page.fill("#su-password", "abc")
    page.fill("#su-confirm", "abc")
    page.fill("#su-displayname", "Test Short")
    page.click("#su-btn")
    page.wait_for_timeout(500)
    err = (page.locator("#su-error").text_content() or "").strip()
    if err and ("6" in err or "short" in err.lower() or "characters" in err.lower()):
        results.append(("PASS", f"short password rejected: '{err}'"))
        log(f"  ✓ short password rejected: '{err}'")
    else:
        results.append(("FAIL", f"short password not properly rejected — error was '{err}'"))

    # Test 4: Password mismatch
    page.fill("#su-password", "longenough123")
    page.fill("#su-confirm", "different123")
    page.click("#su-btn")
    page.wait_for_timeout(500)
    err = (page.locator("#su-error").text_content() or "").strip()
    if err and ("match" in err.lower() or "re-enter" in err.lower()):
        results.append(("PASS", f"password mismatch rejected: '{err}'"))
        log(f"  ✓ password mismatch rejected: '{err}'")
    else:
        results.append(("FAIL", f"password mismatch not properly rejected — error was '{err}'"))

    return {"results": results}
