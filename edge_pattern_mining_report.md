# Edge-Function Pattern Mining Report

- Functions scanned: **59**
- Features extracted: **35**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **6**

## Promotion candidates (sweet spot)

These are emergent patterns ready to graduate into Layer 0 validators.
Review each: write a real validator from the outlier list, or allowlist them.

| Feature | Type | Conformance | Outliers (divergent fns) |
|---|---|---:|---|
| `imports_cors_shared` | convention (stays TRUE) | 98% | gcash-receipt-inbound |
| `handles_options` | convention (stays TRUE) | 98% | visual-defect-capture |
| `uses_error_envelope` | convention (stays TRUE) | 98% | notify-push |
| `sets_content_type_json` | convention (stays TRUE) | 98% | notify-push |
| `createclient_in_handler` | anti-pattern (stays FALSE) | 98% | gcash-receipt-inbound |
| `uses_get_cors_headers` | convention (stays TRUE) | 96% | gcash-receipt-inbound, visual-defect-capture |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_supabase_esm` | 100% | 59 / 59 |
| `has_try_catch` | 100% | 59 / 59 |
| `reads_supabase_url_env` | 100% | 59 / 59 |
| `reads_service_role_env` | 100% | 59 / 59 |
| `imports_cors_shared` | 98% | 58 / 59 |
| `handles_options` | 98% | 58 / 59 |
| `uses_error_envelope` | 98% | 58 / 59 |
| `sets_content_type_json` | 98% | 58 / 59 |
| `uses_get_cors_headers` | 96% | 57 / 59 |
| `ends_with_serve_close` | 81% | 48 / 59 |
| `imports_rate_limit` | 74% | 44 / 59 |
| `responses_spread_cors_headers` | 74% | 44 / 59 |
| `memoizes_supabase_client` | 71% | 42 / 59 |
| `has_jsdoc_header` | 62% | 37 / 59 |
| `uses_wh_env_prefix` | 61% | 36 / 59 |
| `returns_400_on_bad_input` | 59% | 35 / 59 |
| `imports_ai_chain` | 45% | 27 / 59 |
| `has_skills_consulted` | 45% | 27 / 59 |
| `calls_callai` | 44% | 26 / 59 |
| `imports_cost_log` | 40% | 24 / 59 |
| `rejects_wrong_method` | 39% | 23 / 59 |
| `has_capability_tag` | 30% | 18 / 59 |
| `uses_abortsignal_timeout` | 23% | 14 / 59 |
| `binds_jwt_identity` | 22% | 13 / 59 |
| `imports_redact_pii` | 10% | 6 / 59 |
| `imports_memory` | 10% | 6 / 59 |
| `logs_with_fn_name_prefix` | 10% | 6 / 59 |
| `has_any_console_error` | 5% | 3 / 59 |
| `imports_validate_contract` | 3% | 2 / 59 |
| `wraps_in_serve` | 1% | 1 / 59 |
| `createclient_in_handler` | 1% | 1 / 59 |
| `uses_abort_controller` | 1% | 1 / 59 |
| `imports_serve_std` | 0% | 0 / 59 |
| `cors_headers_first_in_handler` | 0% | 0 / 59 |
| `wraps_handler_in_try` | 0% | 0 / 59 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
