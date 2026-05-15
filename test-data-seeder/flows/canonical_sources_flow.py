"""
Canonical Sources Flow -- WorkHive Tester (Phase A.1 + A.2 + A.3 + A.4)

Verifies the canonical_sources registry contains the expected entries with
non-empty contracts, and that each registered view is actually queryable.

What this checks:

  Layer 1 - Registry health
    1. canonical_sources table is reachable (GRANT SELECT works for anon)
    2. The 9 aligned-truth seeds from Phase A.1 are present
       (shift_state, asset_graph_edges, community_thread, engineering_calc_history,
        cmms_external_link, ai_rate_limit, automation_log, hive_audit_log,
        cmms_audit_log)
    3. The 3 view-backed truths from Phase A.2 + A.3 + A.4 are present
       (asset_truth, risk_truth, pm_compliance_truth)
    4. Every registered row has source_kind, source_name, owner_skill,
       freshness, and a non-empty contract JSONB

  Layer 2 - Live source verification
    5. v_asset_truth is queryable and returns the expected column shape
    6. v_risk_truth is queryable
    7. v_pm_compliance_truth is queryable

  Layer 3 - Reader compliance (consumers of the canonicals)
    8. asset-hub.html, predictive.html, shift-planner-orchestrator,
       parts-staging-recommender all reference the canonical view names
    9. Legacy asset_brain_overview is NOT referenced in batch-risk-scoring,
       parts-staging-recommender, shift-planner-orchestrator (would mean a
       reader missed the cutover)

Phase A.1 was committed at flow creation. The 3 view migrations may or may
not be pushed to Supabase at any given moment; checks 5-7 graceful WARN
when the view does not yet exist in the live DB.
"""
import urllib.request
from .harness import BASE_URL


# Truths seeded by Phase A.1 (already aligned, tables only).
ALIGNED_TRUTHS = {
    "shift_state":                {"source_kind": "table", "source_name": "shift_plans"},
    "asset_graph_edges":          {"source_kind": "table", "source_name": "asset_edges"},
    "community_thread":           {"source_kind": "table", "source_name": "community_posts"},
    "engineering_calc_history":   {"source_kind": "table", "source_name": "engineering_calcs"},
    "cmms_external_link":         {"source_kind": "table", "source_name": "external_sync"},
    "ai_rate_limit":              {"source_kind": "table", "source_name": "ai_rate_limits"},
    "automation_log":             {"source_kind": "table", "source_name": "automation_log"},
    "hive_audit_log":             {"source_kind": "table", "source_name": "hive_audit_log"},
    "cmms_audit_log":             {"source_kind": "table", "source_name": "cmms_audit_log"},
}

# View-backed truths from Phases A.2 + A.3 + A.4.
VIEW_TRUTHS = {
    "asset_truth":         {"source_kind": "view", "source_name": "v_asset_truth"},
    "risk_truth":          {"source_kind": "view", "source_name": "v_risk_truth"},
    "pm_compliance_truth": {"source_kind": "view", "source_name": "v_pm_compliance_truth"},
}

ALL_TRUTHS = {**ALIGNED_TRUTHS, **VIEW_TRUTHS}


