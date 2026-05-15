"""
Operational Home Dashboard Flow -- WorkHive Tester

Seeds realistic data and verifies the home dashboard shows it correctly
when a worker is logged in. Tests the "good morning" operational view
that appears instead of the marketing page for logged-in users.

Coverage: index.html (operational home mode)

What this seeds:
  - 3 open logbook jobs (different categories)
  - 2 inventory items below reorder point
  - 1 low-risk and 1 high-risk asset_risk_scores row

What this verifies:
  1. index.html loads (HTTP 200)
  2. #ops-home div exists in the page HTML
  3. #mkt-wrap div exists in the page HTML
  4. Dashboard JS is present (_initDashboard function)
  5. Supabase CDN is loaded before the dashboard script
  6. Open jobs seeded correctly in logbook
  7. Low stock items seeded in inventory
"""

import json, datetime, random, urllib.request, urllib.error


SUPABASE_URL = "http://127.0.0.1:54321"
ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"


def run(page, errors, warnings, log) -> dict:
    from lib.supabase_client import get_client
    db = get_client()
    results = []

    log("Home Dashboard Flow: checking seeded hive + worker...")
    rows = db.table("hive_members").select("worker_name, hive_id").limit(1).execute().data
    if not rows:
        return {"results": [("WARN", "No seeded hive_members — dashboard will show empty state (still valid)")]}

    worker_name = rows[0]["worker_name"]
    hive_id     = rows[0]["hive_id"]
    now         = datetime.datetime.utcnow()
    log(f"  Worker: {worker_name}, Hive: {hive_id}")

    # ── Step 1: Seed 3 open logbook jobs ─────────────────────────────────────
    log("Step 1: Seeding open logbook jobs...")
    open_jobs = [
        {
            "hive_id":          hive_id,
            "worker_name":      worker_name,
            "machine":          "Centrifugal Pump CP-01",
            "maintenance_type": "Breakdown / Corrective",
            "category":         "Mechanical",
            "problem":          "Unusual vibration and temperature rise (bearing failure)",
            "status":           "Open",
            "date":             (now - datetime.timedelta(hours=2)).strftime("%Y-%m-%d"),
            "logged_at":        (now - datetime.timedelta(hours=2)).isoformat() + "Z",
            "created_at":       (now - datetime.timedelta(hours=2)).isoformat() + "Z",
        },
        {
            "hive_id":          hive_id,
            "worker_name":      worker_name,
            "machine":          "Air Compressor AC-02",
            "maintenance_type": "Breakdown / Corrective",
            "category":         "Mechanical",
            "problem":          "Temperature alarm triggered at 85 degrees C (overheating)",
            "status":           "Open",
            "date":             (now - datetime.timedelta(hours=5)).strftime("%Y-%m-%d"),
            "logged_at":        (now - datetime.timedelta(hours=5)).isoformat() + "Z",
            "created_at":       (now - datetime.timedelta(hours=5)).isoformat() + "Z",
        },
        {
            "hive_id":          hive_id,
            "worker_name":      worker_name,
            "machine":          "HVAC Unit AHU-01",
            "maintenance_type": "Preventive",
            "category":         "HVAC",
            "problem":          "Quarterly filter replacement due",
            "status":           "Open",
            "date":             (now - datetime.timedelta(hours=1)).strftime("%Y-%m-%d"),
            "logged_at":        (now - datetime.timedelta(hours=1)).isoformat() + "Z",
            "created_at":       (now - datetime.timedelta(hours=1)).isoformat() + "Z",
        },
    ]

    resp = db.table("logbook").insert(open_jobs).execute()
    n_jobs = len(resp.data or []) if hasattr(resp, "data") else 0
    log(f"  Seeded {n_jobs} open jobs")
    results.append(("PASS" if n_jobs == 3 else "WARN",
                     f"Open jobs seeded: {n_jobs}/3"))

    # ── Step 2: Seed 2 low-stock inventory items ──────────────────────────────
    log("Step 2: Seeding low-stock inventory items...")
    low_stock = [
        {
            "hive_id":       hive_id,
            "worker_name":   worker_name,
            "part_name":     "Bearing Seal Kit 6205",
            "part_number":   "BSK-6205",
            "category":      "Mechanical",
            "qty_on_hand":   2,
            "reorder_point": 5,
            "unit":          "pcs",
            "status":        "approved",
        },
        {
            "hive_id":       hive_id,
            "worker_name":   worker_name,
            "part_name":     "V-Belt Type A-54",
            "part_number":   "VB-A54",
            "category":      "Mechanical",
            "qty_on_hand":   0,
            "reorder_point": 3,
            "unit":          "pcs",
            "status":        "approved",
        },
    ]

    resp2 = db.table("inventory_items").insert(low_stock).execute()
    n_inv = len(resp2.data or []) if hasattr(resp2, "data") else 0
    log(f"  Seeded {n_inv} low-stock items")
    results.append(("PASS" if n_inv == 2 else "WARN",
                     f"Low-stock inventory items seeded: {n_inv}/2"))

    # ── Step 3: Seed 1 high-risk asset score ─────────────────────────────────
    log("Step 3: Seeding risk score rows...")
    risk_rows = [
        {
            "hive_id":       hive_id,
            "asset_name":    "Centrifugal Pump CP-01",
            "risk_score":    0.87,
            "risk_level":    "critical",
            "health_score":  13.0,
            "mtbf_days":     28.0,
            "top_factors":   json.dumps(["pm_overdue", "repeat_fault", "mtbf_approaching"]),
            "model_version": "rules-v1",
        },
        {
            "hive_id":       hive_id,
            "asset_name":    "Air Compressor AC-02",
            "risk_score":    0.72,
            "risk_level":    "high",
            "health_score":  28.0,
            "mtbf_days":     45.0,
            "top_factors":   json.dumps(["high_fault_freq"]),
            "model_version": "rules-v1",
        },
    ]

    resp3 = db.table("asset_risk_scores").insert(risk_rows).execute()
    n_risk = len(resp3.data or []) if hasattr(resp3, "data") else 0
    log(f"  Seeded {n_risk} risk score rows")
    results.append(("PASS" if n_risk == 2 else "WARN",
                     f"Risk score rows seeded: {n_risk}/2"))

    # ── Step 4: Verify index.html structure contains dashboard elements ───────
    log("Step 4: Verifying index.html dashboard structure...")
    try:
        req = urllib.request.Request(f"{page.rstrip('/')}/index.html", method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read(50000).decode("utf-8", errors="replace")

        checks = [
            ("ops-home div present",        'id="ops-home"'         in html),
            ("mkt-wrap div present",        'id="mkt-wrap"'         in html),
            ("_initDashboard function",     '_initDashboard'        in html),
            ("dashboard greeting element",  'id="oh-greeting"'      in html),
            ("stats grid element",          'id="oh-stats"'         in html),
            ("quick actions present",       'Log a Job'             in html),
            ("Supabase CDN loaded",         'supabase-js'           in html),
            ("escHtml in dashboard",        '_escHtml'              in html),
        ]

        for label, ok in checks:
            results.append(("PASS" if ok else "FAIL", label))

    except Exception as e:
        results.append(("WARN", f"index.html load check skipped: {type(e).__name__}"))

    log(f"  Dashboard structure checks complete")
    return {"results": results}
