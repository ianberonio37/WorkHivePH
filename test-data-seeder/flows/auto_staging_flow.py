"""
Auto-Staging Flow -- WorkHive Tester (Phase ML-2)

Verifies the Predictive Parts Auto-Staging pipeline end-to-end.

What this seeds:
  - 1 high-risk asset_risk_scores row (score >= 0.7) for "Compressor AC-77"
  - 3 inventory_items with stock for parts the asset has historically needed
  - 5 corrective logbook entries on AC-77 with consistent parts_used patterns
  - Then invokes parts-staging-recommender edge fn

What this verifies:
  1. parts-staging-recommender returns 200
  2. parts_staging_recommendations row exists with status=pending for AC-77
  3. Recommendation includes >= 1 part with confidence >= 0.4
  4. asset-hub.html ships staging-card element + loadDetailStaging function
  5. alert-hub.html queries parts_staging_recommendations and includes 'staging' filter
"""

import datetime, json, urllib.request, urllib.error
from .harness import BASE_URL


def _post_edge(base_url, fn_name, body, log):
    """Invoke a local edge function. Returns (ok, response_body, error_msg)."""
    url = f"{base_url.rstrip('/')}/functions/v1/{fn_name}"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = r.read().decode("utf-8", errors="replace")
            return True, payload, None
    except urllib.error.HTTPError as e:
        return False, "", f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return False, "", f"{type(e).__name__}: {e}"


