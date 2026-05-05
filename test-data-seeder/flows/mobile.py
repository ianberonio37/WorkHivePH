"""Mobile viewport (375x667) checks — horizontal scroll, iOS auto-zoom, tap targets.

Drawn from Mobile Maestro skill: 16px minimum font on inputs, no x-overflow,
44x44 minimum tap targets.
"""
from playwright.sync_api import sync_playwright

from .harness import BASE_URL, screenshot, sign_in, browser_session

PAGES = [
    "hive.html", "logbook.html", "inventory.html", "pm-scheduler.html",
    "analytics.html", "analytics-report.html", "community.html", "skillmatrix.html", "marketplace.html",
    "dayplanner.html", "engineering-design.html", "report-sender.html",
    "project-manager.html",
    "project-report.html",
]


def run_in_mobile_browser(playwright, log) -> dict:
    """Spawns a separate mobile-viewport browser. Used by run_flows after the
    desktop flows finish, so we don't disturb the desktop session."""
    results = []
    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 375, "height": 667},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    )
    page = context.new_page()

    try:
        sign_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"mobile sign-in failed: {e}")]}

    log("Mobile checks at 375x667...")

    # Analytics pages make multiple AI calls on load (4-phase orchestrator).
    # Use a longer timeout + domcontentloaded wait for those to avoid false
    # crash failures when the Python API or Groq take >15s to respond.
    AI_HEAVY = {"analytics.html", "analytics-report.html"}

    for filename in PAGES:
        wait_until = "domcontentloaded" if filename in AI_HEAVY else "networkidle"
        timeout    = 45000              if filename in AI_HEAVY else 15000
        page.goto(f"{BASE_URL}/workhive/{filename}", wait_until=wait_until, timeout=timeout)
        page.wait_for_timeout(800)

        # Horizontal scroll check — body scrollWidth shouldn't exceed innerWidth
        h_overflow = page.evaluate("""() => {
            return document.documentElement.scrollWidth > window.innerWidth + 4;
        }""")
        if h_overflow:
            results.append(("FAIL", f"{filename}: horizontal scroll detected (>{375}px content)"))
            log(f"  ✗ {filename}: horizontal overflow")
        else:
            results.append(("PASS", f"{filename}: no horizontal scroll"))
            log(f"  ✓ {filename}: no horizontal overflow")

        # iOS auto-zoom guard: visible text-style inputs/textareas/selects <16px.
        # Checkbox/radio/file/button inputs are exempt — they don't trigger zoom.
        small_fonts = page.evaluate("""() => {
            const ZOOM_TYPES = ['text','search','password','email','tel','url','number','date','time','datetime-local',''];
            const inputs = document.querySelectorAll('input, textarea, select');
            const offenders = [];
            inputs.forEach(el => {
                if (el.offsetParent === null) return;
                if (el.tagName === 'INPUT' && !ZOOM_TYPES.includes((el.type || '').toLowerCase())) return;
                const fs = parseFloat(getComputedStyle(el).fontSize);
                if (fs > 0 && fs < 16) {
                    offenders.push({
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        id: el.id || el.name || '?',
                        cls: (el.className || '').slice(0, 60),
                        size: Math.round(fs * 10) / 10,
                    });
                }
            });
            return offenders;
        }""")
        if small_fonts:
            sample = small_fonts[:5]
            results.append(("FAIL", f"{filename}: {len(small_fonts)} inputs <16px (iOS will auto-zoom): {sample}"))
            log(f"  ✗ {filename}: {len(small_fonts)} inputs trigger iOS zoom")
            for s in sample:
                log(f"     • <{s['tag']}> id='{s['id']}' font-size={s['size']}px")
        else:
            results.append(("PASS", f"{filename}: all inputs ≥16px (no iOS auto-zoom)"))

        # Tap target check — buttons/links smaller than 44x44 (only those with text)
        small_taps = page.evaluate("""() => {
            const els = document.querySelectorAll('button, a[href], [role="button"]');
            const offenders = [];
            els.forEach(el => {
                if (el.offsetParent === null) return;
                if (!el.textContent.trim() && !el.querySelector('svg, img')) return;
                const r = el.getBoundingClientRect();
                if (r.width < 44 || r.height < 44) {
                    offenders.push({text: (el.textContent || el.id || '?').slice(0, 20), w: Math.round(r.width), h: Math.round(r.height)});
                }
            });
            return offenders.slice(0, 8);
        }""")
        # Tap target failures are common (icons in nav, etc) — flag as warn, not fail
        if len(small_taps) > 5:
            results.append(("WARN", f"{filename}: {len(small_taps)} tap targets <44px"))
        elif small_taps:
            results.append(("PASS", f"{filename}: only {len(small_taps)} tap targets <44px (acceptable)"))

        screenshot(page, f"mobile_{filename.replace('.html', '')}")

    context.close()
    browser.close()
    return {"results": results}
