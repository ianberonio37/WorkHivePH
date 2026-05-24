# Sentinel Proposals (v1.4 - check-level)

Generated for 51 uncovered CHECK(s) across 11 per-page validators. Each check is one rule
the platform should obey - and currently no Playwright spec exercises it.

**Check coverage:** 81.7% (227 of 278 per-page checks - HONEST behavioral coverage)
**Topic coverage:** 100.0% (35 of 35 per-page validators - loose, validator-level)
**Raw coverage:** 81.5% (243 of 298 validators)

Each section below groups uncovered checks by validator. Use the per-check
list as your test backlog - one scenario per check, not one scenario per
validator. The check-name itself is the test-name anchor: include it in
the new test() name so the next sentinel run picks up the match.

Platform-wide and Infrastructure gaps are listed at the bottom for
transparency - they don't need Playwright scenarios.

---

## Per-page CHECK-level gaps (the test backlog)

## Validator #1: `validate_achievements.py`  -  1 check(s) untested

**Label:** validate_achievements.py - Phase 1.9 of STRATEGIC_ROADMAP.md.  
**Likely surface:** achievements.html  
**Reference pattern:** journey-achievements.spec.ts  
**Already covered (6):** `l1`, `l2`, `l3_worker_ach`, `l3_xp_log`, `l4`, `l5`

### Uncovered checks (1)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `l2_reset_missing`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_achievements.py` (target: `achievements.html`) declares 1
rules that have NO Playwright test exercising them:
  - l2_reset_missing

Read `achievements.html` for selectors, form IDs, routes.
Match the canonical pattern in `tests/journey-achievements.spec.ts` (imports from './_fixtures' + './_helpers', uses whPage + testMarker).

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #2: `validate_agentic_rag_observability.py`  -  4 check(s) untested

**Label:** validate_agentic_rag_observability  
**Likely surface:** agentic-rag-observability.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (6):** `calm_meta`, `eschtml`, `hive_gate`, `hive_scoping`, `narrow_select`, `window_filter`

### Uncovered checks (4)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `bounded_fetch`
- `file_exists`
- `render_blocks`
- `utils_loaded`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_agentic_rag_observability.py` (target: `agentic-rag-observability.html`) declares 4
rules that have NO Playwright test exercising them:
  - bounded_fetch
  - file_exists
  - render_blocks
  - utils_loaded

No journey spec exists for this topic yet. Create `tests/journey-agentic.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #3: `validate_ai_companion_trust_observability.py`  -  8 check(s) untested

**Label:** validate_ai_companion_trust_observability  
**Likely surface:** ai-quality.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (2):** `citation_anchor`, `hallucination_guard`

### Uncovered checks (8)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `acronym_pronunciation`
- `assistant_journal_pull`
- `audio_interrupt`
- `conversation_end_ack`
- `cost_cap`
- `fallback_ux`
- `rate_limit_guard`
- `tts_latency_budget`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_ai_companion_trust_observability.py` (target: `ai-quality.html`) declares 8
rules that have NO Playwright test exercising them:
  - acronym_pronunciation
  - assistant_journal_pull
  - audio_interrupt
  - conversation_end_ack
  - cost_cap
  - fallback_ux
  - rate_limit_guard
  - tts_latency_budget

No journey spec exists for this topic yet. Create `tests/journey-ai.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #4: `validate_ai_regression.py`  -  3 check(s) untested

**Label:** validate_ai_regression  
**Likely surface:** analytics.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (4):** `calc_count_consistent`, `discipline_names`, `tier_s_citation`, `tool_consistency`

### Uncovered checks (3)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `analytics_feature_parity`
- `draft_artifacts`
- `logbook_feature_parity`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_ai_regression.py` (target: `analytics.html`) declares 3
rules that have NO Playwright test exercising them:
  - analytics_feature_parity
  - draft_artifacts
  - logbook_feature_parity

No journey spec exists for this topic yet. Create `tests/journey-ai.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #5: `validate_analytics.py`  -  8 check(s) untested

**Label:** validate_analytics  
**Likely surface:** analytics.html  
**Reference pattern:** journey-analytics.spec.ts  
**Already covered (26):** `abort_timeout`, `auth_gate`, `auth_headers_in_fetch`, `availability_formula`, `calculate_entry`, `descriptive_functions`, `double_submit_guard`, `duplicate_dict_key`, `error_body_read`, `esc_html_erro`

### Uncovered checks (8)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `edge_hive_id_scoping`
- `edge_new_logbook_fields`
- `edge_phases`
- `module_exists`
- `orchestrator_endpoint`
- `py_smoke_descriptive`
- `py_smoke_diagnostic`
- `py_smoke_prescriptive`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_analytics.py` (target: `analytics.html`) declares 8
rules that have NO Playwright test exercising them:
  - edge_hive_id_scoping
  - edge_new_logbook_fields
  - edge_phases
  - module_exists
  - orchestrator_endpoint
  - py_smoke_descriptive
  - py_smoke_diagnostic
  - py_smoke_prescriptive

Read `analytics.html` for selectors, form IDs, routes.
Match the canonical pattern in `tests/journey-analytics.spec.ts` (imports from './_fixtures' + './_helpers', uses whPage + testMarker).

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #6: `validate_content_quality.py`  -  1 check(s) untested

**Label:** validate_content_quality  
**Likely surface:** hive.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (5):** `embed_content_guard`, `failure_consequence_in_python`, `fault_knowledge_type_filter`, `mtbf_filter_consistency`, `mttr_zero_filter_consistency`

### Uncovered checks (1)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `python_column_safety`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_content_quality.py` (target: `hive.html`) declares 1
rules that have NO Playwright test exercising them:
  - python_column_safety

