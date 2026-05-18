# Sentinel Proposals (v1.4 - check-level)

Generated for 42 uncovered CHECK(s) across 13 per-page validators. Each check is one rule
the platform should obey - and currently no Playwright spec exercises it.

**Check coverage:** 83.0% (210 of 253 per-page checks - HONEST behavioral coverage)
**Topic coverage:** 82.9% (29 of 35 per-page validators - loose, validator-level)
**Raw coverage:** 49.7% (93 of 187 validators)

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

## Validator #2: `validate_ai_regression.py`  -  1 check(s) untested

**Label:** validate_ai_regression  
**Likely surface:** analytics.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (3):** `calc_count_consistent`, `discipline_names`, `tool_consistency`

### Uncovered checks (1)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `draft_artifacts`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_ai_regression.py` (target: `analytics.html`) declares 1
rules that have NO Playwright test exercising them:
  - draft_artifacts

No journey spec exists for this topic yet. Create `tests/journey-ai.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #3: `validate_analytics.py`  -  5 check(s) untested

**Label:** validate_analytics  
**Likely surface:** analytics.html  
**Reference pattern:** journey-analytics.spec.ts  
**Already covered (25):** `abort_timeout`, `auth_gate`, `auth_headers_in_fetch`, `availability_formula`, `calculate_entry`, `descriptive_functions`, `double_submit_guard`, `duplicate_dict_key`, `error_body_read`, `esc_html_erro`

### Uncovered checks (5)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `edge_hive_id_scoping`
- `edge_new_logbook_fields`
- `edge_phases`
- `module_exists`
- `orchestrator_endpoint`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_analytics.py` (target: `analytics.html`) declares 5
rules that have NO Playwright test exercising them:
  - edge_hive_id_scoping
  - edge_new_logbook_fields
  - edge_phases
  - module_exists
  - orchestrator_endpoint

Read `analytics.html` for selectors, form IDs, routes.
Match the canonical pattern in `tests/journey-analytics.spec.ts` (imports from './_fixtures' + './_helpers', uses whPage + testMarker).

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #4: `validate_contact_consistency.py`  -  3 check(s) untested

**Label:** validate_contact_consistency  
**Likely surface:** index.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered:** _none_

### Uncovered checks (3)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `canonical_present`
- `no_hello`
- `no_personal`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_contact_consistency.py` (target: `index.html`) declares 3
rules that have NO Playwright test exercising them:
  - canonical_present
  - no_hello
  - no_personal

No journey spec exists for this topic yet. Create `tests/journey-contact.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #5: `validate_content_quality.py`  -  1 check(s) untested

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

## Validator #6: `validate_em_dash.py`  -  1 check(s) untested

**Label:** validate_em_dash  
**Likely surface:** index.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered:** _none_

### Uncovered checks (1)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `em_dashes`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_em_dash.py` (target: `index.html`) declares 1
rules that have NO Playwright test exercising them:
  - em_dashes

No journey spec exists for this topic yet. Create `tests/journey-dash.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #7: `validate_ga4_coverage.py`  -  4 check(s) untested

**Label:** validate_ga4_coverage  
**Likely surface:** index.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered:** _none_

### Uncovered checks (4)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `block_present`
- `canonical_id`
- `wh_ga4_file`
- `wh_ga4_loaded`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_ga4_coverage.py` (target: `index.html`) declares 4
rules that have NO Playwright test exercising them:
  - block_present
  - canonical_id
  - wh_ga4_file
  - wh_ga4_loaded

No journey spec exists for this topic yet. Create `tests/journey-ga4.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #8: `validate_hive.py`  -  1 check(s) untested

**Label:** validate_hive  
**Likely surface:** hive.html  
**Reference pattern:** journey-hive.spec.ts  
**Already covered (10):** `approval_flow`, `approve_scoped`, `audit_log_power_actions`, `audit_log_refreshed`, `auth_gate`, `eschtml_render`, `hive_id_scoping`, `realtime_approval_filter`, `realtime_coverage`, `reject_scoped`

### Uncovered checks (1)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `channel_cleanup`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_hive.py` (target: `hive.html`) declares 1
rules that have NO Playwright test exercising them:
  - channel_cleanup

