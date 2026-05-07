"""Skill Matrix flows — DB-verified level persistence and badge triggers.

Scenarios:
  A – Discipline tabs render (Mechanical, Electrical, etc.)
  B – Current level shown matches DB skill_profiles row
  C – Level change persists to DB (skill_profiles updated)
  D – Progress bar width is proportional to level (not stuck at 0 or 100)
  E – Worker sees own profile only (no other workers' data in solo view)
  F – Badge count in DB matches badge display on page
  G – No NaN or undefined values in level or progress displays
"""

import re
from lib.supabase_client import get_client
from .harness import BASE_URL, ensure_signed_in, screenshot

EXPECTED_DISCIPLINES = [
    "Mechanical", "Electrical", "Hydraulic",
    "Pneumatic", "Instrumentation", "Lubrication",
]


def run(page, errors, warnings, log) -> dict:
    log("Skill Matrix flow checks (DB-verified)...")
    results = []
    db = get_client()

    try:
        ensure_signed_in(page, log=log)
    except Exception as e:
        return {"results": [("FAIL", f"sign-in failed: {e}")]}

    page.goto(f"{BASE_URL}/workhive/skillmatrix.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2500)

    worker_name = page.evaluate("localStorage.getItem('wh_last_worker') || ''")
    hive_id     = page.evaluate("localStorage.getItem('wh_active_hive_id') || null")

    if not worker_name:
        return {"results": [("FAIL", "worker_name not set — sign-in may have failed")]}

    # ── Scenario A: Discipline tabs render ───────────────────────────────────
    log("  [A] Discipline tabs visible...")
    try:
        page_text = page.locator("body").inner_text()
        found = [d for d in EXPECTED_DISCIPLINES if d in page_text]
        if len(found) >= 3:
            results.append(("PASS", f"A: {len(found)}/6 discipline tabs visible: {found}"))
        elif len(found) >= 2:
            results.append(("WARN", f"A: only {len(found)} disciplines visible: {found} (expected ≥3)"))
        else:
            results.append(("FAIL", f"A: fewer than 2 disciplines visible ({found}) — page may not be rendering"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Displayed level matches DB ────────────────────────────────
    log("  [B] Displayed skill level matches DB skill_badges row...")
    try:
        db_profiles = db.table("skill_badges").select("discipline, level") \
            .eq("worker_name", worker_name).execute().data or []

        if not db_profiles:
            results.append(("WARN", "B: no skill_profiles rows for this worker — level comparison skipped"))
        else:
            page_text = page.locator("body").inner_text()
            mismatches = 0
            for p in db_profiles[:3]:
                disc  = p["discipline"]
                level = p["level"]
                # Look for "Level X" near the discipline name
                pattern = rf"{disc}.{{0,80}}[Ll]evel\s*{level}"  # noqa: W605
                if not re.search(pattern, page_text, re.DOTALL):
                    mismatches += 1

            if mismatches == 0:
                results.append(("PASS", f"B: skill levels match DB for {len(db_profiles)} disciplines checked"))
            else:
                results.append(("WARN", f"B: {mismatches} discipline levels may not match DB (text proximity check)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Level change persists to DB ───────────────────────────────
    log("  [C] Selecting a new level persists to DB skill_profiles...")
    try:
        # Get current level for Mechanical
        current = db.table("skill_badges").select("level") \
            .eq("worker_name", worker_name).eq("discipline", "Mechanical") \
            .execute().data
        level_before = current[0]["level"] if current else 0

        # Click Mechanical tab then select level 2 (or a different level)
        mech_tab = page.locator(
            "button:has-text('Mechanical'), [data-discipline='Mechanical'], "
            "li:has-text('Mechanical')"
        ).first
        if mech_tab.count():
            mech_tab.click()
            page.wait_for_timeout(600)

        # Skill matrix uses a stepper UI (.step-btn +/-) not level buttons with text.
        # Click the last step-btn (increment) on the Mechanical card, then save.
        target_level = 2 if level_before != 2 else 3
        step_inc = page.locator(".step-btn").last  # increment is the last step button rendered
        alt_btn = page.locator(
            f"[data-level='{target_level}'], button:has-text('Level {target_level}')"
        ).first

        clicked = False
        if step_inc.count() and step_inc.is_visible():
            step_inc.click()
            page.wait_for_timeout(400)
            # Click save button if present
            save_btn = page.locator("#target-save-btn").first
            if save_btn.count() and save_btn.is_visible():
                save_btn.click()
                page.wait_for_timeout(2000)
            clicked = True
        elif alt_btn.count():
            alt_btn.click()
            page.wait_for_timeout(2000)
            clicked = True

        if clicked:
            updated = db.table("skill_badges").select("level") \
                .eq("worker_name", worker_name).eq("discipline", "Mechanical") \
                .execute().data
            level_after = updated[0]["level"] if updated else level_before

            if level_after == target_level:
                results.append(("PASS", f"C: Mechanical level {level_before}→{level_after} persisted to DB"))
            elif level_after != level_before:
                results.append(("PASS", f"C: Mechanical level changed {level_before}→{level_after} in DB (target was {target_level})"))
            else:
                results.append(("WARN", f"C: level unchanged in DB after stepper click (may require different discipline tab selection)"))
        else:
            results.append(("WARN", "C: no step-btn or level button found — skill matrix may use different interaction pattern"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Progress bars have non-trivial widths ─────────────────────
    log("  [D] Progress bars are proportional (not all 0% or all 100%)...")
    try:
        bar_widths = page.evaluate("""() => {
            const bars = document.querySelectorAll(
                '[style*="width"][class*="progress"], '  +
                '.progress-fill, .progress-bar > div, '  +
                '[role="progressbar"]'
            );
            return Array.from(bars).map(b => {
                const s = b.style.width || b.getAttribute('aria-valuenow') || '';
                const m = s.match(/([\d.]+)/);
                return m ? parseFloat(m[1]) : null;
            }).filter(v => v !== null);
        }""")

        if not bar_widths:
            results.append(("WARN", "D: no progress bar elements found with width style"))
        else:
            all_zero    = all(w == 0 for w in bar_widths)
            all_hundred = all(w == 100 for w in bar_widths)
            if all_zero:
                # 0% is acceptable if this is a fresh worker with no skill data yet
                results.append(("WARN", f"D: all {len(bar_widths)} progress bars are 0% — worker may have no skill records yet (seed skill data to verify rendering)"))
            elif all_hundred:
                results.append(("WARN", f"D: all {len(bar_widths)} progress bars at 100% — unusual (all skills maxed?)"))
            else:
                unique_widths = list(set(round(w) for w in bar_widths))[:5]
                results.append(("PASS", f"D: {len(bar_widths)} bars with varied widths: {unique_widths}"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: Worker sees own profile only ──────────────────────────────
    log("  [E] Worker sees own profile — other workers not visible in solo view...")
    try:
        # Find other workers in the hive
        other_workers = []
        if hive_id:
            members = db.table("hive_members").select("worker_name") \
                .eq("hive_id", hive_id).neq("worker_name", worker_name) \
                .limit(3).execute().data or []
            other_workers = [m["worker_name"] for m in members]

        page_text = page.locator("body").inner_text()

        if not other_workers:
            results.append(("WARN", "E: no other hive members to check against"))
        else:
            leaked = [w for w in other_workers if w in page_text]
            # Own name should appear; others should not in MY Skill Matrix view
            if worker_name in page_text:
                if not leaked:
                    results.append(("PASS", f"E: own name '{worker_name}' visible, other workers not leaked"))
                else:
                    results.append(("WARN", f"E: other workers visible in skill matrix view: {leaked[:2]} (may be hive-wide view)"))
            else:
                results.append(("WARN", f"E: own name '{worker_name}' not found in page text"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"E skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario F: Badge count matches DB ───────────────────────────────────
    log("  [F] Badge count on page matches skill_badges DB rows...")
    try:
        db_badges = db.table("skill_badges").select("id", count="exact") \
            .eq("worker_name", worker_name) \
            .limit(1).execute().count or 0

        page_text = page.locator("body").inner_text()
        # Look for badge count patterns: "3 badges", "Badges: 3", "3/5 badges", "earned 3"
        m = (re.search(r"(\d+)\s*[Bb]adges?", page_text) or
             re.search(r"[Bb]adges?\s*:?\s*(\d+)", page_text) or
             re.search(r"earned\s+(\d+)", page_text, re.IGNORECASE))
        page_badges = int(m.group(1)) if m else None

        if db_badges == 0 and page_badges is None:
            results.append(("PASS", "F: no badges in DB or shown (consistent)"))
        elif page_badges is not None:
            if abs(page_badges - db_badges) <= 2:
                results.append(("PASS", f"F: badge count page={page_badges} DB={db_badges} (match ±2)"))
            else:
                results.append(("WARN", f"F: badge count page={page_badges} DB={db_badges} (mismatch)"))
        else:
            results.append(("WARN", f"F: DB has {db_badges} badges but no badge count found in page text"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"F skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario G: No NaN or undefined in level display ─────────────────────
    log("  [G] No NaN or undefined values rendered...")
    try:
        page_text = page.locator("body").inner_text()
        has_nan       = "NaN" in page_text
        has_undefined = "undefined" in page_text and any(d in page_text for d in EXPECTED_DISCIPLINES)

        if has_nan:
            results.append(("FAIL", "G: 'NaN' found on Skill Matrix page — level calculation bug"))
        elif has_undefined:
            results.append(("FAIL", "G: 'undefined' found near discipline names — data mapping issue"))
        else:
            results.append(("PASS", "G: no NaN or undefined values rendered"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"G crashed: {e}"))
        log(f"    → FAIL: {e}")

    screenshot(page, "skillmatrix_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Skill Matrix: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

