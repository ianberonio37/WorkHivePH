# Calm Dashboard Canonical-Wiring Audit (Layer -1.5)

Classifies every `.from('table')` read on Calm-opted-in pages as
CANONICAL / DRIFT / GAP / ALLOWED. Run by `tools/audit_calm_dashboard_canonical.py`.

## Summary

- Calm-opted-in pages: **15**
- Fully compliant pages (0 drift + 0 gap): **14** (93%)
- Canonical reads (✅): **41**
- Drift reads (⚠️ wrapper exists, page reads raw): **0**
- Gap reads (❌ no wrapper exists yet): **1**
- Allowed reads (legitimate raw): **50**
- Truth views in registry: **39**

## Per-page conformance

| Page | Canonical | Drift | Gap | Allowed | Chip? | Compliant |
|---|---:|---:|---:|---:|:---:|:---:|
| `achievements.html` | 2 | 0 | 0 | 1 | ✓ | ✅ |
| `agentic-rag-observability.html` | 0 | 0 | 0 | 1 | — | ✅ |
| `ai-quality.html` | 0 | 0 | 1 | 1 | ✓ | ❌ |
| `alert-hub.html` | 5 | 0 | 0 | 5 | ✓ | ✅ |
| `analytics.html` | 0 | 0 | 0 | 0 | ✓ | ✅ |
| `asset-hub.html` | 10 | 0 | 0 | 13 | ✓ | ✅ |
| `dayplanner.html` | 1 | 0 | 0 | 2 | ✓ | ✅ |
| `founder-console.html` | 2 | 0 | 0 | 5 | ✓ | ✅ |
| `hive.html` | 10 | 0 | 0 | 9 | ✓ | ✅ |
| `index.html` | 8 | 0 | 0 | 4 | ✓ | ✅ |
| `ph-intelligence.html` | 0 | 0 | 0 | 2 | — | ✅ |
| `plant-connections.html` | 1 | 0 | 0 | 5 | ✓ | ✅ |
| `platform-health.html` | 0 | 0 | 0 | 1 | — | ✅ |
| `predictive.html` | 1 | 0 | 0 | 0 | ✓ | ✅ |
| `shift-brain.html` | 1 | 0 | 0 | 1 | ✓ | ✅ |

## Top GAP tables (no `v_*_truth` exists — next-build queue)

| Raw table | Pages reading it | Suggested wrapper |
|---|---:|---|
| `ai_reply_feedback` | 1 | `v_ai_reply_feedback_truth` (suggested) |

## Top DRIFT tables (wrapper exists, pages still reading raw)

| Raw table | Use instead | Pages reading raw |
|---|---|---:|

## Per-page detail

### `achievements.html` — ✅ compliant

**Canonical** (2): `v_worker_achievements_truth`, `v_worker_truth`
**Allowed raw** (1): `achievement_xp_log`

### `agentic-rag-observability.html` — ✅ compliant

**Allowed raw** (1): `agentic_rag_traces`

### `ai-quality.html` — ❌ not compliant

**Gap** (1): `ai_reply_feedback`
**Allowed raw** (1): `ai_cost_log`

### `alert-hub.html` — ✅ compliant

**Canonical** (5): `v_alert_truth`, `v_anomaly_truth`, `v_inventory_items_truth`, `v_pm_scope_items_truth`, `v_risk_truth`
**Allowed raw** (5): `amc_briefings`, `anomaly_signals`, `automation_log`, `hive_audit_log`, `parts_staging_recommendations`

### `analytics.html` — ✅ compliant


### `asset-hub.html` — ✅ compliant

**Canonical** (10): `v_asset_truth`, `v_external_sync_truth`, `v_fmea_truth`, `v_logbook_truth`, `v_marketplace_listings_truth`, `v_pf_truth`, `v_rcm_truth`, `v_risk_truth`, `v_sensor_truth`, `v_weibull_truth`
**Allowed raw** (13): `asset_edges`, `asset_nodes`, `equipment_reading_templates`, `hive_audit_log`, `hive_members`, `parts_staged_reservations`, `parts_staging_recommendations`, `pm_assets`, `pm_completions`, `pm_scope_items`, `rcm_fmea_modes`, `rcm_strategies`, `v_sensor_recent`

### `dayplanner.html` — ✅ compliant

**Canonical** (1): `v_logbook_truth`
**Allowed raw** (2): `logbook`, `schedule_items`

### `founder-console.html` — ✅ compliant

**Canonical** (2): `v_hive_readiness_truth`, `v_marketplace_orders_truth`
**Allowed raw** (5): `ai_cost_log`, `analytics_events`, `hive_audit_log`, `marketplace_disputes`, `platform_feedback`

### `hive.html` — ✅ compliant

**Canonical** (10): `v_ai_reports_truth`, `v_alert_truth`, `v_hives_truth`, `v_inventory_items_truth`, `v_knowledge_freshness_truth`, `v_logbook_truth`, `v_pm_compliance_truth`, `v_pm_scope_items_truth`, `v_skill_badges_truth`, `v_worker_truth`
**Allowed raw** (9): `asset_nodes`, `community_xp`, `hive_audit_log`, `hive_benchmarks`, `hive_members`, `hives`, `logbook`, `network_benchmarks`, `pm_completions`

### `index.html` — ✅ compliant

**Canonical** (8): `v_alert_truth`, `v_amc_truth`, `v_inventory_items_truth`, `v_logbook_truth`, `v_pm_scope_items_truth`, `v_risk_truth`, `v_sensor_truth`, `v_worker_truth`
**Allowed raw** (4): `early_access_emails`, `pm_assets`, `pm_completions`, `worker_profiles`

### `ph-intelligence.html` — ✅ compliant

**Allowed raw** (2): `hive_benchmarks`, `ph_intelligence_reports`

### `plant-connections.html` — ✅ compliant

**Canonical** (1): `v_external_sync_truth`
**Allowed raw** (5): `gateway_audit_log`, `hive_retention_config`, `integration_configs`, `sensor_topic_map`, `sso_configs`

### `platform-health.html` — ✅ compliant

**Allowed raw** (1): `marketplace_platform_admins`

### `predictive.html` — ✅ compliant

**Canonical** (1): `v_risk_truth`

### `shift-brain.html` — ✅ compliant

**Canonical** (1): `v_worker_truth`
**Allowed raw** (1): `shift_plans`
