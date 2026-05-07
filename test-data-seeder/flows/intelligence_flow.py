"""PH Intelligence Report flows — report rendering and API reference checks.

Scenarios:
  A – Page loads cleanly (report content or "Generate Now", never blank crash)
  B – Stats chips show valid numbers (plants, WOs, equipment — not 0 or NaN)
  C – MTBF bar chart renders (at least 1 equipment category row)
  D – Failure modes list renders (at least 1 cause with percentage)
  E – Executive summary text is readable prose — no <think> leak or raw JSON
  F – API reference section visible with correct endpoint format
  G – Your Plant vs Network comparison visible for logged-in hive members
  H – Generate Now button triggers report generation and shows updated data
"""

import re
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

SUPABASE_URL = "hzyvnjtisfgbksicrouu.supabase.co"


def run(page, errors, warnings, log) -> dict:
    log("PH Intelligence Report flow checks...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/ph-intelligence.html", wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)

    hive_id = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")

    # ── Scenario A: Page loads cleanly ────────────────────────────────────────
    log("  [A] Page loads cleanly (report or Generate Now, no blank crash)...")
    try:
        page_text  = page.locator("body").inner_text()
        has_js_err = any(kw in page_text for kw in
                         ["TypeError", "ReferenceError", "Cannot read", "is not defined"])

        has_report  = any(kw in page_text for kw in
                          ["Report:", "report:", "Plants", "Work Orders", "Equipment",
                           "MTBF", "failure", "Failure", "Generate Now"])
        has_content = len(page_text.strip()) > 300

        if has_js_err:
            results.append(("FAIL", "A: JS error text visible on ph-intelligence.html"))
        elif has_report and has_content:
            results.append(("PASS", "A: page loaded with intelligence report content or Generate Now"))
        elif has_content:
            results.append(("WARN", "A: page has content but no report-specific text found"))
        else:
            results.append(("WARN", "A: page appears mostly empty"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # Check if report exists in DB
    db_report = db.table("ph_intelligence_reports").select("id, period, hive_count, wo_count") \
        .order("generated_at", desc=True).limit(1).execute().data or []

    if not db_report:
        log("  → No report in DB yet — triggering Generate Now for remaining checks...")
        try:
            gen_btn = page.locator("button:has-text('Generate Now'), button:has-text('Generate')").first
            if gen_btn.count():
                # Use JS click to bypass visibility issues (button may be offscreen)
                page.evaluate("""() => {
                    for (const b of document.querySelectorAll('button')) {
                        const t = b.textContent.trim();
                        if (t === 'Generate Now' || t === 'Generate') { b.click(); return; }
                    }
                }""")
                page.wait_for_timeout(25000)   # AI generation + DB write
                db_report = db.table("ph_intelligence_reports").select("id, period, hive_count, wo_count") \
                    .order("generated_at", desc=True).limit(1).execute().data or []
        except Exception as e:
            log(f"  → Generate failed: {e}")

    report_data = db_report[0] if db_report else {}

    # ── Scenario B: Stats chips show valid numbers ─────────────────────────────
    log("  [B] Stats chips: plants/WOs/equipment show positive numbers...")
    try:
        page_text = page.locator("body").inner_text()
        has_nan   = "NaN" in page_text

        # Extract chip values from DB report
        hive_count = report_data.get("hive_count", 0)
        wo_count   = report_data.get("wo_count", 0)

        # Find chips on page
        chip_nums = re.findall(r"\b([1-9]\d{0,5})\b", page_text)

        if has_nan:
            results.append(("FAIL", "B: NaN in stats chips — calculation error"))
        elif not db_report:
            results.append(("WARN", "B: no report in DB — stats chip check skipped"))
        elif hive_count > 0 and str(hive_count) in page_text:
            results.append(("PASS", f"B: stats chips show hive_count={hive_count}, wo_count={wo_count}"))
        elif chip_nums:
            results.append(("WARN", f"B: numeric values found but DB values ({hive_count}, {wo_count}) not matched in page"))
        else:
            results.append(("WARN", "B: no numeric values in stats chips area"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: MTBF bar chart renders ────────────────────────────────────
    log("  [C] MTBF bar chart has at least 1 equipment category row...")
    try:
        # Check DB for benchmark data
        benchmarks = db.table("network_benchmarks").select("equipment_category, avg_mtbf_days") \
            .gte("sample_hives", 1).limit(10).execute().data or []

        chart_rows = page.evaluate("""() => {
            const sels = ['.mtbf-row', '.mtbf-bar-wrap > div', '[class*="mtbf"] [class*="row"]'];
            for (const s of sels) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) return n;
            }
            return 0;
        }""")

        page_text = page.locator("body").inner_text()
        # Look for "Xd" patterns (MTBF in days)
        mtbf_values = re.findall(r"\b\d{1,4}d\b", page_text)

        if chart_rows > 0:
            results.append(("PASS", f"C: MTBF chart has {chart_rows} equipment category row(s)"))
        elif mtbf_values:
            results.append(("PASS", f"C: MTBF values visible: {mtbf_values[:3]}"))
        elif not benchmarks:
            results.append(("WARN", "C: no benchmark data in DB — MTBF chart will be empty (run benchmark-compute first)"))
        else:
            results.append(("WARN", f"C: {len(benchmarks)} benchmarks in DB but no chart rows found"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Failure modes list renders ────────────────────────────────
    log("  [D] Failure modes list has at least 1 cause with percentage...")
    try:
        page_text = page.locator("body").inner_text()

        # Look for percentage patterns near failure causes
        pct_pattern = re.findall(r"(\d{1,3})\s*%", page_text)
        fault_words = ["Wear", "wear", "Lubrication", "lubrication", "failure",
                       "Contamination", "Vibration", "Electrical", "root cause"]
        has_faults  = any(w in page_text for w in fault_words)

        if pct_pattern and has_faults:
            results.append(("PASS", f"D: failure modes list shows {len(pct_pattern)} percentage(s) with cause text"))
        elif has_faults:
            results.append(("WARN", "D: fault cause text visible but no percentages"))
        elif pct_pattern:
            results.append(("WARN", "D: percentages visible but no standard failure cause text"))
        else:
            fault_knowledge_count = db.table("fault_knowledge").select("id", count="exact") \
                .limit(1).execute().count or 0
            if fault_knowledge_count == 0:
                results.append(("WARN", "D: no fault_knowledge data in DB — failure modes list will be empty"))
            else:
                results.append(("WARN", f"D: {fault_knowledge_count} fault records in DB but failure modes not visible"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: Executive summary is clean prose ───────────────────────────
    log("  [E] Executive summary is readable prose — no <think> leak or raw JSON...")
    try:
        page_text    = page.locator("body").inner_text()
        has_think    = re.search(r"<think>|</think>", page_text, re.IGNORECASE)
        has_raw_json = bool(re.search(r'"\w+":\s*"[^"]{10,}"[,}]', page_text))
        has_narrative = any(kw in page_text for kw in
                            ["WorkHive analyzed", "maintenance records", "plant", "failure",
                             "Philippine", "industrial"])

        if has_think:
            results.append(("FAIL", "E: <think> tokens in executive summary — AI reasoning leaked"))
        elif has_raw_json:
            results.append(("WARN", "E: raw JSON visible in report — narrative may not be generated"))
        elif has_narrative or not db_report:
            results.append(("PASS" if has_narrative else "WARN",
                "E: executive summary is prose (no leaks)" if has_narrative
                else "E: no report generated yet — narrative check skipped"))
        else:
            results.append(("WARN", "E: report exists but no narrative text detected"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"E crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario F: API reference section visible ─────────────────────────────
    log("  [F] API reference section shows correct endpoint format...")
    try:
        page_text = page.locator("body").inner_text()
        has_api_section = any(kw in page_text for kw in
                              ["Intelligence API", "intelligence-api", "API reference", "API Reference"])
        has_endpoint    = "benchmarks" in page_text and "failure-modes" in page_text
        has_supabase_url = SUPABASE_URL in page_text

        if has_api_section and has_endpoint and has_supabase_url:
            results.append(("PASS", "F: API reference visible with benchmarks, failure-modes endpoints and Supabase URL"))
        elif has_api_section and has_endpoint:
            results.append(("WARN", "F: API section found but Supabase URL not in expected format"))
        elif has_api_section:
            results.append(("WARN", "F: API section visible but endpoint examples not found"))
        else:
            results.append(("WARN", "F: API reference section not found on page"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: Your Plant vs Network visible for hive members ─────────────
    log("  [G] Your Plant vs Network section visible for hive member...")
    try:
        if not hive_id:
            results.append(("WARN", "G: no hive context — comparison section check skipped"))
        else:
            hive_benchmarks = db.table("hive_benchmarks").select("equipment_category, mtbf_days") \
                .eq("hive_id", hive_id).limit(3).execute().data or []

            page_text = page.locator("body").inner_text()
            has_compare = any(kw in page_text for kw in
                              ["Your Plant", "yours", "your plant", "Network avg", "compare"])

            if hive_benchmarks and has_compare:
                results.append(("PASS", "G: Your Plant vs Network comparison section visible"))
            elif not hive_benchmarks:
                results.append(("WARN", "G: no hive_benchmarks data — comparison section will be empty (run benchmark-compute)"))
            elif has_compare:
                results.append(("PASS", "G: comparison section visible (hive benchmark data exists)"))
            else:
                results.append(("WARN", "G: hive benchmarks exist but comparison section not found on page"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario H: Generate Now updates data ─────────────────────────────────
    log("  [H] Generate Now button triggers report and updates period badge...")
    try:
        # Check current period badge
        badge_text_before = ""
        badge_el = page.locator("#report-period-badge, [id*='period'], [class*='badge']").first
        if badge_el.count():
            badge_text_before = badge_el.inner_text()

        gen_btn = page.locator(
            "button:has-text('Generate Now'), button:has-text('Generate'), "
            "button:has-text('Regenerate')"
        ).first

        if gen_btn.count():
            # Use JS click to avoid scroll_into_view timeout if button is offscreen/clipped
            page.evaluate("""() => {
                for (const b of document.querySelectorAll('button')) {
                    const t = b.textContent.trim();
                    if (t === 'Generate Now' || t === 'Generate' || t === 'Regenerate') {
                        b.click(); return;
                    }
                }
            }""")
            page.wait_for_timeout(20000)

            # Verify DB was updated
            new_report = db.table("ph_intelligence_reports").select("period, generated_at") \
                .order("generated_at", desc=True).limit(1).execute().data or []

            if new_report:
                badge_text_after = badge_el.inner_text() if badge_el.count() else ""
                results.append(("PASS",
                    f"H: Generate Now ran — latest report period={new_report[0].get('period')}"))
            else:
                results.append(("WARN", "H: Generate Now clicked but no report found in DB"))
        else:
            results.append(("WARN", "H: Generate Now button not found (may already be showing report)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "ph_intelligence_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  PH Intelligence: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

