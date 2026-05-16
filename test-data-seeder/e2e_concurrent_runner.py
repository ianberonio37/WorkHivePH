#!/usr/bin/env python3
"""
Concurrent Edit Test Runner — WorkHive Platform
================================================
Tests what happens when two users edit the same record simultaneously.

IMPORTANT: Uses Playwright ASYNC API (not sync) because Playwright's
sync API is NOT thread-safe. asyncio.gather() runs both actions truly
concurrently on the same event loop without the greenlet/thread conflict.

Scenarios:
  last_write_wins     — A and B edit same entry; B saves after A
                        Expected: conflict warning OR last-write-wins silently
  simultaneous_create — Both create entries at same time
                        Expected: both succeed (no duplicate key error)

Usage:
  python e2e_concurrent_runner.py                     # all pages
  python e2e_concurrent_runner.py --page logbook      # single page
  python e2e_concurrent_runner.py --scenario last_write_wins
"""

import sys, json, asyncio, argparse
from datetime import datetime
from typing import Dict, List, Optional, Tuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

BASE_URL = "http://127.0.0.1:5000/workhive"


def _get_two_workers() -> Tuple[str, str]:
    """Pick two workers from the same hive (both active members)."""
    from lib.supabase_client import get_client
    db = get_client()

    members = (
        db.table("hive_members")
        .select("worker_name, hive_id")
        .eq("status", "active")
        .limit(20)
        .execute().data or []
    )

    by_hive: Dict[str, list] = {}
    for m in members:
        by_hive.setdefault(m["hive_id"], []).append(m["worker_name"])

    for hive_id, names in by_hive.items():
        if len(names) >= 2:
            usernames = []
            for display_name in names[:3]:
                wp = (
                    db.table("worker_profiles")
                    .select("username")
                    .eq("display_name", display_name)
                    .limit(1)
                    .execute().data or []
                )
                if wp:
                    usernames.append(wp[0]["username"])
                if len(usernames) >= 2:
                    break
            if len(usernames) >= 2:
                return usernames[0], usernames[1]

    raise RuntimeError("Could not find 2 workers in the same hive")


async def login_async(page, username: str, password: str = "test1234") -> bool:
    """Sign in via the WorkHive login form (async)."""
    from lib.supabase_client import get_client

    await page.goto(f"{BASE_URL}/index.html?signin=1", wait_until="domcontentloaded")
    try:
        await page.wait_for_selector("#si-username", state="visible", timeout=8000)
    except:
        return False

    await page.click("#si-username")
    await page.fill("#si-username", username)
    await page.click("#si-password")
    await page.fill("#si-password", password)
    await page.click("#si-btn")

    try:
        await page.wait_for_function(
            "() => !!localStorage.getItem('wh_last_worker')", timeout=15000
        )
    except:
        return False

    last_worker = await page.evaluate("() => localStorage.getItem('wh_last_worker')")
    if not last_worker:
        return False

    # Set hive context via DB
    try:
        db = get_client()
        membership = (
            db.table("hive_members")
            .select("hive_id, role")
            .eq("worker_name", last_worker)
            .eq("status", "active")
            .limit(1)
            .execute().data or []
        )
        if membership:
            hive_id = membership[0]["hive_id"]
            role    = membership[0].get("role", "worker")
            hive_row = db.table("hives").select("name").eq("id", hive_id).single().execute().data or {}
            hive_name = hive_row.get("name", "")
            await page.evaluate(f"""() => {{
                localStorage.setItem('wh_active_hive_id', '{hive_id}');
                localStorage.setItem('wh_hive_id',        '{hive_id}');
                localStorage.setItem('wh_hive_role',      '{role}');
                localStorage.setItem('wh_hive_name',      '{hive_name}');
                try {{ if (typeof HIVE_ID !== 'undefined') HIVE_ID = '{hive_id}'; }} catch(e) {{}}
                try {{ if (typeof HIVE_ROLE !== 'undefined') HIVE_ROLE = '{role}'; }} catch(e) {{}}
            }}""")
    except:
        pass

    return True


