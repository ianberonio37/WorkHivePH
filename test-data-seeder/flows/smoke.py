"""Page-load smoke test — open every public page, check for console errors."""
from .harness import BASE_URL, screenshot

# Pages to test, in order. (filename, label, anchor selector that should appear once loaded)
PAGES = [
    ("hive.html",                "Hive dashboard",        "body"),
    ("logbook.html",             "Logbook",               "body"),
    ("inventory.html",           "Inventory",             "body"),
    ("pm-scheduler.html",        "PM Scheduler",          "body"),
    ("analytics.html",           "Analytics",             "body"),
    ("analytics-report.html",    "Analytics Report",      "body"),
    ("skillmatrix.html",         "Skill Matrix",          "body"),
    ("community.html",           "Community",             "body"),
    ("public-feed.html",         "Public feed",           "body"),
    ("marketplace.html",         "Marketplace",           "body"),
    ("dayplanner.html",          "Day planner",           "body"),
    ("engineering-design.html",  "Engineering design",    "body"),
    ("report-sender.html",       "Report sender",         "body"),
]

# Errors we tolerate (known/expected)
IGNORED_ERROR_PATTERNS = [
    "workhive-logo-transparent",   # missing logo (PWA manifest)
    "Failed to fetch",             # edge functions without API keys (AI assistant, etc.)
    "ERR_NAME_NOT_RESOLVED",
    "ERR_INTERNET_DISCONNECTED",
    "ERR_ABORTED",                 # request canceled by navigation — not a real error
    "tailwindcss",                 # cdn.tailwindcss.com warning
    "GoTrueClient",                # multiple client instances warning
    "manifest",
    "favicon",                     # browser auto-fetches /favicon.ico
    "127.0.0.1:54321/functions/v1",  # edge function calls without API keys
]


def is_ignored(text: str) -> bool:
    return any(p.lower() in text.lower() for p in IGNORED_ERROR_PATTERNS)


def run(page, errors, warnings, log) -> dict:
    log("Smoke test — opening 12 pages, checking console errors...")
    results = []
    fail_count = 0

    for filename, label, selector in PAGES:
        page_errors_before = len(errors)
        try:
            page.goto(f"{BASE_URL}/workhive/{filename}", wait_until="networkidle", timeout=15000)
            page.wait_for_selector(selector, timeout=5000)
            # Let any deferred fetches finish
            page.wait_for_timeout(500)
            new_errors = [e for e in errors[page_errors_before:] if not is_ignored(e)]
            if new_errors:
                results.append(("FAIL", filename, label, new_errors))
                fail_count += 1
                log(f"  ✗ {label} ({filename}) — {len(new_errors)} errors:")
                for e in new_errors[:3]:
                    log(f"      • {e[:200]}")
            else:
                screenshot_path = screenshot(page, f"smoke_{filename.replace('.html', '')}")
                results.append(("PASS", filename, label, []))
                log(f"  ✓ {label} ({filename}) — no console errors")
        except Exception as e:
            results.append(("FAIL", filename, label, [f"navigation: {type(e).__name__}: {e}"]))
            fail_count += 1
            log(f"  ✗ {label} ({filename}) — {type(e).__name__}: {e}")

    return {"results": results, "fail_count": fail_count, "total": len(PAGES)}
