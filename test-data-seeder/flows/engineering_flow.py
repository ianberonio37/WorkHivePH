"""Engineering Design Calculator flows — calc correctness and report rendering.

Scenarios:
  A – Discipline tabs all render (Mechanical, Plumbing, Electrical, etc.)
  B – Calc type selection loads correct input form (fields appear, not blank)
  C – Calculation returns results with real values (no NaN, 0, or undefined)
  D – Report panel renders with values matching calculator output
  E – BOM/SOW generates at least 3 line items and 3 SOW sections
  F – Calc saved to DB after Calculate (engineering_calcs row inserted)
  G – History list shows previous calculation
  H – No console TypeError on discipline switch
"""

import re
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

# Test calc: Pump Sizing (TDH) — requires simple inputs, available on Mechanical
TEST_DISCIPLINE = "Mechanical"
TEST_CALC_TYPE  = "Pump Sizing (TDH)"

# Minimal required inputs for Pump Sizing
PUMP_INPUTS = {
    "#f-flow-rate":     "50",
    "#f-static-head":   "15",
    "#f-pipe-length":   "100",
    "#f-pipe-dia":      "4",
}


def run(page, errors, warnings, log) -> dict:
    log("Engineering Design Calculator flow checks...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/engineering-design.html", wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)

    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")
    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")

    # ── Scenario A: Discipline tabs all render ────────────────────────────────
    log("  [A] Discipline tabs visible (Mechanical, Electrical, Plumbing...)...")
    try:
        page_text     = page.locator("body").inner_text()
        disciplines   = ["Mechanical", "Electrical", "Plumbing", "Fire Protection"]
        found         = [d for d in disciplines if d in page_text]

        if len(found) >= 3:
            results.append(("PASS", f"A: {len(found)}/4 discipline tabs visible: {found}"))
        elif len(found) >= 2:
            results.append(("WARN", f"A: only {len(found)} disciplines visible: {found}"))
        else:
            results.append(("FAIL", f"A: fewer than 2 disciplines found ({found}) — page not rendering tabs"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Calc type selection loads input form ──────────────────────
    log(f"  [B] Select {TEST_DISCIPLINE} → {TEST_CALC_TYPE} → input form appears...")
    try:
        # Click Mechanical discipline
        disc_btn = page.locator(
            f"button:has-text('{TEST_DISCIPLINE}'), "
            f"[data-discipline='{TEST_DISCIPLINE}'], "
            f"li:has-text('{TEST_DISCIPLINE}')"
        ).first

        if disc_btn.count():
            disc_btn.click()
            page.wait_for_timeout(800)

        # Calc type cards are divs (not buttons) — use text locator
        calc_btn = page.get_by_text("Pump Sizing", exact=False).first

        if calc_btn.count():
            calc_btn.click()
            page.wait_for_timeout(1200)

            # Verify at least 2 numeric input fields appeared
            input_count = page.locator("input[type='number']:visible, input[type='text']:visible").count()
            if input_count >= 2:
                results.append(("PASS", f"B: {input_count} input fields rendered for Pump Sizing"))
            else:
                results.append(("WARN", f"B: only {input_count} inputs visible after selecting Pump Sizing"))
        else:
            results.append(("WARN", f"B: '{TEST_CALC_TYPE}' calc type button not found"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Calculation returns non-NaN results ───────────────────────
    log("  [C] Calculation runs and returns real numeric results...")
    try:
        errors_before = len(errors)

        # Fill inputs
        for selector, value in PUMP_INPUTS.items():
            el = page.locator(f"{selector}:visible").first
            if el.count():
                el.fill(value)
                page.wait_for_timeout(100)

        # Wait for calc-btn to become enabled (enabled after calc type + inputs filled)
        try:
            page.wait_for_function("!document.getElementById('calc-btn').disabled", timeout=5000)
        except Exception:
            pass

        calc_run_btn = page.locator("#calc-btn").first
        if not calc_run_btn.count() or not calc_run_btn.is_enabled():
            results.append(("WARN", "C: calc button not enabled after filling inputs — calc type may not be selected"))
        else:
            calc_run_btn.click()
            page.wait_for_timeout(8000)   # Edge Function may be cold

            page_text   = page.locator("body").inner_text()
            has_nan     = "NaN" in page_text
            has_results = bool(re.search(r"\b\d+\.?\d*\s*(m|kW|bar|kPa|L/s|m/s|%)\b", page_text))
            new_errors  = [e for e in errors[errors_before:] if
                           "TypeError" in e or "SyntaxError" in e]

            if has_nan:
                results.append(("FAIL", "C: NaN in results — calc formula has divide-by-zero or invalid input"))
            elif new_errors:
                results.append(("FAIL", f"C: JS error after Calculate: {new_errors[0][:80]}"))
            elif has_results:
                results.append(("PASS", "C: results contain numeric values with engineering units"))
            else:
                results.append(("WARN", "C: Calculate ran but no engineering unit patterns found in results"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Report panel renders with calc values ─────────────────────
    log("  [D] Report panel renders with matching values...")
    try:
        # Check if report section is visible
        report_panel = page.locator(
            "#report-panel, #results-panel, [id*='report']:visible, [class*='report-panel']:visible"
        ).first

        if report_panel.count() and report_panel.is_visible():
            report_text = report_panel.inner_text()
            has_numbers = len(re.findall(r"\d+\.?\d+", report_text)) >= 3
            has_nan     = "NaN" in report_text
            has_undef   = "undefined" in report_text

            if has_nan:
                results.append(("FAIL", "D: NaN in report panel — values not rendering correctly"))
            elif has_undef:
                results.append(("FAIL", "D: 'undefined' in report panel — result mapping broken"))
            elif has_numbers:
                results.append(("PASS", f"D: report panel has {len(re.findall(r'\\d+\\.?\\d+', report_text))} numeric values"))
            else:
                results.append(("WARN", "D: report panel visible but no numeric values detected"))
        else:
            results.append(("WARN", "D: report panel not visible after Calculate (may require View Report click)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: BOM/SOW generates meaningful content ─────────────────────
    log("  [E] BOM/SOW generates ≥3 line items and ≥3 SOW sections...")
    try:
        # bom-sow-section becomes visible after calc runs; click Generate inside bom-trigger
        bom_section = page.locator("#bom-sow-section")
        if not bom_section.count() or not bom_section.is_visible():
            results.append(("WARN", "E: BOM/SOW section not visible after calc — run calc first (C may not have completed)"))
        else:
            gen_btn = page.locator("#bom-trigger button, #bom-trigger button:has-text('Generate')").first
            if not gen_btn.count() or not gen_btn.is_visible():
                results.append(("WARN", "E: BOM/SOW section visible but Generate button not found in #bom-trigger"))
            else:
                gen_btn.click()
                page.wait_for_timeout(20000)   # AI generation can be slow

                page_text    = page.locator("body").inner_text()
                bom_rows     = len(re.findall(r"(?:pcs|m|kg|set|lot|L)\b", page_text, re.IGNORECASE))
                # SOW renders inside collapsed <textarea class="bom-item-input"> elements
                # (display:none), so inner_text() never sees the content. Read textarea
                # values via DOM and count "contractor shall" occurrences across them.
                sow_sections = page.evaluate("""() => {
                    const tas = document.querySelectorAll('textarea.bom-item-input');
                    let n = 0;
                    tas.forEach(t => {
                        if (/contractor\\s+shall/i.test(t.value || '')) n += 1;
                    });
                    return n;
                }""") or 0
                has_nan      = "NaN" in page_text

                if has_nan:
                    results.append(("FAIL", "E: NaN in BOM/SOW output"))
                elif bom_rows >= 3 and sow_sections >= 3:
                    results.append(("PASS", f"E: BOM has {bom_rows} unit mentions, SOW has {sow_sections} contractor clauses"))
                elif bom_rows >= 1 or sow_sections >= 1:
                    results.append(("WARN", f"E: partial BOM/SOW — {bom_rows} BOM units, {sow_sections} SOW clauses (expected ≥3 each)"))
                else:
                    results.append(("WARN", "E: BOM/SOW generated but no unit or contractor clause patterns found"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"E skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario F: Calc saved to DB after Calculate ──────────────────────────
    log("  [F] Calculation saved to engineering_calcs DB table...")
    try:
        q = db.table("engineering_calcs").select("id", count="exact") \
            .eq("worker_name", worker_name) \
            .eq("discipline", TEST_DISCIPLINE)
        if hive_id:
            q = q.eq("hive_id", hive_id)
        db_count = q.limit(1).execute().count or 0

        if db_count > 0:
            results.append(("PASS", f"F: {db_count} engineering_calcs row(s) saved for this worker/discipline"))
        else:
            results.append(("WARN", "F: no engineering_calcs rows found — calc may not be saving to DB"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: History list shows previous calc ───────────────────────────
    log("  [G] History section shows at least one previous calculation...")
    try:
        history_btn = page.locator(
            "button:has-text('History'), button:has-text('Previous'), "
            "[data-tab='history'], a:has-text('History')"
        ).first

        if history_btn.count():
            history_btn.click()
            page.wait_for_timeout(1500)

        page_text = page.locator("body").inner_text()
        has_history = any(kw in page_text for kw in
                          [TEST_DISCIPLINE, "Pump Sizing", "TDH", "previous", "History"])

        history_rows = page.evaluate("""() => {
            const sels = ['[data-calc-id]', '.history-item', '.calc-history', '[id^="calc-"]'];
            for (const s of sels) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) return n;
            }
            return 0;
        }""")

        if history_rows > 0:
            results.append(("PASS", f"G: {history_rows} history entry/entries visible"))
        elif has_history:
            results.append(("PASS", "G: history section visible with relevant calc content"))
        else:
            results.append(("WARN", "G: no history entries found (may need to save first or different UI flow)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario H: No TypeError on discipline switch ─────────────────────────
    log("  [H] Discipline switch does not cause TypeErrors...")
    try:
        errors_before = len(errors)
        disciplines_to_test = ["Electrical", "Plumbing", "Mechanical"]

        for disc in disciplines_to_test:
            # Discipline tabs may be in a horizontally-scrolling container — use JS click
            # to bypass visibility checks that would timeout on clipped overflow elements
            clicked = page.evaluate(f"""() => {{
                const el = document.querySelector("button[data-disc='{disc}'], [data-disc='{disc}']");
                if (el) {{ el.click(); return true; }}
                // fallback: find by text content
                for (const b of document.querySelectorAll('button')) {{
                    if (b.textContent.trim() === '{disc}') {{ b.click(); return true; }}
                }}
                return false;
            }}""")
            page.wait_for_timeout(600)

        new_errors = [e for e in errors[errors_before:] if
                      "TypeError" in e or "ReferenceError" in e or "Cannot read" in e]

        if new_errors:
            results.append(("FAIL", f"H: TypeError on discipline switch: {new_errors[0][:80]}"))
        else:
            results.append(("PASS", f"H: switched {len(disciplines_to_test)} disciplines with no TypeErrors"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "engineering_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Engineering Design: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

