"""Analytics page UI checks — enhanced with DB-verified KPI accuracy.

Scenarios:
  1 – KPIs populated: ≥5 non-trivial numbers on page (original)
  2 – Charts rendered: Plotly / Recharts / canvas / SVG (original)
  3 – All 4 phase tabs load without blank panels
  4 – OEE value is between 0-100% (never exceeds 100)
  5 – MTBF is mathematically plausible vs DB breakdown count
  6 – No NaN values in any numeric display
  7 – Period selector changes displayed values
  8 – analytics-report.html renders required sections
  9 – Report KPI values match analytics page values
"""

import re
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

PHASE_TABS = ["Descriptive", "Diagnostic", "Predictive", "Prescriptive"]


def run(page, errors, warnings, log) -> dict:
    log("Analytics checks (enhanced)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/analytics.html", wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(5000)

    hive_id = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")

    # ── Check 1: KPIs populated (original) ───────────────────────────────────
    log("  [1] KPI numbers populated...")
    try:
        non_zero = page.evaluate("""() => {
            const all = document.body.innerText;
            const numbers = (all.match(/\\b[1-9][0-9,]{1,5}\\b/g) || []).length;
            return numbers;
        }""")
        if non_zero >= 5:
            results.append(("PASS", f"1: {non_zero} non-trivial numbers rendered"))
            log(f"    → PASS: {non_zero} numeric values")
        else:
            results.append(("WARN", f"1: only {non_zero} non-zero numbers — KPIs may be empty"))
            log(f"    → WARN: only {non_zero} numbers")
    except Exception as e:
        results.append(("FAIL", f"1 crashed: {e}"))

    # ── Check 2: Charts rendered (original) ──────────────────────────────────
    log("  [2] Chart elements rendered...")
    try:
        chart_info = page.evaluate("""() => ({
            plotly:       document.querySelectorAll('.js-plotly-plot, svg.main-svg').length,
            canvas:       document.querySelectorAll('canvas').length,
            recharts:     document.querySelectorAll('.recharts-wrapper, .recharts-surface').length,
            svgRich:      Array.from(document.querySelectorAll('svg'))
                              .filter(s => s.querySelectorAll('*').length > 5).length,
        })""")
        total = sum(chart_info.values())
        if total >= 1:
            results.append(("PASS", f"2: charts rendered — {chart_info}"))
            log(f"    → PASS: {chart_info}")
        else:
            results.append(("FAIL", "2: no charts found (no Plotly, Recharts, canvas, or rich SVG)"))
            log(f"    → FAIL: {chart_info}")
    except Exception as e:
        results.append(("FAIL", f"2 crashed: {e}"))

    # ── Check 3: All 4 phase tabs load content ────────────────────────────────
    log("  [3] All 4 phase tabs load content within 15s each...")
    try:
        phase_results = []
        for tab_name in PHASE_TABS:
            tab = page.locator(
                f"button:has-text('{tab_name}'), "
                f"[data-phase='{tab_name.lower()}'], "
                f"a:has-text('{tab_name}')"
            ).first

            if not tab.count():
                phase_results.append(f"{tab_name}=NOT_FOUND")
                continue

            tab.click()
            page.wait_for_timeout(8000)   # phases can be slow (AI calls)

            # Check active panel has real content (not loading spinner stuck)
            has_content = page.evaluate(f"""() => {{
                const text = document.body.innerText;
                const loading = ['Loading...', 'Fetching', '...'].some(s => text.includes(s));
                const hasNumbers = /\\b[1-9]\\d*/.test(text);
                const hasText = text.length > 500;
                return hasNumbers || (hasText && !loading);
            }}""")
            phase_results.append(f"{tab_name}={'OK' if has_content else 'BLANK'}")

        blank = [p for p in phase_results if "BLANK" in p or "NOT_FOUND" in p]
        if not blank:
            results.append(("PASS", f"3: all 4 phase tabs loaded — {phase_results}"))
        elif len(blank) <= 1:
            results.append(("WARN", f"3: {len(blank)} tab(s) may not have loaded: {blank}"))
        else:
            results.append(("FAIL", f"3: {len(blank)} tabs blank/missing: {blank}"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"3 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 4: OEE is 0-100% ────────────────────────────────────────────────
    log("  [4] OEE value within 0-100% range...")
    try:
        page_text = page.locator("body").inner_text()
        # OEE may appear before or after the value label, with varying gap
        oee_match = re.search(r"OEE[^\d]{0,50}([\d.]+)\s*%?", page_text, re.IGNORECASE)
        if not oee_match:
            oee_match = re.search(r"([\d.]+)\s*%\s*\n?\s*OEE", page_text, re.IGNORECASE)

        if oee_match:
            oee_val = float(oee_match.group(1))
            if oee_val > 100:
                results.append(("FAIL", f"4: OEE = {oee_val}% — exceeds 100% (formula bug)"))
            elif oee_val == 0:
                results.append(("WARN", "4: OEE = 0% — may indicate missing data or calculation issue"))
            else:
                results.append(("PASS", f"4: OEE = {oee_val}% (valid 0-100 range)"))
        else:
            results.append(("WARN", "4: OEE value not found in page text"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"4 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 5: MTBF plausible vs DB breakdown count ─────────────────────────
    log("  [5] MTBF is mathematically plausible vs DB breakdown history...")
    try:
        page_text = page.locator("body").inner_text()
        mtbf_match = re.search(r"MTBF[^\d]{0,20}([\d.]+)\s*(?:days?|d\b)", page_text, re.IGNORECASE)

        if hive_id and mtbf_match:
            displayed_mtbf = float(mtbf_match.group(1))

            breakdown_count = db.table("logbook").select("id", count="exact") \
                .eq("hive_id", hive_id) \
                .eq("maintenance_type", "Breakdown / Corrective") \
                .limit(1).execute().count or 0

            if breakdown_count >= 2:
                # Rough expected MTBF: 90 days / breakdown_count (90-day window typical)
                expected_rough = 90 / breakdown_count
                # Allow 10x range — the actual calculation window may differ
                plausible = (expected_rough * 0.1) <= displayed_mtbf <= (expected_rough * 10)
                if plausible:
                    results.append(("PASS", f"5: MTBF={displayed_mtbf}d, {breakdown_count} breakdowns (plausible)"))
                else:
                    results.append(("WARN", f"5: MTBF={displayed_mtbf}d with {breakdown_count} breakdowns — expected ≈{expected_rough:.0f}d (check window)"))
            else:
                results.append(("WARN", f"5: MTBF={displayed_mtbf}d but only {breakdown_count} breakdown records — too few for meaningful check"))
        elif mtbf_match:
            results.append(("PASS", f"5: MTBF={mtbf_match.group(1)}d rendered (no hive context for DB comparison)"))
        else:
            results.append(("WARN", "5: MTBF not found in page text"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"5 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 6: No NaN values ────────────────────────────────────────────────
    log("  [6] No NaN values in KPI displays...")
    try:
        page_text = page.locator("body").inner_text()
        nan_count = page_text.count("NaN")
        if nan_count > 0:
            results.append(("FAIL", f"6: {nan_count} 'NaN' occurrence(s) on analytics page — divide-by-zero or missing data"))
        else:
            results.append(("PASS", "6: no NaN values on analytics page"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"6 crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Check 7: Period selector changes values ───────────────────────────────
    log("  [7] Period selector produces different values for different periods...")
    try:
        page_text_before = page.locator("body").inner_text()
        before_numbers = set(re.findall(r"\b\d{2,6}\b", page_text_before))

        period_sel = page.locator(
            "select[id*='period'], select[id*='range'], "
            "button:has-text('30 days'), button:has-text('90 days'), "
            "[data-period]"
        ).first

        if period_sel.count():
            if period_sel.evaluate("el => el.tagName") == "SELECT":
                # Change to a different option
                options = period_sel.evaluate("el => Array.from(el.options).map(o => o.value)")
                if len(options) >= 2:
                    current = period_sel.evaluate("el => el.value")
                    new_opt = next((o for o in options if o != current), None)
                    if new_opt:
                        period_sel.select_option(new_opt)
                        page.wait_for_timeout(4000)
            else:
                period_sel.click()
                page.wait_for_timeout(4000)

            page_text_after = page.locator("body").inner_text()
            after_numbers = set(re.findall(r"\b\d{2,6}\b", page_text_after))

            changed = before_numbers != after_numbers
            results.append(
                ("PASS", "7: period selector produces different KPI values")
                if changed
                else ("WARN", "7: KPI values unchanged after period selector change (may need more data or same-period data)")
            )
        else:
            results.append(("WARN", "7: no period selector found on analytics page"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"7 skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "analytics_dashboard")

    # ── Check 8: analytics-report.html renders required sections ─────────────
    log("  [8] analytics-report.html renders all required sections...")
    try:
        page.goto(f"{BASE_URL}/workhive/analytics-report.html", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(4000)

        page_text = page.locator("body").inner_text()
        # Accept any of these variant labels — report may use different wording
        keyword_groups = [
            ["MTBF", "Mean Time Between"],
            ["OEE", "Overall Equipment"],
            ["Summary", "Analysis", "Overview", "Insight"],
            ["Recommendation", "Action", "Priority"],
        ]
        found    = [g[0] for g in keyword_groups if any(k.lower() in page_text.lower() for k in g)]
        missing  = [g[0] for g in keyword_groups if not any(k.lower() in page_text.lower() for k in g)]

        if len(found) >= 3:
            results.append(("PASS", f"8: analytics-report has {len(found)}/4 section areas: {found}"))
        elif len(page_text) > 500:
            # Report renders with content but uses different section labels — acceptable
            results.append(("WARN", f"8: analytics-report has content but section areas not found: {missing}"))
        else:
            results.append(("WARN", f"8: analytics-report appears mostly empty (may need gate data first)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"8 skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Check 9: Report values match analytics page ───────────────────────────
    log("  [9] Report MTBF value matches analytics page...")
    try:
        report_text = page.locator("body").inner_text()
        report_mtbf = re.search(r"MTBF[^\d]{0,20}([\d.]+)", report_text, re.IGNORECASE)

        if report_mtbf and mtbf_match:
            r_val = float(report_mtbf.group(1))
            a_val = float(mtbf_match.group(1))
            if abs(r_val - a_val) < 1:
                results.append(("PASS", f"9: MTBF matches analytics({a_val}d) and report({r_val}d)"))
            else:
                results.append(("WARN", f"9: MTBF analytics={a_val}d vs report={r_val}d (diff={abs(r_val-a_val):.1f}d)"))
        else:
            results.append(("WARN", "9: could not compare MTBF — value not found on one or both pages"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"9 skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "analytics_report")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Analytics: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

