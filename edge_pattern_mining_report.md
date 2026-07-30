# Edge-Function Pattern Mining Report

- Functions scanned: **58**
- Features extracted: **35**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **4**

## Promotion candidates (sweet spot)

These are emergent patterns ready to graduate into Layer 0 validators.
Review each: write a real validator from the outlier list, or allowlist them.

| Feature | Type | Conformance | Outliers (divergent fns) |
|---|---|---:|---|
| `handles_options` | convention (stays TRUE) | 98% | visual-defect-capture |
| `uses_get_cors_headers` | convention (stays TRUE) | 98% | visual-defect-capture |
| `uses_error_envelope` | convention (stays TRUE) | 98% | notify-push |
| `sets_content_type_json` | convention (stays TRUE) | 98% | notify-push |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_cors_shared` | 100% | 58 / 58 |
| `imports_supabase_esm` | 100% | 58 / 58 |
| `has_try_catch` | 100% | 58 / 58 |
| `reads_supabase_url_env` | 100% | 58 / 58 |
| `reads_service_role_env` | 100% | 58 / 58 |
| `handles_options` | 98% | 57 / 58 |
| `uses_get_cors_headers` | 98% | 57 / 58 |
| `uses_error_envelope` | 98% | 57 / 58 |
| `sets_content_type_json` | 98% | 57 / 58 |
| `ends_with_serve_close` | 81% | 47 / 58 |
| `imports_rate_limit` | 75% | 44 / 58 |
| `responses_spread_cors_headers` | 75% | 44 / 58 |
| `memoizes_supabase_client` | 72% | 42 / 58 |
| `has_jsdoc_header` | 63% | 37 / 58 |
| `uses_wh_env_prefix` | 62% | 36 / 58 |
| `returns_400_on_bad_input` | 60% | 35 / 58 |
| `imports_ai_chain` | 46% | 27 / 58 |
| `has_skills_consulted` | 46% | 27 / 58 |
| `calls_callai` | 44% | 26 / 58 |
| `imports_cost_log` | 41% | 24 / 58 |
| `rejects_wrong_method` | 37% | 22 / 58 |
| `has_capability_tag` | 29% | 17 / 58 |
| `uses_abortsignal_timeout` | 24% | 14 / 58 |
| `binds_jwt_identity` | 22% | 13 / 58 |
| `imports_redact_pii` | 10% | 6 / 58 |
| `imports_memory` | 10% | 6 / 58 |
| `logs_with_fn_name_prefix` | 10% | 6 / 58 |
| `has_any_console_error` | 5% | 3 / 58 |
| `imports_validate_contract` | 3% | 2 / 58 |
| `uses_abort_controller` | 1% | 1 / 58 |
| `imports_serve_std` | 0% | 0 / 58 |
| `wraps_in_serve` | 0% | 0 / 58 |
| `cors_headers_first_in_handler` | 0% | 0 / 58 |
| `wraps_handler_in_try` | 0% | 0 / 58 |
| `createclient_in_handler` | 0% | 0 / 58 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
