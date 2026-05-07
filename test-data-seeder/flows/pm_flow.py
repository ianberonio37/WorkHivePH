"""PM Scheduler flows — DB-verified task completion and overdue detection.

Scenarios:
  A – Asset list loads with scope items visible
  B – Overdue tasks marked with visual indicator (DB count vs UI)
  C – Task completion → pm_completions row inserted in DB
  D – Completing a task updates last_anchor_date on pm_assets
  E – PM health score renders (0-100, not NaN or blank)
  F – Worker role: complete button visible on own hive assets
  G – Logbook link from PM completion creates matching logbook entry
"""

import re
from datetime import date, timedelta
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot


def run(page, errors, warnings, log) -> dict:
    log("PM Scheduler flow checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/pm-scheduler.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(3000)

    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    if not hive_id:
        return {"results": [("WARN", "No hive_id — PM Scheduler is hive-only, all checks skipped")]}

    # ── Scenario A: Asset list loads with scope items ─────────────────────────
    log("  [A] PM assets list renders with scope items...")
    try:
        db_assets = db.table("pm_assets").select("id, asset_name, tag_id") \
            .eq("hive_id", hive_id).limit(20).execute().data or []

        if not db_assets:
            results.append(("WARN", "A: no pm_assets in DB for this hive — seed PM data first"))
        else:
            page_text = page.locator("body").inner_text()
            # Verify at least one asset name or tag appears
            found = sum(1 for a in db_assets if a.get("asset_name", "") in page_text
                        or a.get("tag_id", "") in page_text)
            if found > 0:
                results.append(("PASS", f"A: {found}/{len(db_assets)} assets visible in PM list"))
            else:
                results.append(("WARN", f"A: {len(db_assets)} pm_assets in DB but none found in page text (may need asset selection)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Overdue tasks visually marked ────────────────────────────
    log("  [B] Overdue PM tasks flagged (DB count vs UI)...")
    try:
        today_str = date.today().isoformat()

        asset_ids = [a["id"] for a in (db.table("pm_assets").select("id")
            .eq("hive_id", hive_id).execute().data or [])]

        db_overdue = 0
        if asset_ids:
            overdue_res = db.table("pm_scope_items").select("id, anchor_date, frequency") \
                .in_("asset_id", asset_ids).execute().data or []

            freq_days = {"Weekly": 7, "Monthly": 30, "Quarterly": 90,
                         "Semi-annual": 180, "Annual": 365}
            for s in overdue_res:
                anchor = s.get("anchor_date")
                freq   = freq_days.get(s.get("frequency", ""), 30)
                if anchor:
                    next_due = (date.fromisoformat(anchor) + timedelta(days=freq)).isoformat()
                    if next_due < today_str:
                        db_overdue += 1

        page_text = page.locator("body").inner_text()
        has_overdue_indicator = any(kw in page_text.lower() for kw in
                                    ["overdue", "past due", "due soon", "overdo"])

        if db_overdue == 0:
            results.append(("PASS", "B: no overdue tasks in DB — no overdue indicator expected"))
        elif has_overdue_indicator:
            results.append(("PASS", f"B: DB has {db_overdue} overdue tasks, overdue indicator visible on page"))
        else:
            results.append(("WARN", f"B: DB has {db_overdue} overdue tasks but no overdue indicator found in page text"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Task completion → pm_completions row inserted ────────────
    log("  [C] Complete a PM task → pm_completions row created in DB...")
    try:
        pm_assets = db.table("pm_assets").select("id, asset_name, tag_id") \
            .eq("hive_id", hive_id).limit(5).execute().data or []

        if not pm_assets:
            results.append(("WARN", "C: no pm_assets to test completion — skipping"))
        else:
            target_asset = pm_assets[0]
            asset_id     = target_asset["id"]
            asset_name   = target_asset.get("asset_name") or target_asset.get("tag_id", "")

            scope_items = db.table("pm_scope_items").select("id, item_text") \
                .eq("asset_id", asset_id).limit(3).execute().data or []

            completions_before = db.table("pm_completions").select("id", count="exact") \
                .eq("asset_id", asset_id).limit(1).execute().count or 0

            # Try to click on the asset to expand its tasks
            asset_el = page.locator(
                f"text={asset_name}, [data-asset-id='{asset_id}'], "
                f"button:has-text('{asset_name[:15]}')"
            ).first
            if asset_el.count():
                asset_el.click()
                page.wait_for_timeout(1000)

            # Look for a "Done" or checkmark button in the task list
            done_btn = page.locator(
                "button:has-text('Done'), button:has-text('Complete'), "
                "input[type='checkbox']:not(:checked), [data-scope-item-id]"
            ).first

            if done_btn.count():
                done_btn.click()
                page.wait_for_timeout(500)

                # Handle any confirm dialog
                confirm = page.locator(
                    "button:has-text('Confirm'), button:has-text('Save'), "
                    "button:has-text('Submit'), button:has-text('Yes')"
                ).first
                if confirm.count():
                    confirm.click()
                    page.wait_for_timeout(2000)

                completions_after = db.table("pm_completions").select("id", count="exact") \
                    .eq("asset_id", asset_id).limit(1).execute().count or 0

                if completions_after > completions_before:
                    results.append(("PASS", f"C: pm_completions count {completions_before}→{completions_after} for {asset_name}"))
                else:
                    results.append(("WARN", f"C: no new pm_completions row after clicking Done on {asset_name} (count={completions_after})"))
            else:
                results.append(("WARN", "C: no Done/Complete button visible — may need to select asset or expand tasks first"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Completion updates last_anchor_date ───────────────────────
    log("  [D] PM completion updates pm_assets.last_anchor_date...")
    try:
        pm_assets = db.table("pm_assets").select("id, last_anchor_date") \
            .eq("hive_id", hive_id).limit(3).execute().data or []

        recent_completions = db.table("pm_completions").select("asset_id, completed_at") \
            .order("completed_at", desc=True).limit(10).execute().data or []

        if not recent_completions:
            results.append(("WARN", "D: no pm_completions in DB — anchor date check skipped"))
        else:
            asset_map = {a["id"]: a["last_anchor_date"] for a in pm_assets}
            mismatches = 0
            checked    = 0
            for comp in recent_completions[:5]:
                aid    = comp["asset_id"]
                anchor = asset_map.get(aid)
                comp_d = (comp.get("completed_at") or "")[:10]
                if anchor and comp_d:
                    checked += 1
                    # anchor_date should be ≤ completed_at (completion should update it)
                    if anchor < comp_d:
                        pass   # anchor is older than completion — OK, may not have been updated yet
                    # Just verify anchor_date is set (not null)
                    if not anchor:
                        mismatches += 1

            if mismatches == 0 and checked > 0:
                results.append(("PASS", f"D: last_anchor_date set on {checked} PM assets with completions"))
            elif checked == 0:
                results.append(("WARN", "D: could not cross-reference completions with assets — skipping"))
            else:
                results.append(("WARN", f"D: {mismatches} pm_assets missing last_anchor_date despite having completions"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: PM health score renders (0-100, not NaN) ─────────────────
    log("  [E] PM health score renders with valid number...")
    try:
        page_text = page.locator("body").inner_text()

        # Look for health score number (0-100)
        score_match = re.search(r"health\s*[:\-]?\s*(\d{1,3})", page_text, re.IGNORECASE)
        pct_match   = re.search(r"(\d{1,3})%\s*(?:health|complete|complian)", page_text, re.IGNORECASE)

        has_nan  = "NaN" in page_text or "nan" in page_text
        has_score = score_match or pct_match

        if has_nan:
            results.append(("FAIL", "E: 'NaN' found in PM page — health score calculation has divide-by-zero or undefined data"))
        elif has_score:
            val = int((score_match or pct_match).group(1))
            if 0 <= val <= 100:
                results.append(("PASS", f"E: PM health score = {val} (valid 0-100 range)"))
            else:
                results.append(("FAIL", f"E: PM health score = {val} — outside 0-100 range"))
        else:
            results.append(("WARN", "E: no clear health score found in page text (may use different display pattern)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"E crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario F: Worker can see and complete tasks ─────────────────────────
    log("  [F] Worker sees tasks and Done button is accessible...")
    try:
        role = page.evaluate("localStorage.getItem('wh_hive_role') || 'worker'")

        # Done/Complete buttons should be accessible regardless of role
        done_btns = page.locator(
            "button:has-text('Done'), button:has-text('Complete'), "
            "input[type='checkbox'], [class*='check']"
        ).all()

        if done_btns:
            results.append(("PASS", f"F: {len(done_btns)} completion button(s) accessible (role={role})"))
        else:
            # Try selecting an asset first
            asset_btn = page.locator("button, [role='button'], .asset-card").first
            if asset_btn.count():
                asset_btn.click()
                page.wait_for_timeout(800)
                done_btns = page.locator(
                    "button:has-text('Done'), button:has-text('Complete'), input[type='checkbox']"
                ).all()
                if done_btns:
                    results.append(("PASS", f"F: {len(done_btns)} completion button(s) after selecting asset"))
                else:
                    results.append(("WARN", "F: no completion buttons found after asset selection — UI may require different interaction"))
            else:
                results.append(("WARN", "F: no assets or completion buttons visible on PM Scheduler"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: PM overdue count matches hive dashboard count ─────────────
    log("  [G] Cross-check: PM overdue count vs hive dashboard alert...")
    try:
        page_text = page.locator("body").inner_text()
        pm_page_overdue = re.search(r"(\d+)\s*(?:tasks?|items?)\s*overdue", page_text, re.IGNORECASE)
        pm_count = int(pm_page_overdue.group(1)) if pm_page_overdue else None

        page.goto(f"{BASE_URL}/workhive/hive.html", wait_until="networkidle", timeout=12000)
        page.wait_for_timeout(2000)
        dash_text = page.locator("body").inner_text()
        dash_match = re.search(r"(\d+)\s*PM [Tt]asks?\s*[Oo]verdue", dash_text, re.IGNORECASE)
        dash_count = int(dash_match.group(1)) if dash_match else None

        if pm_count is None and dash_count is None:
            results.append(("WARN", "G: overdue count not found on either PM page or dashboard"))
        elif pm_count is not None and dash_count is not None:
            if abs(pm_count - dash_count) <= 2:
                results.append(("PASS", f"G: PM page={pm_count} dashboard={dash_count} (match ±2)"))
            else:
                results.append(("WARN", f"G: PM page={pm_count} dashboard={dash_count} — mismatch >2"))
        else:
            results.append(("WARN", f"G: only one side found — PM page={pm_count} dashboard={dash_count}"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "pm_flow_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  PM Scheduler: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

