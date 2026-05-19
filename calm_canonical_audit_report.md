# Calm Dashboard Canonical-Wiring Audit (Layer -1.5)

Classifies every `.from('table')` read on Calm-opted-in pages as
CANONICAL / DRIFT / GAP / ALLOWED. Run by `tools/audit_calm_dashboard_canonical.py`.

## Summary

- Calm-opted-in pages: **14**
- Fully compliant pages (0 drift + 0 gap): **5** (35%)
- Canonical reads (✅): **27**
- Drift reads (⚠️ wrapper exists, page reads raw): **0**
- Gap reads (❌ no wrapper exists yet): **38**
- Allowed reads (legitimate raw): **24**
- Truth views in registry: **22**

## Per-page conformance

| Page | Canonical | Drift | Gap | Allowed | Chip? | Compliant |
|---|---:|---:|---:|---:|:---:|:---:|
| `achievements.html` | 1 | 0 | 2 | 0 | ✓ | ❌ |
| `ai-quality.html` | 0 | 0 | 0 | 1 | ✓ | ✅ |
| `alert-hub.html` | 4 | 0 | 4 | 2 | ✓ | ❌ |
| `analytics.html` | 0 | 0 | 0 | 0 | ✓ | ✅ |
| `asset-hub.html` | 7 | 0 | 10 | 6 | ✓ | ❌ |
| `dayplanner.html` | 1 | 0 | 0 | 2 | ✓ | ✅ |
| `founder-console.html` | 1 | 0 | 4 | 2 | ✓ | ❌ |
| `hive.html` | 6 | 0 | 6 | 6 | ✓ | ❌ |
| `index.html` | 5 | 0 | 3 | 4 | ✓ | ❌ |
| `ph-intelligence.html` | 0 | 0 | 2 | 0 | — | ❌ |
| `plant-connections.html` | 0 | 0 | 6 | 0 | ✓ | ❌ |
| `platform-health.html` | 0 | 0 | 0 | 1 | — | ✅ |
| `predictive.html` | 1 | 0 | 0 | 0 | ✓ | ✅ |
| `shift-brain.html` | 1 | 0 | 1 | 0 | ✓ | ❌ |

## Top GAP tables (no `v_*_truth` exists — next-build queue)

| Raw table | Pages reading it | Suggested wrapper |
|---|---:|---|
| `failure_signature_alerts` | 3 | `v_failure_signature_alert_truth` (suggested) |
| `amc_briefings` | 2 | `v_amc_briefing_truth` (suggested) |
| `parts_staging_recommendations` | 2 | `v_parts_staging_recommendation_truth` (suggested) |
| `external_sync` | 2 | `v_external_sync_truth` (suggested) |
| `sensor_readings` | 2 | `v_sensor_reading_truth` (suggested) |
| `hive_benchmarks` | 2 | `v_hive_benchmark_truth` (suggested) |
| `achievement_xp_log` | 1 | `v_achievement_xp_log_truth` (suggested) |
| `worker_achievements` | 1 | `v_worker_achievement_truth` (suggested) |
| `anomaly_signals` | 1 | `v_anomaly_signal_truth` (suggested) |
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
**Gap** (4): `amc_briefings`, `anomaly_signals`, `failure_signature_alerts`, `parts_staging_recommendations`
**Allowed raw** (2): `automation_log`, `hive_audit_log`

### `analytics.html` — ✅ compliant


### `asset-hub.html` — ❌ not compliant

**Canonical** (7): `v_asset_truth`, `v_fmea_truth`, `v_logbook_truth`, `v_pf_truth`, `v_rcm_truth`, `v_risk_truth`, `v_weibull_truth`
**Gap** (10): `asset_edges`, `equipment_reading_templates`, `external_sync`, `marketplace_listings`, `parts_staged_reservations`, `parts_staging_recommendations`, `rcm_fmea_modes`, `rcm_strategies`, `sensor_readings`, `v_sensor_recent`
**Allowed raw** (6): `asset_nodes`, `hive_audit_log`, `hive_members`, `pm_assets`, `pm_completions`, `pm_scope_items`

### `dayplanner.html` — ✅ compliant

**Canonical** (1): `v_logbook_truth`
**Allowed raw** (2): `logbook`, `schedule_items`

### `founder-console.html` — ❌ not compliant

**Canonical** (1): `v_hive_readiness_truth`
**Gap** (4): `analytics_events`, `marketplace_disputes`, `marketplace_orders`, `platform_feedback`
**Allowed raw** (2): `ai_cost_log`, `hive_audit_log`

### `hive.html` — ❌ not compliant

**Canonical** (6): `v_inventory_items_truth`, `v_knowledge_freshness_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`, `v_worker_truth`
**Gap** (6): `ai_reports`, `failure_signature_alerts`, `hive_benchmarks`, `hives`, `network_benchmarks`, `skill_badges`
**Allowed raw** (6): `asset_nodes`, `community_xp`, `hive_audit_log`, `hive_members`, `logbook`, `pm_completions`

### `index.html` — ❌ not compliant

**Canonical** (5): `v_inventory_items_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_risk_truth`, `v_worker_truth`
**Gap** (3): `amc_briefings`, `failure_signature_alerts`, `sensor_readings`
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
