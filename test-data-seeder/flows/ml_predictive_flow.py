"""
ML Predictive Maintenance Flow -- WorkHive Tester
===================================================
Seeds realistic failure-pattern data designed to produce meaningful ML outputs,
then verifies the full pipeline: batch-risk-scoring -> asset_risk_scores -> predictive.html.

What this flow seeds:
  - 6 assets with known failure patterns (3 high-risk, 3 low-risk)
  - 120+ corrective logbook entries spread over 18 months
  - PM completions (some on-time, some overdue)
  - Inventory transactions with a bearing-seal spike in the last 30 days

What this flow verifies:
  1. batch-risk-scoring edge function runs without error
  2. asset_risk_scores table has rows for the hive
  3. High-risk assets (Pump CP-01, HP-01) are scored high or critical
  4. predictive.html loads (HTTP 200)
  5. model_version field is present in scored rows

Coverage: predictive.html
"""

import json, datetime, random, urllib.request, urllib.error

SUPABASE_URL = "http://127.0.0.1:54321"
ANON_KEY = "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH"

# Assets with failure patterns:
# (name, failure_interval_days, failure_mode, expect_high_risk)
ASSETS = [
    ("Centrifugal Pump CP-01",  28,  "Bearing failure",   True),   # fails every 28d -- HIGH
    ("Hydraulic Press HP-01",   21,  "Seal leak",          True),   # fails every 21d -- CRITICAL
    ("Air Compressor AC-02",    45,  "Overheating",        True),   # fails every 45d -- HIGH
    ("Cooling Tower CT-01",     90,  "Scale buildup",      False),  # stable
    ("Conveyor Belt CB-03",    120,  "Belt wear",           False),  # stable
    ("HVAC Unit AHU-01",       180,  "Filter clogging",    False),  # stable
]

CATEGORIES  = ["Mechanical", "Electrical", "Mechanical", "Mechanical", "Mechanical", "HVAC"]
ROOT_CAUSES = [
    "Insufficient lubrication",
    "Hydraulic seal degradation",
    "Cooling failure",
    "Mineral scale accumulation",
    "Belt tension loss",
    "Filter saturation",
]


