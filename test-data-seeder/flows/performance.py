"""Performance budget flow — measures page load timings against fixed budgets.

For each public page, capture:
  domContentLoaded — HTML + CSS parsed (before images / async JS)
  load             — fully loaded incl. images + sync JS
  firstContentfulPaint — first time anything is painted

A page FAILs if it exceeds any budget. Future regressions get caught
before they ship.

Budgets are intentionally relaxed for a feature-rich industrial app on
local Supabase (which is not optimized like prod). Tighten as you optimize.
"""
import json
from pathlib import Path

from .harness import BASE_URL, sign_in

PAGES = [
    "hive.html", "logbook.html", "inventory.html", "pm-scheduler.html",
    "analytics.html", "analytics-report.html", "skillmatrix.html", "community.html",
    "marketplace.html", "dayplanner.html", "engineering-design.html",
    "report-sender.html",
]

# All in milliseconds
BUDGETS = {
    "domContentLoaded": 2500,
    "load": 6000,
    "firstContentfulPaint": 3000,
}

PERF_HISTORY_DIR = Path(__file__).resolve().parent.parent / ".tmp" / "perf_history"
PERF_HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _measure(page) -> dict:
    """Pull navigation + paint timings via the Performance API."""
    return page.evaluate("""() => {
        const nav = performance.getEntriesByType('navigation')[0] || {};
        const paint = performance.getEntriesByType('paint');
        const fcp = paint.find(p => p.name === 'first-contentful-paint');
        return {
            domContentLoaded: nav.domContentLoadedEventEnd ? Math.round(nav.domContentLoadedEventEnd - nav.startTime) : null,
            load:             nav.loadEventEnd            ? Math.round(nav.loadEventEnd - nav.startTime)            : null,
            firstContentfulPaint: fcp ? Math.round(fcp.startTime) : null,
        };
    }""")


def run_in_perf_browser(playwright, log) -> dict:
    results = []
    history: dict = {}

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()

    try:
        sign_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"perf sign-in failed: {e}")]}

    log("Performance budgets — measuring page load timings...")

    for filename in PAGES:
        try:
            page.goto(f"{BASE_URL}/workhive/{filename}", wait_until="load", timeout=20000)
            page.wait_for_timeout(500)
            metrics = _measure(page)
        except Exception as e:
            results.append(("FAIL", f"{filename}: navigation error: {e}"))
            continue

        # Validate metrics
        if not all(metrics.get(k) is not None for k in BUDGETS):
            results.append(("WARN", f"{filename}: incomplete metrics: {metrics}"))
            continue

        # Check each budget
        violations = []
        for metric, budget in BUDGETS.items():
            value = metrics[metric]
            if value > budget:
                violations.append(f"{metric}={value}ms (budget {budget}ms)")

        history[filename] = metrics
        line = ", ".join(f"{k}={v}ms" for k, v in metrics.items())

        if violations:
            results.append((
                "FAIL",
                f"{filename}: over budget: {' | '.join(violations)}. Full metrics: {line}",
            ))
            log(f"  ✗ {filename}: BUDGET BUSTED — {' | '.join(violations)}")
        else:
            margins = [f"{m}={metrics[m]}/{BUDGETS[m]}ms" for m in BUDGETS]
            results.append(("PASS", f"{filename}: {' '.join(margins)}"))
            log(f"  ✓ {filename}: {line}")

    # Persist history (latest run's metrics) for trend reference
    try:
        from datetime import datetime, timezone
        history_path = PERF_HISTORY_DIR / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
        history_path.write_text(json.dumps(history, indent=2))
        # Keep only last 20 runs
        all_runs = sorted(PERF_HISTORY_DIR.glob("*.json"))
        for old in all_runs[:-20]:
            old.unlink()
    except Exception as e:
        log(f"  WARN: could not save perf history: {e}")

    context.close()
    browser.close()
    return {"results": results}