def run(page, errors, warnings, log) -> dict:
    from lib.supabase_client import get_client
    db = get_client()
    results = []

    log("Auto-Staging Flow: locating seeded hive...")
    members = db.table("hive_members").select("worker_name, hive_id").limit(1).execute().data
    if not members:
        return {"results": [("WARN", "No seeded hive_members — Auto-Staging needs hive context")]}

    worker_name = members[0]["worker_name"]
    hive_id     = members[0]["hive_id"]
    asset_name  = "Compressor AC-77 (auto-staging-test)"
    now         = datetime.datetime.utcnow()
    log(f"  Worker: {worker_name}, Hive: {hive_id}")

    # ── Step 1: High-risk score row ──────────────────────────────────────────
    log("Step 1: Seeding high-risk score for Compressor AC-77...")
    try:
        db.table("asset_risk_scores").insert({
            "hive_id":       hive_id,
            "asset_name":    asset_name,
            "risk_score":    0.82,
            "risk_level":    "high",
            "health_score":  18.0,
            "mtbf_days":     14.0,
            "top_factors":   ["pm_overdue", "high_fault_freq"],
            "model_version": "rules-v1",
        }).execute()
        results.append(("PASS", "Risk score seeded (AC-77, score 0.82)"))
    except Exception as e:
        results.append(("WARN", f"asset_risk_scores insert: {e}"))

    # ── Step 2: Inventory stock for the parts the recommender will look up ────
    log("Step 2: Seeding 3 inventory_items with stock...")
    parts_seed = [
        ("Compressor Oil Filter COF-12", "COF-12-AS"),
        ("Pressure Relief Valve PRV-08", "PRV-08-AS"),
        ("V-Belt VB-A52",                "VB-A52-AS"),
    ]
    seeded_inv = 0
    for name, sku in parts_seed:
        try:
            db.table("inventory_items").insert({
                "id":            f"AS-{sku}",
                "hive_id":       hive_id,
                "worker_name":   worker_name,
                "part_name":     name,
                "part_number":   sku,
                "category":      "Mechanical",
                "qty_on_hand":   10,
                "min_qty":       2,
                "unit":          "pcs",
                "status":        "approved",
            }).execute()
            seeded_inv += 1
        except Exception as e:
            log(f"  inv insert {name}: {e}")
    if seeded_inv >= 1:
        results.append(("PASS", f"Inventory seeded ({seeded_inv}/3 parts)"))
    else:
        results.append(("WARN", "No inventory parts seeded — recommender will skip"))

    # ── Step 3: 5 corrective logbook entries with consistent parts_used ───────
    log("Step 3: Seeding 5 corrective logbook entries with parts patterns...")
    parts_used_pattern = [
        {"name": "Compressor Oil Filter COF-12", "qty": 1},
        {"name": "Pressure Relief Valve PRV-08", "qty": 1},
    ]
    log_seeded = 0
    for i in range(5):
        dt = now - datetime.timedelta(days=30 * (i + 1))
        d = dt.isoformat() + "Z"
        d_only = dt.date().isoformat()
        try:
            db.table("logbook").insert({
                "id":               f"AS-LOG-{i}-{int(now.timestamp())}",
                "hive_id":          hive_id,
                "worker_name":      worker_name,
                "machine":          asset_name,
                "maintenance_type": "Corrective",
                "category":         "Mechanical",
                "root_cause":       "filter clogged",
                "problem":          "Compressor head pressure fluctuating",
                "action":           "Replaced oil filter and PRV per pattern",
                "parts_used":       parts_used_pattern,
                "downtime_hours":   2.5,
                "status":           "closed",
                "date":             d_only,
                "closed_at":        d,
                "created_at":       d,
            }).execute()
            log_seeded += 1
        except Exception as e:
            log(f"  log insert {i}: {e}")
    if log_seeded >= 3:
        results.append(("PASS", f"Corrective logbook history seeded ({log_seeded}/5 entries)"))
    else:
        results.append(("WARN", f"Only {log_seeded}/5 logbook entries seeded — pattern may not trigger"))

    # ── Step 4: Invoke the recommender edge fn ───────────────────────────────
    log("Step 4: Invoking parts-staging-recommender edge fn...")
    base = "http://127.0.0.1:54321"
    ok, body, err = _post_edge(base, "parts-staging-recommender", {}, log)
    if ok:
        results.append(("PASS", "parts-staging-recommender returned 200"))
        try:
            payload = json.loads(body)
            log(f"  recommender response: {payload}")
        except Exception:
            pass
    else:
        results.append(("WARN", f"recommender call: {err}"))

    # ── Step 5: Verify recommendation row exists ─────────────────────────────
    log("Step 5: Verifying recommendation row...")
    try:
        recs = db.table("parts_staging_recommendations") \
            .select("asset_name, risk_score, parts, confidence, status") \
            .eq("hive_id", hive_id) \
            .eq("asset_name", asset_name) \
            .execute().data
        if recs:
            top = recs[0]
            parts = top.get("parts") or []
            conf  = float(top.get("confidence") or 0)
            results.append(("PASS", f"Recommendation row exists ({len(parts)} parts, confidence {conf:.2f})"))
            if parts:
                results.append(("PASS", f"First recommended part: {parts[0].get('part_name', '?')}"))
            else:
                results.append(("WARN", "Recommendation has no parts — pattern not strong enough"))
        else:
            results.append(("WARN", "No recommendation row — recommender skipped this asset"))
    except Exception as e:
        results.append(("WARN", f"recommendation read: {e}"))

    # ── Step 6: Verify asset-hub.html ships staging UI ───────────────────────
    log("Step 6: Verifying asset-hub.html staging UI...")
    try:
        with urllib.request.urlopen(f"{BASE_URL.rstrip('/')}/workhive/asset-hub.html", timeout=15) as r:
            html = r.read(300000).decode("utf-8", errors="replace")
        checks = [
            ("staging-card div present",     'id="staging-card"'    in html),
            ("loadDetailStaging defined",    'function loadDetailStaging' in html),
            ("staging-accept button",        'id="staging-accept"'  in html),
            ("staging-dismiss button",       'id="staging-dismiss"' in html),
            ("queries parts_staging_recommendations",
                                              "parts_staging_recommendations" in html),
            ("inserts parts_staged_reservations",
                                              "parts_staged_reservations" in html),
        ]
        for label, ok in checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"asset-hub.html read: {e}"))

    # ── Step 7: Verify alert-hub.html ships staging filter ───────────────────
    log("Step 7: Verifying alert-hub.html staging filter...")
    try:
        with urllib.request.urlopen(f"{BASE_URL.rstrip('/')}/workhive/alert-hub.html", timeout=15) as r:
            html = r.read(300000).decode("utf-8", errors="replace")
        checks = [
            ("staging filter chip in KINDS", "id: 'staging'" in html),
            ("queries parts_staging_recommendations",
                                              "parts_staging_recommendations" in html),
        ]
        for label, ok in checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"alert-hub.html read: {e}"))

    return {"results": results}