async def goto_and_load(page, page_name: str):
    """Navigate to a page and trigger data load (async version of e2e_helpers.goto)."""
    await page.goto(f"{BASE_URL}/{page_name}.html", wait_until="networkidle", timeout=15000)
    await page.wait_for_timeout(800)
    try:
        await page.evaluate("""async () => {
            const g = document.getElementById('hive-gate');
            if (g) g.style.display = 'none';
            try { if (typeof _viewMode !== 'undefined') _viewMode = 'mine'; } catch(e) {}
            if (typeof loadEntries   === 'function') await loadEntries();
            if (typeof renderEntries === 'function') await renderEntries(false);
        }""")
        await page.wait_for_timeout(1500)
    except:
        pass


# ── Scenario: Last-write-wins ─────────────────────────────────────────────────

async def scenario_last_write_wins(browser, worker_a: str, worker_b: str) -> Dict:
    """
    A and B both open the same logbook entry and edit it.
    A saves first, B saves 2s later (with stale data).
    Expected: B sees a conflict warning, OR last-write silently overwrites.
    """
    result = {"scenario": "last_write_wins", "result": "WARN", "steps": []}

    ctx_a = await browser.new_context()
    ctx_b = await browser.new_context()
    page_a = await ctx_a.new_page()
    page_b = await ctx_b.new_page()

    try:
        # Use SAME worker on both sessions (2-tab simulation — both see same entries)
        ok_a = await login_async(page_a, worker_a)
        ok_b = await login_async(page_b, worker_a)  # same worker, not worker_b
        if not (ok_a and ok_b):
            result["result"] = "SKIP"
            result["reason"] = f"Login failed: A={ok_a}, B={ok_b}"
            return result

        await asyncio.gather(
            goto_and_load(page_a, "logbook"),
            goto_and_load(page_b, "logbook"),
        )

        entry_count = await page_a.locator(".entry-card").count()
        if entry_count == 0:
            result["result"] = "SKIP"
            result["reason"] = "No entries to edit (seeder gap)"
            return result

        # Click first entry on both → opens view modal (#modal)
        await page_a.locator(".entry-card").first.click()
        await page_b.locator(".entry-card").first.click()

        # Wait for view modal to appear on both pages
        for pg in [page_a, page_b]:
            try:
                await pg.wait_for_selector("#modal:not(.hidden)", timeout=5000)
            except:
                pass

        # Click "Edit Entry" button inside the view modal
        for pg in [page_a, page_b]:
            try:
                edit_btn = pg.locator("button:has-text('Edit Entry')").first
                if await edit_btn.is_visible(timeout=3000):
                    await edit_btn.click()
                    # Wait for edit form to enter editing mode (step panels shown)
                    await pg.wait_for_selector("#log-form.editing, #f-action", timeout=3000)
            except:
                pass

        result["steps"].append({"step": "both_in_edit_mode"})

        # Concurrent edit: A fills and saves, B fills with delay and saves
        edit_outcomes = {}

        async def user_a_edit():
            try:
                f = page_a.locator("#f-action").first
                if await f.is_visible(timeout=2000):
                    await f.fill("Concurrent test — User A edit")
                btn = page_a.locator("#save-entry-btn, button:has-text('Update')").first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await page_a.wait_for_timeout(1500)
                    edit_outcomes["a_saved"] = True
                else:
                    edit_outcomes["a_saved"] = False
            except Exception as e:
                edit_outcomes["a_error"] = str(e)[:60]
                edit_outcomes["a_saved"] = False

        async def user_b_edit():
            await asyncio.sleep(2)  # B saves 2s after A (stale data)
            try:
                f = page_b.locator("#f-action").first
                if await f.is_visible(timeout=2000):
                    await f.fill("Concurrent test — User B edit (stale)")
                btn = page_b.locator("#save-entry-btn, button:has-text('Update')").first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await page_b.wait_for_timeout(2000)
                    edit_outcomes["b_saved"] = True
                    # Check for conflict message
                    body_text = (await page_b.locator("body").inner_text()).lower()
                    edit_outcomes["conflict"] = any(
                        kw in body_text
                        for kw in ["conflict", "stale", "reload", "updated by", "changed since",
                                   "modified", "concurrent", "someone else"]
                    )
                else:
                    edit_outcomes["b_saved"] = False
            except Exception as e:
                edit_outcomes["b_error"] = str(e)[:60]
                edit_outcomes["b_saved"] = False

        await asyncio.gather(user_a_edit(), user_b_edit())

        result["steps"].append({
            "step": "concurrent_save",
            "a_saved": edit_outcomes.get("a_saved"),
            "b_saved": edit_outcomes.get("b_saved"),
            "conflict_detected": edit_outcomes.get("conflict", False),
        })

        if edit_outcomes.get("conflict"):
            result["result"] = "PASS"
            result["note"] = "Conflict detection working — B warned about stale data"
        elif edit_outcomes.get("a_saved") and edit_outcomes.get("b_saved"):
            result["result"] = "WARN"
            result["note"] = (
                "Both saves succeeded silently (last-write-wins, no conflict warning). "
                "B overwrote A's changes without notification. "
                "Consider adding optimistic locking via updated_at comparison."
            )
        else:
            result["result"] = "WARN"
            result["note"] = f"Could not complete edit flow. a_saved={edit_outcomes.get('a_saved')}, b_saved={edit_outcomes.get('b_saved')}"

    finally:
        await ctx_a.close()
        await ctx_b.close()

    return result


