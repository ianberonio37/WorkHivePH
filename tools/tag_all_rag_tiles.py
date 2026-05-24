"""
tag_all_rag_tiles.py — Bulk-add data-rag-tile to ALL KPI section containers
across all 16 WorkHive pages.

Phase 1 (turns 1-29): only 3 hero tiles per page = 48 tiles total.
Phase 2 (this script): tags every section panel, sub-stat, and detail view
so the flywheel covers the FULL dashboard content on each page.

Strategy:
  - Find element by id="XXXX"
  - Replace opening tag with version that has data-rag-tile="page:key"
    data-rag-label="Human label"
  - Idempotent: if data-rag-tile already present on that element, skip.

Output: prints a summary + seeds canonical_sources rows for each new tile.
"""

import re
import sys
import os
from pathlib import Path
from typing import List, Tuple

# (page_slug, element_id, tile_key, tile_label, source_table, source_description)
TILE_PLAN: List[Tuple[str, str, str, str, str, str]] = [
    # ── analytics ──────────────────────────────────────────────────────────
    ("analytics", "an-summary-details",
     "analytics:detail_panel", "Analytics detail breakdown",
     "v_kpi_truth",
     "Full analytics detail panel on analytics.html. Contains per-machine OEE, MTBF, PM compliance, root cause, downtime, parts risk, and action item tables. Rendered after page load from v_kpi_truth and logbook data."),

    ("analytics", "results-panel",
     "analytics:results_panel", "Per-machine analytics results",
     "v_kpi_truth",
     "Per-machine results panel on analytics.html. Shows OEE table, MTBF/reliability table, PM compliance by asset, root cause ranking, downtime ranking, parts risk, and sensor anomaly tables. Source: v_kpi_truth, logbook, pm_completions."),

    # ── alert-hub ──────────────────────────────────────────────────────────
    ("alert-hub", "ah-summary-details",
     "alert-hub:detail_panel", "Alert detail breakdown",
     "v_risk_truth",
     "Alert detail panel on alert-hub.html. Shows AMC sub-stats and alert list breakdown. Source: v_risk_truth, amc_briefings."),

    ("alert-hub", "amc-stat-assets",
     "alert-hub:amc_assets", "AMC assets checked",
     "v_amc_truth",
     "AMC assets checked count on alert-hub.html. Shows how many assets the AI Maintenance Companion reviewed in the latest daily brief. Source: v_amc_truth / amc_briefings.assets_checked."),

    ("alert-hub", "amc-stat-pms",
     "alert-hub:amc_pms", "AMC PMs flagged",
     "v_amc_truth",
     "AMC PMs flagged count on alert-hub.html. Number of PM tasks flagged as overdue or at-risk by the AI Maintenance Companion. Source: v_amc_truth / amc_briefings.pms_flagged."),

    ("alert-hub", "amc-stat-parts",
     "alert-hub:amc_parts", "AMC parts at risk",
     "v_amc_truth",
     "AMC parts at risk count on alert-hub.html. Parts identified as low stock or stockout-risk in the latest AMC brief. Source: v_amc_truth / amc_briefings.parts_at_risk."),

    ("alert-hub", "amc-stat-crew",
     "alert-hub:amc_crew", "AMC crew alerts",
     "v_amc_truth",
     "AMC crew alerts count on alert-hub.html. Number of crew-level issues (skill gaps, overload) flagged by the AI Maintenance Companion. Source: v_amc_truth."),

    # ── asset-hub ──────────────────────────────────────────────────────────
    ("asset-hub", "ah-summary-details",
     "asset-hub:detail_panel", "Asset detail breakdown",
     "v_asset_truth",
     "Asset detail panel on asset-hub.html. Shows logbook stats, PM stats, last failure data, and edge (RCM) stats per asset. Source: v_asset_truth, logbook, pm_completions."),

    ("asset-hub", "stat-logbook",
     "asset-hub:logbook_count", "Asset logbook entries",
     "v_logbook_truth",
     "Logbook entries count for the selected asset on asset-hub.html. Shows total logbook records for the currently viewed asset. Source: v_logbook_truth filtered by asset_id."),

    ("asset-hub", "stat-pm",
     "asset-hub:pm_count", "Asset PM completions",
     "v_pm_compliance_truth",
     "PM completions count for the selected asset on asset-hub.html. Shows preventive maintenance tasks completed for the current asset. Source: v_pm_compliance_truth."),

    ("asset-hub", "stat-last-failure",
     "asset-hub:last_failure", "Asset last failure",
     "v_logbook_truth",
     "Last failure date/stat for the selected asset on asset-hub.html. Shows the most recent failure event logged for this asset. Source: v_logbook_truth filtered by failure_mode."),

    ("asset-hub", "stat-edges",
     "asset-hub:rcm_edges", "Asset RCM edges",
     "asset_nodes",
     "RCM edge count for the selected asset on asset-hub.html. Shows number of cause-effect relationships mapped in the RCM/FMEA model for this asset. Source: asset_nodes / RCM graph."),

    # ── pm-scheduler ───────────────────────────────────────────────────────
    ("pm-scheduler", "pm-summary-details",
     "pm-scheduler:detail_panel", "PM detail breakdown",
     "v_pm_compliance_truth",
     "PM detail panel on pm-scheduler.html. Shows per-asset PM task lists, completion history, and scope items. Source: v_pm_compliance_truth, schedule_items."),

    # ── predictive ─────────────────────────────────────────────────────────
    ("predictive", "pr-summary-details",
     "predictive:detail_panel", "Predictive detail breakdown",
     "v_risk_truth",
     "Predictive detail panel on predictive.html. Contains risk ranking table, failure probability heatmap, and MTBF trend charts. Source: v_risk_truth, logbook."),

    ("predictive", "panel-ranking",
     "predictive:risk_ranking", "Risk ranking table",
     "v_risk_truth",
     "Risk ranking table on predictive.html. Shows all assets sorted by composite risk score with MTBF, top failure factors, and forecast dates. Source: v_risk_truth."),

    ("predictive", "panel-heatmap",
     "predictive:risk_heatmap", "Risk heatmap",
     "v_risk_truth",
     "Risk heatmap on predictive.html. Shows failure probability grid by asset and time window. Source: v_risk_truth / asset_risk_scores."),

    ("predictive", "panel-trend",
     "predictive:mtbf_trend", "MTBF trend panel",
     "v_kpi_truth_mtbf",
     "MTBF trend panel on predictive.html. Shows historical MTBF trajectory per asset to identify degradation trends. Source: v_kpi_truth_mtbf."),

    # ── inventory ──────────────────────────────────────────────────────────
    ("inventory", "inv-summary-details",
     "inventory:detail_panel", "Inventory detail breakdown",
     "v_inventory_items_truth",
     "Inventory detail panel on inventory.html. Shows full parts list with stock levels, usage rates, stockout risk, and reorder alerts. Source: v_inventory_items_truth."),

    ("inventory", "stat-total",
     "inventory:total_parts", "Total parts in stock",
     "v_inventory_items_truth",
     "Total parts count on inventory.html. Total number of distinct part SKUs tracked in the hive inventory. Source: v_inventory_items_truth count."),

    # ── skillmatrix ────────────────────────────────────────────────────────
    ("skillmatrix", "sm-summary-details",
     "skillmatrix:detail_panel", "Skill matrix detail",
     "v_worker_skill_truth",
     "Skill matrix detail panel on skillmatrix.html. Shows per-worker skill levels by domain, quiz history, badge breakdown, and target progress. Source: v_worker_skill_truth, worker_achievements."),

    # ── hive ───────────────────────────────────────────────────────────────
    ("hive", "supervisor-summary-details",
     "hive:detail_panel", "Hive supervisor detail",
     "v_hive_readiness_truth",
     "Hive supervisor detail panel on hive.html. Shows hive member list, maturity stair evidence, open issues list, and task breakdown. Source: v_hive_readiness_truth, logbook."),

    ("hive", "stat-members",
     "hive:member_count", "Active hive members",
     "worker_profiles",
     "Active member count on hive.html. Number of workers with active membership in this hive. Source: worker_profiles filtered by hive_id."),

    ("hive", "stat-open",
     "hive:open_tasks", "Open issues count",
     "v_logbook_truth",
     "Open issues count on hive.html. Number of logbook entries with status=Open across all hive assets. Source: v_logbook_truth filtered by status=Open."),

    # ── achievements ───────────────────────────────────────────────────────
    ("achievements", "ac-summary-details",
     "achievements:detail_panel", "Achievements detail",
     "worker_achievements",
     "Achievements detail panel on achievements.html. Shows full badge gallery, XP activity log, domain leaderboard, and quiz results. Source: worker_achievements, community_xp, skill_badges."),

    ("achievements", "stat-composite",
     "achievements:composite_score", "Composite skill score",
     "v_worker_skill_truth",
     "Composite skill score on achievements.html. Overall skill composite across all domains for the current worker. Source: v_worker_skill_truth.composite_score."),

    ("achievements", "stat-active",
     "achievements:active_domains_stat", "Active domains stat",
     "skill_badges",
     "Active domains stat box on achievements.html. Count of distinct skill domains the worker has at least one badge in. Source: skill_badges."),

    ("achievements", "stat-top",
     "achievements:top_domain", "Top skill domain",
     "v_worker_skill_truth",
     "Top skill domain on achievements.html. The domain where the worker has the highest skill level. Source: v_worker_skill_truth."),

    # ── dayplanner ─────────────────────────────────────────────────────────
    ("dayplanner", "dp-summary-details",
     "dayplanner:detail_panel", "Day planner detail",
     "schedule_items",
     "Day planner detail panel on dayplanner.html. Shows full task list organized by day, week, month, and year views. Source: schedule_items filtered by worker_name."),

    # ── integrations ───────────────────────────────────────────────────────
    ("integrations", "it-summary-details",
     "integrations:detail_panel", "Integrations detail",
     "integration_configs",
     "Integrations detail panel on integrations.html. Shows connector list, sync logs, API keys, and field mapping. Source: integration_configs, external_sync."),

    ("integrations", "tab-sync-content",
     "integrations:sync_log", "Sync log",
     "external_sync",
     "Sync log tab on integrations.html. Shows recent sync events for each integration connector. Source: external_sync table sorted by last_sync_at."),

    ("integrations", "tab-api-content",
     "integrations:api_config", "API configuration",
     "integration_configs",
     "API configuration tab on integrations.html. Shows configured API endpoints, auth methods, and connection status per integration. Source: integration_configs."),

    # ── marketplace ────────────────────────────────────────────────────────
    ("marketplace", "mk-summary-details",
     "marketplace:detail_panel", "Marketplace detail",
     "v_marketplace_listings_truth",
     "Marketplace detail panel on marketplace.html. Shows full listing grid with prices, conditions, and seller info. Source: v_marketplace_listings_truth."),

    ("marketplace", "listing-grid",
     "marketplace:listing_grid", "Marketplace listing grid",
     "v_marketplace_listings_truth",
     "Listing grid on marketplace.html. Shows all marketplace items visible under the active tab filter. Source: v_marketplace_listings_truth."),

    # ── ph-intelligence ────────────────────────────────────────────────────
    ("ph-intelligence", "ph-summary-details",
     "ph-intelligence:detail_panel", "PH Intelligence detail",
     "ph_intelligence_reports",
     "PH Intelligence detail panel on ph-intelligence.html. Shows network-wide failure cause distribution, plant comparison benchmarks, and trend charts. Source: ph_intelligence_reports."),

    # ── project-manager ────────────────────────────────────────────────────
    ("project-manager", "list-view",
     "project-manager:project_list", "Project list view",
     "projects",
     "Project list view on project-manager.html. Shows all projects as a sortable list with status, owner, and progress. Source: projects table."),

    ("project-manager", "card-grid",
     "project-manager:project_cards", "Project card grid",
     "projects",
     "Project card grid on project-manager.html. Shows active projects as cards with progress bars, end dates, and team assignments. Source: projects table."),

    # ── report-sender ──────────────────────────────────────────────────────
    ("report-sender", "rs-summary-details",
     "report-sender:detail_panel", "Report sender detail",
     "ai_reports",
     "Report sender detail panel on report-sender.html. Shows available reports to select, recipient list, and send history. Source: ai_reports, report_contacts."),

    # ── shift-brain ────────────────────────────────────────────────────────
    ("shift-brain", "sb-summary-details",
     "shift-brain:detail_panel", "Shift brain detail",
     "v_logbook_truth",
     "Shift brain detail panel on shift-brain.html. Shows full shift intelligence: asset risk list, PM task schedule, and carry-forward items from previous shift. Source: v_logbook_truth, v_risk_truth, v_pm_compliance_truth."),
]


