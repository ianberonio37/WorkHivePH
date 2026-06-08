# Sentinel Proposals (v1.4 - check-level)

Generated for 24 uncovered CHECK(s) across 5 per-page validators. Each check is one rule
the platform should obey - and currently no Playwright spec exercises it.

**Check coverage:** 91.4% (255 of 279 per-page checks - HONEST behavioral coverage)
**Topic coverage:** 100.0% (36 of 36 per-page validators - loose, validator-level)
**Raw coverage:** 82.8% (275 of 332 validators)

Each section below groups uncovered checks by validator. Use the per-check
list as your test backlog - one scenario per check, not one scenario per
validator. The check-name itself is the test-name anchor: include it in
the new test() name so the next sentinel run picks up the match.

Platform-wide and Infrastructure gaps are listed at the bottom for
transparency - they don't need Playwright scenarios.

---

## Per-page CHECK-level gaps (the test backlog)

## Validator #1: `validate_ai_seams_inventory.py`  -  1 check(s) untested

**Label:** validate_ai_seams_inventory  
**Likely surface:** inventory.html  
**Reference pattern:** journey-ai.spec.ts  
**Already covered:** _none_

### Uncovered checks (1)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `ai_seams_inventory`

### LLM prompt

```
You are extending Layer 2 of the WorkHive platform.

Validator `validate_ai_seams_inventory.py` (target: `inventory.html`) declares 1
rules that have NO Playwright test exercising them:
  - ai_seams_inventory

Read `inventory.html` for selectors, form IDs, routes.
Match the canonical pattern in `tests/journey-ai.spec.ts` (imports from './_fixtures' + './_helpers', uses whPage + testMarker).

Propose ONE test() block per check above. Each test()'s name MUST
start with the check name (e.g. `test('approval_channel_events: ...', ...)`)
so the next sentinel run automatically marks the check as covered.
```

---

## Validator #2: `validate_hive.py`  -  3 check(s) untested

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

## Validator #3: `validate_notifications.py`  -  1 check(s) untested

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

## Validator #4: `validate_reliability_workbench.py`  -  16 check(s) untested

**Label:** validate_reliability_workbench  
**Likely surface:** asset-hub.html  
**Reference pattern:** _no journey spec for this topic_  
**Already covered (14):** `asset_hub_pf_ui`, `asset_hub_pm_writeback`, `asset_hub_rcm_modal`, `asset_hub_rcm_realtime`, `asset_hub_rcm_strategy_writes`, `asset_hub_reliability_report_button`, `asset_hub_reliability_report_print`

### Uncovered checks (16)

Each line is one rule that needs a Playwright scenario. The check name
(in backticks) MUST appear in the test() name so the next sentinel run
matches the new scenario to the rule.

- `canonical_sources_registered`
- `grants_present`
- `hive_membership_join_rls`
- `pf_calculator_edge_fn`
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

Validator `validate_reliability_workbench.py` (target: `asset-hub.html`) declares 16
rules that have NO Playwright test exercising them:
  - canonical_sources_registered
  - grants_present
  - hive_membership_join_rls
  - pf_calculator_edge_fn
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

## Validator #5: `validate_renderers.py`  -  3 check(s) untested

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


## Infrastructure gaps (57)

These validators have no UI surface - they enforce backend / schema /
edge function / configuration rules. Layer 0 is the right enforcement
layer; no Playwright scenario is needed.

- `validate_auto_discovery.py` (no named checks) - validate_auto_discovery
- `validate_avatar_state_phase10.py` (no named checks) - validate_avatar_state_phase10
- `validate_bundle_bloat.py` (4 checks) - validate_bundle_bloat
- `validate_button_type_in_form.py` (1 checks) - validate_button_type_in_form
- `validate_c_track_self_coverage.py` (1 checks) - validate_c_track_self_coverage
- `validate_clone_debt.py` (no named checks) - validate_clone_debt
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
- `validate_em_dash.py` (1 checks) - validate_em_dash
- `validate_fields.py` (no named checks) - validate_fields
- `validate_fk_on_delete.py` (1 checks) - validate_fk_on_delete
- `validate_followup_queue_wiring.py` (7 checks) - validate_followup_queue_wiring
- `validate_ga4_coverage.py` (4 checks) - validate_ga4_coverage
- `validate_gateway_coverage.py` (4 checks) - validate_gateway_coverage
- `validate_industry_defining.py` (8 checks) - validate_industry_defining.py — Phase 6 of STRATEGIC_ROADMAP.
- `validate_integration.py` (no named checks) - validate_integration
- `validate_iot_protocols.py` (6 checks) - validate_iot_protocols
- `validate_js_syntax_sanity.py` (1 checks) - validate_js_syntax_sanity
- `validate_jsonb_drift.py` (4 checks) - validate_jsonb_drift
- `validate_llm_cache_adoption.py` (1 checks) - validate_llm_cache_adoption
- `validate_llms_sync.py` (4 checks) - validate_llms_sync
- `validate_meta_gate.py` (1 checks) - validate_meta_gate
- `validate_migration_immutability.py` (4 checks) - validate_migration_immutability
- `validate_migration_immutability_strict.py` (1 checks) - validate_migration_immutability_strict
- `validate_multilingual_phase11.py` (no named checks) - validate_multilingual_phase11
- `validate_pdf_pipeline.py` (4 checks) - validate_pdf_pipeline
- `validate_pii_egress.py` (4 checks) - validate_pii_egress
- `validate_playwright_coverage.py` (4 checks) - validate_playwright_coverage
- `validate_playwright_staleness.py` (3 checks) - validate_playwright_staleness
- `validate_prod_path_leak.py` (no named checks) - validate_prod_path_leak
- `validate_render_budget.py` (1 checks) - validate_render_budget
- `validate_reproducible_build_pin.py` (1 checks) - validate_reproducible_build_pin
- `validate_reset_coverage.py` (2 checks) - validate_reset_coverage
- `validate_rls_strict.py` (1 checks) - validate_rls_strict
- `validate_schema_coverage.py` (no named checks) - validate_schema_coverage
- `validate_seed_consumer_contract.py` (3 checks) - validate_seed_consumer_contract
- `validate_sentinel_baseline.py` (no named checks) - validate_sentinel_baseline.py - forward-only ratchet on sentinel coverage.
- `validate_sitemap_sync.py` (3 checks) - validate_sitemap_sync
- `validate_soft_delete.py` (1 checks) - validate_soft_delete
- `validate_status_enum_drift.py` (no named checks) - validate_status_enum_drift
- `validate_supabase_object_existence.py` (1 checks) - validate_supabase_object_existence
- `validate_supabase_singleton.py` (2 checks) - validate_supabase_singleton
- `validate_tester_coverage.py` (no named checks) - validate_tester_coverage
- `validate_trigger_reentrancy.py` (4 checks) - validate_trigger_reentrancy
- `validate_validator_freshness.py` (2 checks) - validate_validator_freshness
- `validate_validator_self_coverage.py` (4 checks) - validate_validator_self_coverage
- `validate_verified_state_wiring.py` (1 checks) - validate_verified_state_wiring

_Generated 5 per-page proposal bundles. Skipped 0 with no extractable tokens. Tagged 0 platform-wide and 57 infrastructure._