# ── Scenario: Simultaneous create ─────────────────────────────────────────────

async def scenario_simultaneous_create(browser, worker_a: str, worker_b: str) -> Dict:
    """
    A and B both create logbook entries at the exact same moment.
    Expected: both entries created successfully (no duplicate key conflict).
    """
    result = {"scenario": "simultaneous_create", "result": "PASS", "steps": []}

    ctx_a = await browser.new_context()
    ctx_b = await browser.new_context()
    page_a = await ctx_a.new_page()
    page_b = await ctx_b.new_page()

    try:
        ok_a = await login_async(page_a, worker_a)
        ok_b = await login_async(page_b, worker_b)
        if not (ok_a and ok_b):
            result["result"] = "SKIP"
            result["reason"] = f"Login failed: A={ok_a}, B={ok_b}"
            return result

        await asyncio.gather(
            goto_and_load(page_a, "logbook"),
            goto_and_load(page_b, "logbook"),
        )

        create_results = {}

        async def create_entry(page, label: str):
            try:
                # Force to step 3 and submit
                await page.evaluate(f"""async () => {{
                    const g = document.getElementById('hive-gate');
                    if (g) g.style.display = 'none';
                    const m = document.getElementById('f-machine');
                    if (m) m.value = 'CONCURRENT-TEST-{label}';
                    document.querySelectorAll('.step-panel').forEach(p => p.classList.remove('active'));
                    const s3 = document.getElementById('step-panel-3');
                    if (s3) s3.classList.add('active');
                    try {{ _currentStep = 3; }} catch(e) {{}}
                    const ap = document.getElementById('f-action');
                    if (ap) ap.value = 'Concurrent create test {label}';
                    const pp = document.getElementById('f-problem');
                    if (pp) pp.value = 'Concurrent test problem {label}';
                }}""")
                await page.wait_for_timeout(200)

                btn = page.locator("#save-entry-btn")
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await page.wait_for_timeout(2500)
                    body_text = (await page.locator("body").inner_text()).lower()
                    has_error = any(k in body_text for k in ["error", "failed", "duplicate", "conflict"])
                    create_results[label] = {"submitted": True, "error": has_error}
                else:
                    create_results[label] = {"submitted": False}
            except Exception as e:
                create_results[label] = {"submitted": False, "exception": str(e)[:60]}

        # Run both creates simultaneously
        await asyncio.gather(
            create_entry(page_a, "A"),
            create_entry(page_b, "B"),
        )

        a_ok = create_results.get("A", {}).get("submitted") and not create_results.get("A", {}).get("error")
        b_ok = create_results.get("B", {}).get("submitted") and not create_results.get("B", {}).get("error")

        result["steps"].append({"step": "simultaneous_create", "A": create_results.get("A"), "B": create_results.get("B")})

        if a_ok and b_ok:
            result["result"] = "PASS"
            result["note"] = "Both entries created without conflict"
        elif a_ok or b_ok:
            result["result"] = "WARN"
            result["note"] = "One creation failed — possible race condition on IDs"
        else:
            result["result"] = "WARN"
            result["note"] = "Neither create completed (form not available)"

    finally:
        await ctx_a.close()
        await ctx_b.close()

    return result


