# Canonical Drift — Platform-Wide (Layer -1.5)

Every HTML page + shared JS scanned for `.from('T').select(...)` calls.
Drift on a **user-facing KPI page** (e.g. hero numbers on tiles) is TIER A —
the class that produces _two pages, two numbers_ inconsistency.

## Summary

- Files scanned: **187**
- KPI-rendering pages: **78**
- Pages with local truth-math (FREQ_DAYS / calcNextDue / ...): **0**
- **TIER A drift pages** (user-facing KPI surface): **0**
- TIER B drift pages (internal / shared JS): **0**
- Canonical reads: 292 · Drift: 0 · Gap: 53 · Allowed: 146

## Gap tables (no `v_*_truth` yet — next-build queue)

| Raw table | Files reading it |
|---|---:|
| `integration_configs` | 4 |
| `project_links` | 3 |
| `asset_edges` | 2 |
| `rcm_fmea_modes` | 2 |
| `equipment_reading_templates` | 2 |
| `community_replies` | 2 |
| `engineering_calcs` | 2 |
| `marketplace_disputes` | 2 |
| `platform_feedback` | 2 |
| `marketplace_reviews` | 2 |
| `ph_intelligence_reports` | 2 |
| `project_roles` | 2 |
| `project_change_orders` | 2 |
| `skill_profiles` | 2 |
| `pdf_jobs` | 2 |
| `achievement_xp_log` | 1 |
| `v_sensor_recent` | 1 |
| `rcm_strategies` | 1 |
| `community_reactions` | 1 |
| `cmms_audit_log` | 1 |
| `parts_staged_reservations` | 1 |
| `marketplace_saved_searches` | 1 |
| `marketplace_watchlist` | 1 |
| `sensor_topic_map` | 1 |
| `gateway_audit_log` | 1 |
| `hive_retention_config` | 1 |
| `sso_configs` | 1 |
| `x` | 1 |
| `resume_versions` | 1 |
| `resume_documents` | 1 |
