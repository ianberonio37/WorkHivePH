#!/usr/bin/env python3
"""Debug marketplace.html - find why verdict stays at Loading"""

from playwright.sync_api import sync_playwright

BASE_URL = "http://127.0.0.1:5000/workhive"
TEST_WORKER_NAME = "Leandro Marquez"
# TEST_HIVE_ID resolved at runtime from the live membership (test_identity pattern) —
# a pinned UUID rots across reseeds. Literal = hive fallback only.
def _resolve_hive(_fallback="586fd158-42d1-4853-a406-64a4695e71c4"):
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

    requests_log = []
    page.on("request", lambda req: requests_log.append(f"REQ: {req.method} {req.url[:200]}"))
    page.on("response", lambda res: requests_log.append(f"RES: {res.status} {res.url[:200]}"))

    console_messages = []
    page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text[:200]}"))
    page.on("pageerror", lambda err: console_messages.append(f"[ERROR] {str(err)[:200]}"))

    page.goto(BASE_URL + "/index.html", wait_until="domcontentloaded")
    page.evaluate(f"""() => {{
        localStorage.setItem('wh_last_worker', '{TEST_WORKER_NAME}');
        localStorage.setItem('wh_active_hive_id', '{TEST_HIVE_ID}');
        localStorage.setItem('wh_hive_id', '{TEST_HIVE_ID}');
        localStorage.setItem('workerName', '{TEST_WORKER_NAME}');
    }}""")

    print("Loading marketplace.html...")
    page.goto(BASE_URL + "/marketplace.html", wait_until="domcontentloaded")
    print("Waiting 15s for verdict...")
    page.wait_for_timeout(15000)

    verdict_label = page.text_content("#mk-verdict-label") or ""
    verdict_sub = page.text_content("#mk-verdict-sub") or ""
    total_hero = page.text_content("#mk-total-hero") or ""
    total_sub = page.text_content("#mk-total-sub") or ""
    print(f"\nVerdict label: '{verdict_label}'")
    print(f"Verdict sub: '{verdict_sub[:200]}'")
    print(f"Total hero: '{total_hero}'")
    print(f"Total sub: '{total_sub}'")

    # Check if hive-gate is blocking
    hive_gate_visible = page.evaluate("""() => {
        const el = document.querySelector('#hive-gate, [class*=hive-gate]');
        return el ? { exists: true, visible: el.offsetParent !== null, text: el.textContent.slice(0,200) } : { exists: false };
    }""")
    print(f"\nHive gate: {hive_gate_visible}")

    print("\n=== NETWORK REQUESTS (filtered) ===")
    for log in requests_log:
        if "marketplace" in log.lower() or "rpc" in log.lower() or "rest/v1" in log.lower():
            print(f"  {log[:200]}")

    print("\n=== CONSOLE (last 10) ===")
    for msg in console_messages[-10:]:
        print(f"  {msg}")

    browser.close()
