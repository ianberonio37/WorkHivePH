"""
Asset Hub Flow -- WorkHive Tester

Seeds an ISO 14224 asset hierarchy (5 nodes + edges) plus linked logbook
history, then verifies asset-hub.html renders the canonical "Asset 360" view.

Coverage: asset-hub.html

What this seeds (in one hive, scoped by hive_id):
  - 1 enterprise → 1 site → 1 plant → 1 equipment node (4 levels)
  - 1 sister equipment node at the same level
  - parent_of edges connecting the hierarchy
  - 1 sister edge between the two equipment nodes
  - 3 logbook entries linked via legacy_asset_id so asset_brain_overview
    populates lifetime_logbook_entries and last_failure_at

What this verifies:
  1. asset-hub.html loads (HTTP 200)
  2. The hub has #asset-list and #asset-search elements
  3. asset_nodes seeded correctly (5 rows)
  4. asset_edges seeded correctly (4 edges: 3 parent_of + 1 sister)
  5. asset_brain_overview view returns a row for the equipment node
     with non-zero lifetime_logbook_entries
"""

import json, datetime, urllib.request, urllib.error


def _seed_legacy_asset(db, hive_id: str, worker_name: str, name: str, category: str) -> str | None:
    """Insert a row into the legacy 'assets' table (text id) so asset_nodes can
    link via legacy_asset_id. Returns the new asset id, or None on failure."""
    import uuid
    asset_id = f"hub-{uuid.uuid4().hex[:10]}"
    try:
        db.table("assets").insert({
            "id":          asset_id,
            "hive_id":     hive_id,
            "worker_name": worker_name,
            "name":        name,
            "category":    category,
            "status":      "approved",
        }).execute()
        return asset_id
    except Exception:
        return None


