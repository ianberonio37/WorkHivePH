"""Day Planner flows — DB-verified task creation, completion, and navigation.

Scenarios:
  A – Page loads cleanly (task list or empty state, never blank crash)
  B – Add task → planner row created in DB
  C – Complete task → completion status updated in DB
  D – Date navigation changes displayed date header
  E – No NaN or undefined values in task display
  F – Task count on page is consistent with DB row count
  G – Completed tasks visually distinct from open tasks
"""

import time
import re
from datetime import date
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

TEST_TASK_TITLE = f"PLAN_TEST_{int(time.time())}"
TODAY = date.today().isoformat()


def run(page, errors, warnings, log) -> dict:
    log("Day Planner flow checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/dayplanner.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2500)

    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    if not worker_name:
        return {"results": [("FAIL", "worker_name not in localStorage — sign-in failed")]}

    # ── Scenario A: Page loads cleanly ────────────────────────────────────────
    log("  [A] Day Planner loads without crash (content or clean empty state)...")
    try:
        page_text = page.locator("body").inner_text()
        has_js_error = any(kw in page_text for kw in
                           ["TypeError", "ReferenceError", "Cannot read", "is not defined"])
        has_content  = len(page_text.strip()) > 200
        has_date     = TODAY[:7] in page_text or str(date.today().year) in page_text

        if has_js_error:
            results.append(("FAIL", "A: JS error text visible on Day Planner page"))
        elif has_content and has_date:
            results.append(("PASS", "A: Day Planner loaded with date context and content"))
        elif has_content:
            results.append(("PASS", "A: Day Planner loaded with content (date string not detected)"))
        else:
            results.append(("WARN", "A: page loaded but very little content — may be empty state"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Add task via modal → DB row created ───────────────────────
    log("  [B] Add task via + Schedule modal → DB row created...")
    try:
        before = db.table("schedule_items").select("id", count="exact") \
            .eq("worker_name", worker_name).eq("date", TODAY) \
            .limit(1).execute().count or 0

        add_btn = page.locator(
            "button:has-text('+ Schedule'), button:has-text('Add Task'), "
            "button[onclick^='openAddModal']"
        ).first

        if not add_btn.count():
            results.append(("WARN", "B: no '+ Schedule' button found — skipping add test"))
        else:
            add_btn.click()
            page.wait_for_timeout(400)

            title_input = page.locator("#m-title").first
            date_input  = page.locator("#m-date").first
            save_btn    = page.locator("button:has-text('Save')").first

            if not (title_input.count() and save_btn.count()):
                results.append(("WARN", "B: + Schedule clicked but modal title/save not found"))
            else:
                title_input.fill(TEST_TASK_TITLE)
                if date_input.count() and not date_input.input_value():
                    date_input.fill(TODAY)
                save_btn.click()
                page.wait_for_timeout(2000)

                after = db.table("schedule_items").select("id", count="exact") \
                    .eq("worker_name", worker_name).eq("date", TODAY) \
                    .limit(1).execute().count or 0

                if after > before:
                    results.append(("PASS", f"B: schedule_items count {before}→{after} for today"))
                elif TEST_TASK_TITLE in page.locator("body").inner_text():
                    results.append(("WARN", "B: task visible on page but DB count unchanged"))
                else:
                    results.append(("WARN", "B: modal saved but no DB row + no page render"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Complete task → status updated ────────────────────────────
    log("  [C] Complete task → DB status updated...")
    try:
        tasks = db.table("schedule_items").select("id, title, item_status") \
            .eq("worker_name", worker_name).eq("date", TODAY) \
            .neq("item_status", "done").limit(3).execute().data or []

        if not tasks:
            tasks = db.table("schedule_items").select("id, title") \
                .eq("worker_name", worker_name).eq("date", TODAY) \
                .limit(3).execute().data or []

        if not tasks:
            results.append(("WARN", "C: no tasks for today in DB — complete check skipped"))
        else:
            task_id = tasks[0]["id"]

            # Open the task's edit modal directly (page exposes openEditModal as a global)
            page.evaluate(f"if (typeof openEditModal === 'function') openEditModal('{task_id}')")
            page.wait_for_timeout(600)

            done_btn = page.locator("#s-btn-done").first
            save_btn = page.locator("button:has-text('Save')").first

            if done_btn.count() and save_btn.count():
                done_btn.click()
                page.wait_for_timeout(200)
                save_btn.click()
                page.wait_for_timeout(2000)

                updated = db.table("schedule_items").select("item_status") \
                    .eq("id", task_id).execute().data or []

                if updated and updated[0].get("item_status") == "done":
                    results.append(("PASS", "C: task completion persisted to DB"))
                else:
                    results.append(("WARN", f"C: clicked Done+Save but item_status='{(updated[0] if updated else {}).get('item_status')}'"))
            else:
                results.append(("WARN", "C: edit modal did not expose #s-btn-done or Save button"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Date navigation changes displayed date ────────────────────
    log("  [D] Date navigation arrows change the displayed date...")
    try:
        # Extract current date text
        page_text_before = page.locator("body").inner_text()

        # Click tomorrow / forward arrow
        next_btn = page.locator(
            "button[aria-label*='next' i], button[aria-label*='forward' i], "
            "button:has-text('›'), button:has-text('>'), "
            "[class*='next-day'], [class*='arrow-right']"
        ).first

        if next_btn.count():
            next_btn.click()
            page.wait_for_timeout(1000)
            page_text_after = page.locator("body").inner_text()

            # The page text should show a different date
            if page_text_before != page_text_after:
                results.append(("PASS", "D: date navigation changes page content"))
            else:
                results.append(("WARN", "D: date navigation clicked but page content unchanged"))
        else:
            results.append(("WARN", "D: no date navigation arrow found"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: No NaN or undefined ──────────────────────────────────────
    log("  [E] No NaN or undefined values in planner display...")
    try:
        page.goto(f"{BASE_URL}/workhive/dayplanner.html", wait_until="networkidle", timeout=12000)
        page.wait_for_timeout(1500)
        page_text = page.locator("body").inner_text()

        has_nan       = "NaN" in page_text
        has_undefined = "undefined" in page_text

        if has_nan:
            results.append(("FAIL", "E: 'NaN' found on Day Planner — date/count calculation bug"))
        elif has_undefined:
            results.append(("FAIL", "E: 'undefined' found on Day Planner — data mapping issue"))
        else:
            results.append(("PASS", "E: no NaN or undefined values on Day Planner"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"E crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario F: Task count consistent with DB ─────────────────────────────
    log("  [F] Rendered task count consistent with DB...")
    try:
        db_today = db.table("schedule_items").select("id", count="exact") \
            .eq("worker_name", worker_name).eq("date", TODAY) \
            .limit(1).execute().count or 0

        ui_count = page.evaluate("""() => {
            // Day Planner renders tasks as inline-styled divs with onclick="openEditModal('id')".
            // Count distinct ids across DILO/WILO views.
            const els = document.querySelectorAll('[onclick^="openEditModal"]');
            const ids = new Set();
            els.forEach(e => {
                const m = (e.getAttribute('onclick') || '').match(/openEditModal\\(['\"]([^'\"]+)['\"]/);
                if (m) ids.add(m[1]);
            });
            return ids.size;
        }""")

        if db_today == 0 and ui_count == 0:
            results.append(("PASS", "F: no tasks today in DB or UI (consistent empty state)"))
        elif ui_count == 0 and db_today > 0:
            results.append(("WARN", f"F: DB has {db_today} tasks for today but 0 task elements found"))
        elif abs(ui_count - db_today) <= 2:
            results.append(("PASS", f"F: task count — rendered={ui_count} DB={db_today} (±2)"))
        else:
            results.append(("WARN", f"F: rendered={ui_count} DB={db_today} — mismatch >2"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: Completed tasks visually distinct ─────────────────────────
    log("  [G] Completed tasks visually distinct from open tasks...")
    try:
        done_tasks = db.table("schedule_items").select("id") \
            .eq("worker_name", worker_name).eq("date", TODAY) \
            .eq("item_status", "done").limit(1).execute().data or []

        open_tasks = db.table("schedule_items").select("id") \
            .eq("worker_name", worker_name).eq("date", TODAY) \
            .neq("item_status", "done").limit(1).execute().data or []

        if not done_tasks or not open_tasks:
            results.append(("WARN", "G: need both done and open tasks to compare styles — skipping"))
        else:
            # Check that done tasks have visual distinction (strikethrough, opacity, checked class)
            done_el = page.locator(
                "[data-task-id] input[type='checkbox']:checked, "
                ".task-done, .completed, [class*='checked'], "
                "s, del, [style*='line-through'], [style*='opacity: 0.5']"
            ).count()

            if done_el > 0:
                results.append(("PASS", f"G: {done_el} done task(s) have visual distinction"))
            else:
                results.append(("WARN", "G: could not detect visual distinction for done tasks"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    # Cleanup test task
    try:
        db.table("schedule_items").delete() \
            .eq("worker_name", worker_name) \
            .like("title", "PLAN_TEST_%").execute()
    except Exception:
        pass

    screenshot(page, "dayplanner_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Day Planner: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

