# Edge-Function Pattern Mining Report

- Functions scanned: **57**
- Features extracted: **35**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **2**

## Promotion candidates (sweet spot)

These are emergent patterns ready to graduate into Layer 0 validators.
Review each: write a real validator from the outlier list, or allowlist them.

| Feature | Type | Conformance | Outliers (divergent fns) |
|---|---|---:|---|
| `handles_options` | convention (stays TRUE) | 98% | visual-defect-capture |
| `uses_get_cors_headers` | convention (stays TRUE) | 98% | visual-defect-capture |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_cors_shared` | 100% | 57 / 57 |
| `imports_supabase_esm` | 100% | 57 / 57 |
| `uses_error_envelope` | 100% | 57 / 57 |
| `sets_content_type_json` | 100% | 57 / 57 |
| `has_try_catch` | 100% | 57 / 57 |
| `reads_supabase_url_env` | 100% | 57 / 57 |
| `reads_service_role_env` | 100% | 57 / 57 |
| `handles_options` | 98% | 56 / 57 |
| `uses_get_cors_headers` | 98% | 56 / 57 |
| `ends_with_serve_close` | 80% | 46 / 57 |
| `imports_rate_limit` | 77% | 44 / 57 |
| `responses_spread_cors_headers` | 77% | 44 / 57 |
| `memoizes_supabase_client` | 71% | 41 / 57 |
| `has_jsdoc_header` | 64% | 37 / 57 |
| `uses_wh_env_prefix` | 63% | 36 / 57 |
| `returns_400_on_bad_input` | 59% | 34 / 57 |
| `imports_ai_chain` | 47% | 27 / 57 |
| `calls_callai` | 45% | 26 / 57 |
| `has_skills_consulted` | 45% | 26 / 57 |
| `imports_cost_log` | 42% | 24 / 57 |
| `rejects_wrong_method` | 36% | 21 / 57 |
| `has_capability_tag` | 28% | 16 / 57 |
| `uses_abortsignal_timeout` | 24% | 14 / 57 |
| `binds_jwt_identity` | 22% | 13 / 57 |
| `imports_redact_pii` | 10% | 6 / 57 |
| `imports_memory` | 10% | 6 / 57 |
| `logs_with_fn_name_prefix` | 10% | 6 / 57 |
| `has_any_console_error` | 5% | 3 / 57 |
| `imports_validate_contract` | 3% | 2 / 57 |
| `uses_abort_controller` | 1% | 1 / 57 |
| `imports_serve_std` | 0% | 0 / 57 |
| `wraps_in_serve` | 0% | 0 / 57 |
| `cors_headers_first_in_handler` | 0% | 0 / 57 |
| `wraps_handler_in_try` | 0% | 0 / 57 |
| `createclient_in_handler` | 0% | 0 / 57 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
