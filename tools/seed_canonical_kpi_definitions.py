"""
Seed canonical_sources with KPI definition rows (RAG Flywheel Lane D fuel)
==========================================================================
Lane D in agentic-rag-loop searches canonical_sources.description for
keyword matches. Without per-KPI rows, definition-probe questions
("What does OEE measure?") return 0 chunks. This script seeds 15 rows
covering the platform's most-asked KPIs so Lane D has fuel.

Idempotent: upserts on (source_name) via PostgREST ignore-duplicates.
Local-first per [[feedback-local-first-never-push-prod]].
"""

from __future__ import annotations
import os
import sys
import json
import argparse


# 15 KPI definition rows. Each names the canonical v_*_truth view + the
# platform standard the metric implements. source_kind=view since these
# are all read-via views in the platform.
KPI_DEFINITIONS = [
    {
        "domain":      "kpi_def:kpi_oee",
        "source_kind": "view",
        "source_name": "v_kpi_truth_oee",
        "owner_skill": "maintenance-expert",
        "freshness":   "live",
        "contract":    "OEE = Availability × Performance × Quality (ISO 22400-2:2014 §5.5). On WorkHive the OEE tile reads from v_kpi_truth, partial (A × Q) until ideal cycle time is captured per asset.",
        "description": "Overall Equipment Effectiveness — the OEE KPI measures how well equipment is utilized: Availability × Performance × Quality. Standard: ISO 22400-2:2014 §5.5. Sourced from v_kpi_truth view. On the analytics page the OEE tile shows a rolling average across the hive.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py for RAG Flywheel Lane D",
    },
    {
        "domain":      "kpi_def:kpi_mtbf",
        "source_kind": "view",
        "source_name": "v_kpi_truth_mtbf",
        "owner_skill": "maintenance-expert",
        "freshness":   "live",
        "contract":    "MTBF = mean of inter-arrival intervals of Breakdown/Corrective logbook entries (ISO 14224:2016 §9.3). WorkHive computes per-machine MTBF via get_mtbf_by_machine RPC, sourced from v_logbook_truth.",
        "description": "Mean Time Between Failures — MTBF measures how long equipment runs between breakdowns. Standard: ISO 14224:2016 §9.3. Computed from v_logbook_truth via the get_mtbf_by_machine Postgres RPC. The analytics page's MTBF tile shows the worst per-asset MTBF in the selected window.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:kpi_mttr",
        "source_kind": "view",
        "source_name": "v_kpi_truth_mttr",
        "owner_skill": "maintenance-expert",
        "freshness":   "live",
        "contract":    "MTTR = mean of downtime_hours for closed Breakdown/Corrective logbook entries (ISO 14224:2016 §9.3). WorkHive prefers user-entered downtime_hours over clock difference per data-engineer skill.",
        "description": "Mean Time To Repair — MTTR measures how long equipment takes to be fixed after a breakdown. Standard: ISO 14224:2016 §9.3. Computed from v_logbook_truth where status='Closed' and maintenance_type='Breakdown / Corrective'.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:pm_compliance_30d",
        "source_kind": "view",
        "source_name": "v_pm_compliance_truth_30d",
        "owner_skill": "maintenance-expert",
        "freshness":   "live",
        "contract":    "PM compliance = completed PM tasks / scheduled PM tasks within window. WorkHive computes via v_pm_compliance_truth with is_due based on last_anchor_date and 30-day floor.",
        "description": "Preventive Maintenance Compliance — the PM compliance KPI measures the percentage of scheduled PM tasks completed on time. Standard: SMRP Best Practices v5.0 §2.1.1. Sourced from v_pm_compliance_truth. The pm-scheduler.html and analytics.html pages both show this.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:logbook_downtime",
        "source_kind": "view",
        "source_name": "v_logbook_truth_downtime",
        "owner_skill": "maintenance-expert",
        "freshness":   "live",
        "contract":    "Downtime = sum of downtime_hours for Breakdown/Corrective entries in the analysis window. Sourced from v_logbook_truth.",
        "description": "Downtime hours — sum of hours equipment was non-productive due to breakdowns. Sourced from v_logbook_truth where maintenance_type='Breakdown / Corrective'. Surfaced on analytics.html, alert-hub.html, and asset-hub.html risk tiles.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:risk_high_severity_alerts",
        "source_kind": "view",
        "source_name": "v_risk_truth_high_severity_alerts",
        "owner_skill": "predictive-analytics",
        "freshness":   "daily-13-00-pht",
        "contract":    "High-severity alerts = count of v_risk_truth rows where risk_level='high' or 'critical'. Computed daily by batch-risk-scoring; surfaced on alert-hub.html.",
        "description": "High-severity alerts — the alert-hub tile counts assets whose composite risk score is high or critical. Sourced from v_risk_truth (daily snapshot at 13:00 PHT, regenerated by batch-risk-scoring edge fn).",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:risk_anomaly_signals",
        "source_kind": "view",
        "source_name": "v_risk_truth_anomaly_signals",
        "owner_skill": "predictive-analytics",
        "freshness":   "live",
        "contract":    "Anomaly signals = count of failure_signature_alerts matching recent failure_signature_scan output. Surfaced on alert-hub.html as the anomaly tile.",
        "description": "Anomaly signals — the alert-hub tile counts active failure-signature alerts where the platform detected an anomalous pattern. Sourced from failure_signature_alerts table, populated by failure-signature-scan edge fn.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:asset_total",
        "source_kind": "view",
        "source_name": "v_asset_truth_total",
        "owner_skill": "architect",
        "freshness":   "live",
        "contract":    "Total assets = count of approved rows in asset_nodes for the hive. Sourced from v_asset_truth which bridges asset_nodes + legacy assets.id + pm_assets.id.",
        "description": "Total assets — the asset-hub tile shows the count of approved assets in the hive's catalog. Sourced from v_asset_truth (canonical asset 360 view). Pending approvals are counted separately.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:asset_critical",
        "source_kind": "view",
        "source_name": "v_asset_truth_critical",
        "owner_skill": "architect",
        "freshness":   "live",
        "contract":    "Critical assets = count of v_asset_truth rows where criticality='critical'. Higher count = more strict PM cadence + risk thresholds.",
        "description": "Critical assets — the asset-hub tile shows the count of assets flagged as 'critical' criticality. These get stricter PM cadence + risk thresholds. Sourced from v_asset_truth.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:pm_compliance_overdue",
        "source_kind": "view",
        "source_name": "v_pm_compliance_truth_overdue",
        "owner_skill": "maintenance-expert",
        "freshness":   "live",
        "contract":    "Overdue PMs = count of v_pm_compliance_truth rows where is_due=true and last_anchor_date older than 30 days. Surfaced on pm-scheduler.html.",
        "description": "Overdue PMs — the pm-scheduler tile counts preventive maintenance tasks past their due date. Sourced from v_pm_compliance_truth where is_due flag is true based on last_anchor_date < now - 30 days.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:pm_compliance_duesoon",
        "source_kind": "view",
        "source_name": "v_pm_compliance_truth_duesoon",
        "owner_skill": "maintenance-expert",
        "freshness":   "live",
        "contract":    "Due soon = count of v_pm_compliance_truth rows where next_due_date is within the next 14 days. Surfaced on pm-scheduler.html.",
        "description": "Due this week — the pm-scheduler tile counts preventive maintenance tasks coming due in the next 14 days. Sourced from v_pm_compliance_truth.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:inventory_items_out_of_stock",
        "source_kind": "view",
        "source_name": "v_inventory_items_truth_out_of_stock",
        "owner_skill": "data-engineer",
        "freshness":   "live",
        "contract":    "Out of stock = count of v_inventory_items_truth rows where qty_on_hand = 0. Surfaced on inventory.html.",
        "description": "Out of stock parts — the inventory tile counts parts whose qty_on_hand is zero. Sourced from v_inventory_items_truth. Drives reorder recommendations via parts-staging-recommender edge fn.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:inventory_items_low_stock",
        "source_kind": "view",
        "source_name": "v_inventory_items_truth_low_stock",
        "owner_skill": "data-engineer",
        "freshness":   "live",
        "contract":    "Low stock = count of v_inventory_items_truth rows where qty_on_hand <= reorder_point AND qty_on_hand > 0. Surfaced on inventory.html.",
        "description": "Low stock parts — the inventory tile counts parts at or below reorder point but not yet zero. Sourced from v_inventory_items_truth. These should be reordered soon to avoid hitting out-of-stock.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:worker_skill_on_target",
        "source_kind": "view",
        "source_name": "v_worker_skill_truth_on_target",
        "owner_skill": "community",
        "freshness":   "live",
        "contract":    "On-target workers = count of v_worker_skill_truth rows where skill_count >= target. Surfaced on skillmatrix.html.",
        "description": "Workers on target — the skillmatrix tile counts workers who have met or exceeded their skill-count target. Sourced from v_worker_skill_truth, the canonical worker-skill aggregate view.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
    {
        "domain":      "kpi_def:kpi_hive_maturity_stair",
        "source_kind": "view",
        "source_name": "v_kpi_truth_hive_maturity_stair",
        "owner_skill": "platform-guardian",
        "freshness":   "live",
        "contract":    "Hive maturity stair = composite of Reliability/Operations/Safety/People/Cost dimensions per KPI_ENGINE.md WorkHive Stair Model. Surfaced on hive.html.",
        "description": "Hive maturity stair — the hive page tile shows the WorkHive Stair Model composite (5-dimension: Reliability, Operations, Safety, People, Cost). See KPI_ENGINE.md. Stair 1-5 unlocks progressively richer platform features.",
        "notes":       "Seeded by tools/seed_canonical_kpi_definitions.py",
    },
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed canonical_sources with KPI definition rows (Lane D fuel)")
    ap.add_argument("--commit", action="store_true", help="Actually insert (default: dry-run)")
    args = ap.parse_args()

    if not args.commit:
        print(f"DRY-RUN: would seed {len(KPI_DEFINITIONS)} KPI definition rows into canonical_sources")
        for kd in KPI_DEFINITIONS:
            print(f"  - {kd['source_name']:50s} {kd['description'][:60]}...")
        return 0

    try:
        import requests
    except ImportError:
        print("FAIL: pip install requests")
        return 2

    url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not key:
        print("FAIL: SUPABASE_SERVICE_ROLE_KEY required for --commit")
        return 2

    inserted = 0
    skipped = 0
    failed = []
    for kd in KPI_DEFINITIONS:
        r = requests.post(
            f"{url}/rest/v1/canonical_sources",
            headers={
                "apikey":        key,
                "Authorization": f"Bearer {key}",
                "Content-Type":  "application/json",
                "Prefer":        "return=minimal,resolution=ignore-duplicates",
            },
            data=json.dumps(kd),
            timeout=20,
        )
        if r.status_code in (200, 201, 204):
            inserted += 1
            print(f"  OK   {kd['source_name']}")
        elif r.status_code == 409 or "duplicate" in r.text.lower():
            skipped += 1
            print(f"  SKIP {kd['source_name']} (already exists)")
        else:
            failed.append((kd['source_name'], r.status_code, r.text[:120]))
            print(f"  FAIL {kd['source_name']} HTTP {r.status_code}: {r.text[:120]}")

    print()
    print(f"Done. inserted={inserted}  skipped={skipped}  failed={len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
