"""
Global Search Flow -- WorkHive Tester

Verifies the search-overlay.js module exists, is auto-loaded via nav-hub,
exposes the documented public API, and the Cmd+K trigger button is in
the nav-hub panel. Real keystroke + DB queries can't be exercised
headlessly here — that's a desktop UX check.

Coverage: search-overlay.js (shared module), nav-hub.js wiring.
"""

import urllib.request
from .harness import BASE_URL


def run(page, errors, warnings, log) -> dict:
    results = []
    base = BASE_URL.rstrip('/')

    # ── 1. search-overlay.js loads ───────────────────────────────────────────
    log("Global Search Flow: fetching search-overlay.js...")
    js_text = ""
    try:
        with urllib.request.urlopen(f"{base}/search-overlay.js", timeout=10) as r:
            js_text = r.read().decode("utf-8", errors="replace")
        results.append(("PASS", "search-overlay.js loads (HTTP 200)"))
    except Exception as e:
        results.append(("FAIL", f"search-overlay.js load failed: {type(e).__name__}: {e}"))
        return {"results": results}

    # ── 2. Public API + 4 source queries ─────────────────────────────────────
    api_checks = [
        ("WHSearch global namespace",     "window.WHSearch"   in js_text),
        ("open() exported",               "open: openOverlay" in js_text or "open: function" in js_text or "open:"        in js_text),
        ("close() exported",              "close: closeOverlay" in js_text or "close: function" in js_text),
        ("Cmd+K / Ctrl+K shortcut",       "ev.ctrlKey"        in js_text and "ev.metaKey" in js_text and "'k'" in js_text),
        ("queries asset_nodes",           "asset_nodes"       in js_text),
        ("queries logbook",               "from('logbook')"   in js_text or 'from("logbook")' in js_text),
        ("queries inventory_items",       "inventory_items"   in js_text),
        ("queries pm_assets",             "pm_assets"         in js_text),
        (".limit() on each source",       js_text.count(".limit(") >= 4),
        ("ilike escape for security",     "replace(/%/g"      in js_text and "replace(/_/g" in js_text),
        ("hive scoping (HIVE_ID filter)", "HIVE_ID"           in js_text and "hive_id"      in js_text),
    ]
    for label, ok in api_checks:
        results.append(("PASS" if ok else "FAIL", label))

    # ── 3. Mobile + accessibility patterns ───────────────────────────────────
    mobile_checks = [
        ("44px tap target rows",          "min-height: 44"  in js_text),
        ("16px input font (no iOS zoom)", "font-size: 16"   in js_text),
        ("safe-area inset usage",         "safe-area-inset" in js_text),
        ("escHtml-equivalent escape",     "&amp;"           in js_text and "&lt;" in js_text),
        ("ArrowDown keyboard nav",        "ArrowDown"       in js_text),
        ("Enter activates result",        "key === 'Enter'" in js_text),
    ]
    for label, ok in mobile_checks:
        results.append(("PASS" if ok else "WARN", label))

    # ── 4. nav-hub.js loads search-overlay + has trigger button ──────────────
    log("Verifying nav-hub.js auto-loads search-overlay + Cmd+K button...")
    try:
        with urllib.request.urlopen(f"{base}/nav-hub.js", timeout=10) as r:
            nav_text = r.read().decode("utf-8", errors="replace")
        nav_checks = [
            ("nav-hub auto-loads search-overlay", 'src = \'search-overlay.js\'' in nav_text or 'src = "search-overlay.js"' in nav_text),
            ("Search button id present",          'id="wh-hub-global-search"'   in nav_text),
            ("Search button calls WHSearch.open", "WHSearch.open"               in nav_text),
        ]
        for label, ok in nav_checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"nav-hub.js load skipped: {type(e).__name__}"))

    return {"results": results}
