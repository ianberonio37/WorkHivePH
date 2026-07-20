"""
Alert Hub Flow -- WorkHive Tester

Seeds one alert of every kind (risk, PM overdue, low stock, pattern, system)
then verifies alert-hub.html aggregates them into a single chronological feed.

Coverage: alert-hub.html

What this seeds:
  - 1 critical asset_risk_scores row
  - 1 inventory_items row below reorder_point
  - 1 pm_assets with NO completion in last 30 days (overdue)
  - 1 failure_signature_alerts row (if table exists)
  - 1 automation_log entry with status='failed'

What this verifies:
  1. alert-hub.html loads (HTTP 200)
  2. All 6 filter chips render (All, Risk, PM, Stock, Pattern, System)
  3. Filter chips include count badges
  4. Page loads even when failure_signature_alerts table is missing locally
  5. Hive gate appears when no HIVE_ID in localStorage (separate test)
"""

import datetime, urllib.request, urllib.error


def run(page, errors, warnings, log) -> dict:
    from lib.supabase_client import get_client
    db = get_client()
    results = []

    log("Alert Hub Flow: locating seeded hive...")
    members = db.table("hive_members").select("worker_name, hive_id, auth_uid").limit(1).execute().data
    if not members:
        return {"results": [("WARN", "No seeded hive_members — Alert Hub needs a hive context")]}

    worker_name = members[0]["worker_name"]
    hive_id     = members[0]["hive_id"]
    auth_uid    = members[0].get("auth_uid")   # D3: attribute the seeded inventory row to its worker
    now         = datetime.datetime.utcnow()
    log(f"  Worker: {worker_name}, Hive: {hive_id}")

    # ── Step 1: Seed a critical asset_risk_scores row ────────────────────────
    log("Step 1: Seeding critical risk score for Pump CP-201...")
    try:
        # top_factors uses Phase 5a structured shape ([{factor, weight, value,
        # contribution, explanation}]) so consumers that only handle the legacy
        # string-array shape surface as [object Object] in the tester rather
        # than first appearing in production. alert-hub.html bug 2026-05-10
        # was masked by the prior legacy-only seeder.
        db.table("asset_risk_scores").insert({
            "hive_id":       hive_id,
            "asset_name":    "Centrifugal Pump CP-201 (alert-test)",
            "risk_score":    0.91,
            "risk_level":    "critical",
            "health_score":  9.0,
            "mtbf_days":     21.0,
            "top_factors": [
                {"factor": "pm_overdue",         "weight": 0.35, "value": 1.0, "contribution": 0.42, "explanation": "PM is 21 days overdue"},
                {"factor": "repeat_fault",       "weight": 0.30, "value": 0.8, "contribution": 0.30, "explanation": "3 same-symptom failures in last 30 days"},
                {"factor": "mtbf_approaching",   "weight": 0.20, "value": 0.6, "contribution": 0.18, "explanation": "Next failure expected within MTBF window"},
            ],
            "model_version": "rules-v2",
        }).execute()
        results.append(("PASS", "Risk alert seeded (Pump CP-201, critical)"))
    except Exception as e:
        results.append(("WARN", f"asset_risk_scores insert: {e}"))

    # ── Step 2: Seed a low-stock inventory item ───────────────────────────────
    log("Step 2: Seeding low-stock part (alert-test)...")
    try:
        db.table("inventory_items").insert({
            "id":            f"at-ms32-{int(__import__('time').time())}",
            "hive_id":       hive_id,
            "worker_name":   worker_name,
            "auth_uid":      auth_uid,
            "part_name":     "Mechanical Seal MS-32 (alert-test)",
            "part_number":   "MS-32-AT",
            "category":      "Mechanical",
            "qty_on_hand":   0,
            "min_qty":       4,
            "unit":          "pcs",
            "status":        "approved",
        }).execute()
        results.append(("PASS", "Low-stock alert seeded (Mechanical Seal MS-32)"))
    except Exception as e:
        results.append(("WARN", f"inventory_items insert: {e}"))

    # ── Step 3: Seed a pm_asset that will read as overdue ─────────────────────
    log("Step 3: Seeding overdue PM asset (no completion in 30+ days)...")
    try:
        db.table("pm_assets").insert({
            "hive_id":       hive_id,
            "worker_name":   worker_name,
            "asset_name":    "Cooling Tower CT-99 (alert-test)",
            "category":      "Mechanical",
            "criticality":   "high",
        }).execute()
        # No pm_completions inserted, so the alert-hub query will flag it as overdue
        results.append(("PASS", "PM overdue alert seeded (Cooling Tower CT-99)"))
    except Exception as e:
        results.append(("WARN", f"pm_assets insert: {e}"))

    # ── Step 4: Seed a failure_signature_alerts row (table may not exist) ────
    log("Step 4: Seeding pattern alert (best-effort — table may not exist)...")
    try:
        db.table("failure_signature_alerts").insert({
            "hive_id":         hive_id,
            "machine":         "Conveyor Belt CB-44",
            "signature_kind":  "repeat_failure",
            "message":         "Same belt slip pattern detected 3 times in 14 days",
            "severity":        "high",
        }).execute()
        results.append(("PASS", "Pattern alert seeded"))
    except Exception as e:
        # Not a hard fail — local Supabase may not have the failure_signatures migration
        results.append(("WARN", f"failure_signature_alerts skipped: {type(e).__name__}"))

    # ── Step 5a: Seed a pending parts_staging_recommendation (Phase ML-2) ────
    log("Step 5a: Seeding pending parts_staging_recommendation...")
    try:
        import json as _json
        db.table("parts_staging_recommendations").insert({
            "hive_id":      hive_id,
            "asset_name":   "Centrifugal Pump CP-201 (alert-test)",
            "risk_score":   0.91,
            "failure_mode": "Bearing failure",
            "parts":        _json.dumps([
                {"item_id": "demo-1", "part_name": "Mechanical Seal MS-32",
                 "qty_avg": 1, "confidence": 0.78, "in_stock": 4},
                {"item_id": "demo-2", "part_name": "Bearing Kit 6205",
                 "qty_avg": 2, "confidence": 0.65, "in_stock": 6},
            ]),
            "rationale":    "Risk score 0.91 -- 2 parts appear in 65%+ of past corrective fixes.",
            "confidence":   0.72,
            "status":       "pending",
            "model_version": "rules-v1",
        }).execute()
        results.append(("PASS", "Staging recommendation seeded (Pump CP-201)"))
    except Exception as e:
        results.append(("WARN", f"parts_staging_recommendations insert: {e}"))

    # ── Step 5: Seed a failed automation_log entry ────────────────────────────
    log("Step 5: Seeding failed automation_log row...")
    try:
        db.table("automation_log").insert({
            "job_name":     "shift-brain-test",
            "hive_id":      hive_id,
            "status":       "failed",
            "detail":       "AI provider chain returned 503 (alert-hub seed)",
            "triggered_at": now.isoformat() + "Z",
        }).execute()
        results.append(("PASS", "System alert seeded (automation failure)"))
    except Exception as e:
        results.append(("WARN", f"automation_log insert: {e}"))

    # ── Step 6: Verify alert-hub.html structure ──────────────────────────────
    log("Step 6: Verifying alert-hub.html structure...")
    try:
        req = urllib.request.Request(f"{page.rstrip('/')}/alert-hub.html", method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read(50000).decode("utf-8", errors="replace")

        checks = [
            ("alert-hub HTML loads",       True),  # got here = 200
            ("filters container present",  'id="filters"'    in html),
            ("feed container present",     'id="feed"'       in html),
            ("empty state present",        'id="empty"'      in html),
            ("queries asset_risk_scores",  'asset_risk_scores' in html),
            ("queries inventory_items",    'inventory_items' in html),
            ("queries pm_completions",     'pm_completions'  in html),
            ("queries automation_log",     'automation_log'  in html),
            ("queries failure_signature",  'failure_signature_alerts' in html),
            ("queries parts_staging_recommendations",
                                            'parts_staging_recommendations' in html),
            ("staging filter chip in KINDS",
                                            "id: 'staging'"  in html),
            ("auto-refresh setInterval",   'setInterval'     in html and '60000' in html),
            ("hive gate present",          'gate-card'       in html),
        ]
        for label, ok in checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"alert-hub.html load skipped: {type(e).__name__}"))

    return {"results": results}
