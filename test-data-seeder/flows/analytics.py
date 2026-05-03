"""Analytics page UI checks."""
from .harness import BASE_URL, screenshot


def run(page, errors, warnings, log) -> dict:
    log("Analytics UI checks...")
    results = []

    page.goto(f"{BASE_URL}/workhive/analytics.html", wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(5000)  # charts take a bit

    # Check 1: at least one numeric KPI rendered (not "—" or "0")
    try:
        non_zero = page.evaluate("""() => {
            const all = document.body.innerText;
            const numbers = (all.match(/\\b[1-9][0-9,]{1,5}\\b/g) || []).length;
            return numbers;
        }""")
        if non_zero >= 5:
            results.append(("PASS", f"page shows {non_zero} non-trivial numbers (KPIs likely populated)"))
            log(f"  ✓ analytics has {non_zero} numeric values rendered")
        else:
            results.append(("WARN", f"only {non_zero} non-zero numbers — KPIs may be empty"))
    except Exception as e:
        results.append(("FAIL", f"KPI presence crashed: {e}"))

    # Check 2: chart elements present (Plotly, Recharts, canvas, svg)
    try:
        chart_info = page.evaluate("""() => {
            return {
                plotly: document.querySelectorAll('.js-plotly-plot, svg.main-svg').length,
                canvas: document.querySelectorAll('canvas').length,
                recharts: document.querySelectorAll('.recharts-wrapper, .recharts-surface').length,
                svgWith100Plus: Array.from(document.querySelectorAll('svg')).filter(s => s.querySelectorAll('*').length > 5).length,
            };
        }""")
        total = chart_info["plotly"] + chart_info["canvas"] + chart_info["recharts"] + chart_info["svgWith100Plus"]
        if total >= 1:
            results.append(("PASS", f"chart elements found: {chart_info}"))
            log(f"  ✓ chart elements present: {chart_info}")
        else:
            results.append(("FAIL", "no charts rendered (no Plotly, Recharts, canvas, or non-trivial SVG)"))
            log(f"  ✗ no charts rendered (analyzed: {chart_info})")
    except Exception as e:
        results.append(("FAIL", f"chart check crashed: {e}"))

    screenshot(page, "analytics_dashboard")
    return {"results": results}