def add_rag_tile_to_element(html: str, element_id: str, tile_key: str, label: str) -> Tuple[str, bool]:
    """Add data-rag-tile/label to the opening tag of element with given id.
    Returns (new_html, was_changed)."""
    # Find the opening tag with this id
    pattern = re.compile(
        r'(<\w+[^>]*?\bid=["\']' + re.escape(element_id) + r'["\'][^>]*?)(?<!data-rag-tile)(\s*/?>)',
        re.DOTALL
    )
    # Check if already tagged
    already = re.compile(r'data-rag-tile=["\']' + re.escape(tile_key) + r'["\']')
    if already.search(html):
        return html, False

    # Find the tag and inject attributes before the closing >
    tag_pattern = re.compile(
        r'(<(?:div|section|article|main|aside|nav|ul|table|tbody)\b[^>]*?\bid=["\']'
        + re.escape(element_id)
        + r'["\'][^>]*?)(>)',
        re.DOTALL
    )
    def inject(m):
        return (m.group(1)
                + f'\n    data-rag-tile="{tile_key}"\n    data-rag-label="{label}"'
                + m.group(2))

    new_html, count = tag_pattern.subn(inject, html, count=1)
    return new_html, count > 0


def main():
    cwd = Path(".")
    changed_tiles = []
    skipped = []

    for (page, elem_id, tile_key, label, source, desc) in TILE_PLAN:
        p = cwd / f"{page}.html"
        if not p.exists():
            print(f"SKIP {page}.html (not found)")
            continue
        html = p.read_text(encoding="utf-8", errors="ignore")
        new_html, changed = add_rag_tile_to_element(html, elem_id, tile_key, label)
        if changed:
            p.write_text(new_html, encoding="utf-8")
            print(f"  TAGGED  {page}#{elem_id} -> {tile_key}")
            changed_tiles.append((tile_key, label, source, desc))
        else:
            skipped.append((page, elem_id, tile_key))

    print(f"\nTagged {len(changed_tiles)} new tiles, skipped {len(skipped)} already-done.")

    # Seed canonical_sources for new tiles
    if changed_tiles and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        import requests, json
        url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        payloads = []
        for tile_key, label, source, desc in changed_tiles:
            kind = "view" if source.startswith("v_") else "table"
            payloads.append({
                "domain":      f"ui_kpi_tile:rag_tile:{tile_key}",  # must match processor lookup
                "source_kind": kind,
                "source_name": source,
                "owner_skill": "frontend",
                "freshness":   "live",
                "contract":    f"surfaced via {tile_key}",
                "description": desc[:500],
                "notes":       "turn 30 bulk tag — section-level tiles (tools/tag_all_rag_tiles.py)",
            })
        r = requests.post(
            f"{url}/rest/v1/canonical_sources",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "Prefer": "return=minimal,resolution=ignore-duplicates"},
            data=json.dumps(payloads), timeout=30,
        )
        print(f"canonical_sources seed: HTTP {r.status_code}, {len(payloads)} rows attempted")
    else:
        print("(set SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY to auto-seed canonical_sources)")

    print("\nNew tiles:")
    for tk, lbl, src, _ in changed_tiles:
        print(f"  {tk:55s}  src={src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
