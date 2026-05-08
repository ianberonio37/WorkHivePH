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
    ("project-manager.html",   "Project Manager",  "body"),
    ("project-report.html",    "Project Report",   "body"),
    ("integrations.html",      "CMMS Integration",    "body"),
    ("ph-intelligence.html",   "PH Intelligence",     "body"),
    ("predictive.html",        "Predictive ML",       "body"),
    ("achievements.html",      "Achievements",        "body"),
    ("asset-hub.html",         "Asset Hub",           "body"),
    ("shift-brain.html",       "Shift Brain",         "body"),
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
    "localhost:8000",                 # Python calc API — not running during gate
    "127.0.0.1:8000",                 # Python calc API — not running during gate
    "host.docker.internal:8000",      # Python calc API docker variant
    "ERR_CONNECTION_REFUSED",         # any service not running (Python API, etc.)
    "ERR_FAILED",                     # general network failure from unavailable services
    "Failed to load resource",        # network resource unavailable
    "AbortError",                     # fetch aborted by navigation
    "Load failed",                    # Safari/mobile network load failure
    "NetworkError",                   # generic network error
    "Cannot read properties of undefined (reading 'from')",  # Supabase not ready
    "Edge Function returned a non-2xx status code",          # analytics/AI edge fn error
    "non-2xx status code",                                   # same, shorter match
    "The operation was aborted",                             # fetch aborted by timeout
    "signal is aborted",                                     # AbortSignal timeout
    "FunctionsHttpError",                                    # Supabase functions error class
    "FunctionsFetchError",                                   # Supabase fetch error class
    "FunctionsRelayError",                                   # Supabase relay error
    "504",                                                   # Gateway timeout from Edge Function
    "502",                                                   # Bad gateway
    "SyntaxError: Unexpected end of JSON input",             # empty/truncated API response
    "Unexpected token",                                      # malformed JSON from API
    "PGRST205",                                             # table not in schema cache — migration not yet applied to local Supabase
    "Could not find the table",                             # same error, plain text form
    "schema cache",                                         # same error, partial match
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
            # Let deferred fetches (analytics Python API, Edge Functions) finish or fail
            page.wait_for_timeout(1500)
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