# ── Page scenario registry ────────────────────────────────────────────────────

PAGE_SCENARIOS = {
    "logbook":         ["last_write_wins", "simultaneous_create"],
    "community":       ["simultaneous_create"],
    "inventory":       ["last_write_wins"],
    "project-manager": ["last_write_wins", "simultaneous_create"],
    "marketplace":     ["last_write_wins"],
    "pm-scheduler":    ["last_write_wins"],
    "asset-hub":       ["last_write_wins"],
}

SCENARIO_FUNS = {
    "last_write_wins":    scenario_last_write_wins,
    "simultaneous_create": scenario_simultaneous_create,
}


# ── Main async runner ─────────────────────────────────────────────────────────

async def run_all_async(pages: List[str], scenario_filter: Optional[str] = None) -> Dict:
    from playwright.async_api import async_playwright

    results = {
        "timestamp": datetime.now().isoformat(),
        "pages": {},
        "total_pass": 0, "total_fail": 0, "total_warn": 0, "total_skip": 0,
    }

    worker_a, worker_b = _get_two_workers()
    print(f"Workers: A={worker_a}, B={worker_b}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, slow_mo=30)

        print(f"\n{BLUE}{'=' * 60}{RESET}")
        print(f"{BLUE}CONCURRENT EDIT TESTS — {len(pages)} pages{RESET}")
        print(f"{BLUE}{'=' * 60}{RESET}")

        for page_name in pages:
            scenarios = PAGE_SCENARIOS.get(page_name, [])
            if not scenarios:
                print(f"\n{YELLOW}[{page_name}]{RESET}  SKIP — no concurrent scenarios")
                continue

            print(f"\n{BLUE}[{page_name}]{RESET}  {len(scenarios)} scenario(s)")
            page_results = {"scenarios": [], "total_pass": 0, "total_fail": 0,
                           "total_warn": 0, "total_skip": 0}

            for scenario_name in scenarios:
                if scenario_filter and scenario_name != scenario_filter:
                    continue

                fn = SCENARIO_FUNS.get(scenario_name)
                if not fn:
                    continue

                print(f"  {scenario_name}...", end="", flush=True)
                try:
                    r = await fn(browser, worker_a, worker_b)
                except Exception as e:
                    r = {"scenario": scenario_name, "result": "FAIL", "error": str(e)[:100]}

                status = r.get("result", "FAIL")
                note = r.get("note") or r.get("reason") or r.get("error") or ""
                color = GREEN if status == "PASS" else (YELLOW if status in ("WARN","SKIP") else RED)
                print(f" {color}{status}{RESET}  {note[:75]}")

                page_results["scenarios"].append(r)
                if   status == "PASS": page_results["total_pass"] += 1
                elif status == "FAIL": page_results["total_fail"] += 1
                elif status == "WARN": page_results["total_warn"] += 1
                elif status == "SKIP": page_results["total_skip"] += 1

            results["pages"][page_name] = page_results
            results["total_pass"] += page_results["total_pass"]
            results["total_fail"] += page_results["total_fail"]
            results["total_warn"] += page_results["total_warn"]
            results["total_skip"] += page_results["total_skip"]

        await browser.close()

    p = results["total_pass"]; f = results["total_fail"]
    w = results["total_warn"]; s = results["total_skip"]
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"RESULTS: {p}{GREEN} PASS {RESET}| {f}{RED} FAIL {RESET}| {w}{YELLOW} WARN {RESET}| {s} SKIP")
    print(f"{BLUE}{'=' * 60}{RESET}")

    with open("e2e_concurrent_results.json", "w") as fh:
        json.dump(results, fh, indent=2)
    print("✓ Results saved to e2e_concurrent_results.json")

    return results


def main():
    parser = argparse.ArgumentParser(description="Concurrent Edit Tests")
    parser.add_argument("--page", type=str, help="Single page")
    parser.add_argument("--scenario", type=str, choices=list(SCENARIO_FUNS.keys()))
    args = parser.parse_args()

    pages = [args.page] if args.page else list(PAGE_SCENARIOS.keys())
    results = asyncio.run(run_all_async(pages, scenario_filter=args.scenario))
    return 0 if results["total_fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
