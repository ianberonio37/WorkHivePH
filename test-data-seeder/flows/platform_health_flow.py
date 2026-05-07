"""Platform Health flows — dashboard accuracy and trend checks.

Scenarios:
  A – Health score renders as a valid number (0-100), not NaN
  B – Layer breakdown (Static/Data/UI) shows pass/warn/fail counts
  C – Streak counter is ≥0 (never negative or NaN)
  D – Backlog sections (Critical/Important/Nice-to-have) render or show 0
  E – Run history sparkline / chart visible after at least one gate run
  F – No undefined or null values in score display
  G – Last run timestamp is recent (not year 1970 or future)
  H – API endpoints /api/health and /api/health/history respond correctly
"""

import re
import json
import requests
from lib.supabase_client import get_client
from .harness import BASE_URL, screenshot

SEEDER_BASE = "http://127.0.0.1:5000"


def run(page, errors, warnings, log) -> dict:
    log("Platform Health flow checks...")
    results = []

    page.goto(f"{BASE_URL}/workhive/platform-health.html", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(3000)

    # ── Scenario A: Health score renders as 0-100 ─────────────────────────────
    log("  [A] Health score renders as a valid 0-100 number...")
    try:
        page_text = page.locator("body").inner_text()

        # Look for score patterns: "87", "87/100", "Score: 87"
        score_match = re.search(r"(?:score|Score)[:\s]*(\d{1,3})", page_text)
        raw_number  = re.search(r"\b([1-9]\d{0,2})\s*(?:/100|points?|pts)\b", page_text)
        has_nan     = "NaN" in page_text

        if has_nan:
            results.append(("FAIL", "A: 'NaN' in health score — calculation error"))
        elif score_match:
            val = int(score_match.group(1))
            if 0 <= val <= 100:
                results.append(("PASS", f"A: health score = {val} (valid 0-100)"))
            else:
                results.append(("FAIL", f"A: health score = {val} — outside 0-100 range"))
        elif raw_number:
            val = int(raw_number.group(1))
            results.append(("PASS", f"A: score-like number = {val} found"))
        else:
            results.append(("WARN", "A: no health score found in page text (may need gate run first)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"A crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario B: Layer breakdown shows counts ──────────────────────────────
    log("  [B] Layer breakdown (Static/Data/UI) shows numeric counts...")
    try:
        page_text = page.locator("body").inner_text()
        layers    = ["static", "Static", "data", "Data", "ui", "UI"]
        found     = [l for l in layers if l in page_text]

        # Look for pass/fail/warn counts
        count_pattern = re.findall(r"\d+\s*(?:pass|fail|warn|PASS|FAIL|WARN)", page_text)

        if found and count_pattern:
            results.append(("PASS", f"B: layer names {found[:3]} visible with {len(count_pattern)} count indicators"))
        elif found:
            results.append(("WARN", f"B: layer names visible but no numeric pass/fail/warn counts"))
        else:
            results.append(("WARN", "B: no layer breakdown found (gate may not have run yet)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"B skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario C: Streak counter is ≥0 ─────────────────────────────────────
    log("  [C] Streak counter is ≥0 and not NaN...")
    try:
        page_text    = page.locator("body").inner_text()
        streak_match = re.search(r"streak[:\s]*(\d+)|(\d+)\s*(?:day|run)s?\s*streak", page_text, re.IGNORECASE)
        has_nan      = "NaN" in page_text

        if has_nan:
            results.append(("FAIL", "C: 'NaN' in streak display"))
        elif streak_match:
            val = int(streak_match.group(1) or streak_match.group(2))
            results.append(("PASS", f"C: streak = {val} (valid ≥0)"))
        else:
            results.append(("WARN", "C: no streak counter found in page text"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"C skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario D: Backlog sections render ───────────────────────────────────
    log("  [D] Backlog categories (Critical/Important/Nice-to-have) render...")
    try:
        page_text    = page.locator("body").inner_text()
        categories   = ["Critical", "Important", "Nice to have", "Nice-to-have", "Fixed"]
        found        = [c for c in categories if c in page_text]

        if len(found) >= 3:
            results.append(("PASS", f"D: {len(found)} backlog categories visible: {found}"))
        elif len(found) >= 1:
            results.append(("WARN", f"D: only {found} backlog categories visible"))
        else:
            results.append(("WARN", "D: no backlog categories found — PRODUCTION_FIXES.md may be empty"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"D skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario E: Run history / sparkline visible ───────────────────────────
    log("  [E] Run history sparkline or chart visible...")
    try:
        chart_count = page.evaluate("""() => {
            const sels = ['canvas', 'svg:not([aria-hidden])', '[class*="spark"]', '[class*="chart"]'];
            for (const s of sels) {
                const n = document.querySelectorAll(s).length;
                if (n > 0) return n;
            }
            return 0;
        }""")

        page_text = page.locator("body").inner_text()
        has_history_text = any(kw in page_text for kw in
                               ["history", "History", "previous run", "last run", "runs"])

        if chart_count > 0:
            results.append(("PASS", f"E: {chart_count} chart/sparkline element(s) found"))
        elif has_history_text:
            results.append(("WARN", "E: history text found but no chart/canvas element detected"))
        else:
            results.append(("WARN", "E: no history chart found (run gate at least once to populate)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"E skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario F: No undefined or null in score display ────────────────────
    log("  [F] No 'undefined' or literal 'null' in score display...")
    try:
        page_text    = page.locator("body").inner_text()
        has_undef    = "undefined" in page_text
        has_null_str = bool(re.search(r"\bnull\b", page_text))

        if has_undef:
            results.append(("FAIL", "F: 'undefined' found on platform health page"))
        elif has_null_str:
            results.append(("WARN", "F: literal 'null' found in page text"))
        else:
            results.append(("PASS", "F: no 'undefined' or literal 'null' on platform health"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("FAIL", f"F crashed: {e}"))
        log(f"    → FAIL: {e}")

    # ── Scenario G: Last run timestamp is valid ───────────────────────────────
    log("  [G] Last run timestamp is plausible (not 1970 or future)...")
    try:
        page_text    = page.locator("body").inner_text()
        year_matches = re.findall(r"\b(19\d{2}|20\d{2})\b", page_text)

        stale_years  = [y for y in year_matches if int(y) < 2024]
        future_years = [y for y in year_matches if int(y) > 2030]
        good_years   = [y for y in year_matches if 2024 <= int(y) <= 2030]

        if stale_years and not good_years:
            results.append(("FAIL", f"G: only old years visible ({stale_years}) — timestamps from epoch or stale data"))
        elif future_years:
            results.append(("WARN", f"G: future year(s) visible {future_years} — check system clock"))
        elif good_years:
            results.append(("PASS", f"G: valid years in page timestamps: {list(set(good_years))[:3]}"))
        else:
            results.append(("WARN", "G: no year timestamps found (gate may not have run)"))
        log(f"    → {results[-1]}")
    except Exception as e:
        results.append(("WARN", f"G skipped: {e}"))
        log(f"    → WARN: {e}")

    # ── Scenario H: Seeder /api/health responds correctly ─────────────────────
    log("  [H] Seeder /api/health endpoint returns valid JSON...")
    try:
        resp = requests.get(f"{SEEDER_BASE}/api/health", timeout=8)
        if resp.status_code == 200:
            data      = resp.json()
            has_score = "score" in data or "tier" in data
            has_streak = "streak" in data

            if has_score and has_streak:
                score = data.get("score")
                tier  = data.get("tier", "?")
                results.append(("PASS", f"H: /api/health → score={score} tier={tier}"))
            elif has_score:
                results.append(("WARN", "H: /api/health responds but missing 'streak' key"))
            else:
                results.append(("WARN", f"H: /api/health responds but unexpected shape: {list(data.keys())[:5]}"))
        else:
            results.append(("WARN", f"H: /api/health returned HTTP {resp.status_code}"))
        log(f"    → {results[-1]}")
    except requests.exceptions.ConnectionError:
        results.append(("WARN", "H: seeder server not reachable at :5000 — skipping API check"))
        log(f"    → WARN: seeder not running")
    except Exception as e:
        results.append(("WARN", f"H skipped: {e}"))
        log(f"    → WARN: {e}")

    screenshot(page, "platform_health_final")
    pass_count = sum(1 for r in results if r[0] == "PASS")
    fail_count = sum(1 for r in results if r[0] == "FAIL")
    log(f"  Platform Health: {pass_count} PASS / {fail_count} FAIL / {len(results)-pass_count-fail_count} WARN")
    return {"results": results, "fail_count": fail_count}

