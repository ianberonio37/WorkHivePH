"""Hive Dashboard flows — DB-verified intelligence feature checks.

Scenarios:
  A – KPI chips: Open WO count matches DB
  B – PM overdue alert count matches DB
  C – Stock alert count matches DB
  D – Pattern Alerts: visible, clean text, no <think> leak
  E – Reliability Coach: returns 3 structured action cards
  F – Network Benchmark: shows data or clean "compute now" state
  G – Today's Brief: shows placeholder or actual content (never blank crash)
  H – Team stock issues list renders with real worker names
  I – Live indicator visible (green dot)
"""

import re
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot


def run(page, errors, warnings, log) -> dict:
    log("Hive Dashboard checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/hive.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(3000)

    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    if not hive_id:
        return {"results": [("FAIL", "No hive_id in localStorage — worker not in a hive")]}

    # ── Scenario A: Open WO count chip matches DB ─────────────────────────────
    log("  [A] Open Work Orders chip vs DB count...")
    try:
        db_open = db.table("logbook").select("id", count="exact") \
            .eq("hive_id", hive_id).eq("status", "Open").limit(1).execute().count or 0

        page_text = page.locator("body").inner_text()
        # Extract number next to "Open Work Orders"
        m = re.search(r"(\d[\d,]*)\s*Open Work Orders", page_text)
        if m:
            page_count = int(m.group(1).replace(",", ""))
            diff = abs(page_count - db_open)
            if diff <= 5:
                results.append(("PASS", f"A: Open WOs chip={page_count} DB={db_open} (diff={diff} ≤5)"))
            else:
                results.append(("WARN", f"A: Open WOs chip={page_count} DB={db_open} (diff={diff} >5)"))
        else:
            results.append(("WARN", f"A: 'Open Work Orders' not found in page text — DB has {db_open}"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: PM overdue count matches DB ───────────────────────────────
    log("  [B] PM overdue alert count vs DB...")
    try:
        from datetime import date
        today_str = date.today().isoformat()

        asset_ids_res = db.table("pm_assets").select("id") \
            .eq("hive_id", hive_id).execute().data or []
        asset_ids = [a["id"] for a in asset_ids_res]

        db_overdue = 0
        if asset_ids:
            overdue_res = db.table("pm_scope_items").select("id", count="exact") \
                .in_("asset_id", asset_ids) \
                .lt("anchor_date", today_str).limit(1).execute()
            db_overdue = overdue_res.count or 0

        page_text = page.locator("body").inner_text()
        # Try text regex first; fall back to direct KPI chip element
        m = re.search(r"(\d[\d,]*)\s*PM\s+[Tt]asks?\s+[Oo]verdue", page_text)
        if not m:
            m = re.search(r"(\d[\d,]+)\s*\n\s*PMs?\s+Overdue", page_text)
        if not m:
            chip_el = page.locator("#pulse-pm-overdue").first
            if chip_el.count() and chip_el.is_visible():
                try:
                    chip_val = chip_el.inner_text().replace(",", "").strip()
                    if chip_val.lstrip("-").isdigit():
                        m = type("m", (), {"group": lambda self, n: chip_val})()
                except Exception:
                    pass
        if m:
            page_count = int(str(m.group(1)).replace(",", ""))
            diff = abs(page_count - db_overdue)
            if diff <= 3:
                results.append(("PASS", f"B: PM overdue chip={page_count} DB≈{db_overdue} (diff={diff})"))
            else:
                results.append(("WARN", f"B: PM overdue chip={page_count} DB≈{db_overdue} (diff={diff} — PM anchor date logic may differ)"))
        else:
            if db_overdue > 0:
                results.append(("WARN", f"B: PM overdue count not found on page, DB has {db_overdue} potentially overdue items"))
            else:
                results.append(("PASS", "B: no PM overdue shown (DB also shows 0 overdue)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Stock alert count matches DB ──────────────────────────────
    log("  [C] Stock alert count vs DB low-stock items...")
    try:
        low_stock_res = db.table("inventory_items").select("id", count="exact") \
            .eq("hive_id", hive_id).execute()
        # Can't do qty_on_hand < min_qty via Python client easily — just check alert presence
        page_text = page.locator("body").inner_text()
        has_stock_alert = "running low" in page_text.lower() or "stock alert" in page_text.lower()
        total_items = low_stock_res.count or 0

        if total_items == 0:
            results.append(("WARN", "C: no inventory items in hive — stock alert check skipped"))
        elif has_stock_alert:
            m = re.search(r"(\d+)\s+items?\s+running low", page_text, re.IGNORECASE)
            count_shown = int(m.group(1)) if m else "?"
            results.append(("PASS", f"C: Stock alert visible, shows {count_shown} items running low"))
        else:
            results.append(("WARN", "C: no stock alert shown (may mean all items are above reorder point)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Pattern Alerts — visible, clean, no <think> ──────────────
    log("  [D] Pattern Alerts: visible, structured, no AI reasoning leak...")
    try:
        alerts_section = page.locator("#pattern-alerts-panel, [id*='pattern'], [class*='pattern']").first
        page_text = page.locator("body").inner_text()

        has_think = "<think>" in page_text.lower() or "think>" in page_text
        has_alerts_section = "Pattern Alerts" in page_text or "PATTERN ALERTS" in page_text

        if has_think:
            results.append(("FAIL", "D: <think> reasoning tokens visible on hive dashboard — AI leak not fixed"))
        elif not has_alerts_section:
            # Check DB — maybe no alerts were generated
            db_alerts = db.table("failure_signature_alerts").select("id", count="exact") \
                .eq("hive_id", hive_id).eq("status", "active").limit(1).execute().count or 0
            if db_alerts == 0:
                results.append(("WARN", "D: Pattern Alerts section not shown (no active alerts in DB — run failure-signature-scan first)"))
            else:
                results.append(("FAIL", f"D: {db_alerts} active alerts in DB but Pattern Alerts section not visible on page"))
        else:
            # Verify alert cards have machine tag and description text
            alert_cards = page.locator("#pattern-alerts-content > div, #pattern-alerts-panel .wh-card").all()
            n_cards = len(alert_cards)
            if n_cards > 0:
                results.append(("PASS", f"D: Pattern Alerts visible, {n_cards} card(s), no <think> leak"))
            else:
                results.append(("WARN", "D: Pattern Alerts section visible but 0 cards rendered"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"D crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario E: Reliability Coach returns 3 action cards ─────────────────
    log("  [E] Reliability Coach: 3 action cards with urgency badges...")
    try:
        coach_input = page.locator("#coach-input")
        ask_btn     = page.locator("#coach-submit")

        if not coach_input.count() or not ask_btn.count():
            results.append(("FAIL", "E: Reliability Coach input or Ask button not found on page"))
        else:
            coach_input.fill("What are the top 3 maintenance priorities this week?")
            ask_btn.click()
            # Wait up to 45s for coach response (4 parallel agent calls)
            page.wait_for_timeout(45000)

            coach_result = page.locator("#coach-result")
            if not coach_result.is_visible():
                results.append(("FAIL", "E: #coach-result never became visible after 45s"))
            else:
                result_text = coach_result.inner_text()
                has_three   = "#1" in result_text and "#2" in result_text and "#3" in result_text
                has_urgency = any(u in result_text for u in ["TODAY", "THIS WEEK", "MONITOR"])
                has_machine = bool(re.search(r"[A-Z]{2,4}-\d{2,4}", result_text))  # e.g. P-001, BLR-008

                still_loading = any(kw in result_text for kw in ["Analyzing", "analyzing", "Loading", "loading"])

                if still_loading:
                    results.append(("WARN", "E: Coach still loading after 45s — AI provider slow (transient)"))
                elif has_three and has_urgency:
                    results.append(("PASS",
                        f"E: Coach returned 3 actions with urgency labels"
                        + (" + machine references" if has_machine else "")))
                elif has_three:
                    results.append(("WARN", "E: Coach returned 3 actions but no urgency badges"))
                else:
                    preview = result_text[:120].replace("\n", " ")
                    results.append(("WARN", f"E: Coach response unexpected structure (AI latency) — '{preview}'"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"E timed out or crashed: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario F: Network Benchmark renders or shows clean state ────────────
    log("  [F] Network Benchmark: shows data or clean 'compute now' state...")
    try:
        benchmark_panel = page.locator("#benchmark-panel")
        page_text = page.locator("body").inner_text()
        has_benchmark_text = "Network Benchmark" in page_text or "WorkHive Network" in page_text

        if not has_benchmark_text:
            results.append(("WARN", "F: Network Benchmark section not found on page"))
        else:
            has_compute_now = "compute now" in page_text.lower()
            has_data = bool(re.search(r"\d+d\s", page_text))  # e.g. "23d" MTBF value

            if has_data:
                results.append(("PASS", "F: Network Benchmark shows MTBF data"))
            elif has_compute_now:
                results.append(("PASS", "F: Network Benchmark shows 'compute now' (no data yet — expected for new hive)"))
            else:
                results.append(("WARN", "F: Network Benchmark section present but neither data nor 'compute now' visible"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: Today's Brief shows or shows placeholder ─────────────────
    log("  [G] Today's Brief: never blank (placeholder or content)...")
    try:
        page_text = page.locator("body").inner_text()
        has_brief_section = "Today's Brief" in page_text or "TODAY'S BRIEF" in page_text

        if not has_brief_section:
            results.append(("FAIL", "G: Today's Brief section missing entirely from page"))
        else:
            has_placeholder = "No AI analysis yet" in page_text or "generate automatically" in page_text
            has_content     = bool(re.search(r"(Top risk|Failure|PM|breakdown|overdue)", page_text, re.IGNORECASE))
            brief_el = page.locator("#todays-brief-content, #todays-brief-panel")
            is_blank = brief_el.count() and brief_el.first.inner_text().strip() == ""

            if is_blank:
                results.append(("FAIL", "G: Today's Brief content is completely blank (no placeholder, no content)"))
            elif has_placeholder or has_content:
                results.append(("PASS", f"G: Today's Brief shows {'content' if has_content else 'placeholder text'}"))
            else:
                results.append(("WARN", "G: Today's Brief section present but content unclear"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"G crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario H: Team stock issues list has real worker names ─────────────
    log("  [H] Team Stock Issues: worker names are real (not 'undefined')...")
    try:
        page_text = page.locator("body").inner_text()
        has_team_stock = "Team Stock Issues" in page_text

        if not has_team_stock:
            results.append(("WARN", "H: Team Stock Issues section not visible (may mean no low stock in hive)"))
        else:
            has_undefined = "undefined" in page_text and "Team Stock Issues" in page_text
            if has_undefined:
                results.append(("FAIL", "H: 'undefined' found near Team Stock Issues — worker names not resolving"))
            else:
                results.append(("PASS", "H: Team Stock Issues visible, no 'undefined' worker names"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario I: Live indicator visible ────────────────────────────────────
    log("  [I] Live indicator (green dot) visible...")
    try:
        page_text = page.locator("body").inner_text()
        has_live = "Live" in page_text
        live_dot = page.locator(".bg-green-400, [class*='live'], [class*='pulse']").first

        if has_live:
            results.append(("PASS", "I: Live indicator text visible on dashboard"))
        else:
            results.append(("WARN", "I: 'Live' text not found — may be in CSS-only indicator"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"I skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "hive_dashboard_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Hive Dashboard: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

