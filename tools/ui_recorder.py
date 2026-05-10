"""
WorkHive UI Auto-Recorder
Uses Playwright to automate WorkHive UI interactions and record them as video.
The recorded .webm becomes the "Solution Reveal" section of the ad video.

Each feature has a DEMO_SEQUENCE: a scripted story showing the pain (wrong way)
then the solution (WorkHive way), timed for video production.

Usage:
    python tools/ui_recorder.py <feature_key> [--url http://...] [--worker "Name"]

Features:
    engineering_calc    Engineering Design Calculator
    logbook             Maintenance Logbook
    pm_checklist        PM Checklist
    inventory           Inventory Management
"""

import os
import sys
import argparse
import requests as _requests
from pathlib import Path
from datetime import datetime

ROOT           = Path(__file__).parent.parent
RECORDINGS_DIR = ROOT / ".tmp/ui_recordings"
WORKHIVE_URL   = os.getenv("WORKHIVE_URL", "http://127.0.0.1:5000")
DEFAULT_PASS   = "test1234"


def _tester_is_running() -> bool:
    try:
        _requests.get(f"{WORKHIVE_URL}/workhive/index.html", timeout=2)
        return True
    except Exception:
        return False


def _get_test_worker() -> tuple:
    """
    Get a real worker (username, display_name) via Supabase REST API.
    Returns (username, display_name).
    - username: used for sign-in form
    - display_name: used to look up hive_members (worker_name column)
    """
    try:
        from tools.platform_intel import _sb_get
        rows = _sb_get("worker_profiles", select="username,display_name", limit=1)
        if rows:
            return rows[0].get("username", ""), rows[0].get("display_name", "")
    except Exception:
        pass
    fallback = os.getenv("WORKHIVE_WORKER", "Demo Engineer")
    return fallback, fallback


def _get_worker_hive(display_name: str) -> str:
    """
    Get the hive_id for a worker using their display_name.
    hive_members.worker_name stores the display_name, not the username.
    """
    if not display_name:
        return ""
    try:
        from tools.platform_intel import _sb_get
        # Try active/approved first
        for status in ["eq.active", "eq.approved", None]:
            params = {"worker_name": f"eq.{display_name}"}
            if status:
                params["status"] = status
            rows = _sb_get("hive_members", select="hive_id", params=params, limit=1)
            if rows and rows[0].get("hive_id"):
                return rows[0]["hive_id"]
    except Exception:
        pass
    return ""


def _sign_in(page, log=print):
    """
    Sign in via WorkHive modal then inject wh_active_hive_id.
    Without hive_id every feature page (logbook, dashboard, PM, etc)
    loads with no data — blank screen, empty tables, nothing to show.
    """
    username, display_name = _get_test_worker()
    log(f"  signing in as: {username} ({display_name})")
    page.goto(f"{WORKHIVE_URL}/workhive/index.html?signin=1", wait_until="domcontentloaded")
    try:
        page.wait_for_selector("#si-username", timeout=10000, state="visible")
        page.fill("#si-username", username)
        page.fill("#si-password", DEFAULT_PASS)
        page.click("#si-btn")
        page.wait_for_function("() => localStorage.getItem('wh_last_worker')", timeout=15000)
        log(f"  signed in OK")
    except Exception as exc:
        log(f"  sign-in timeout ({exc}) — injecting localStorage directly")
        page.evaluate(f"() => localStorage.setItem('wh_last_worker', '{display_name}')")

    # Inject hive_id — without this all feature pages show empty state
    hive_id = _get_worker_hive(display_name)
    if hive_id:
        page.evaluate(
            f"() => {{"
            f"  localStorage.setItem('wh_active_hive_id', '{hive_id}');"
            f"  localStorage.setItem('wh_hive_id', '{hive_id}');"
            f"}}"
        )
        log(f"  hive injected: {hive_id}")
    else:
        log(f"  [WARN] no hive found for {worker} — pages may show empty state")


# ── Timing helpers ────────────────────────────────────────────────────────────

def slow_type(page, selector: str, text: str, delay: int = 120):
    """Type like a human — one character at a time with a delay."""
    el = page.locator(f"{selector}:visible").first
    if not el.count():
        print(f"  [WARN] selector not found: {selector}")
        return
    el.click()
    el.fill("")
    page.wait_for_timeout(300)
    for ch in text:
        page.keyboard.type(ch)
        page.wait_for_timeout(delay)


def clear_inputs(page, selectors: list):
    for sel in selectors:
        el = page.locator(f"{sel}:visible").first
        if el.count():
            el.fill("")
            page.wait_for_timeout(100)


def click_btn(page, text_variants: list, wait_after: int = 1500):
    for text in text_variants:
        btn = page.locator(f"button:has-text('{text}'):visible").first
        if btn.count():
            btn.scroll_into_view_if_needed()
            page.wait_for_timeout(300)
            btn.click()
            page.wait_for_timeout(wait_after)
            return True
    print(f"  [WARN] button not found: {text_variants}")
    return False


def pause(page, ms: int, label: str = ""):
    if label:
        print(f"  [{label}]")
    page.wait_for_timeout(ms)


def auth_inject(page, worker: str = None):
    """No-op — auth is now injected via add_init_script before any page load."""
    pass


# ── Demo sequences ─────────────────────────────────────────────────────────────

