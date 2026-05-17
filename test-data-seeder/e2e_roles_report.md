# Role Permission Test Report
Generated: 2026-05-17T11:56:31.854364

## Summary
- **PASS:** 66
- **FAIL:** 57
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
- **worker** / `handover_entries`: expected `True` but got `False`
- **supervisor** / `handover_entries`: expected `True` but got `False`
- **worker** / `submit_handover_btn`: expected `True` but got `False`
- **supervisor** / `submit_handover_btn`: expected `True` but got `False`

### alert-hub
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `alert_list`: expected `True` but got `False`
- **supervisor** / `alert_list`: expected `True` but got `False`
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
- **worker** / `skill_rows`: expected `True` but got `False`
- **supervisor** / `skill_rows`: expected `True` but got `False`
- **supervisor** / `update_target_btn`: expected `True` but got `False`

### report-sender
- **solo** / `access_gated`: expected `True` but got `False`
- **supervisor** / `report_template`: expected `True` but got `False`

### plant-connections
- **supervisor** / `plant_list`: expected `True` but got `False`

### audit-log
- **solo** / `access_gated`: expected `True` but got `False`
- **supervisor** / `audit_entries`: expected `True` but got `False`

### platform-health
- **solo** / `access_gated`: expected `True` but got `False`
- **supervisor** / `health_cards`: expected `True` but got `False`

### achievements
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `badge_cards`: expected `True` but got `False`
- **supervisor** / `badge_cards`: expected `True` but got `False`
- **supervisor** / `award_btn`: expected `True` but got `False`

### voice-journal
- **solo** / `access_gated`: expected `True` but got `False`
- **worker** / `voice_logs`: expected `True` but got `False`
- **supervisor** / `voice_logs`: expected `True` but got `False`
- **worker** / `record_btn`: expected `True` but got `False`
- **supervisor** / `record_btn`: expected `True` but got `False`

### integrations
- **supervisor** / `integration_cards`: expected `True` but got `False`
- **supervisor** / `configure_btn`: expected `True` but got `False`

### public-feed
- **solo** / `post_feed`: expected `True` but got `False`
- **worker** / `post_feed`: expected `True` but got `False`
- **supervisor** / `post_feed`: expected `True` but got `False`

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
- **supervisor** / `approve_btn`: expected `True` but got `False`

## Role Diff per Page

### logbook
- Worker+ (not solo): `view_team_tab, view_mine_tab`

### hive
- Supervisor-only: `show_invite_code_btn`

### community
- Worker+ (not solo): `post_submit_btn`

### asset-hub
- Worker+ (not solo): `asset_list`

### audit-log
- Supervisor-only: `action_filter`