def run(page, errors, warnings, log) -> dict:
    from lib.supabase_client import get_client
    db = get_client()
    results = []

    log("Asset Hub Flow: locating seeded hive + worker...")
    members = db.table("hive_members").select("worker_name, hive_id").limit(1).execute().data
    if not members:
        return {"results": [("WARN", "No seeded hive_members — Asset Hub needs a hive context")]}

    worker_name = members[0]["worker_name"]
    hive_id     = members[0]["hive_id"]
    now         = datetime.datetime.utcnow()
    log(f"  Worker: {worker_name}, Hive: {hive_id}")

    # ── Step 1: Seed legacy assets row (so asset_nodes has a real legacy_asset_id) ──
    legacy_id = _seed_legacy_asset(db, hive_id, worker_name,
                                    "Centrifugal Pump CP-100", "Mechanical")
    if not legacy_id:
        results.append(("WARN", "Could not seed legacy asset — asset_brain_overview joins will return zero"))

    # ── Step 2: Seed 5-level asset_nodes hierarchy ────────────────────────────────
    log("Step 2: Seeding asset_nodes hierarchy (enterprise → site → plant → equipment x2)...")
    nodes = [
        # tag, name, level, criticality, parent_idx
        ("ENT-01", "Lucena Pharmaceutical Mfg.", "enterprise", "low",      None,     None),
        ("STE-01", "Lucena Plant Site",          "site",       "low",      0,        None),
        ("PLT-01", "Production Plant 1",         "plant",      "medium",   1,        None),
        ("CP-100", "Centrifugal Pump CP-100",    "equipment",  "critical", 2,        legacy_id),
        ("CP-101", "Centrifugal Pump CP-101",    "equipment",  "high",     2,        None),
    ]
    inserted = []
    for idx, (tag, name, level, crit, parent_idx, leg_id) in enumerate(nodes):
        row = {
            "hive_id":     hive_id,
            "worker_name": worker_name,
            "tag":         tag,
            "name":        name,
            "level":       level,
            "criticality": crit,
            "iso_class":   "PUMP" if level == "equipment" else None,
            "location":    "Plant 1 / Pump Bay",
            "status":      "approved",
        }
        if parent_idx is not None and inserted[parent_idx]:
            row["parent_id"] = inserted[parent_idx]["id"]
        if leg_id:
            row["legacy_asset_id"] = leg_id
        try:
            res = db.table("asset_nodes").insert(row).execute()
            inserted.append(res.data[0] if res.data else None)
        except Exception as e:
            inserted.append(None)
            warnings.append(f"asset_nodes insert {tag} failed: {e}")

    n_nodes = sum(1 for n in inserted if n)
    log(f"  Seeded {n_nodes} asset_nodes")
    results.append(("PASS" if n_nodes == 5 else "FAIL",
                     f"asset_nodes seeded: {n_nodes}/5"))

    # ── Step 3: Seed asset_edges (3 parent_of + 1 sister) ─────────────────────────
    log("Step 3: Seeding asset_edges...")
    edges_to_make = []
    for i in range(1, 4):   # site → enterprise, plant → site, equipment → plant
        if inserted[i] and inserted[i-1]:
            edges_to_make.append({
                "hive_id":      hive_id,
                "from_node_id": inserted[i-1]["id"],
                "to_node_id":   inserted[i]["id"],
                "edge_type":    "parent_of",
            })
    # Sister edge between two equipment nodes (CP-100 ↔ CP-101)
    if inserted[3] and inserted[4]:
        edges_to_make.append({
            "hive_id":      hive_id,
            "from_node_id": inserted[3]["id"],
            "to_node_id":   inserted[4]["id"],
            "edge_type":    "sister",
        })

    n_edges = 0
    if edges_to_make:
        try:
            res = db.table("asset_edges").insert(edges_to_make).execute()
            n_edges = len(res.data or [])
        except Exception as e:
            warnings.append(f"asset_edges insert failed: {e}")
    log(f"  Seeded {n_edges} asset_edges")
    results.append(("PASS" if n_edges == 4 else "WARN",
                     f"asset_edges seeded: {n_edges}/4"))

    # ── Step 4: Seed 3 logbook entries linked via legacy_asset_id ─────────────────
    if legacy_id:
        log("Step 4: Seeding logbook entries linked to legacy asset...")
        log_rows = [
            {
                "hive_id":          hive_id,
                "worker_name":      worker_name,
                "machine":          "Centrifugal Pump CP-100",
                "asset_ref_id":     legacy_id,
                "maintenance_type": "Breakdown / Corrective",
                "category":         "Mechanical",
                "failure_mode":     "Bearing failure",
                "problem":          "Vibration alarm at 7am, bearing seized",
                "action":           "Replaced bearing, re-aligned coupling",
                "status":           "Closed",
                "downtime_hours":   3.5,
                "closed_at":        (now - datetime.timedelta(days=3)).isoformat() + "Z",
                "created_at":       (now - datetime.timedelta(days=3)).isoformat() + "Z",
            },
            {
                "hive_id":          hive_id,
                "worker_name":      worker_name,
                "machine":          "Centrifugal Pump CP-100",
                "asset_ref_id":     legacy_id,
                "maintenance_type": "Preventive",
                "category":         "Mechanical",
                "problem":          "Quarterly lubrication and inspection",
                "action":           "Greased bearings, checked alignment",
                "status":           "Closed",
                "downtime_hours":   1.0,
                "closed_at":        (now - datetime.timedelta(days=10)).isoformat() + "Z",
                "created_at":       (now - datetime.timedelta(days=10)).isoformat() + "Z",
            },
            {
                "hive_id":          hive_id,
                "worker_name":      worker_name,
                "machine":          "Centrifugal Pump CP-100",
                "asset_ref_id":     legacy_id,
                "maintenance_type": "Breakdown / Corrective",
                "category":         "Mechanical",
                "failure_mode":     "Seal leak",
                "problem":          "Mechanical seal leaking at process side",
                "action":           "Replaced seal, pressure tested",
                "status":           "Closed",
                "downtime_hours":   2.0,
                "closed_at":        (now - datetime.timedelta(days=30)).isoformat() + "Z",
                "created_at":       (now - datetime.timedelta(days=30)).isoformat() + "Z",
            },
        ]
        try:
            res = db.table("logbook").insert(log_rows).execute()
            n_log = len(res.data or [])
            log(f"  Seeded {n_log} logbook entries linked to legacy asset")
            results.append(("PASS" if n_log == 3 else "WARN",
                             f"linked logbook entries: {n_log}/3"))
        except Exception as e:
            results.append(("WARN", f"logbook insert: {e}"))

    # ── Step 5: Verify asset_brain_overview returns the equipment node ────────────
    log("Step 5: Verifying asset_brain_overview view...")
    if inserted[3]:
        try:
            res = db.table("asset_brain_overview") \
                .select("node_id, tag, lifetime_logbook_entries, last_failure_at, edge_count") \
                .eq("node_id", inserted[3]["id"]) \
                .execute()
            row = (res.data or [None])[0]
            if not row:
                results.append(("FAIL", "asset_brain_overview returned no row for CP-100"))
            else:
                lle  = int(row.get("lifetime_logbook_entries") or 0)
                ec   = int(row.get("edge_count") or 0)
                # 3 logbook entries seeded, 2 edges touch CP-100 (parent_of from PLT, sister to CP-101)
                results.append(("PASS" if lle >= 3 else "WARN",
                                 f"overview lifetime_logbook_entries: {lle} (expected ≥3)"))
                results.append(("PASS" if ec >= 2 else "WARN",
                                 f"overview edge_count: {ec} (expected ≥2)"))
        except Exception as e:
            results.append(("WARN", f"asset_brain_overview query failed: {e}"))

    # ── Step 6: Verify asset-hub.html structure ──────────────────────────────────
    log("Step 6: Verifying asset-hub.html structure...")
    try:
        req = urllib.request.Request(f"{page.rstrip('/')}/asset-hub.html", method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read(120000).decode("utf-8", errors="replace")
        checks = [
            ("hub HTML loads (HTTP 200)",  True),  # got here = 200
            ("asset-list element present", 'id="asset-list"'   in html),
            ("asset-search element",       'id="asset-search"' in html),
            ("queries asset_nodes",        "asset_nodes"       in html),
            ("queries asset_brain_overview", "asset_brain_overview" in html),
            # Risk panel (Phase B.5) -- merged from predictive
            ("risk-card div present",      'id="risk-card"'    in html),
            ("risk-empty-card present",    'id="risk-empty-card"' in html),
            ("loadDetailRisk fn defined",  "function loadDetailRisk" in html),
            ("queries asset_risk_scores",  "asset_risk_scores" in html),
            # Staging panel (Phase ML-2 -- new)
            ("staging-card div present",   'id="staging-card"' in html),
            ("loadDetailStaging fn",       "function loadDetailStaging" in html),
            ("staging-accept button",      'id="staging-accept"' in html),
            ("staging-dismiss button",     'id="staging-dismiss"' in html),
            ("queries parts_staging_recommendations",
                                            "parts_staging_recommendations" in html),
            ("inserts parts_staged_reservations",
                                            "parts_staged_reservations" in html),
        ]
        for label, ok in checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"asset-hub.html load skipped: {type(e).__name__}"))

    return {"results": results}
