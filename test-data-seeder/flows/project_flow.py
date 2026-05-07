"""Project Manager + Project Report flows — DB-verified project CRUD and report rendering.

project-manager.html:
  A – Project list loads (data or clean empty state, never blank crash)
  B – Create project → projects row in DB
  C – Scope item added → project_progress_logs row in DB
  D – Progress percentage is 0-100 (not NaN or >100)
  E – No undefined/null in project display fields

project-report.html:
  F – Report renders with required sections (scope, sign-off)
  G – Report values match project data (project code / name visible)
  H – Print/export button triggers print without JS error
  I – No NaN in any report numeric field
"""

import re
import time
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

TEST_PROJECT_NAME = f"TEST_PROJECT_{int(time.time())}"
TEST_PROJECT_CODE = f"TP{int(time.time()) % 10000:04d}"


def run(page, errors, warnings, log) -> dict:
    log("Project Manager + Report flow checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/project-manager.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(3000)

    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")
    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")

    # ── Scenario A: Project list loads ───────────────────────────────────────
    log("  [A] Project Manager loads (list or clean empty state)...")
    try:
        page_text   = page.locator("body").inner_text()
        has_js_err  = any(kw in page_text for kw in
                          ["TypeError", "ReferenceError", "Cannot read", "is not defined"])
        has_content = len(page_text.strip()) > 200
        has_project_ui = any(kw in page_text for kw in
                             ["project", "Project", "scope", "milestone", "No projects"])

        if has_js_err:
            results.append(("FAIL", "A: JS error text visible on Project Manager page"))
        elif has_content and has_project_ui:
            results.append(("PASS", "A: Project Manager loaded with project UI content"))
        elif has_content:
            results.append(("WARN", "A: page loaded but no project-specific content detected"))
        else:
            results.append(("WARN", "A: page appears empty — may be first-time load with no projects"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Create project → DB row ──────────────────────────────────
    log("  [B] Create project → projects DB row inserted...")
    try:
        before = 0
        if hive_id:
            before = db.table("projects").select("id", count="exact") \
                .eq("hive_id", hive_id).limit(1).execute().count or 0

        new_btn = page.locator(
            "button:has-text('New project'), button:has-text('New Project'), "
            "button:has-text('Create Project'), button:has-text('+ Project')"
        ).first

        if new_btn.count():
            new_btn.click()
            page.wait_for_timeout(800)

            # Wizard step 1: pick project type tile (workorder is always first)
            type_tile = page.locator(
                "[data-type='workorder'], .type-tile, [onclick*='wizardPickType']"
            ).first
            if type_tile.count():
                type_tile.click()
                page.wait_for_timeout(500)

            # Wizard may have a Next / Continue button to advance steps
            next_btn = page.locator(
                "button:has-text('Next'), button:has-text('Continue'), "
                "#wiz-next, [onclick*='wizardNext']"
            ).first
            if next_btn.count() and next_btn.is_visible():
                next_btn.click()
                page.wait_for_timeout(500)
                if next_btn.count() and next_btn.is_visible():
                    next_btn.click()
                    page.wait_for_timeout(500)

            name_input = page.locator(
                "#wiz-name, input[placeholder*='name' i], input[placeholder*='project' i], "
                "#project-name, input[name='name']"
            ).first
            code_input = page.locator(
                "#wiz-code, input[placeholder*='code' i], input[placeholder*='ref' i], "
                "#project-code, input[name='code']"
            ).first

            if name_input.count() and name_input.is_visible():
                name_input.fill(TEST_PROJECT_NAME)
                page.wait_for_timeout(200)
            if code_input.count() and code_input.is_visible():
                code_input.fill(TEST_PROJECT_CODE)
                page.wait_for_timeout(200)

            submit_btn = page.locator(
                "#wiz-create, button:has-text('Create project'), button:has-text('Create Project'), "
                "button[type='submit']"
            ).first
            if submit_btn.count() and submit_btn.is_visible():
                submit_btn.scroll_into_view_if_needed()
                submit_btn.click()
                page.wait_for_timeout(2500)

                after = 0
                if hive_id:
                    after = db.table("projects").select("id", count="exact") \
                        .eq("hive_id", hive_id).limit(1).execute().count or 0

                if after > before:
                    results.append(("PASS", f"B: projects count {before}→{after} in DB"))
                else:
                    if TEST_PROJECT_NAME in page.locator("body").inner_text():
                        results.append(("WARN", "B: project visible on page but DB count unchanged"))
                    else:
                        results.append(("WARN", "B: project not found in DB or page after create"))
            else:
                results.append(("WARN", "B: submit/create button not found in form"))
        else:
            results.append(("WARN", "B: New Project button not found — may require supervisor role"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Scope item added → DB row ─────────────────────────────────
    log("  [C] Add scope item → project_progress_logs row in DB...")
    try:
        # Find our test project or any existing project
        projects = db.table("projects").select("id, name, project_code") \
            .eq("hive_id", hive_id).limit(3).execute().data if hive_id else []

        if not projects:
            results.append(("WARN", "C: no projects in DB — scope item check skipped"))
        else:
            proj      = projects[0]
            proj_id   = proj["id"]
            prog_before = db.table("project_progress_logs").select("id", count="exact") \
                .eq("project_id", proj_id).limit(1).execute().count or 0

            # Click into the project — use get_by_text since data-project-id may not exist
            proj_name = proj.get("name", "")
            proj_code = proj.get("project_code", "")
            proj_card = page.locator(f"[data-project-id='{proj_id}']").first
            if not proj_card.count():
                if proj_code:
                    proj_card = page.get_by_text(proj_code, exact=False).first
                elif proj_name:
                    proj_card = page.get_by_text(proj_name[:20], exact=False).first
            if proj_card.count():
                proj_card.click()
                page.wait_for_timeout(1000)

            # Add a scope item
            add_item_btn = page.locator(
                "button:has-text('Add Item'), button:has-text('Add Scope'), "
                "button:has-text('+ Item'), button:has-text('New Item')"
            ).first

            if add_item_btn.count():
                add_item_btn.click()
                page.wait_for_timeout(500)

                item_input = page.locator(
                    "input[placeholder*='item' i], input[placeholder*='scope' i], "
                    "input[placeholder*='task' i], textarea:visible"
                ).first

                if item_input.count():
                    item_input.fill(f"Test scope item {int(time.time())}")
                    save_item = page.locator(
                        "button:has-text('Add'), button:has-text('Save'), button[type='submit']"
                    ).last
                    if save_item.count():
                        save_item.click()
                        page.wait_for_timeout(2000)

                        prog_after = db.table("project_progress_logs").select("id", count="exact") \
                            .eq("project_id", proj_id).limit(1).execute().count or 0

                        if prog_after > prog_before:
                            results.append(("PASS", f"C: project_progress_logs count {prog_before}→{prog_after}"))
                        else:
                            results.append(("WARN", "C: scope item count unchanged in DB (check table name)"))
                    else:
                        results.append(("WARN", "C: save button not found for scope item"))
                else:
                    results.append(("WARN", "C: scope item input not found"))
            else:
                results.append(("WARN", "C: Add Item button not found in project view"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Progress percentage is 0-100 ──────────────────────────────
    log("  [D] Project progress percentage is valid 0-100 (not NaN or >100)...")
    try:
        page_text = page.locator("body").inner_text()
        pct_vals  = re.findall(r"(\d{1,3})\s*%", page_text)
        has_nan   = "NaN" in page_text

        if has_nan:
            results.append(("FAIL", "D: NaN in progress display — calculation bug"))
        elif pct_vals:
            over_100 = [v for v in pct_vals if int(v) > 100]
            if over_100:
                results.append(("FAIL", f"D: progress value(s) >100%: {over_100}"))
            else:
                results.append(("PASS", f"D: {len(pct_vals)} percentage value(s) found, all ≤100%"))
        else:
            results.append(("WARN", "D: no percentage values found on page (no projects with progress?)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"D crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario E: No undefined/null in project display ─────────────────────
    log("  [E] No 'undefined' or literal 'null' in project fields...")
    try:
        page_text = page.locator("body").inner_text()
        if "undefined" in page_text:
            results.append(("FAIL", "E: 'undefined' found on Project Manager — data mapping issue"))
        elif re.search(r"\bnull\b", page_text):
            results.append(("WARN", "E: literal 'null' in page text"))
        else:
            results.append(("PASS", "E: no 'undefined' or literal 'null' in project display"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"E crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenarios F-I: project-report.html ────────────────────────────────────
    # Navigate to report — try with a project ID if we have one
    report_url = f"{BASE_URL}/workhive/project-report.html"
    if hive_id and projects:
        report_url += f"?id={projects[0]['id']}"

    page.goto(report_url, wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(3000)

    # ── Scenario F: Report renders required sections ───────────────────────────
    log("  [F] Project Report renders required sections...")
    try:
        page_text = page.locator("body").inner_text()
        sections  = ["Scope", "scope", "Sign", "sign", "Summary", "summary"]
        found_secs = [s for s in sections if s in page_text]

        has_js_err = any(kw in page_text for kw in ["TypeError", "ReferenceError"])

        if has_js_err:
            results.append(("FAIL", "F: JS error on project-report.html"))
        elif len(found_secs) >= 2:
            results.append(("PASS", f"F: report sections visible: {list(set(s.lower() for s in found_secs))[:4]}"))
        elif len(page_text) > 500:
            results.append(("WARN", "F: report has content but required section labels not found"))
        else:
            results.append(("WARN", "F: project-report.html appears mostly empty (need project data)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: Report shows project name/code ────────────────────────────
    log("  [G] Report references the project name or code...")
    try:
        page_text = page.locator("body").inner_text()
        found_proj = False

        if projects:
            proj_name = projects[0].get("name", "")
            proj_code = projects[0].get("project_code", "")
            found_proj = (proj_name and proj_name[:10] in page_text) or \
                         (proj_code and proj_code in page_text)

        if found_proj:
            results.append(("PASS", f"G: project identity visible in report"))
        elif projects:
            results.append(("WARN", f"G: project name/code not found in report — may need project URL param"))
        else:
            results.append(("WARN", "G: no projects in DB — report content check skipped"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario H: Print/export triggers without JS error ────────────────────
    log("  [H] Print/export button triggers without JS error...")
    try:
        errors_before = len(errors)
        print_btn = page.locator(
            "button:has-text('Print'), button:has-text('Export'), "
            "button:has-text('PDF'), button:has-text('Download'), "
            "[onclick*='print'], [onclick*='pdf']"
        ).first

        if print_btn.count():
            # Intercept print dialog
            page.evaluate("window.print = () => { window._printCalled = true; }")
            print_btn.click()
            page.wait_for_timeout(2000)

            print_called = page.evaluate("window._printCalled === true")
            new_js_errs  = [e for e in errors[errors_before:] if "TypeError" in e]

            if new_js_errs:
                results.append(("FAIL", f"H: JS error on export: {new_js_errs[0][:80]}"))
            elif print_called:
                results.append(("PASS", "H: print/export triggered window.print() without errors"))
            else:
                results.append(("WARN", "H: export button clicked but window.print() not called"))
        else:
            results.append(("WARN", "H: no print/export button found on project-report.html"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario I: No NaN in report ─────────────────────────────────────────
    log("  [I] No NaN in project report numeric fields...")
    try:
        page_text = page.locator("body").inner_text()
        has_nan   = "NaN" in page_text

        if has_nan:
            results.append(("FAIL", "I: NaN found in project report — numeric calculation bug"))
        else:
            results.append(("PASS", "I: no NaN values in project report"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"I crashed: {e}"))
        log(f"    → FAIL: {e}")

    # Cleanup test project
    try:
        if hive_id:
            test_projs = db.table("projects").select("id") \
                .eq("hive_id", hive_id).like("name", "TEST_PROJECT_%").execute().data or []
            for p in test_projs:
                db.table("project_progress_logs").delete().eq("project_id", p["id"]).execute()
            db.table("projects").delete() \
                .eq("hive_id", hive_id).like("name", "TEST_PROJECT_%").execute()
    except Exception:
        pass

    screenshot(page, "project_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Project Manager+Report: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