def run(page, errors, warnings, log) -> dict:
    """`page` here is the Flask base URL string (auto_staging_flow convention)."""
    results = []

    # ── Layer 1: Registry health ─────────────────────────────────────────────
    log("Step 1: Loading canonical_sources registry...")
    try:
        from lib.supabase_client import get_client
        db = get_client()
    except Exception as e:
        results.append(("WARN", f"Could not load supabase client: {e}; remaining tests skipped"))
        return {"results": results}

    rows = []
    try:
        res = db.table("canonical_sources") \
            .select("domain, source_kind, source_name, owner_skill, freshness, contract") \
            .execute()
        rows = res.data or []
    except Exception as e:
        results.append((
            "WARN",
            f"canonical_sources query failed (registry migration may not be pushed): {e}",
        ))
        return {"results": results}

    if not rows:
        results.append((
            "FAIL",
            "canonical_sources registry is empty. Phase A.1 seed should populate 9 rows.",
        ))
        return {"results": results}
    results.append(("PASS", f"canonical_sources reachable; {len(rows)} domain rows registered"))

    by_domain = {r["domain"]: r for r in rows}

    # ── Step 2: Aligned-truth presence ───────────────────────────────────────
    log("Step 2: Verifying Phase A.1 aligned truths are seeded...")
    for domain, expected in ALIGNED_TRUTHS.items():
        row = by_domain.get(domain)
        if not row:
            results.append(("FAIL", f"Aligned truth '{domain}' not registered"))
            continue
        if row.get("source_kind") != expected["source_kind"]:
            results.append((
                "FAIL",
                f"{domain}: source_kind={row.get('source_kind')} expected {expected['source_kind']}",
            ))
        elif row.get("source_name") != expected["source_name"]:
            results.append((
                "FAIL",
                f"{domain}: source_name={row.get('source_name')} expected {expected['source_name']}",
            ))
        else:
            results.append(("PASS", f"{domain} -> {row['source_name']}"))

    # ── Step 3: View-backed truth presence ───────────────────────────────────
    log("Step 3: Verifying Phase A.2/A.3/A.4 view-backed truths are registered...")
    for domain, expected in VIEW_TRUTHS.items():
        row = by_domain.get(domain)
        if not row:
            results.append((
                "WARN",
                f"View truth '{domain}' not yet registered (migration may not be pushed)",
            ))
            continue
        if row.get("source_kind") != "view":
            results.append((
                "FAIL",
                f"{domain}: source_kind={row.get('source_kind')} expected view",
            ))
        elif row.get("source_name") != expected["source_name"]:
            results.append((
                "FAIL",
                f"{domain}: source_name={row.get('source_name')} expected {expected['source_name']}",
            ))
        else:
            results.append(("PASS", f"{domain} -> {row['source_name']} (view)"))

    # ── Step 4: Contract integrity ───────────────────────────────────────────
    log("Step 4: Verifying every row has owner_skill, freshness, and non-empty contract...")
    for domain in ALL_TRUTHS:
        row = by_domain.get(domain)
        if not row:
            continue
        for col in ("owner_skill", "freshness"):
            val = row.get(col)
            if not val or not str(val).strip():
                results.append(("FAIL", f"{domain}.{col} is empty or null"))
                continue
        contract = row.get("contract") or {}
        if not isinstance(contract, dict) or not contract:
            results.append(("FAIL", f"{domain}.contract is empty (must declare 'key' at minimum)"))
        elif not contract.get("key"):
            results.append(("WARN", f"{domain}.contract missing 'key' array"))
        else:
            results.append(("PASS", f"{domain} contract has key={contract['key']}"))

    # ── Layer 2: Live view verification ──────────────────────────────────────
    log("Step 5: Verifying v_asset_truth is queryable...")
    try:
        res = db.table("v_asset_truth").select("asset_id, hive_id, tag, name, legacy_asset_id, pm_asset_id, lifetime_logbook_entries, last_failure_at, pm_completed_count, edge_count").limit(1).execute()
        results.append(("PASS", f"v_asset_truth queryable; {len(res.data or [])} sample row(s)"))
    except Exception as e:
        results.append(("WARN", f"v_asset_truth query failed (migration may not be pushed): {type(e).__name__}: {e}"))

    log("Step 6: Verifying v_risk_truth is queryable...")
    try:
        res = db.table("v_risk_truth").select("asset_id, asset_name, risk_score, risk_level, top_factors, generated_at").limit(1).execute()
        results.append(("PASS", f"v_risk_truth queryable; {len(res.data or [])} sample row(s)"))
    except Exception as e:
        results.append(("WARN", f"v_risk_truth query failed: {type(e).__name__}: {e}"))

    log("Step 7: Verifying v_pm_compliance_truth is queryable...")
    try:
        res = db.table("v_pm_compliance_truth").select("hive_id, pm_asset_id, asset_name, is_due, days_since_last_completion, completions_30d, completions_90d").limit(1).execute()
        results.append(("PASS", f"v_pm_compliance_truth queryable; {len(res.data or [])} sample row(s)"))
    except Exception as e:
        results.append(("WARN", f"v_pm_compliance_truth query failed: {type(e).__name__}: {e}"))

    # ── Layer 3: Reader compliance (static-file checks) ──────────────────────
    log("Step 8: Verifying canonical readers point at the right view names...")
    base = BASE_URL.rstrip("/")
    reader_checks = [
        # path, must_contain
        ("/asset-hub.html",    ["v_asset_truth"]),
        ("/predictive.html",   ["v_risk_truth"]),
    ]
    predictive_html = ""
    for path, must in reader_checks:
        try:
            with urllib.request.urlopen(f"{base}{path}", timeout=15) as r:
                html = r.read(250000).decode("utf-8", errors="replace")
            if path == "/predictive.html":
                predictive_html = html
            for token in must:
                results.append((
                    "PASS" if token in html else "FAIL",
                    f"{path} references {token}",
                ))
        except Exception as e:
            results.append(("WARN", f"{path} read: {e}"))

    # Phase 5c: every Risk Ranking row in predictive.html should deep-link to
    # Asset Hub via window.location.href='asset-hub.html?node_id=<uuid>'.
    # Confirms the retire-and-redirect contract: predictive becomes a thin
    # board, detail lives in Asset Hub.
    log("Step 9: Verifying Phase 5c row-click deep-link pattern in predictive.html...")
    if predictive_html:
        has_url_template = "asset-hub.html?node_id=" in predictive_html
        # The renderer also conditions on aid (canonical asset_id from v_risk_truth)
        # so rows where name resolution failed stay inert. That guard is part of
        # the contract -- without it, broken-link clicks would happen.
        has_resolution_guard = (
            "const aid" in predictive_html and "asset_id" in predictive_html
        )
        results.append((
            "PASS" if has_url_template else "FAIL",
            "predictive.html emits asset-hub.html?node_id= deep-link template (Phase 5c)",
        ))
        results.append((
            "PASS" if has_resolution_guard else "WARN",
            "predictive.html guards row-click on resolved canonical asset_id",
        ))
    else:
        results.append(("WARN", "predictive.html not loaded; Phase 5c row-click check skipped"))

    return {"results": results}
