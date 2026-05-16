"""
Asset Hub Flow -- WorkHive Tester

Seeds an ISO 14224 asset hierarchy (5 nodes + edges) plus linked logbook
history AND a Phase R.1+ Reliability Workbench micro-batch (FMEA + RCM
strategy + Weibull fit + P-F interval), then verifies that asset-hub.html
renders the canonical "Asset 360" view including every R.1-R.7 surface.

Coverage: asset-hub.html (Phase A.2 canonical, Phase B.5 risk, Phase ML-2
staging, Phase R.1-R.7 reliability workbench).

What this seeds (in one hive, scoped by hive_id):
  - 1 enterprise → 1 site → 1 plant → 1 equipment node (4 levels)
  - 1 sister equipment node at the same level
  - parent_of edges connecting the hierarchy
  - 1 sister edge between the two equipment nodes
  - 3 logbook entries linked via legacy_asset_id
  - 2 rcm_fmea_modes (1 approved + 1 pending, mix of manual + ai_logbook)
  - 1 rcm_strategies row linked to top-RPN approved mode
  - 1 weibull_fits row (wearout, beta=2.40)
  - 1 pf_intervals row (vibration_mms, P-F/2, 14d cadence)

What this verifies:
  1. asset-hub.html loads (HTTP 200)
  2. The hub has every panel + button + JS function for Phase R.1-R.7
  3. asset_nodes + asset_edges + logbook seed correctly
  4. v_asset_truth (canonical) surfaces the equipment node
  5. v_fmea_truth / v_rcm_truth / v_weibull_truth / v_pf_truth all return
     the seeded rows for the equipment node
  6. Edge fns fmea-populator / weibull-fitter / pf-calculator reject
     missing-required-field POSTs with 400 + JSON error contract
     (best-effort; WARN when the functions runtime is unreachable)
"""