def demo_engineering_calc(page):
    """
    Story: Engineer guesses wrong pump values → dangerous result →
    corrects with proper values → WorkHive gives result to PH standards.
    Uses real selectors from engineering-design.html.
    """
    print("  [1/7] Opening Engineering Design Calculator...")
    page.goto(f"{WORKHIVE_URL}/workhive/engineering-design.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)

    print("  [2/7] Selecting Mechanical discipline...")
    disc = page.locator("button.discipline-pill[data-disc='Mechanical']")
    if disc.count():
        disc.click()
    else:
        # fallback: call JS directly
        page.evaluate("selectDiscipline('Mechanical')")
    page.wait_for_timeout(2000)

    print("  [3/7] Selecting Pump Sizing (TDH)...")
    # Try clicking the calc card; fall back to JS call
    card = page.locator(".calc-card").filter(has_text="Pump Sizing").first
    if card.count():
        card.scroll_into_view_if_needed()
        card.click()
    else:
        page.evaluate("selectCalcType('Pump Sizing (TDH)')")
    page.wait_for_timeout(2500)
    pause(page, 2000, "blank form loaded — engineer about to guess")

    print("  [4/7] PROBLEM: typing wrong unrealistic values...")
    pause(page, 1000)
    slow_type(page, "#f-flow-rate",     "999",  delay=160)   # dangerously high
    slow_type(page, "#f-static-head",   "250",  delay=160)
    slow_type(page, "#f-pipe-length",   "5000", delay=130)
    slow_type(page, "#f-pipe-diameter", "0.5",  delay=160)
    pause(page, 1000)

    print("  [5/7] Calculating with wrong values...")
    calc_btn = page.locator("#calc-btn")
    if calc_btn.count() and calc_btn.is_enabled():
        calc_btn.click()
    else:
        page.evaluate("runCalculation()")
    page.wait_for_timeout(6000)
    pause(page, 3000, "wrong/dangerous result — let viewer see the problem")

    print("  [6/7] SOLUTION: clearing and entering correct values...")
    clear_inputs(page, [
        "#f-flow-rate", "#f-static-head",
        "#f-pipe-length", "#f-pipe-diameter",
    ])
    pause(page, 1500, "clearing — moment of realisation")

    slow_type(page, "#f-flow-rate",     "50",  delay=120)
    slow_type(page, "#f-static-head",   "15",  delay=120)
    slow_type(page, "#f-pipe-length",   "100", delay=120)
    slow_type(page, "#f-pipe-diameter", "4",   delay=120)
    pause(page, 1000)

    calc_btn2 = page.locator("#calc-btn")
    if calc_btn2.count() and calc_btn2.is_enabled():
        calc_btn2.click()
    else:
        page.evaluate("runCalculation()")
    page.wait_for_timeout(6000)
    pause(page, 4000, "correct result — engineering units, PH standards")

    print("  [7/7] Scrolling to show full report...")
    page.mouse.wheel(0, 600)
    pause(page, 3000, "full report visible")
    page.mouse.wheel(0, 400)
    pause(page, 2000)


def demo_ai_assistant(page):
    """
    Story: Veteran retires, knowledge gone → AI Assistant answers from logbook data.
    Pattern from assistant_flow.py: #chat-input, button:has-text('Send'), wait 45s.
    """
    print("  [1/5] Opening AI Maintenance Assistant...")
    page.goto(f"{WORKHIVE_URL}/workhive/assistant.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    pause(page, 2000, "empty chat — all that knowledge, locked in one person's head")

    print("  [2/5] Typing a real maintenance question slowly...")
    chat_input = page.locator("#chat-input, textarea[placeholder*='ask' i]").first
    if chat_input.count():
        chat_input.click()
        page.wait_for_timeout(400)
        question = "Why does Pump 3 keep overloading? How many times has this happened?"
        for ch in question:
            page.keyboard.type(ch)
            page.wait_for_timeout(85)
    pause(page, 800)

    print("  [3/5] Sending — AI pulls from logbook data...")
    send_btn = page.locator("button:has-text('Send')").first
    if send_btn.count():
        send_btn.click()
    else:
        page.keyboard.press("Enter")
    page.wait_for_timeout(1000)

    print("  [4/5] Waiting for AI response (up to 45s — same as test)...")
    pause(page, 40000, "AI thinking — cross-referencing every logbook entry for this machine")

    print("  [5/5] Showing full answer...")
    page.mouse.wheel(0, 400)
    pause(page, 5000, "specific answer from real data — Mang Ben retired but his knowledge stayed")


def demo_shift_handover(page):
    """
    Story: Critical info dies between shifts → Shift Handover Report in one click.
    Logbook page has a Handover tab — click it, generate, show the report.
    """
    print("  [1/5] Opening Logbook...")
    page.goto(f"{WORKHIVE_URL}/workhive/logbook.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    pause(page, 2500, "open entries, running machines — next shift will walk in blind without this")

    print("  [2/5] Finding Handover tab/button...")
    # Try data-tab, text, or JS evaluate
    handover = page.locator(
        "[data-tab='handover'], button:has-text('Handover'), "
        "a:has-text('Handover'), #handover-tab"
    ).first
    if handover.count():
        handover.click()
        page.wait_for_timeout(2000)
    else:
        page.evaluate("""() => {
            const el = document.querySelector('[data-tab="handover"], .handover-tab');
            if (el) el.click();
        }""")
        page.wait_for_timeout(2000)
    pause(page, 2000, "handover section — auto-pulls open issues and pending PMs")

    print("  [3/5] Generating the report...")
    gen = page.locator(
        "button:has-text('Generate'), button:has-text('Create Handover'), "
        "button:has-text('Handover Report'), button:has-text('Print')"
    ).first
    if gen.count():
        gen.click()
        page.wait_for_timeout(3000)
    pause(page, 3000, "report generated in seconds")

    print("  [4/5] Scrolling through the report...")
    page.mouse.wheel(0, 500)
    pause(page, 4000, "open work orders, hot machines, overdue PMs — all structured")
    page.mouse.wheel(0, 400)
    pause(page, 3000, "LOTO status, pending tasks — nothing left to guess")

    print("  [5/5] Top of report...")
    page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
    page.wait_for_timeout(1500)
    pause(page, 2000)


def demo_day_planner(page):
    """
    Story: PMs pile up, no plan → Day Planner gives every worker a structured day.
    Pattern from dayplanner_flow.py: #task-input, button:has-text('Add'), checkbox.
    """
    print("  [1/5] Opening Day Planner...")
    page.goto(f"{WORKHIVE_URL}/workhive/dayplanner.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    pause(page, 3000, "DILO — today's tasks, time-blocked and prioritised")

    print("  [2/5] Adding a new task...")
    task_input = page.locator("#task-input, input[type='text']:visible").first
    if task_input.count():
        task_input.click()
        slow_type(page, "#task-input, input[type='text']:visible",
                  "Check bearing alignment — Pump 3", delay=80)
        page.wait_for_timeout(400)
        add_btn = page.locator("button:has-text('Add')").first
        if add_btn.count():
            add_btn.click()
        else:
            page.keyboard.press("Enter")
        page.wait_for_timeout(1500)
    pause(page, 2000, "task added — visible to supervisor in real time")

    print("  [3/5] Checking off a task...")
    cb = page.locator("input[type='checkbox']:visible").first
    if cb.count():
        cb.click()
        page.wait_for_timeout(1500)
    pause(page, 2500, "done — completion logged with timestamp")

    print("  [4/5] Switching to WILO (weekly view)...")
    wilo = page.locator("button:has-text('WILO'), button:has-text('Week')").first
    if wilo.count():
        wilo.click()
        page.wait_for_timeout(2000)
    pause(page, 4000, "WILO — full week at a glance, PMs planned ahead")

    print("  [5/5] Back to DILO...")
    dilo = page.locator("button:has-text('DILO'), button:has-text('Today'), button:has-text('Day')").first
    if dilo.count():
        dilo.click()
        page.wait_for_timeout(1500)
    pause(page, 2500, "every shift, every worker — structured and accountable")


def demo_skill_matrix(page):
    """
    Story: Wrong person assigned to untrained job →
    Skill Matrix shows exactly who can do what.
    Pattern from skillmatrix_flow.py: [data-discipline], button:has-text('Mechanical'),
    [data-level], progress bars.
    """
    print("  [1/4] Opening Skill Matrix...")
    page.goto(f"{WORKHIVE_URL}/workhive/skillmatrix.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    pause(page, 3000, "full team competency — every worker, every skill, every level")

    print("  [2/4] Clicking a discipline tab...")
    disc = page.locator("[data-discipline], button:has-text('Mechanical')").first
    if disc.count():
        disc.click()
        page.wait_for_timeout(1500)
    page.mouse.wheel(0, 350)
    pause(page, 3500, "skill levels per worker — red gaps mean untrained, don't assign")

    print("  [3/4] Scrolling to show badge progress...")
    page.mouse.wheel(0, 400)
    pause(page, 3500, "badges and certifications — updated automatically as workers complete PMs")

    print("  [4/4] Back to overview...")
    page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
    page.wait_for_timeout(1500)
    pause(page, 3000, "right person, right job — every time")


def demo_marketplace(page):
    """
    Story: Inventory hits zero, no local supplier →
    Marketplace connects plant to plant, Philippine industry to Philippine industry.
    Pattern from marketplace_flow.py: /marketplace.html, [data-listing-id],
    input[type='search'], button[data-category], button:has-text('Contact').
    """
    print("  [1/5] Opening Marketplace...")
    page.goto(f"{WORKHIVE_URL}/workhive/marketplace.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    pause(page, 3000, "parts from Philippine plants — not Lazada, not China — fellow workers")

    print("  [2/5] Searching for a part...")
    search = page.locator("input[type='search'], #marketplace-search, input[placeholder*='search' i]").first
    if search.count():
        search.fill("bearing")
        page.wait_for_timeout(1500)
    pause(page, 2500, "instant search across all listings")

    print("  [3/5] Clicking a category filter...")
    cat_btn = page.locator("button[data-category], button:has-text('Mechanical'), button:has-text('Electrical')").first
    if cat_btn.count():
        cat_btn.click()
        page.wait_for_timeout(1500)

    print("  [4/5] Opening a listing...")
    listing = page.locator("[data-listing-id], .listing-card").first
    if listing.count():
        listing.scroll_into_view_if_needed()
        listing.click()
        page.wait_for_timeout(2000)
    pause(page, 4000, "seller verified, price listed — contact directly, no middleman")

    print("  [5/5] Contact button...")
    contact = page.locator("button:has-text('Contact'), button:has-text('Inquire')").first
    if contact.count():
        contact.click()
        page.wait_for_timeout(1500)
    pause(page, 3000, "plant to plant — Philippine industry helping Philippine industry")


def demo_community(page):
    """
    Story: Obscure machine failure, nobody knows the fix →
    Community Forum — plant workers sharing real solutions.
    Pattern from community.py: /community.html, [data-post-id],
    textarea[placeholder*='share'], button:has-text('Post').
    """
    print("  [1/5] Opening Community Forum...")
    page.goto(f"{WORKHIVE_URL}/workhive/community.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    pause(page, 3000, "real questions, real answers — plant workers helping each other")

    print("  [2/5] Scrolling through posts...")
    page.mouse.wheel(0, 400)
    pause(page, 3500, "not generic Google results — someone who fixed this exact machine")

    print("  [3/5] Opening a post...")
    post = page.locator("[data-post-id], .community-post, .post-card").first
    if post.count():
        post.scroll_into_view_if_needed()
        post.click()
        page.wait_for_timeout(2000)
    pause(page, 4000, "full solution thread — parts used, steps taken, lessons learned")

    print("  [4/5] Going back and composing a new question...")
    page.go_back()
    page.wait_for_timeout(2000)

    compose = page.locator("textarea[placeholder*='share' i], textarea[placeholder*='post' i], textarea[placeholder*='ask' i]").first
    if compose.count():
        compose.click()
        slow_type(page, "textarea[placeholder*='share' i], textarea[placeholder*='post' i]",
                  "Sino nakaranas ng overheating sa VFD ng conveyor? Pano niyo naayos?",
                  delay=70)
        page.wait_for_timeout(500)

    print("  [5/5] Showing Post button (don't actually post in demo)...")
    pause(page, 3000, "post to the entire network — answers from across Philippine industry")


def demo_logbook(page):
    """
    Story: machine breaks → log it in WorkHive → knowledge captured forever.
    Uses the same JS patterns as logbook_crud.py (the working test):
      - selectAsset() to pick machine (not the flaky picker UI)
      - stepGo(n) to navigate wizard steps
      - Direct value assignment for selects (reliable)
    """
    print("  [1/6] Opening Maintenance Logbook...")
    page.goto(f"{WORKHIVE_URL}/workhive/logbook.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    pause(page, 2500, "team logbook — every repair, every machine, every shift")

    print("  [2/6] STEP 1 — Selecting machine via JS (reliable)...")
    # Get a real asset from the hive database
    hive_id = page.evaluate("localStorage.getItem('wh_active_hive_id') || ''")
    asset = None
    if hive_id:
        try:
            from tools.platform_intel import _sb_get
            rows = _sb_get("assets", select="id,asset_name,asset_ref",
                           params={"hive_id": f"eq.{hive_id}", "status": "eq.approved"},
                           limit=1)
            if rows:
                asset = rows[0]
        except Exception:
            pass

    if asset:
        asset_id   = asset.get("id", "")
        asset_name = asset.get("asset_name", "Machine A")
        asset_ref  = asset.get("asset_ref", "")
        page.evaluate(f"selectAsset('{asset_id}', '{asset_name}', '{asset_ref}')")
        print(f"     selected: {asset_name}")
    else:
        # Fallback: use asset ref directly (like the test uses TEST_MACHINE = "P-001")
        page.evaluate("selectAsset('P-001', 'Pump P-001', null)")
    page.wait_for_timeout(1500)
    pause(page, 2000, "machine selected — past failures and PM history auto-load")

    # Set maintenance type via JS (avoids select visibility issues)
    page.evaluate("document.getElementById('f-maint-type').value = 'Breakdown / Corrective'")
    page.wait_for_timeout(500)

    print("  [3/6] → Step 2: What happened...")
    page.evaluate("stepGo(2)")
    page.wait_for_timeout(1500)

    page.evaluate("document.getElementById('f-category').value = 'Mechanical'")
    page.wait_for_timeout(400)

    slow_type(page, "#f-problem",
              "Belt slipping at startup. Stops every 2 hours. Third time this month.",
              delay=65)
    page.wait_for_timeout(500)

    page.evaluate("document.getElementById('f-root-cause').value = 'Wear'")
    page.wait_for_timeout(400)
    pause(page, 1500, "problem described — root cause selected")

    print("  [4/6] → Step 3: What did you do...")
    page.evaluate("stepGo(3)")
    page.wait_for_timeout(1500)

    slow_type(page, "#f-action",
              "Replaced tensioner pulley bearing. Re-aligned belt. Torque set to 45 Nm.",
              delay=60)
    page.wait_for_timeout(500)

    slow_type(page, "#f-knowledge",
              "Check tensioner every 500 hrs. Replace bearing at first vibration sign. "
              "Correct torque is 45 Nm — NOT 40 Nm as per old manual.",
              delay=55)
    pause(page, 2500, "knowledge captured — the next technician will know this")

    print("  [5/6] Saving entry...")
    save = page.locator("#save-entry-btn")
    if save.count():
        save.scroll_into_view_if_needed()
        save.click()
        page.wait_for_timeout(4000)

    print("  [6/6] Entry saved — showing in the list...")
    pause(page, 4000, "saved — searchable by every team member, forever")


def demo_hive_dashboard(page):
    """
    Story: Supervisor blind to plant status → Hive Dashboard reveals
    everything in real time: open WOs, PM overdue, stock alerts, AI patterns.
    This is a tour-style demo — no wrong/right comparison, just the reveal.
    """
    print("  [1/6] Opening Hive Dashboard...")
    page.goto(f"{WORKHIVE_URL}/workhive/hive.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)   # let KPI chips populate from DB

    print("  [2/6] KPI chips — open WOs, PM overdue, stock alerts...")
    pause(page, 4000, "viewer reads the KPI numbers — this is the money shot")

    print("  [3/6] Scrolling to Pattern Alerts (AI-detected)...")
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(1500)
    pause(page, 4000, "AI-detected failure patterns — viewer absorbs it")

    print("  [4/6] Scrolling to Reliability Coach...")
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(1500)
    pause(page, 4000, "structured action cards — what to do about each alert")

    print("  [5/6] Scrolling to Today's Brief...")
    page.mouse.wheel(0, 450)
    page.wait_for_timeout(1500)
    pause(page, 3500, "AI daily summary — supervisor reads the full picture")

    print("  [6/6] Scroll back to top — live indicator visible...")
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    page.wait_for_timeout(2000)
    pause(page, 3000, "green live dot — real-time, always current")


def demo_pm_checklist(page):
    """
    Story: paper checklist signed without doing the work →
    WorkHive digital PM requires real completion with timestamp.
    Pattern from pm_flow.py: /pm-scheduler.html, [data-asset-id], [data-scope-item-id],
    button:has-text('Done').
    """
    print("  [1/5] Opening PM Scheduler...")
    page.goto(f"{WORKHIVE_URL}/workhive/pm-scheduler.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3000)
    pause(page, 2500, "every asset, every PM task — due dates, frequencies, history")

    print("  [2/5] Clicking first PM asset to expand tasks...")
    asset = page.locator("[data-asset-id]").first
    if asset.count():
        asset.scroll_into_view_if_needed()
        asset.click()
        page.wait_for_timeout(2000)
    pause(page, 2500, "scope items expand — what to check, step by step")

    print("  [3/5] Completing a scope item...")
    scope_item = page.locator("[data-scope-item-id]").first
    if scope_item.count():
        scope_item.scroll_into_view_if_needed()
        scope_item.click()
        page.wait_for_timeout(800)

    done_btn = page.locator("button:has-text('Done'), button:has-text('Complete')").first
    if done_btn.count():
        done_btn.click()
        page.wait_for_timeout(2500)
    pause(page, 3000, "timestamped, worker-signed — this cannot be faked on paper")

    print("  [4/5] Scrolling to show overdue assets...")
    page.mouse.wheel(0, 500)
    pause(page, 3500, "overdue highlighted — management sees this in real time on the dashboard")

    print("  [5/5] Back to top...")
    page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
    page.wait_for_timeout(1500)
    pause(page, 2000)


def demo_inventory(page):
    """
    Story: part not available, repair delayed →
    WorkHive inventory shows stock, alerts before it hits zero.
    Read-only demo — no mutating actions to avoid stale-modal selector traps.
    """
    print("  [1/6] Opening Inventory...")
    page.goto(f"{WORKHIVE_URL}/workhive/inventory.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(3500)
    pause(page, 3000, "all parts, all stock levels — one screen")

    print("  [2/6] Showing the parts list...")
    page.mouse.wheel(0, 250)
    pause(page, 3000, "every part you have, every part you need")

    print("  [3/6] Scrolling further to surface low-stock alerts...")
    page.mouse.wheel(0, 400)
    pause(page, 3500, "items below reorder point — system flags them before you run out")

    print("  [4/6] Searching for a critical part...")
    search = page.locator("#inv-search, input[placeholder*='search' i]").first
    if search.count():
        search.click()
        for ch in "bearing":
            page.keyboard.type(ch)
            page.wait_for_timeout(110)
        pause(page, 2500, "instant search — any part across all stock")

    print("  [5/6] Clearing search and clicking a low-stock card...")
    if search.count():
        search.fill("")
        page.wait_for_timeout(800)
    item = page.locator("[data-item-id], .inv-card").first
    if item.count():
        item.scroll_into_view_if_needed()
        item.click()
        pause(page, 3000, "tap any part to see usage history and reorder details")

    print("  [6/6] Back to top — emphasising the dashboard view...")
    page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
    page.wait_for_timeout(1200)
    pause(page, 2500, "no more 'out of stock' surprises in the middle of a repair")


# ── New features (added 2026-05) ──────────────────────────────────────────────

def demo_analytics(page):
    """
    Story: Manager opens dashboard at start of week → sees OEE, MTBF, downtime
    across 4 analytics phases (Descriptive, Diagnostic, Predictive, Prescriptive).
    """
    print("  [1/5] Opening Analytics & OEE Dashboard...")
    page.goto(f"{WORKHIVE_URL}/workhive/analytics.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4500)
    pause(page, 2500, "OEE, MTBF, downtime — your plant in numbers")

    print("  [2/5] Scrolling through KPI cards...")
    page.mouse.wheel(0, 350)
    pause(page, 2500, "every machine, every breakdown, every minute lost")

    print("  [3/5] Clicking Diagnostic tab — the why...")
    diag_tab = page.locator(
        "button:has-text('Diagnostic'), [data-phase='diagnostic'], a:has-text('Diagnostic')"
    ).first
    if diag_tab.count():
        diag_tab.click()
        pause(page, 5000, "not just what broke — why it broke")

    print("  [4/5] Clicking Predictive tab — the future...")
    pred_tab = page.locator(
        "button:has-text('Predictive'), [data-phase='predictive'], a:has-text('Predictive')"
    ).first
    if pred_tab.count():
        pred_tab.click()
        pause(page, 5000, "what is going to break next — before it does")

    print("  [5/5] Clicking Prescriptive — the action...")
    prescr_tab = page.locator(
        "button:has-text('Prescriptive'), [data-phase='prescriptive'], a:has-text('Prescriptive')"
    ).first
    if prescr_tab.count():
        prescr_tab.click()
        pause(page, 4500, "and what to do about it — written for you")


def demo_predictive(page):
    """
    Story: ML model ranks every asset by failure risk → critical machines surface
    before they break. Worker sees Pump CP-01 flagged red, prevents a $50k stoppage.
    """
    print("  [1/5] Opening Predictive Analytics...")
    page.goto(f"{WORKHIVE_URL}/workhive/predictive.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4500)
    pause(page, 2500, "machine learning — every asset scored by failure risk")

    print("  [2/5] Showing critical / high / medium / low counts...")
    pause(page, 3000, "red = critical risk, orange = high risk, yellow = medium")

    print("  [3/5] Scrolling through ranking table...")
    page.mouse.wheel(0, 350)
    pause(page, 3500, "the model knows which pump will fail before you do")

    print("  [4/5] Switching to Health Heatmap view...")
    heat_btn = page.locator(
        "[data-panel='panel-heatmap'], button:has-text('Health Heatmap'), button.tab:has-text('Heatmap')"
    ).first
    if heat_btn.count():
        heat_btn.click()
        page.wait_for_timeout(1500)
        pause(page, 4500, "whole plant at a glance — green safe, red about to break")

    print("  [5/5] Final: prevent the breakdown before it happens...")
    page.mouse.wheel(0, -300)
    pause(page, 3000, "fix it now or fix it tomorrow at 2am — your call")


def demo_asset_brain(page):
    """
    Story: Engineer needs full history on Pump CP-100 → Asset Brain shows ISO 14224
    hierarchy + every failure + every PM + every part used + sister assets.
    """
    print("  [1/5] Opening Asset Hub...")
    page.goto(f"{WORKHIVE_URL}/workhive/asset-hub.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)
    pause(page, 2500, "every machine — full lifetime in one view")

    print("  [2/5] Searching for an asset...")
    search = page.locator("#asset-search, input[placeholder*='search' i]").first
    if search.count():
        search.click()
        for ch in "Pump":
            page.keyboard.type(ch)
            page.wait_for_timeout(120)
        pause(page, 1500, "search across the whole plant hierarchy")

    print("  [3/5] Clicking the first matching asset...")
    first_card = page.locator("#asset-list .asset-card, #asset-list [data-asset-id], #asset-list > div").first
    if first_card.count():
        first_card.click()
        page.wait_for_timeout(2500)

    print("  [4/5] Showing Asset 360 — failures, PMs, parts, sister assets...")
    pause(page, 4500, "every failure, every PM, every part — asset 360")

    print("  [5/5] Scrolling through lifetime data...")
    page.mouse.wheel(0, 400)
    pause(page, 4000, "ISO 14224 hierarchy — enterprise to equipment, all linked")


def demo_shift_brain(page):
    """
    Story: Supervisor opens Shift Brain at 5:50am → AI-generated plan for the
    06-14 shift: risk-top assets, due PMs, carry-overs, parts to pre-stage.
    """
    print("  [1/5] Opening Shift Brain...")
    page.goto(f"{WORKHIVE_URL}/workhive/shift-brain.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)
    pause(page, 3000, "5:50am — your shift plan written before you arrive")

    print("  [2/5] Showing the AI briefing...")
    pause(page, 4500, "AI reads logbook, PMs, predictive scores — produces the brief")

    print("  [3/5] Scrolling to risk-top section...")
    page.mouse.wheel(0, 350)
    pause(page, 3500, "top risks today: which machines need eyes on them first")

    print("  [4/5] Showing PMs due + carry-forward from previous shift...")
    page.mouse.wheel(0, 350)
    pause(page, 3500, "open work from night shift, PMs due today, parts to stage")

    print("  [5/5] Showing assignments...")
    page.mouse.wheel(0, 300)
    pause(page, 3500, "who does what — supervisor reviews, publishes, shift starts")


def demo_achievements(page):
    """
    Story: Worker logs an entry → sees XP go up, level progress bar fill, new
    badge unlock. Maintenance feels like progress, not chore.
    """
    print("  [1/5] Opening Achievements...")
    page.goto(f"{WORKHIVE_URL}/workhive/achievements.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)
    pause(page, 3000, "every closed entry, every PM, every helpful answer = XP")

    print("  [2/5] Showing level + composite score...")
    pause(page, 3500, "level, XP, composite skill score — you, on paper")

    print("  [3/5] Scrolling through earned badges...")
    page.mouse.wheel(0, 400)
    pause(page, 4000, "badges for breakdown response, PM streaks, knowledge sharing")

    print("  [4/5] Showing badge progress bars...")
    page.mouse.wheel(0, 350)
    pause(page, 3500, "5 more PMs and you unlock the next tier")

    print("  [5/5] End: maintenance work = recognized progress...")
    page.mouse.wheel(0, -400)
    pause(page, 3000, "your work, finally seen — beyond just paychecks")


def demo_alert_hub(page):
    """
    Story: Supervisor opens Alert Hub → one inbox for every alert: critical risk
    spikes, overdue PMs, low stock, failure signature warnings.
    """
    print("  [1/5] Opening Alert Hub...")
    page.goto(f"{WORKHIVE_URL}/workhive/alert-hub.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)
    pause(page, 3000, "everything that needs your attention — one inbox")

    print("  [2/5] Showing the alert feed...")
    page.mouse.wheel(0, 200)
    pause(page, 3500, "critical risk, overdue PM, low stock, signature alerts")

    print("  [3/5] Clicking a filter chip (e.g. Critical)...")
    crit_chip = page.locator(
        "#filters button:has-text('Critical'), [data-filter='critical'], .ftab:has-text('Critical')"
    ).first
    if crit_chip.count():
        crit_chip.click()
        page.wait_for_timeout(1500)
        pause(page, 3000, "filter to only what cannot wait")

    print("  [4/5] Scrolling through filtered alerts...")
    page.mouse.wheel(0, 300)
    pause(page, 3000, "no more 200 emails — just what matters now")

    print("  [5/5] Clicking the first alert to drill in...")
    first_alert = page.locator("#feed > *, .alert-card").first
    if first_alert.count():
        first_alert.click()
        pause(page, 3500, "one tap from alert to action")


def demo_ph_intelligence(page):
    """
    Story: Plant manager wants to know if his MTBF is good vs Philippine industry
    average → PH Intelligence shows benchmark + recommendations.
    """
    print("  [1/5] Opening PH Industry Intelligence...")
    page.goto(f"{WORKHIVE_URL}/workhive/ph-intelligence.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4500)
    pause(page, 3000, "your plant — vs Philippine industry peers")

    print("  [2/5] Showing the executive summary...")
    pause(page, 4500, "where you lead, where you lag — written, not just charted")

    print("  [3/5] Scrolling to MTBF benchmark chart...")
    page.mouse.wheel(0, 350)
    pause(page, 4000, "MTBF, OEE, downtime — ranked against the country")

    print("  [4/5] Showing failure mode breakdown...")
    page.mouse.wheel(0, 350)
    pause(page, 3500, "which failure modes hit your industry hardest")

    print("  [5/5] Scrolling to recommendations...")
    page.mouse.wheel(0, 350)
    pause(page, 4500, "specific actions for your plant — not generic advice")


def demo_integrations(page):
    """
    Story: IT manager doesn't want to abandon SAP PM → Integrations page shows
    Import / Live Sync / API Keys — three ways to bridge WorkHive to existing CMMS.
    """
    print("  [1/5] Opening Integrations...")
    page.goto(f"{WORKHIVE_URL}/workhive/integrations.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)
    pause(page, 3000, "already on SAP PM or Maximo? Bridge it, do not replace it")

    print("  [2/5] Showing Import File tab (default)...")
    pause(page, 3500, "Tab 1: drop a CSV from your existing CMMS — done")

    print("  [3/5] Switching to Live Sync tab...")
    sync_tab = page.locator("#tab-sync, button:has-text('Live Sync')").first
    if sync_tab.count():
        sync_tab.click()
        page.wait_for_timeout(1500)
        pause(page, 4000, "Tab 2: live two-way sync with your CMMS via webhook")

    print("  [4/5] Switching to API Keys tab...")
    api_tab = page.locator("#tab-api, button:has-text('API Keys')").first
    if api_tab.count():
        api_tab.click()
        page.wait_for_timeout(1500)
        pause(page, 4000, "Tab 3: REST API for custom integrations")

    print("  [5/5] Back to import — emphasising the easiest path...")
    imp_tab = page.locator("#tab-import, button:has-text('Import File')").first
    if imp_tab.count():
        imp_tab.click()
        pause(page, 3500, "start with import — upgrade to live sync when ready")


def demo_audit_log(page):
    """
    Story: Plant manager has to prove regulator compliance →
    Audit Log shows every supervisor + worker action with timestamps.
    """
    print("  [1/5] Opening Audit Log...")
    page.goto(f"{WORKHIVE_URL}/workhive/audit-log.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)
    pause(page, 3000, "every action — every worker, every supervisor — recorded")

    print("  [2/5] Showing the activity stream...")
    page.mouse.wheel(0, 250)
    pause(page, 3500, "approvals, edits, stock changes, work orders — full trail")

    print("  [3/5] Scrolling deeper into history...")
    page.mouse.wheel(0, 400)
    pause(page, 3500, "weeks of activity, ranked newest first")

    print("  [4/5] Filtering by action type if available...")
    filter_btn = page.locator(
        "select[id*='filter'], button:has-text('Filter'), [data-action='filter']"
    ).first
    if filter_btn.count():
        filter_btn.click()
        page.wait_for_timeout(1500)
        pause(page, 3000, "filter by actor, action type, or date range")

    print("  [5/5] Back to top — emphasising compliance value...")
    page.evaluate("window.scrollTo({top:0, behavior:'smooth'})")
    page.wait_for_timeout(1200)
    pause(page, 3500, "ready for ISO audit, regulator review, or insurance claim")


def demo_project_manager(page):
    """
    Story: Plant manager planning Q3 overhaul → opens Project Manager, sees all
    open projects, drills into the boiler overhaul, reviews tasks + parts + skills.
    """
    print("  [1/6] Opening Project Manager...")
    page.goto(f"{WORKHIVE_URL}/workhive/project-manager.html",
              wait_until="networkidle", timeout=20000)
    page.wait_for_timeout(4000)
    pause(page, 3000, "long-running maintenance projects — overhauls, shutdowns, capex")

    print("  [2/6] Showing the project card grid...")
    page.mouse.wheel(0, 250)
    pause(page, 3000, "every project, status at a glance")

    print("  [3/6] Searching for a project...")
    search = page.locator("#filter-search").first
    if search.count():
        search.click()
        for ch in "overhaul":
            page.keyboard.type(ch)
            page.wait_for_timeout(120)
        pause(page, 1800, "filter by name, type, or owner")

    print("  [4/6] Clearing search and clicking the first project card...")
    if search.count():
        search.fill("")
        page.wait_for_timeout(500)
    first_card = page.locator("#card-grid > *").first
    if first_card.count():
        first_card.click()
        page.wait_for_timeout(2500)

    print("  [5/6] Showing project detail — milestones, tasks, parts...")
    pause(page, 4500, "milestones, tasks, parts staging, skill assignments — one view")

    print("  [6/6] Scrolling through deliverables...")
    page.mouse.wheel(0, 400)
    pause(page, 4000, "from kickoff to handover — nothing falls through the cracks")


# ── Feature registry ──────────────────────────────────────────────────────────

DEMOS = {
    # ── Engineering ─────────────────────────────────────────────────────────
    "engineering_calc":              demo_engineering_calc,
    "Engineering Design Calculator": demo_engineering_calc,
    # ── Logbook ─────────────────────────────────────────────────────────────
    "logbook":                       demo_logbook,
    "Maintenance Logbook":           demo_logbook,
    # ── PM ──────────────────────────────────────────────────────────────────
    "pm_checklist":                  demo_pm_checklist,
    "PM Checklist":                  demo_pm_checklist,
    # ── Inventory ───────────────────────────────────────────────────────────
    "inventory":                     demo_inventory,
    "Inventory Management":          demo_inventory,
    # ── Hive Dashboard ──────────────────────────────────────────────────────
    "hive_dashboard":                demo_hive_dashboard,
    "Hive Dashboard":                demo_hive_dashboard,
    # ── AI Assistant ────────────────────────────────────────────────────────
    "ai_assistant":                  demo_ai_assistant,
    "AI Maintenance Assistant":      demo_ai_assistant,
    # ── Shift Handover ──────────────────────────────────────────────────────
    "shift_handover":                demo_shift_handover,
    "Shift Handover Report":         demo_shift_handover,
    # ── Day Planner ─────────────────────────────────────────────────────────
    "day_planner":                   demo_day_planner,
    "Day Planner":                   demo_day_planner,
    # ── Skill Matrix ────────────────────────────────────────────────────────
    "skill_matrix":                  demo_skill_matrix,
    "Skill Matrix":                  demo_skill_matrix,
    # ── Marketplace ─────────────────────────────────────────────────────────
    "marketplace":                   demo_marketplace,
    "Marketplace":                   demo_marketplace,
    # ── Community ───────────────────────────────────────────────────────────
    "community":                     demo_community,
    "Community Forum":               demo_community,
    # ── Analytics & OEE Dashboard ───────────────────────────────────────────
    "analytics":                     demo_analytics,
    "Analytics & OEE Dashboard":     demo_analytics,
    # ── Predictive Analytics ────────────────────────────────────────────────
    "predictive":                    demo_predictive,
    "Predictive Analytics":          demo_predictive,
    # ── Asset Brain ─────────────────────────────────────────────────────────
    "asset_brain":                   demo_asset_brain,
    "Asset Brain":                   demo_asset_brain,
    # ── Shift Brain ─────────────────────────────────────────────────────────
    "shift_brain":                   demo_shift_brain,
    "Shift Brain":                   demo_shift_brain,
    # ── Achievements ────────────────────────────────────────────────────────
    "achievements":                  demo_achievements,
    "Achievements":                  demo_achievements,
    # ── Alert Hub ───────────────────────────────────────────────────────────
    "alert_hub":                     demo_alert_hub,
    "Alert Hub":                     demo_alert_hub,
    # ── PH Industry Intelligence ────────────────────────────────────────────
    "ph_intelligence":               demo_ph_intelligence,
    "PH Industry Intelligence":      demo_ph_intelligence,
    # ── CMMS Integrations ───────────────────────────────────────────────────
    "integrations":                  demo_integrations,
    "CMMS Integrations":             demo_integrations,
    # ── Project Manager ─────────────────────────────────────────────────────
    "project_manager":               demo_project_manager,
    "Project Manager":               demo_project_manager,
    # ── Audit Log & Compliance ──────────────────────────────────────────────
    "audit_log":                     demo_audit_log,
    "Audit Log & Compliance":        demo_audit_log,
}

# Features that have a demo sequence (used by the dashboard UI)
SUPPORTED_FEATURES = [k for k in DEMOS if not k.replace(" ", "_").islower()]

# Landing URL for each feature (used by manual recording)
FEATURE_URLS = {
    "Engineering Design Calculator": "/workhive/engineering-design.html",
    "Maintenance Logbook":           "/workhive/logbook.html",
    "PM Checklist":                  "/workhive/pm-scheduler.html",
    "Inventory Management":          "/workhive/inventory.html",
    "Hive Dashboard":                "/workhive/hive.html",
    "AI Maintenance Assistant":      "/workhive/assistant.html",
    "Shift Handover Report":         "/workhive/logbook.html",
    "Day Planner":                   "/workhive/dayplanner.html",
    "Skill Matrix":                  "/workhive/skillmatrix.html",
    "Marketplace":                   "/workhive/marketplace.html",
    "Community Forum":               "/workhive/community.html",
    # New 2026-05
    "Analytics & OEE Dashboard":     "/workhive/analytics.html",
    "Predictive Analytics":          "/workhive/predictive.html",
    "Asset Brain":                   "/workhive/asset-hub.html",
    "Shift Brain":                   "/workhive/shift-brain.html",
    "Achievements":                  "/workhive/achievements.html",
    "Alert Hub":                     "/workhive/alert-hub.html",
    "PH Industry Intelligence":      "/workhive/ph-intelligence.html",
    "CMMS Integrations":             "/workhive/integrations.html",
    "Project Manager":               "/workhive/project-manager.html",
    "Audit Log & Compliance":        "/workhive/audit-log.html",
}


# ── Manual recorder ───────────────────────────────────────────────────────────

def record_manual_session(feature: str, duration_s: int = 60) -> Path:
    """
    Open a visible browser authenticated and ready at the feature page.
    Show a countdown timer overlay so the user knows how much time remains.
    Record everything the user does. Auto-close when time is up.
    """
    from playwright.sync_api import sync_playwright

    url      = FEATURE_URLS.get(feature, "/workhive/index.html")
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_key = feature.lower().replace(" ", "_").replace("/", "_")[:30]
    video_dir = RECORDINGS_DIR / f"manual_{safe_key}_{ts}"
    video_dir.mkdir(parents=True, exist_ok=True)

    username, display_name = _get_test_worker()
    hive_id = _get_worker_hive(display_name)

    print(f"\n  Manual recording: {feature}")
    print(f"  URL:      {WORKHIVE_URL}{url}")
    print(f"  Worker:   {display_name}  |  Hive: {hive_id or 'none'}")
    print(f"  Duration: {duration_s} seconds")
    print(f"  → Browser will open. Do your demo. It auto-closes when the timer hits 0.\n")

    saved_path = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=["--start-maximized", "--disable-infobars"],
        )
        context = browser.new_context(
            # no_viewport lets the browser use its full maximized window size.
            # The user can scroll and click everything naturally.
            # record_video_size controls what gets captured for the video output.
            no_viewport=True,
            record_video_dir=str(video_dir),
            record_video_size={"width": 1280, "height": 900},
        )

        # Inject auth before every page load — same as auto recorder
        if hive_id:
            context.add_init_script(f"""
                (function() {{
                    localStorage.setItem('wh_last_worker',     '{display_name}');
                    localStorage.setItem('wh_worker_name',     '{display_name}');
                    localStorage.setItem('wh_active_hive_id',  '{hive_id}');
                    localStorage.setItem('wh_hive_id',         '{hive_id}');
                    const _remove = localStorage.removeItem.bind(localStorage);
                    localStorage.removeItem = function(key) {{
                        if (key === 'wh_active_hive_id' || key === 'wh_hive_id') return;
                        return _remove(key);
                    }};
                }})();
            """)

        page = context.new_page()
        page.on("console", lambda msg: None)

        # Navigate to the feature page
        page.goto(f"{WORKHIVE_URL}{url}", wait_until="networkidle", timeout=20000)
        page.wait_for_timeout(2000)

        # Inject countdown timer overlay (visible on screen + in recording)
        page.evaluate(f"""
            (function() {{
                const overlay = document.createElement('div');
                overlay.id = 'wh-rec-timer';
                overlay.style.cssText = [
                    'position:fixed', 'top:14px', 'right:14px', 'z-index:2147483647',
                    'background:rgba(239,68,68,0.92)', 'color:white',
                    'padding:7px 18px', 'border-radius:10px',
                    'font-family:Poppins,Inter,sans-serif', 'font-weight:700',
                    'font-size:14px', 'letter-spacing:0.03em',
                    'box-shadow:0 4px 20px rgba(0,0,0,0.5)',
                    'pointer-events:none',
                ].join(';');
                overlay.textContent = '● REC  {duration_s}s';
                document.body.appendChild(overlay);

                let secs = {duration_s};
                const iv = setInterval(() => {{
                    secs--;
                    overlay.textContent = '● REC  ' + secs + 's';
                    if (secs <= 15) overlay.style.background = 'rgba(220,20,20,1)';
                    if (secs <= 5)  overlay.textContent = '● REC  ' + secs + 's  FINISHING';
                    if (secs <= 0) {{
                        clearInterval(iv);
                        overlay.style.background = 'rgba(34,197,94,0.95)';
                        overlay.textContent = '✓  Recording saved';
                    }}
                }}, 1000);
            }})();
        """)

        # Wait for the full duration — user does whatever they want
        page.wait_for_timeout(duration_s * 1000)
        print(f"  Time is up. Saving recording...")

        context.close()
        browser.close()

    # Locate and rename the .webm
    webm_files = list(video_dir.glob("*.webm"))
    if webm_files:
        final_name = RECORDINGS_DIR / f"manual_{safe_key}_{ts}.webm"
        webm_files[0].rename(final_name)
        saved_path = final_name
        print(f"  Saved: {saved_path.name}  ({saved_path.stat().st_size // 1024} KB)")

    return saved_path


# ── Recorder ──────────────────────────────────────────────────────────────────

def record(feature_key: str, output_path: Path = None, headless: bool = False) -> Path:
    """
    Run a feature demo using the WorkHive Tester session and save as .webm.
    Requires the WorkHive Tester to be running on port 5000.
    Returns the path to the saved video.
    """
    from playwright.sync_api import sync_playwright

    demo_fn = DEMOS.get(feature_key)
    if not demo_fn:
        raise ValueError(
            f"No demo sequence for '{feature_key}'.\n"
            f"Available: {[k for k in DEMOS if '_' not in k]}"
        )

    # Gate: tester must be running
    if not _tester_is_running():
        raise RuntimeError(
            f"WorkHive Tester is not running at {WORKHIVE_URL}.\n"
            "Start it first: double-click 'WorkHive Tester' on your Desktop, "
            "then try recording again."
        )

    print(f"\nRecording: {feature_key}")
    print(f"  Server:  {WORKHIVE_URL}")
    print(f"  Mode:    {'headless' if headless else 'visible browser (you will see it run)'}\n")

    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_key  = feature_key.lower().replace(" ", "_").replace("/", "_")[:30]
    video_dir = RECORDINGS_DIR / f"{safe_key}_{ts}"
    video_dir.mkdir(parents=True, exist_ok=True)

    saved_path = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--start-maximized"] if not headless else [],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            record_video_dir=str(video_dir),
            record_video_size={"width": 1280, "height": 900},
        )
        # Resolve auth values BEFORE opening the browser
        username, display_name = _get_test_worker()
        hive_id = _get_worker_hive(display_name)
        print(f"  Auth: {display_name} / hive: {hive_id or 'none'}")

        if not hive_id:
            raise RuntimeError(
                f"No hive found for worker '{display_name}'. "
                "Make sure the WorkHive Tester has seeded data."
            )

        # Inject ALL auth values before every page load via init script.
        # This bypasses the sign-in modal and prevents membership re-check redirects.
        # Also freezes localStorage.removeItem for hive keys so pages can't strip them.
        context.add_init_script(f"""
            (function() {{
                // Set auth values before any page code runs
                localStorage.setItem('wh_last_worker',     '{display_name}');
                localStorage.setItem('wh_worker_name',     '{display_name}');
                localStorage.setItem('wh_active_hive_id',  '{hive_id}');
                localStorage.setItem('wh_hive_id',         '{hive_id}');

                // Freeze hive keys — prevent membership checks from removing them
                const _remove = localStorage.removeItem.bind(localStorage);
                localStorage.removeItem = function(key) {{
                    if (key === 'wh_active_hive_id' || key === 'wh_hive_id') return;
                    return _remove(key);
                }};
            }})();
        """)

        page = context.new_page()
        page.on("console", lambda msg: None)

        try:
            page.wait_for_timeout(500)

            # Run the demo sequence
            demo_fn(page)
            print("\n  Demo complete. Saving video...")
            page.wait_for_timeout(1500)

        except Exception as exc:
            print(f"\n  [ERROR] {exc}")
            raise
        finally:
            context.close()   # Playwright saves .webm on context close
            browser.close()

    # Locate and rename the saved file
    webm_files = list(video_dir.glob("*.webm"))
    if webm_files:
        saved_path = webm_files[0]
        final_name = RECORDINGS_DIR / f"{safe_key}_{ts}.webm"
        saved_path.rename(final_name)
        saved_path = final_name
        print(f"  Saved:  {saved_path}")
        print(f"  Size:   {saved_path.stat().st_size // 1024} KB")
    else:
        print("  [WARN] No .webm produced — check that the tester page rendered correctly.")

    return saved_path


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WorkHive UI Auto-Recorder")
    parser.add_argument("feature", nargs="?", default="engineering_calc",
                        help="Feature to demo (default: engineering_calc)")
    parser.add_argument("--url", default=None, help="WorkHive base URL")
    parser.add_argument("--worker", default=None, help="Worker name to inject")
    parser.add_argument("--headless", action="store_true", help="Run headless (no visible browser)")
    parser.add_argument("--list", action="store_true", help="List available features")
    args = parser.parse_args()

    if args.list:
        print("\nAvailable features:")
        for k in DEMOS:
            print(f"  {k}")
        sys.exit(0)

    if args.url:
        WORKHIVE_URL = args.url
    if args.worker:
        WORKHIVE_WORKER = args.worker

    result = record(args.feature, headless=args.headless)
    if result:
        print(f"\nDone. Open this file in CapCut:\n  {result}")
    else:
        print("\nRecording failed.")
        sys.exit(1)