No journey spec exists for this topic yet. Create `tests/journey-content.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #7: `validate_hive.py`  -  3 check(s) untested

**Label:** validate_hive  
**Likely surface:** hive.html  
**Reference pattern:** journey-hive.spec.ts  
**Already covered (11):** `approval_flow`, `approve_scoped`, `audit_log_power_actions`, `audit_log_refreshed`, `auth_gate`, `channel_cleanup`, `eschtml_render`, `hive_id_scoping`, `realtime_approval_filter`, `realtime_coverage``

### Uncovered checks (3)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `supervisor_gate_approve`
- `supervisor_gate_kick`
- `supervisor_gate_reject`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_hive.py` (target: `hive.html`) declares 3
rules that have NO Playwright test exercising them:
  - supervisor_gate_approve
  - supervisor_gate_kick
  - supervisor_gate_reject

Read `hive.html` for selectors, form IDs, routes.
Match the canonical pattern in `tests/journey-hive.spec.ts` (imports from './_fixtures' + './_helpers', uses whPage + testMarker).

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #8: `validate_hive_quota.py`  -  2 check(s) untested

**Label:** validate_hive_quota  
**Likely surface:** hive.html  
**Reference pattern:** journey-hive.spec.ts  
**Already covered (2):** `table_inventory`, `trigger_coverage`

### Uncovered checks (2)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `adoption_inventory`
- `quota_table`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_hive_quota.py` (target: `hive.html`) declares 2
rules that have NO Playwright test exercising them:
  - adoption_inventory
  - quota_table

Read `hive.html` for selectors, form IDs, routes.
Match the canonical pattern in `tests/journey-hive.spec.ts` (imports from './_fixtures' + './_helpers', uses whPage + testMarker).

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #9: `validate_notifications.py`  -  1 check(s) untested

**Label:** validate_notifications  
**Likely surface:** hive.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (6):** `approval_channel_events`, `build_notifications_init`, `notification_bell`, `pm_alert_completeness`, `stock_alert_completeness`, `worker_approval_toasts`

### Uncovered checks (1)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `module_level_channels`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_notifications.py` (target: `hive.html`) declares 1
rules that have NO Playwright test exercising them:
  - module_level_channels

No journey spec exists for this topic yet. Create `tests/journey-notifications.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #10: `validate_reliability_workbench.py`  -  17 check(s) untested

**Label:** validate_reliability_workbench  
**Likely surface:** asset-hub.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (13):** `asset_hub_pf_ui`, `asset_hub_pm_writeback`, `asset_hub_rcm_modal`, `asset_hub_rcm_realtime`, `asset_hub_rcm_strategy_writes`, `asset_hub_reliability_report_button`, `asset_hub_reliability_report_print`

### Uncovered checks (17)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `canonical_sources_registered`
- `grants_present`
- `hive_membership_join_rls`
- `pf_calculator_edge_fn`
- `python_pf_module`
- `python_weibull_endpoint`
- `python_weibull_module`
- `rcm_fmea_modes_schema`
- `rcm_strategies_schema`
- `realtime_publication`
- `rls_enabled`
- `v_fmea_truth_view`
- `v_pf_truth_view_and_registration`
- `v_rcm_truth_view`
- `v_weibull_truth_view`
- `weibull_fits_schema`
- `weibull_fitter_edge_fn`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_reliability_workbench.py` (target: `asset-hub.html`) declares 17
rules that have NO Playwright test exercising them:
  - canonical_sources_registered
  - grants_present
  - hive_membership_join_rls
  - pf_calculator_edge_fn
  - python_pf_module
  - python_weibull_endpoint
  - python_weibull_module
  - rcm_fmea_modes_schema
  - rcm_strategies_schema
  - realtime_publication
  - rls_enabled
  - v_fmea_truth_view
  - v_pf_truth_view_and_registration
  - v_rcm_truth_view
  - v_weibull_truth_view
  - weibull_fits_schema
  - weibull_fitter_edge_fn

No journey spec exists for this topic yet. Create `tests/journey-reliability.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #11: `validate_renderers.py`  -  3 check(s) untested

**Label:** validate_renderers  
**Likely surface:** engineering-design.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered:** _none_

### Uncovered checks (3)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `calcref_completeness`
- `render_null_guard`
- `renderer_field_contract`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_renderers.py` (target: `engineering-design.html`) declares 3
rules that have NO Playwright test exercising them:
  - calcref_completeness
  - render_null_guard
  - renderer_field_contract

