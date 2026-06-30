# Role Permission Test Report
Generated: 2026-06-19T17:47:39.784231

## Summary
- **PASS:** 82
- **FAIL:** 45
- **INFO (no expectation):** 120

## Permission Violations

### analytics
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `kpi_cards`: expected `True` but got `False`
- **supervisor** / `kpi_cards`: expected `True` but got `False`

### analytics-report
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `report_sections`: expected `True` but got `False`
- **supervisor** / `report_sections`: expected `True` but got `False`

### shift-brain
- **worker** / `submit_handover_btn`: expected `True` but got `False`
- **supervisor** / `submit_handover_btn`: expected `True` but got `False`

### alert-hub
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `acknowledge_btn`: expected `True` but got `False`
- **supervisor** / `acknowledge_btn`: expected `True` but got `False`
- **supervisor** / `resolve_btn`: expected `True` but got `False`

### predictive
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `prediction_cards`: expected `True` but got `False`
- **supervisor** / `prediction_cards`: expected `True` but got `False`
- **supervisor** / `score_btn`: expected `True` but got `False`

### ai-quality
- **worker** / `quality_metrics`: expected `True` but got `False`
- **supervisor** / `quality_metrics`: expected `True` but got `False`
- **supervisor** / `evaluate_btn`: expected `True` but got `False`

### skillmatrix
- **solo** / `access_gated`: expected `True` but got `False`
- **solo** / `skill_rows`: expected `False` but got `True`
- **supervisor** / `update_target_btn`: expected `True` but got `False`

### report-sender
- **solo** / `access_gated`: expected `True` but got `False`
- **supervisor** / `report_template`: expected `True` but got `False`

### plant-connections
- **supervisor** / `plant_list`: expected `True` but got `False`

### audit-log
- **solo** / `access_gated`: expected `True` but got `False`

### platform-health
- **solo** / `access_gated`: expected `True` but got `False`
- **supervisor** / `health_cards`: expected `True` but got `False`

### achievements
- **solo** / `access_gated`: expected `True` but got `False`
- **solo** / `badge_cards`: expected `False` but got `True`
- **supervisor** / `award_btn`: expected `True` but got `False`

### voice-journal
- **solo** / `access_gated`: expected `True` but got `False`
- **solo** / `voice_logs`: expected `False` but got `True`
- **worker** / `record_btn`: expected `True` but got `False`
- **supervisor** / `record_btn`: expected `True` but got `False`

### integrations
- **worker** / `integration_cards`: expected `False` but got `True`
- **supervisor** / `configure_btn`: expected `True` but got `False`

### assistant
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `chat_input`: expected `True` but got `False`
- **supervisor** / `chat_input`: expected `True` but got `False`

### ph-intelligence
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `insight_cards`: expected `True` but got `False`
- **supervisor** / `insight_cards`: expected `True` but got `False`

### marketplace-admin
- **solo** / `access_gated`: expected `True` but got `False`
- **supervisor** / `listing_queue`: expected `True` but got `False`

## Role Diff per Page

### logbook
- Worker+ (not solo): `view_mine_tab, view_team_tab`

### hive
- Supervisor-only: `show_invite_code_btn`

### community
- Worker+ (not solo): `post_submit_btn`

### shift-brain
- Worker+ (not solo): `handover_entries`

### asset-hub
- Worker+ (not solo): `asset_list`

### alert-hub
- Worker+ (not solo): `alert_list`

### audit-log
- Supervisor-only: `action_filter, audit_entries`

### integrations
- Worker+ (not solo): `integration_cards`

### marketplace-admin
- Supervisor-only: `reject_btn, approve_btn`