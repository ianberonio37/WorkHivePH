"""
Seed canonical_sources with KPI defs for the 8 new pages added in turn 23.
Idempotent (resolution=ignore-duplicates on the domain PK).
"""
import os, json, sys, requests

SEEDS = [
    ("kpi_def:achievements_xp_week", "v_achievements_truth_xp_week", "community",
     "XP this week — the achievements tile shows total community XP earned by the worker in the past 7 days. Sourced from community_xp table joined to worker_profiles. Awarded via increment_community_xp RPC for logbook entries, PM completions, badges, and helpful forum activity."),
    ("kpi_def:achievements_active_domains", "v_achievements_truth_active_domains", "community",
     "Active domains — the achievements tile counts distinct skill domains the worker has earned at least one badge in (Mechanical, Electrical, Instrumentation, etc.). Sourced from skill_badges + skillmatrix. Each domain unlocks domain-specific quizzes plus leaderboards."),
    ("kpi_def:achievements_total_level", "v_achievements_truth_total_level", "community",
     "Total level — the achievements tile shows the worker cumulative level across all earned skill badges. Each badge has a level 1 to 5. Sourced from worker_achievements joined to achievement_definitions."),
    ("kpi_def:dayplanner_today", "v_dayplanner_truth_today", "frontend",
     "Tasks today — the dayplanner tile counts schedule_items due today for the current worker. Sourced from schedule_items filtered by due_date and worker_name. Includes PM-derived items, logbook follow-ups, and manually-added entries."),
    ("kpi_def:dayplanner_week", "v_dayplanner_truth_week", "frontend",
     "Tasks this week — the dayplanner tile counts schedule_items due in the next 7 days for the current worker. Sourced from schedule_items."),
    ("kpi_def:dayplanner_overdue", "v_dayplanner_truth_overdue", "frontend",
     "Overdue tasks — the dayplanner tile counts schedule_items past their due date and not yet marked done, for the current worker. Sourced from schedule_items."),
    ("kpi_def:integrations_active", "v_integrations_truth_active", "integration-engineer",
     "Active integrations — the integrations tile counts CMMS/ERP/sensor connectors that are enabled AND synced within the last 7 days. Sourced from integration_configs plus external_sync. Stale syncs and disabled count separately."),
    ("kpi_def:integrations_stale", "v_integrations_truth_stale", "integration-engineer",
     "Stale syncs — the integrations tile counts integrations that are enabled but have not synced in 7 plus days. Sourced from external_sync.last_sync_at compared to now."),
    ("kpi_def:integrations_disabled", "v_integrations_truth_disabled", "integration-engineer",
     "Disabled integrations — the integrations tile counts connectors that have been turned off. Sourced from integration_configs where enabled=false."),
    ("kpi_def:marketplace_listings", "v_marketplace_listings_truth", "marketplace",
     "Listings in view — the marketplace tile counts items currently visible after applying the active tab filter (All / Public / My Hive). Sourced from v_marketplace_listings_truth."),
    ("kpi_def:marketplace_my_listings", "v_marketplace_listings_truth_mine", "marketplace",
     "My listings — the marketplace tile counts items the current worker has posted as seller. Sourced from v_marketplace_listings_truth filtered by seller_worker_name."),
    ("kpi_def:marketplace_current_tab", "v_marketplace_listings_truth_tab", "marketplace",
     "Current tab — the marketplace tile shows the active filter the user has selected (All listings / Public only / My hive only). UI state, not a count. Does not ground to a v_*_truth view directly."),
    ("kpi_def:ph_intel_plants", "v_ph_intelligence_truth_plants", "data-engineer",
     "Plants in network — the PH Intelligence tile counts how many hives are contributing anonymized data to the cross-network benchmarks. Sourced from ph_intelligence_reports table aggregated by hive_id."),
    ("kpi_def:ph_intel_cause", "v_ph_intelligence_truth_cause", "data-engineer",
     "Top failure cause — the PH Intelligence tile shows the most common root_cause across the network-wide aggregated logbook. Sourced from ph_intelligence_reports.cause_distribution."),
    ("kpi_def:ph_intel_fresh", "v_ph_intelligence_truth_freshness", "data-engineer",
     "Report freshness — the PH Intelligence tile shows how recent the network benchmark report is, in days. Sourced from ph_intelligence_reports.generated_at compared to now."),
    ("kpi_def:projects_active", "v_projects_truth_active", "architect",
     "Active projects — the project-manager tile counts projects currently in active status (not on_hold, not done, not cancelled). Sourced from projects table."),
    ("kpi_def:projects_overdue", "v_projects_truth_overdue", "architect",
     "Past end date — the project-manager tile counts projects past their planned end_date that are still active. Sourced from projects table."),
    ("kpi_def:projects_blocked", "v_projects_truth_blocked", "architect",
     "On hold or planning — the project-manager tile counts projects in non-active states. Sourced from projects table."),
    ("kpi_def:report_sender_reports", "v_report_sender_truth_reports", "data-engineer",
     "Reports selected — the report-sender tile counts how many reports the user has ticked to include in the next send. Sourced from ai_reports table plus UI selection state."),
    ("kpi_def:report_sender_recipients", "v_report_sender_truth_recipients", "data-engineer",
     "Recipients — the report-sender tile counts how many email addresses have been added to the current send. UI state, validated against contacts list."),
    ("kpi_def:report_sender_contacts", "v_report_sender_truth_contacts", "data-engineer",
     "Saved contacts — the report-sender tile counts addresses saved in the hive contacts list. Sourced from report_contacts table filtered by hive_id."),
    ("kpi_def:shift_brain_risk", "v_shift_brain_truth_risk", "predictive-analytics",
     "Top risk this shift — the shift-brain tile names the highest-risk asset the current shift is responsible for. Sourced from v_risk_truth filtered by current shift asset assignments."),
    ("kpi_def:shift_brain_pms", "v_shift_brain_truth_pms", "predictive-analytics",
     "PMs due — the shift-brain tile counts preventive maintenance tasks due during the current shift on shift-assigned assets. Sourced from v_pm_compliance_truth filtered by asset_assignments."),
    ("kpi_def:shift_brain_carry", "v_shift_brain_truth_carry", "predictive-analytics",
     "Carry-forward — the shift-brain tile counts logbook items the previous shift left open that the current shift inherits. Sourced from v_logbook_truth filtered by status=Open and shift transition time."),
]

url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
if not key:
    print("FAIL: SUPABASE_SERVICE_ROLE_KEY required")
    sys.exit(2)

payloads = []
for domain, source_name, owner, desc in SEEDS:
    payloads.append({
        "domain": domain,
        "source_kind": "view",
        "source_name": source_name,
        "owner_skill": owner,
        "freshness": "live",
        "contract": f"See description. Cite source_name verbatim ({source_name}).",
        "description": desc,
        "notes": "Turn 23 seed by tools/seed_new_page_kpis.py",
    })

r = requests.post(
    f"{url}/rest/v1/canonical_sources",
    headers={
        "apikey": key, "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal,resolution=ignore-duplicates",
    },
    data=json.dumps(payloads), timeout=30,
)
print(f"HTTP {r.status_code} | body: {r.text[:200] if r.text else '(empty)'}")

# Verify
r2 = requests.get(
    f"{url}/rest/v1/canonical_sources?select=count&domain=like.kpi_def:*",
    headers={"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact"},
    timeout=20,
)
print(f"Total kpi_def rows now: {r2.headers.get('content-range', '?')}")