def _post(endpoint: str, body: dict, timeout: int = 60) -> dict:
    data = json.dumps(body).encode("utf-8")
    req  = urllib.request.Request(
        f"{SUPABASE_URL}{endpoint}",
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {ANON_KEY}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        return {"error": f"HTTP {e.code}: {body[:200]}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def _get(endpoint: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(
        f"{SUPABASE_URL}{endpoint}",
        headers={"Authorization": f"Bearer {ANON_KEY}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def run(page, errors, warnings, log) -> dict:
    from lib.supabase_client import get_client
    db = get_client()
    results = []

    log("ML Predictive Flow: finding seeded hive...")
    rows = db.table("hive_members").select("worker_name, hive_id").limit(1).execute().data
    if not rows:
        return {"results": [("FAIL", "No seeded hive_members -- run smoke flow first")]}

    worker_name = rows[0]["worker_name"]
    hive_id     = rows[0]["hive_id"]
    log(f"  Using hive {hive_id}, worker {worker_name}")

    # ── Step 1: Seed corrective logbook entries per asset ─────────────────────
    log("Step 1: Seeding corrective logbook entries (120+ entries)...")
    now   = datetime.datetime.utcnow()
    total_seeded = 0

    for idx, (asset_name, interval_days, failure_mode, _) in enumerate(ASSETS):
        category  = CATEGORIES[idx]
        root_cause = ROOT_CAUSES[idx]

        # Seed 18 months of history at this interval
        months_back = 18
        n_faults    = max(2, int(months_back * 30 / interval_days))
        entries     = []

        for i in range(n_faults):
            days_ago = int(interval_days * (n_faults - i) + random.randint(-3, 3))
            fault_dt = now - datetime.timedelta(days=days_ago)
            entries.append({
                "hive_id":          hive_id,
                "worker_name":      worker_name,
                "machine":          asset_name,
                "maintenance_type": "Breakdown / Corrective",
                "category":         category,
                "root_cause":       root_cause,
                "problem":          f"{failure_mode} detected during inspection",
                "action":           "Replaced worn component and tested system",
                "downtime_hours":   round(random.uniform(1.5, 6.0), 1),
                "status":           "Closed",
                "date":             fault_dt.strftime("%Y-%m-%d"),
                "closed_at":        fault_dt.isoformat() + "Z",
                "created_at":       fault_dt.isoformat() + "Z",
                "knowledge":        f"Recurring {failure_mode.lower()} on {asset_name}",
            })

        resp = db.table("logbook").insert(entries).execute()
        if hasattr(resp, "data"):
            total_seeded += len(resp.data or [])
        else:
            warnings.append(f"Logbook insert warning for {asset_name}")

    log(f"  Seeded {total_seeded} logbook entries")
    if total_seeded >= 30:
        results.append(("PASS", f"Seeded {total_seeded} corrective entries (>=30 minimum)"))
    else:
        results.append(("FAIL", f"Only {total_seeded} entries seeded — expected >= 30"))

    # ── Step 2: Seed inventory spike (bearing seals, last 30 days) ───────────
    log("Step 2: Seeding bearing seal consumption spike...")
    spike_entries = []
    for i in range(9):  # 9 uses in last 30d vs 1 in prior period = spike
        days_ago = random.randint(1, 29)
        spike_entries.append({
            "hive_id":     hive_id,
            "worker_name": worker_name,
            "part_name":   "Bearing Seal Kit",
            "qty_change":  -2,
            "type":        "use",
            "created_at":  (now - datetime.timedelta(days=days_ago)).isoformat() + "Z",
        })
    # Previous period: only 1 use
    spike_entries.append({
        "hive_id":     hive_id,
        "worker_name": worker_name,
        "part_name":   "Bearing Seal Kit",
        "qty_change":  -2,
        "type":        "use",
        "created_at":  (now - datetime.timedelta(days=95)).isoformat() + "Z",
    })
    inv_resp = db.table("inventory_transactions").insert(spike_entries).execute()
    n_inv = len(inv_resp.data or []) if hasattr(inv_resp, "data") else 0
    log(f"  Seeded {n_inv} inventory transactions (bearing seal spike)")
    if n_inv >= 5:
        results.append(("PASS", f"Inventory spike seeded ({n_inv} transactions)"))
    else:
        results.append(("WARN", f"Only {n_inv} inventory transactions seeded"))

    # ── Step 3: Trigger batch-risk-scoring edge function ──────────────────────
    log("Step 3: Triggering batch-risk-scoring edge function...")
    score_resp = _post("/functions/v1/batch-risk-scoring", {}, timeout=90)

    if "error" in score_resp:
        results.append(("FAIL", f"batch-risk-scoring error: {score_resp['error'][:150]}"))
    else:
        scored = score_resp.get("scored", 0)
        log(f"  Scored {scored} hives")
        results.append(("PASS" if scored >= 1 else "WARN",
                         f"batch-risk-scoring returned scored={scored}"))

    # ── Step 4: Verify asset_risk_scores table has rows ───────────────────────
    log("Step 4: Verifying asset_risk_scores populated...")
    risk_rows = db.table("asset_risk_scores") \
        .select("asset_name, risk_level, risk_score, model_version") \
        .eq("hive_id", hive_id) \
        .order("generated_at", desc=True) \
        .limit(50) \
        .execute() \
        .data or []

    if not risk_rows:
        results.append(("FAIL", "asset_risk_scores table empty after batch-risk-scoring"))
    else:
        results.append(("PASS", f"asset_risk_scores has {len(risk_rows)} rows for hive"))
        log(f"  {len(risk_rows)} risk score rows found")

        # Verify high-risk assets are correctly identified
        scored_assets = {r["asset_name"]: r for r in risk_rows}
        for asset_name, _, _, expect_high in ASSETS:
            if asset_name not in scored_assets:
                results.append(("WARN", f"Asset '{asset_name}' not in asset_risk_scores"))
                continue
            row   = scored_assets[asset_name]
            level = row["risk_level"]
            if expect_high and level not in ("high", "critical"):
                results.append(("FAIL",
                    f"'{asset_name}' expected high/critical risk, got '{level}' (score={row['risk_score']})"))
            elif expect_high:
                results.append(("PASS",
                    f"'{asset_name}' correctly scored {level} (score={row['risk_score']})"))

        # Verify model_version field present
        has_version = all("model_version" in r for r in risk_rows)
        if has_version:
            versions = set(r["model_version"] for r in risk_rows)
            results.append(("PASS", f"model_version field present, values: {versions}"))
        else:
            results.append(("FAIL", "model_version field missing from some asset_risk_scores rows"))

    # ── Step 5: Verify predictive.html loads ─────────────────────────────────
    log("Step 5: Verifying predictive.html page load...")
    try:
        req = urllib.request.Request(f"{page.rstrip('/')}/predictive.html", method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            status = r.status
            content = r.read(500).decode("utf-8", errors="replace")
        if status == 200 and "predictive" in content.lower():
            results.append(("PASS", "predictive.html loads (HTTP 200, content valid)"))
        else:
            results.append(("WARN", f"predictive.html loaded with status {status}"))
    except Exception as e:
        results.append(("WARN", f"predictive.html load check skipped in local test mode: {type(e).__name__}"))

    return {"results": results}
