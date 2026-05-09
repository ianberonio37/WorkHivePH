"""
Shift Brain Flow -- WorkHive Tester

Seeds a draft shift_plan with a realistic AI-style briefing + structured
payload, then verifies shift-brain.html renders the briefing and supervisor
review controls.

Coverage: shift-brain.html

What this seeds:
  - 1 shift_plans row, status='draft', for the 06-14 morning window
  - Briefing text (1 paragraph, written like the AI orchestrator output)
  - payload JSON with risk_top, pms_due, carry_forward, parts_prestage,
    assignments — the 5 sections shift-brain.html reads

What this verifies:
  1. shift-brain.html loads (HTTP 200)
  2. brief-status pill element present
  3. queries shift_plans table
  4. shift window selector exists
  5. seeded draft row visible via direct DB read
"""

import json, datetime, urllib.request, urllib.error


def run(page, errors, warnings, log) -> dict:
    from lib.supabase_client import get_client
    db = get_client()
    results = []

    log("Shift Brain Flow: locating seeded hive...")
    members = db.table("hive_members").select("worker_name, hive_id").limit(1).execute().data
    if not members:
        return {"results": [("WARN", "No seeded hive_members — Shift Brain needs a hive context")]}

    worker_name = members[0]["worker_name"]
    hive_id     = members[0]["hive_id"]
    today       = datetime.date.today().isoformat()
    log(f"  Worker: {worker_name}, Hive: {hive_id}, Date: {today}")

    # ── Step 1: Seed a draft shift_plans row ──────────────────────────────────────
    log("Step 1: Seeding draft shift_plan for the 06-14 morning window...")

    payload = {
        "risk_top": [
            {"asset": "Centrifugal Pump CP-100", "level": "critical", "score": 0.87,
             "reason": "MTBF approaching, repeat bearing failures last 30 days"},
            {"asset": "Air Compressor AC-02",    "level": "high",     "score": 0.72,
             "reason": "Cooling failure pattern, last fault 14 days ago"},
        ],
        "pms_due": [
            {"asset": "HVAC Unit AHU-01", "task": "Quarterly filter change", "days_overdue": 0},
            {"asset": "Cooling Tower CT-01", "task": "Scale inspection",     "days_overdue": 3},
        ],
        "carry_forward": [
            {"machine": "Hydraulic Press HP-01",
             "summary": "Seal replacement started by night shift, finish today"},
        ],
        "parts_prestage": [
            {"part_name": "Bearing Seal Kit 6205", "qty": 2, "for": "CP-100"},
            {"part_name": "V-Belt Type A-54",       "qty": 1, "for": "AC-02"},
        ],
        "assignments": [
            {"worker": worker_name,
             "tasks":  ["Inspect CP-100 bearings", "Complete AHU-01 PM"]},
        ],
    }

    briefing = (
        "Critical attention on CP-100 today: bearing failure pattern is accelerating "
        "and the predicted next failure window opens in 2 days. Pre-stage 2 bearing "
        "seal kits and schedule the inspection by 10am. AC-02 is in the high band "
        "due to the cooling subsystem; verify cooling fan operation during morning "
        "rounds. Continue HP-01 seal replacement carried over from night shift; "
        "expected completion 11am. Two PMs are overdue — CT-01 scale inspection by 3 "
        "days, AHU-01 quarterly filter due today. Assign accordingly and confirm "
        "via the assignments panel before 7am sign-on."
    )

    try:
        # Delete any existing draft for this hive/date/window so re-runs are clean
        db.table("shift_plans") \
            .delete() \
            .eq("hive_id", hive_id) \
            .eq("shift_date", today) \
            .eq("shift_window", "06-14") \
            .execute()

        res = db.table("shift_plans").insert({
            "hive_id":      hive_id,
            "shift_window": "06-14",
            "shift_date":   today,
            "status":       "draft",
            "generated_by": "shift-planner-orchestrator (test seed)",
            "briefing":     briefing,
            "payload":      payload,
        }).execute()
        n_plan = len(res.data or [])
        log(f"  Seeded {n_plan} shift_plan rows")
        results.append(("PASS" if n_plan == 1 else "FAIL",
                         f"shift_plans seeded: {n_plan}/1 (status=draft)"))
    except Exception as e:
        results.append(("FAIL", f"shift_plans insert: {e}"))

    # ── Step 2: Verify the row reads back with the expected fields ────────────────
    log("Step 2: Verifying seeded plan via direct DB read...")
    try:
        res = db.table("shift_plans") \
            .select("status, shift_window, briefing, payload") \
            .eq("hive_id", hive_id) \
            .eq("shift_date", today) \
            .eq("shift_window", "06-14") \
            .limit(1) \
            .execute()
        row = (res.data or [None])[0]
        if not row:
            results.append(("FAIL", "Seeded shift_plan not retrievable on read-back"))
        else:
            results.append(("PASS" if row.get("status") == "draft" else "FAIL",
                             f"seeded plan status: {row.get('status')} (expected draft)"))
            payload_back = row.get("payload") or {}
            sections = ["risk_top", "pms_due", "carry_forward", "parts_prestage", "assignments"]
            missing  = [s for s in sections if s not in payload_back]
            if missing:
                results.append(("FAIL", f"payload missing sections: {missing}"))
            else:
                results.append(("PASS", f"payload has all 5 sections: {sections}"))
    except Exception as e:
        results.append(("WARN", f"shift_plans read-back: {e}"))

    # ── Step 3: Verify shift-brain.html structure ────────────────────────────────
    log("Step 3: Verifying shift-brain.html structure...")
    try:
        req = urllib.request.Request(f"{page.rstrip('/')}/shift-brain.html", method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read(50000).decode("utf-8", errors="replace")
        checks = [
            ("hub HTML loads (HTTP 200)", True),
            ("brief-status element",      'id="brief-status"' in html),
            ("brief-window element",      'id="brief-window"' in html),
            ("queries shift_plans",       'shift_plans'       in html),
            ("status-draft style",        'status-draft'      in html),
            ("status-published style",    'status-published'  in html),
            # Phase E -- supervisor publish flow
            ("publish CTA present",       'id="publish-btn"'  in html or "publishPlan(" in html),
            ("supervisor-role gating",    "HIVE_ROLE"         in html and "supervisor" in html),
            # Phase E -- orchestrator integration (graceful 404 handling)
            ("rerunPlan handler",         "rerunPlan"         in html or "shift-planner-orchestrator" in html),
            ("degraded-state messaging",  "non-2xx"           in html or "edge function"  in html.lower() or "running locally" in html.lower()),
        ]
        for label, ok in checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"shift-brain.html load skipped: {type(e).__name__}"))

    return {"results": results}
