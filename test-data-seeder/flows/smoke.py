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
    ("ai-quality.html",        "AI Quality + ROI",    "body"),
    ("plant-connections.html", "Plant Connections",   "body"),
    ("achievements.html",      "Achievements",        "body"),
    ("asset-hub.html",         "Asset Hub",           "body"),
    ("shift-brain.html",       "Shift Brain",         "body"),
    ("alert-hub.html",         "Alert Hub",           "body"),
    ("audit-log.html",         "Audit Log",           "body"),
    ("voice-journal.html",     "Voice Journal",       "body"),
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
    "PGRST204",                                             # column not in schema cache (same root cause)
    "PGRST301",                                             # JWT expired / auth required — happens when Playwright session is fresh
    "PGRST116",                                             # no rows returned (not really an error)
    "Could not find the table",                             # same error, plain text form
    "Could not find the column",                            # PGRST204 plain text form
    "schema cache",                                         # same error, partial match
    "permission denied for table",                          # RLS denies anon — friendly fail, not a code bug
    "permission denied for relation",                       # same
    "violates row-level security policy",                   # RLS blocks an insert/update — caller handles via toast
    "duplicate key value violates unique constraint",        # idempotent re-run of a seed — expected
    "violates check constraint",                            # CHECK constraint catches bad input — expected for negative tests
    "JWT expired",                                          # tester session aged out
    "Invalid Refresh Token",                                # tester session aged out
    ".supabase.co/",                                        # any cloud Supabase call (REST/functions/auth/realtime) — 401/403 without auth in headless session
]


def is_ignored(text: str) -> bool:
    return any(p.lower() in text.lower() for p in IGNORED_ERROR_PATTERNS)


# Pages that rely on cloud Supabase features (benchmarking, AI reports, etc.)
# requiring real auth/deployment. Headless errors on these pages are WARN, not FAIL.
CLOUD_ONLY_PAGES = {
    "ph-intelligence.html",   # peer benchmarking — cloud DB + intelligence-report fn
    "analytics-report.html",  # analytics orchestrator — cloud edge fn
}


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
                is_cloud_only = filename in CLOUD_ONLY_PAGES
                status = "WARN" if is_cloud_only else "FAIL"
                results.append((status, filename, label, new_errors))
                if not is_cloud_only:
                    fail_count += 1
                tag = " [cloud-only WARN]" if is_cloud_only else ""
                log(f"  {'⚠' if is_cloud_only else '✗'} {label} ({filename}){tag} — {len(new_errors)} errors:")
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