No journey spec exists for this topic yet. Create `tests/journey-renderers.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---


---

## Platform-wide gaps (0)

These validators scan ALL pages (LIVE_PAGES list, glob, etc.). Layer 0
is the right enforcement layer because writing a Playwright scenario per
page would just duplicate the validator with 50x the runtime.


## Infrastructure gaps (55)

These validators have no UI surface - they enforce backend / schema /
edge function / configuration rules. Layer 0 is the right enforcement
layer; no Playwright scenario is needed.

- `validate_auto_discovery.py` (no named checks) - validate_auto_discovery
- `validate_avatar_state_phase10.py` (no named checks) - validate_avatar_state_phase10
- `validate_bundle_bloat.py` (4 checks) - validate_bundle_bloat
- `validate_button_type_in_form.py` (1 checks) - validate_button_type_in_form
- `validate_capability_dedup.py` (3 checks) - validate_capability_dedup
- `validate_cold_start_memoization.py` (4 checks) - validate_cold_start_memoization
- `validate_contact_consistency.py` (3 checks) - validate_contact_consistency
- `validate_cors_wildcard.py` (4 checks) - validate_cors_wildcard
- `validate_cron_functional.py` (4 checks) - validate_cron_functional
- `validate_data_governance.py` (6 checks) - validate_data_governance
- `validate_data_retention.py` (4 checks) - validate_data_retention
- `validate_date_arithmetic.py` (4 checks) - validate_date_arithmetic
- `validate_diagram_inputs.py` (no named checks) - validate_diagram_inputs
- `validate_dialog_flow.py` (no named checks) - validate_dialog_flow
- `validate_digital_twin.py` (6 checks) - validate_digital_twin
- `validate_drop_if_exists.py` (1 checks) - validate_drop_if_exists
- `validate_duplicate_html_id.py` (1 checks) - validate_duplicate_html_id
- `validate_edge_caller_contract.py` (4 checks) - validate_edge_caller_contract
- `validate_edge_config.py` (4 checks) - validate_edge_config
- `validate_em_dash.py` (1 checks) - validate_em_dash
- `validate_embed_integrity.py` (4 checks) - validate_embed_integrity
- `validate_fields.py` (no named checks) - validate_fields
- `validate_fk_on_delete.py` (1 checks) - validate_fk_on_delete
- `validate_ga4_coverage.py` (4 checks) - validate_ga4_coverage
- `validate_gateway_coverage.py` (4 checks) - validate_gateway_coverage
- `validate_hardcoded_secrets.py` (4 checks) - validate_hardcoded_secrets
- `validate_industry_defining.py` (8 checks) - validate_industry_defining.py — Phase 6 of STRATEGIC_ROADMAP.
- `validate_integration.py` (no named checks) - validate_integration
- `validate_iot_protocols.py` (6 checks) - validate_iot_protocols
- `validate_js_syntax_sanity.py` (1 checks) - validate_js_syntax_sanity
- `validate_jsonb_drift.py` (4 checks) - validate_jsonb_drift
- `validate_llms_sync.py` (4 checks) - validate_llms_sync
- `validate_migration_immutability.py` (4 checks) - validate_migration_immutability
- `validate_migration_order.py` (4 checks) - validate_migration_order
- `validate_multilingual_phase11.py` (no named checks) - validate_multilingual_phase11
- `validate_pdf_pipeline.py` (4 checks) - validate_pdf_pipeline
- `validate_pii_egress.py` (4 checks) - validate_pii_egress
- `validate_playwright_coverage.py` (4 checks) - validate_playwright_coverage
- `validate_playwright_smoke.py` (3 checks) - validate_playwright_smoke
- `validate_playwright_staleness.py` (3 checks) - validate_playwright_staleness
- `validate_provider_bypass.py` (4 checks) - validate_provider_bypass
- `validate_reset_coverage.py` (2 checks) - validate_reset_coverage
- `validate_rls_readiness.py` (4 checks) - validate_rls_readiness
- `validate_schema_coverage.py` (no named checks) - validate_schema_coverage
- `validate_seed_consumer_contract.py` (3 checks) - validate_seed_consumer_contract
- `validate_sentinel_baseline.py` (no named checks) - validate_sentinel_baseline.py - forward-only ratchet on sentinel coverage.
- `validate_service_role_exposure.py` (4 checks) - validate_service_role_exposure
- `validate_sitemap_sync.py` (3 checks) - validate_sitemap_sync
- `validate_soft_delete.py` (1 checks) - validate_soft_delete
- `validate_state_machine_integrity.py` (4 checks) - validate_state_machine_integrity
- `validate_supabase_singleton.py` (2 checks) - validate_supabase_singleton
- `validate_tester_coverage.py` (no named checks) - validate_tester_coverage
- `validate_trigger_reentrancy.py` (4 checks) - validate_trigger_reentrancy
- `validate_validator_self_coverage.py` (4 checks) - validate_validator_self_coverage
- `validate_write_path_monitor.py` (4 checks) - validate_write_path_monitor

_Generated 11 per-page proposal bundles. Skipped 0 with no extractable tokens. Tagged 0 platform-wide and 55 infrastructure._