Read `hive.html` for selectors, form IDs, routes.
Match the canonical pattern in `tests/journey-hive.spec.ts` (imports from './_fixtures' + './_helpers', uses whPage + testMarker).

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #9: `validate_hive_quota.py`  -  2 check(s) untested

**Label:** validate_hive_quota  
**Likely surface:** hive.html  
**Reference pattern:** journey-hive.spec.ts  
**Already covered:** _none_

### Uncovered checks (2)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `quota_table`
- `trigger_coverage`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_hive_quota.py` (target: `hive.html`) declares 2
rules that have NO Playwright test exercising them:
  - quota_table
  - trigger_coverage

Read `hive.html` for selectors, form IDs, routes.
Match the canonical pattern in `tests/journey-hive.spec.ts` (imports from './_fixtures' + './_helpers', uses whPage + testMarker).

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #10: `validate_llms_sync.py`  -  4 check(s) untested

**Label:** validate_llms_sync  
**Likely surface:** index.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered:** _none_

### Uncovered checks (4)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `articles_present`
- `contact_present`
- `no_stale_slugs`
- `required_sections`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_llms_sync.py` (target: `index.html`) declares 4
rules that have NO Playwright test exercising them:
  - articles_present
  - contact_present
  - no_stale_slugs
  - required_sections

No journey spec exists for this topic yet. Create `tests/journey-llms.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #11: `validate_notifications.py`  -  1 check(s) untested

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

## Validator #12: `validate_reliability_workbench.py`  -  15 check(s) untested

**Label:** validate_reliability_workbench  
**Likely surface:** asset-hub.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (12):** `asset_hub_pf_ui`, `asset_hub_pm_writeback`, `asset_hub_rcm_modal`, `asset_hub_rcm_realtime`, `asset_hub_rcm_strategy_writes`, `asset_hub_reliability_report_button`, `asset_hub_reliability_report_print`

### Uncovered checks (15)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `canonical_sources_registered`
- `grants_present`
- `hive_membership_join_rls`
- `pf_calculator_edge_fn`
- `pf_intervals_schema`
- `python_pf_module`
- `python_weibull_endpoint`
- `python_weibull_module`
- `rcm_fmea_modes_schema`
- `rcm_strategies_schema`
- `realtime_publication`
- `rls_enabled`
- `v_pf_truth_view_and_registration`
- `weibull_fits_schema`
- `weibull_fitter_edge_fn`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_reliability_workbench.py` (target: `asset-hub.html`) declares 15
rules that have NO Playwright test exercising them:
  - canonical_sources_registered
  - grants_present
  - hive_membership_join_rls
  - pf_calculator_edge_fn
  - pf_intervals_schema
  - python_pf_module
  - python_weibull_endpoint
  - python_weibull_module
  - rcm_fmea_modes_schema
  - rcm_strategies_schema
  - realtime_publication
  - rls_enabled
  - v_pf_truth_view_and_registration
  - weibull_fits_schema
  - weibull_fitter_edge_fn

No journey spec exists for this topic yet. Create `tests/journey-reliability.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #13: `validate_sitemap_sync.py`  -  3 check(s) untested

**Label:** validate_sitemap_sync  
**Likely surface:** index.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered:** _none_

### Uncovered checks (3)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `expected_urls_present`
- `loc_resolves`
- `metadata_complete`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_sitemap_sync.py` (target: `index.html`) declares 3
rules that have NO Playwright test exercising them:
  - expected_urls_present
  - loc_resolves
  - metadata_complete

