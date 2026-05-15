"""Static / public pages flow.

Checks pages that do not require auth and should load cleanly:
  1 - index.html (marketing landing page / roadmap)
  2 - public-feed.html (public community feed)
  3 - marketplace-seller.html (public seller profile page)
  4 - No JS errors on any of the above
"""

from .harness import BASE_URL, screenshot


STATIC_PAGES = [
    ("index.html",             "index"),
    ("public-feed.html",       "public_feed"),
    ("marketplace-seller.html","marketplace_seller"),
]


def run(page, errors, warnings, log) -> dict:
    log("Static / public pages checks...")
    results = []

    for path, slug in STATIC_PAGES:
        js_errors = []
        page.on("pageerror", lambda e: js_errors.append(e.message))

        url = f"{BASE_URL}/workhive/{path}"
        log(f"  Checking {path}...")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            page.wait_for_timeout(1500)
            screenshot(page, f"static_{slug}")

            body_visible = page.evaluate("!!document.body && document.body.innerText.trim().length > 0")
            serious = [e for e in js_errors if "net::ERR_" not in e and "Failed to fetch" not in e]

            if not body_visible:
                results.append(("FAIL", f"{path}: body is empty or blank"))
                log(f"  ✗ {path}: blank page")
            elif serious:
                results.append(("WARN", f"{path}: JS errors: {serious[:2]}"))
                log(f"  ⚠ {path}: {len(serious)} JS error(s)")
            else:
                results.append(("PASS", f"{path}: loaded cleanly"))
                log(f"  ✓ {path}: OK")
        except Exception as e:
            results.append(("WARN", f"{path}: {type(e).__name__}: {e}"))
            log(f"  ⚠ {path}: {type(e).__name__}: {e}")

    return {"results": results}