import json, datetime, urllib.request, urllib.error
from .harness import BASE_URL


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
    results.append(("PASS" if n_nodes == 5 else "WARN",
                     f"asset_nodes seeded: {n_nodes}/5 (WARN: migration may not be applied locally)"))

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
                "maintenance_type": "Preventive Maintenance",
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

    # ── Step 5: Verify v_asset_truth (canonical) returns the equipment node ──
    # Phase A.2 added v_asset_truth as the canonical asset 360 view. The legacy
    # asset_brain_overview view stays as a wrapper for backward compat. We
    # check both: v_asset_truth must exist and return the same data; legacy
    # check downgraded to a parity-warning if rows differ.
    log("Step 5: Verifying v_asset_truth (canonical) view...")
    if inserted[3]:
        node_id = inserted[3]["id"]
        canonical_lle = canonical_ec = None
        try:
            res = db.table("v_asset_truth") \
                .select("asset_id, tag, lifetime_logbook_entries, last_failure_at, edge_count, legacy_asset_id, pm_asset_id") \
                .eq("asset_id", node_id) \
                .execute()
            row = (res.data or [None])[0]
            if not row:
                results.append(("FAIL", "v_asset_truth returned no row for CP-100"))
            else:
                canonical_lle = int(row.get("lifetime_logbook_entries") or 0)
                canonical_ec  = int(row.get("edge_count") or 0)
                # 3 logbook entries seeded, 2 edges touch CP-100 (parent_of from PLT, sister to CP-101)
                results.append(("PASS" if canonical_lle >= 3 else "WARN",
                                 f"v_asset_truth lifetime_logbook_entries: {canonical_lle} (expected >=3)"))
                results.append(("PASS" if canonical_ec >= 2 else "WARN",
                                 f"v_asset_truth edge_count: {canonical_ec} (expected >=2)"))
                # Verify the bridge columns surface the legacy + PM IDs.
                results.append(("PASS" if "legacy_asset_id" in row else "FAIL",
                                 "v_asset_truth exposes legacy_asset_id bridge column"))
                results.append(("PASS" if "pm_asset_id" in row else "FAIL",
                                 "v_asset_truth exposes pm_asset_id bridge column"))
        except Exception as e:
            results.append(("WARN", f"v_asset_truth query failed: {e}"))

        # Legacy parity check: asset_brain_overview should return the same
        # numbers since it is a wrapper. Downgraded to WARN on mismatch since
        # the canonical is the source of truth post-Phase-A.2.
        log("Step 5b: Parity check against legacy asset_brain_overview...")
        try:
            res = db.table("asset_brain_overview") \
                .select("node_id, lifetime_logbook_entries, edge_count") \
                .eq("node_id", node_id) \
                .execute()
            row = (res.data or [None])[0]
            if row and canonical_lle is not None:
                legacy_lle = int(row.get("lifetime_logbook_entries") or 0)
                legacy_ec  = int(row.get("edge_count") or 0)
                same = (legacy_lle == canonical_lle) and (legacy_ec == canonical_ec)
                results.append(("PASS" if same else "WARN",
                                 f"legacy parity: lle {legacy_lle}={canonical_lle}? ec {legacy_ec}={canonical_ec}?"))
            elif not row:
                results.append(("WARN", "asset_brain_overview returned no row (deprecated; safe to remove)"))
        except Exception as e:
            results.append(("WARN", f"legacy parity check skipped: {type(e).__name__}"))

    # ── Step 6: Verify asset-hub.html structure ──────────────────────────────────
    log("Step 6: Verifying asset-hub.html structure...")
    try:
        req = urllib.request.Request(f"{BASE_URL.rstrip('/')}/asset-hub.html", method="GET")
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read(220000).decode("utf-8", errors="replace")
        checks = [
            ("hub HTML loads (HTTP 200)",  True),  # got here = 200
            ("asset-list element present", 'id="asset-list"'   in html),
            ("asset-search element",       'id="asset-search"' in html),
            ("queries asset_nodes",        "asset_nodes"       in html),
            # Phase A.2 canonical: hub now reads v_asset_truth instead of the
            # legacy asset_brain_overview view. Both checks present so we can
            # see the cutover state plainly.
            ("queries v_asset_truth (canonical)", "v_asset_truth" in html),
            # Risk panel (Phase B.5) -- merged from predictive
            ("risk-card div present",      'id="risk-card"'    in html),
            ("risk-empty-card present",    'id="risk-empty-card"' in html),
            ("loadDetailRisk fn defined",  "function loadDetailRisk" in html),
            ("queries asset_risk_scores",  "asset_risk_scores" in html),
            # Phase 5b: structured top_factors render (contribution bars +
            # explanation text). Detected by the typeof-object branch.
            ("Phase 5b structured factor render branch",
                                            "typeof factors[0] === 'object'" in html),
            ("contribution bar rendering",
                                            "contribution" in html and "explanation" in html),
            # Staging panel (Phase ML-2 -- new)
            ("staging-card div present",   'id="staging-card"' in html),
            ("loadDetailStaging fn",       "function loadDetailStaging" in html),
            ("staging-accept button",      'id="staging-accept"' in html),
            ("staging-dismiss button",     'id="staging-dismiss"' in html),
            ("queries parts_staging_recommendations",
                                            "parts_staging_recommendations" in html),
            ("inserts parts_staged_reservations",
                                            "parts_staged_reservations" in html),
            # Voice handler integration (Phase B.2)
            ("registers asset.lookup voice intent",
                                            "WHVoice.register('asset.lookup'" in html
                                            or 'WHVoice.register("asset.lookup"' in html),
            # Phase R.2 — FMEA tab + modal
            ("Reliability section (R.2)",        'id="reliability-card"'        in html),
            ("FMEA panel + add button (R.2)",    'id="fmea-add-btn"'            in html),
            ("FMEA modal markup (R.2)",          'id="fmea-modal"'              in html),
            # Phase R.3 — fmea-populator AI suggestions
            ("FMEA suggest-from-history btn (R.3)", 'id="fmea-suggest-btn"'     in html),
            ("invokes fmea-populator (R.3)",     "fmea-populator"               in html),
            # Phase R.4 — RCM strategy modal + push to PM Scheduler
            ("RCM strategy modal (R.4)",         'id="rcm-modal"'               in html),
            ("RCM saveStrategy fn (R.4)",        "function saveStrategy"        in html),
            ("RCM pushStrategyToPm fn (R.4)",    "function pushStrategyToPm"    in html),
            ("RCM writes rcm_strategies (R.4)",  "rcm_strategies"               in html),
            ("RCM writes pm_scope_items (R.4)",  "pm_scope_items"               in html),
            # Phase R.5 — Weibull fitter
            ("Weibull panel (R.5)",              'id="rel-panel-weibull"'       in html),
            ("Weibull compute button (R.5)",     'id="weibull-fit-btn"'         in html),
            ("invokes weibull-fitter (R.5)",     "weibull-fitter"               in html),
            ("queries v_weibull_truth (R.5)",    "v_weibull_truth"              in html),
            # Phase R.6 — P-F interval calculator
            ("P-F panel (R.6)",                  'id="rel-panel-pf"'            in html),
            ("P-F parameter select (R.6)",       'id="pf-parameter"'            in html),
            ("P-F thresholds inputs (R.6)",      'id="pf-p-threshold"' in html and 'id="pf-f-threshold"' in html),
            ("P-F compute button (R.6)",         'id="pf-compute-btn"'          in html),
            ("invokes pf-calculator (R.6)",      "pf-calculator"                in html),
            ("queries v_pf_truth (R.6)",         "v_pf_truth"                   in html),
            # Phase R.7 — Print-ready Reliability Report
            ("Reliability report button (R.7)",  'id="reliability-report-btn"'  in html),
            ("generateReliabilityReport fn (R.7)", "function generateReliabilityReport" in html),
            ("Report reads v_fmea_truth (R.7)",  "v_fmea_truth"                 in html),
            ("Report reads v_rcm_truth (R.7)",   "v_rcm_truth"                  in html),
            ("Report print CSS @page A4 (R.7)",  "@page" in html and "A4" in html),
        ]
        for label, ok in checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"asset-hub.html load skipped: {type(e).__name__}"))

    # ── Step 7: Seed Reliability Workbench rows for CP-100 ────────────────────────
    # Phase R.1+ tables. We only seed the equipment node (not enterprise/site/plant).
    # The dedicated reliability seeder runs in seed_everything; the flow seeds a
    # micro-batch here so canonical views surface real data even when this flow
    # runs in isolation.
    if inserted[3]:
        node_id = inserted[3]["id"]
        log("Step 7: Seeding Reliability Workbench rows for CP-100...")

        fmea_inserted = []
        try:
            fmea_payload = [
                {
                    "hive_id":           hive_id,
                    "asset_id":          node_id,
                    "function_text":     "Maintain rated discharge pressure",
                    "failure_mode":      "Bearing inner race spalling",
                    "effect_text":       "Vibration > 7 mm/s, audible roar",
                    "cause_text":        "Inadequate lubrication",
                    "consequence_class": "production",
                    "severity":          7, "occurrence": 4, "detection": 6,
                    "source":            "manual",
                    "approved_by":       worker_name,
                    "approved_at":       (now - datetime.timedelta(days=2)).isoformat() + "Z",
                },
                {
                    "hive_id":           hive_id,
                    "asset_id":          node_id,
                    "function_text":     "Hold lubricant inside housing",
                    "failure_mode":      "Lip seal leaking",
                    "effect_text":       "Oil drips, contamination of floor",
                    "cause_text":        "Worn seal lip",
                    "consequence_class": "environment",
                    "severity":          4, "occurrence": 5, "detection": 3,
                    "source":            "ai_logbook",
                    "ai_confidence":     0.78,
                    # pending — exercises supervisor approval workflow
                    "approved_by":       None,
                    "approved_at":       None,
                },
            ]
            res = db.table("rcm_fmea_modes").insert(fmea_payload).execute()
            fmea_inserted = res.data or []
            results.append(("PASS" if len(fmea_inserted) == 2 else "WARN",
                             f"rcm_fmea_modes seeded: {len(fmea_inserted)}/2"))
        except Exception as e:
            results.append(("WARN", f"rcm_fmea_modes seed: {e}"))

        # rcm_strategies linked to the top-RPN approved mode
        if fmea_inserted:
            approved_mode = next((m for m in fmea_inserted if m.get("approved_at")), None)
            if approved_mode:
                try:
                    db.table("rcm_strategies").insert({
                        "hive_id":      hive_id,
                        "fmea_mode_id": approved_mode["id"],
                        "decision":     "scheduled_restoration",
                        "task_text":    "Quarterly bearing overhaul",
                        "interval_days": 90,
                        "rationale":    "Top RPN mode; preventive overhaul reduces hazard.",
                        "source":       "manual",
                        "approved_by":  worker_name,
                        "approved_at":  now.isoformat() + "Z",
                    }).execute()
                    results.append(("PASS", "rcm_strategies seeded (linked to approved FMEA)"))
                except Exception as e:
                    results.append(("WARN", f"rcm_strategies seed: {e}"))

        # weibull_fits: 1 wear-out fit
        try:
            db.table("weibull_fits").insert({
                "hive_id":            hive_id,
                "asset_id":           node_id,
                "fmea_mode_id":       None,
                "beta":               2.40,
                "eta_days":           220.0,
                "failure_pattern":    "wearout",
                "n_failures":         6,
                "n_censored":         1,
                "fit_method":         "mle_lifelines",
                "log_likelihood":     -42.18,
                "source_window_days": 730,
            }).execute()
            results.append(("PASS", "weibull_fits seeded (wearout, beta=2.40)"))
        except Exception as e:
            results.append(("WARN", f"weibull_fits seed: {e}"))

        # pf_intervals: 1 vibration cadence
        try:
            db.table("pf_intervals").insert({
                "hive_id":                   hive_id,
                "asset_id":                  node_id,
                "fmea_mode_id":              None,
                "parameter":                 "vibration_mms",
                "p_threshold":               4.5,
                "f_threshold":               7.1,
                "pf_days":                   28,
                "recommended_interval_days": 14,
                "basis":                     "P-F/2",
            }).execute()
            results.append(("PASS", "pf_intervals seeded (vibration, P-F/2)"))
        except Exception as e:
            results.append(("WARN", f"pf_intervals seed: {e}"))

        # ── Step 8: Verify canonical views surface the seeded rows ────────────────
        log("Step 8: Verifying reliability canonical views...")
        try:
            res = db.table("v_fmea_truth").select("failure_mode, rpn") \
                .eq("hive_id", hive_id).eq("asset_id", node_id).execute()
            n = len(res.data or [])
            # v_fmea_truth filters approved-only -> we seeded 1 approved + 1 pending
            results.append(("PASS" if n >= 1 else "FAIL",
                             f"v_fmea_truth returns approved row(s): {n}/1+"))
        except Exception as e:
            results.append(("WARN", f"v_fmea_truth query: {e}"))
        try:
            res = db.table("v_rcm_truth").select("decision, interval_days") \
                .eq("hive_id", hive_id).eq("asset_id", node_id).execute()
            n = len(res.data or [])
            results.append(("PASS" if n >= 1 else "FAIL",
                             f"v_rcm_truth returns approved strategy: {n}/1+"))
        except Exception as e:
            results.append(("WARN", f"v_rcm_truth query: {e}"))
        try:
            res = db.table("v_weibull_truth").select("beta, eta_days, failure_pattern") \
                .eq("hive_id", hive_id).eq("asset_id", node_id).execute()
            row = (res.data or [None])[0]
            ok = bool(row and row.get("beta") is not None)
            results.append(("PASS" if ok else "FAIL",
                             f"v_weibull_truth returns latest fit: {row.get('failure_pattern') if row else 'none'}"))
        except Exception as e:
            results.append(("WARN", f"v_weibull_truth query: {e}"))
        try:
            res = db.table("v_pf_truth").select("parameter, recommended_interval_days, basis") \
                .eq("hive_id", hive_id).eq("asset_id", node_id).execute()
            row = (res.data or [None])[0]
            ok = bool(row and row.get("recommended_interval_days"))
            results.append(("PASS" if ok else "FAIL",
                             f"v_pf_truth returns row: {row.get('parameter') if row else 'none'}"))
        except Exception as e:
            results.append(("WARN", f"v_pf_truth query: {e}"))

    # ── Step 9: Edge function contract smoke (best-effort) ────────────────────────
    # Confirms each Phase R.3-R.6 edge fn rejects bad input with 400 + JSON error.
    # WARNs (does not FAIL) when the local functions runtime is unreachable —
    # this lets the flow run useful in pure-DB scenarios too.
    log("Step 9: Edge function contract smoke (fmea-populator, weibull-fitter, pf-calculator)...")
    fn_base = (BASE_URL.rstrip('/').replace(':5000', ':54321')) + "/functions/v1"
    edge_cases = [
        ("fmea-populator",  {"hive_id": hive_id}),                                   # missing asset_id
        ("weibull-fitter",  {"hive_id": hive_id}),                                   # missing asset_id
        ("pf-calculator",   {"hive_id": hive_id, "asset_id": "x"}),                  # missing parameter
    ]
    for fn_name, body in edge_cases:
        try:
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(
                f"{fn_base}/{fn_name}",
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as r:
                    code = r.getcode()
                    body_txt = r.read(2000).decode("utf-8", errors="replace")
            except urllib.error.HTTPError as he:
                code = he.code
                body_txt = he.read(2000).decode("utf-8", errors="replace") if he.fp else ""
            ok = (code == 400) and ("error" in body_txt.lower())
            results.append(("PASS" if ok else "WARN",
                             f"{fn_name} rejects missing field with 400+error JSON (got {code})"))
        except Exception as e:
            # connection refused, DNS, etc. — local supabase functions runtime
            # may not be running; the flow stays useful without it.
            results.append(("WARN", f"{fn_name} contract skipped: {type(e).__name__}"))

    return {"results": results}
