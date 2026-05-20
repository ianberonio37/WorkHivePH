# Canonical Drift — Platform-Wide (Layer -1.5)

Every HTML page + shared JS scanned for `.from('T').select(...)` calls.
Drift on a **user-facing KPI page** (e.g. hero numbers on tiles) is TIER A —
the class that produces _two pages, two numbers_ inconsistency.

## Summary

- Files scanned: **41**
- KPI-rendering pages: **28**
- Pages with local truth-math (FREQ_DAYS / calcNextDue / ...): **0**
- **TIER A drift pages** (user-facing KPI surface): **0**
- TIER B drift pages (internal / shared JS): **3**
- Canonical reads: 92 · Drift: 7 · Gap: 84 · Allowed: 86

## Drift by table (which raw tables are still being read)

| Raw table | Files reading raw | Use instead |
|---|---:|---|
| `asset_nodes` | 3 | `v_asset_truth` |
| `worker_profiles` | 2 | `v_worker_truth` |
| `projects` | 1 | `v_project_truth` |
| `pm_assets` | 1 | `v_pm_compliance_truth` |

## Gap tables (no `v_*_truth` yet — next-build queue)

| Raw table | Files reading it |
|---|---:|
| `external_sync` | 5 |
| `analytics_events` | 5 |
| `marketplace_inquiries` | 5 |
| `hives` | 4 |
| `integration_configs` | 4 |
| `project_links` | 4 |
| `worker_achievements` | 3 |
| `skill_badges` | 3 |
| `marketplace_orders` | 3 |
| `ai_reports` | 3 |
| `inventory_transactions` | 3 |
| `project_items` | 3 |
| `parts_staging_recommendations` | 2 |
| `equipment_reading_templates` | 2 |
| `community_replies` | 2 |
| `marketplace_disputes` | 2 |
| `hive_benchmarks` | 2 |
| `marketplace_reviews` | 2 |
| `project_progress_logs` | 2 |
| `achievement_xp_log` | 1 |
| `asset_edges` | 1 |
| `v_sensor_recent` | 1 |
| `rcm_fmea_modes` | 1 |
| `rcm_strategies` | 1 |
| `community_reactions` | 1 |
| `engineering_calcs` | 1 |
| `platform_feedback` | 1 |
| `network_benchmarks` | 1 |
| `api_keys` | 1 |
| `cmms_audit_log` | 1 |
