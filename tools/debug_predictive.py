#!/usr/bin/env python3
"""Debug what's actually rendered on predictive.html"""

from playwright.sync_api import sync_playwright
import time

BASE_URL = "http://127.0.0.1:5000/workhive"
TEST_WORKER_NAME = "Leandro Marquez"
# TEST_HIVE_ID resolved at runtime from the live membership (test_identity pattern) —
# a pinned UUID rots across reseeds. Literal = hive fallback only.
def _resolve_hive(_fallback="3776bd17-97f0-4a3c-a850-11c992cb140c"):
    try:
        import sys as _s, pathlib as _p
        _s.path.insert(0, str(_p.Path(__file__).resolve().parent / "lib"))
        from test_identity import resolve_test_identity
        return resolve_test_identity("leandromarquez@auth.workhiveph.com").hive_id
    except Exception:
        return _fallback
TEST_HIVE_ID = _resolve_hive()

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()

    # Collect console messages and errors
    console_messages = []
    page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
    page.on("pageerror", lambda err: console_messages.append(f"[ERROR] {err}"))

    # Set localStorage
    page.goto(BASE_URL + "/index.html", wait_until="domcontentloaded")
    page.evaluate(f"""() => {{
        localStorage.setItem('wh_last_worker', '{TEST_WORKER_NAME}');
        localStorage.setItem('wh_active_hive_id', '{TEST_HIVE_ID}');
        localStorage.setItem('wh_hive_id', '{TEST_HIVE_ID}');
        localStorage.setItem('workerName', '{TEST_WORKER_NAME}');
    }}""")

    print("Loading predictive.html...")
    page.goto(BASE_URL + "/predictive.html", wait_until="domcontentloaded")

    # Wait longer for content to compute
    print("Waiting 8 seconds for AI verdict to compute...")
    page.wait_for_timeout(8000)

    # Check selector states
    selectors_to_check = [
        "#pr-verdict",
        "#pr-verdict-label",
        "#pr-verdict-sub",
        "#pr-card-hot",
        "#wh-source-chip",
        "#model-chip",
        "#hive-gate",
    ]

    for sel in selectors_to_check:
        el = page.query_selector(sel)
        if el:
            visible = el.is_visible()
            text = (el.text_content() or "").strip()[:80]
            print(f"  {sel}: visible={visible}, text='{text}'")
        else:
            print(f"  {sel}: NOT FOUND")

    # Get all IDs on page
    print("\nAll IDs on page:")
    ids = page.evaluate("""() => Array.from(document.querySelectorAll('[id]')).map(el => el.id)""")
    for i in ids[:30]:
        print(f"  #{i}")

    print(f"\nTotal IDs: {len(ids)}")
    print("Full page title:", page.title())
    print("Page URL:", page.url)

    print("\n=== CONSOLE MESSAGES ===")
    for msg in console_messages[-20:]:
        print(f"  {msg}")

    browser.close()