No journey spec exists for this topic yet. Create `tests/journey-sitemap.spec.ts` following the canonical pattern.

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---


---

## Platform-wide gaps (10)

These validators scan ALL pages (LIVE_PAGES list, glob, etc.). Layer 0
is the right enforcement layer because writing a Playwright scenario per
page would just duplicate the validator with 50x the runtime.

- `validate_home_stack_coverage.py` (2 checks) - validate_home_stack_coverage
- `validate_loading_state.py` (2 checks) - validate_loading_state
- `validate_ml.py` (12 checks) - validate_ml
- `validate_mobile.py` (11 checks) - validate_mobile
- `validate_nav_registry.py` (8 checks) - validate_nav_registry
- `validate_observability.py` (8 checks) - validate_observability
- `validate_optimistic_reconciliation.py` (2 checks) - validate_optimistic_reconciliation
- `validate_performance.py` (8 checks) - validate_performance
- `validate_seo.py` (6 checks) - validate_seo
- `validate_sw_offline.py` (2 checks) - validate_sw_offline

## Infrastructure gaps (78)

These validators have no UI surface - they enforce backend / schema /
edge function / configuration rules. Layer 0 is the right enforcement
layer; no Playwright scenario is needed.

- `validate_adoption_observability.py` (15 checks) - validate_adoption_observability.py — Phase 3.6 of STRATEGIC_ROADMAP.
- `validate_agent_handoff_contract.py` (3 checks) - validate_agent_handoff_contract
- `validate_auto_discovery.py` (no named checks) - validate_auto_discovery
- `validate_avatar_state_phase10.py` (no named checks) - validate_avatar_state_phase10
- `validate_bundle_bloat.py` (2 checks) - validate_bundle_bloat
- `validate_cache_invalidation.py` (2 checks) - validate_cache_invalidation
- `validate_canonical_anchor.py` (no named checks) - validate_canonical_anchor
- `validate_capability_dedup.py` (3 checks) - validate_capability_dedup
- `validate_cascade_behavior.py` (2 checks) - validate_cascade_behavior
- `validate_cmms_contracts.py` (1 checks) - validate_cmms_contracts
- `validate_cmms_reconciliation.py` (3 checks) - validate_cmms_reconciliation
- `validate_cold_start_memoization.py` (2 checks) - validate_cold_start_memoization
- `validate_cors_wildcard.py` (2 checks) - validate_cors_wildcard
- `validate_cron_functional.py` (2 checks) - validate_cron_functional
- `validate_cron_schedule_integrity.py` (4 checks) - validate_cron_schedule_integrity
- `validate_data_governance.py` (6 checks) - validate_data_governance
- `validate_data_retention.py` (2 checks) - validate_data_retention
- `validate_date_arithmetic.py` (2 checks) - validate_date_arithmetic
- `validate_diagram_inputs.py` (no named checks) - validate_diagram_inputs
- `validate_dialog_flow.py` (no named checks) - validate_dialog_flow
- `validate_digital_twin.py` (6 checks) - validate_digital_twin
- `validate_edge_caller_contract.py` (4 checks) - validate_edge_caller_contract
- `validate_edge_config.py` (4 checks) - validate_edge_config
- `validate_edge_contracts.py` (6 checks) - validate_edge_contracts
- `validate_edge_response_contract.py` (3 checks) - validate_edge_response_contract
- `validate_embed_integrity.py` (3 checks) - validate_embed_integrity
- `validate_embedding_coverage.py` (2 checks) - validate_embedding_coverage
- `validate_env_secret_coverage.py` (4 checks) - validate_env_secret_coverage
- `validate_fields.py` (no named checks) - validate_fields
- `validate_formula_invocation.py` (2 checks) - validate_formula_invocation
- `validate_function_security.py` (2 checks) - validate_function_security
- `validate_gateway_coverage.py` (3 checks) - validate_gateway_coverage
- `validate_hardcoded_secrets.py` (2 checks) - validate_hardcoded_secrets
- `validate_html_id_unique.py` (2 checks) - validate_html_id_unique
- `validate_idempotency.py` (14 checks) - validate_idempotency
- `validate_industry_defining.py` (8 checks) - validate_industry_defining.py — Phase 6 of STRATEGIC_ROADMAP.
- `validate_integration.py` (no named checks) - validate_integration
- `validate_iot_protocols.py` (6 checks) - validate_iot_protocols
- `validate_js_syntax_sanity.py` (1 checks) - validate_js_syntax_sanity
- `validate_jsonb_drift.py` (2 checks) - validate_jsonb_drift
- `validate_memory_integrity.py` (no named checks) - validate_memory_integrity
- `validate_migration_immutability.py` (3 checks) - validate_migration_immutability
- `validate_migration_order.py` (3 checks) - validate_migration_order
- `validate_module_scope_state.py` (1 checks) - validate_module_scope_state
- `validate_multilingual_phase11.py` (no named checks) - validate_multilingual_phase11
- `validate_offline_resilience_phase6.py` (no named checks) - validate_offline_resilience_phase6
- `validate_pdf_pipeline.py` (3 checks) - validate_pdf_pipeline
- `validate_persona_contract.py` (7 checks) - validate_persona_contract
- `validate_pii_egress.py` (2 checks) - validate_pii_egress
- `validate_playwright_coverage.py` (4 checks) - validate_playwright_coverage
- `validate_playwright_smoke.py` (3 checks) - validate_playwright_smoke
- `validate_playwright_staleness.py` (no named checks) - validate_playwright_staleness
- `validate_provider_bypass.py` (3 checks) - validate_provider_bypass
- `validate_rag_completeness.py` (3 checks) - validate_rag_completeness
- `validate_rag_integrity.py` (no named checks) - validate_rag_integrity
- `validate_realtime_cleanup.py` (3 checks) - validate_realtime_cleanup
- `validate_realtime_payload_contract.py` (4 checks) - validate_realtime_payload_contract
- `validate_realtime_publication.py` (1 checks) - validate_realtime_publication
- `validate_reset_coverage.py` (2 checks) - validate_reset_coverage
- `validate_rls_readiness.py` (4 checks) - validate_rls_readiness
- `validate_schema.py` (8 checks) - validate_schema
- `validate_schema_coverage.py` (no named checks) - validate_schema_coverage
- `validate_schema_drift.py` (1 checks) - validate_schema_drift
- `validate_schema_phantom.py` (3 checks) - validate_schema_phantom
- `validate_seed_consumer_contract.py` (3 checks) - validate_seed_consumer_contract
- `validate_sentinel_baseline.py` (no named checks) - validate_sentinel_baseline.py - forward-only ratchet on sentinel coverage.
- `validate_service_role_exposure.py` (3 checks) - validate_service_role_exposure
- `validate_silo_monitor.py` (4 checks) - validate_silo_monitor
- `validate_soft_delete.py` (1 checks) - validate_soft_delete
- `validate_state_machine_integrity.py` (3 checks) - validate_state_machine_integrity
- `validate_supabase_singleton.py` (2 checks) - validate_supabase_singleton
- `validate_team_coordination.py` (no named checks) - validate_team_coordination
- `validate_tester_coverage.py` (no named checks) - validate_tester_coverage
- `validate_timers.py` (7 checks) - validate_timers
- `validate_tool_aligned_cta.py` (3 checks) - validate_tool_aligned_cta
- `validate_trigger_reentrancy.py` (2 checks) - validate_trigger_reentrancy
- `validate_validator_self_coverage.py` (3 checks) - validate_validator_self_coverage
- `validate_write_path_monitor.py` (4 checks) - validate_write_path_monitor

_Generated 13 per-page proposal bundles. Skipped 0 with no extractable tokens. Tagged 10 platform-wide and 78 infrastructure._