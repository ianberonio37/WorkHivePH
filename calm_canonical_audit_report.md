# Calm Dashboard Canonical-Wiring Audit (Layer -1.5)

Classifies every `.from('table')` read on Calm-opted-in pages as
CANONICAL / DRIFT / GAP / ALLOWED. Run by `tools/audit_calm_dashboard_canonical.py`.

## Summary

- Calm-opted-in pages: **14**
- Fully compliant pages (0 drift + 0 gap): **6** (42%)
- Canonical reads (✅): **32**
- Drift reads (⚠️ wrapper exists, page reads raw): **0**
- Gap reads (❌ no wrapper exists yet): **30**
- Allowed reads (legitimate raw): **27**
- Truth views in registry: **25**

## Per-page conformance

| Page | Canonical | Drift | Gap | Allowed | Chip? | Compliant |
|---|---:|---:|---:|---:|:---:|:---:|
| `achievements.html` | 1 | 0 | 2 | 0 | ✓ | ❌ |
| `ai-quality.html` | 0 | 0 | 0 | 1 | ✓ | ✅ |
| `alert-hub.html` | 4 | 0 | 1 | 5 | ✓ | ❌ |
| `analytics.html` | 0 | 0 | 0 | 0 | ✓ | ✅ |
| `asset-hub.html` | 8 | 0 | 9 | 6 | ✓ | ❌ |
| `dayplanner.html` | 1 | 0 | 0 | 2 | ✓ | ✅ |
| `founder-console.html` | 1 | 0 | 4 | 2 | ✓ | ❌ |
| `hive.html` | 7 | 0 | 5 | 6 | ✓ | ❌ |
| `index.html` | 8 | 0 | 0 | 4 | ✓ | ✅ |
| `ph-intelligence.html` | 0 | 0 | 2 | 0 | — | ❌ |
| `plant-connections.html` | 0 | 0 | 6 | 0 | ✓ | ❌ |
| `platform-health.html` | 0 | 0 | 0 | 1 | — | ✅ |
| `predictive.html` | 1 | 0 | 0 | 0 | ✓ | ✅ |
| `shift-brain.html` | 1 | 0 | 1 | 0 | ✓ | ❌ |

## Top GAP tables (no `v_*_truth` exists — next-build queue)

| Raw table | Pages reading it | Suggested wrapper |
|---|---:|---|
| `parts_staging_recommendations` | 2 | `v_parts_staging_recommendation_truth` (suggested) |
| `external_sync` | 2 | `v_external_sync_truth` (suggested) |
| `hive_benchmarks` | 2 | `v_hive_benchmark_truth` (suggested) |
| `achievement_xp_log` | 1 | `v_achievement_xp_log_truth` (suggested) |
| `worker_achievements` | 1 | `v_worker_achievement_truth` (suggested) |
| `asset_edges` | 1 | `v_asset_edge_truth` (suggested) |
| `equipment_reading_templates` | 1 | `v_equipment_reading_template_truth` (suggested) |
| `marketplace_listings` | 1 | `v_marketplace_listing_truth` (suggested) |
| `parts_staged_reservations` | 1 | `v_parts_staged_reservation_truth` (suggested) |
| `rcm_fmea_modes` | 1 | `v_rcm_fmea_mode_truth` (suggested) |
| `rcm_strategies` | 1 | `v_rcm_strategie_truth` (suggested) |
| `v_sensor_recent` | 1 | `v_v_sensor_recent_truth` (suggested) |
| `analytics_events` | 1 | `v_analytics_event_truth` (suggested) |
| `marketplace_disputes` | 1 | `v_marketplace_dispute_truth` (suggested) |
| `marketplace_orders` | 1 | `v_marketplace_order_truth` (suggested) |
| `platform_feedback` | 1 | `v_platform_feedback_truth` (suggested) |
| `ai_reports` | 1 | `v_ai_report_truth` (suggested) |
| `hives` | 1 | `v_hive_truth` (suggested) |
| `network_benchmarks` | 1 | `v_network_benchmark_truth` (suggested) |
| `skill_badges` | 1 | `v_skill_badge_truth` (suggested) |

## Top DRIFT tables (wrapper exists, pages still reading raw)

| Raw table | Use instead | Pages reading raw |
|---|---|---:|

## Per-page detail

### `achievements.html` — ❌ not compliant

**Canonical** (1): `v_worker_truth`
**Gap** (2): `achievement_xp_log`, `worker_achievements`

### `ai-quality.html` — ✅ compliant

**Allowed raw** (1): `ai_cost_log`

### `alert-hub.html` — ❌ not compliant

**Canonical** (4): `v_anomaly_truth`, `v_inventory_items_truth`, `v_pm_compliance_truth`, `v_risk_truth`
**Gap** (1): `parts_staging_recommendations`
**Allowed raw** (5): `amc_briefings`, `anomaly_signals`, `automation_log`, `failure_signature_alerts`, `hive_audit_log`

### `analytics.html` — ✅ compliant


### `asset-hub.html` — ❌ not compliant

**Canonical** (8): `v_asset_truth`, `v_fmea_truth`, `v_logbook_truth`, `v_pf_truth`, `v_rcm_truth`, `v_risk_truth`, `v_sensor_truth`, `v_weibull_truth`
**Gap** (9): `asset_edges`, `equipment_reading_templates`, `external_sync`, `marketplace_listings`, `parts_staged_reservations`, `parts_staging_recommendations`, `rcm_fmea_modes`, `rcm_strategies`, `v_sensor_recent`
**Allowed raw** (6): `asset_nodes`, `hive_audit_log`, `hive_members`, `pm_assets`, `pm_completions`, `pm_scope_items`

### `dayplanner.html` — ✅ compliant

**Canonical** (1): `v_logbook_truth`
**Allowed raw** (2): `logbook`, `schedule_items`

### `founder-console.html` — ❌ not compliant

**Canonical** (1): `v_hive_readiness_truth`
**Gap** (4): `analytics_events`, `marketplace_disputes`, `marketplace_orders`, `platform_feedback`
**Allowed raw** (2): `ai_cost_log`, `hive_audit_log`

### `hive.html` — ❌ not compliant

**Canonical** (7): `v_alert_truth`, `v_inventory_items_truth`, `v_knowledge_freshness_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`, `v_worker_truth`
**Gap** (5): `ai_reports`, `hive_benchmarks`, `hives`, `network_benchmarks`, `skill_badges`
**Allowed raw** (6): `asset_nodes`, `community_xp`, `hive_audit_log`, `hive_members`, `logbook`, `pm_completions`

### `index.html` — ✅ compliant

**Canonical** (8): `v_alert_truth`, `v_amc_truth`, `v_inventory_items_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_risk_truth`, `v_sensor_truth`, `v_worker_truth`
**Allowed raw** (4): `early_access_emails`, `pm_assets`, `pm_completions`, `worker_profiles`

### `ph-intelligence.html` — ❌ not compliant

**Gap** (2): `hive_benchmarks`, `ph_intelligence_reports`

### `plant-connections.html` — ❌ not compliant

**Gap** (6): `external_sync`, `gateway_audit_log`, `hive_retention_config`, `integration_configs`, `sensor_topic_map`, `sso_configs`

### `platform-health.html` — ✅ compliant

**Allowed raw** (1): `marketplace_platform_admins`

### `predictive.html` — ✅ compliant

**Canonical** (1): `v_risk_truth`

### `shift-brain.html` — ❌ not compliant

**Canonical** (1): `v_worker_truth`
**Gap** (1): `shift_plans`
