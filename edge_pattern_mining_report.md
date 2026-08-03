# Edge-Function Pattern Mining Report

- Functions scanned: **60**
- Features extracted: **35**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **8**

## Promotion candidates (sweet spot)

These are emergent patterns ready to graduate into Layer 0 validators.
Review each: write a real validator from the outlier list, or allowlist them.

| Feature | Type | Conformance | Outliers (divergent fns) |
|---|---|---:|---|
| `imports_supabase_esm` | convention (stays TRUE) | 98% | gcash-receipt-ocr |
| `handles_options` | convention (stays TRUE) | 98% | visual-defect-capture |
| `sets_content_type_json` | convention (stays TRUE) | 98% | notify-push |
| `reads_supabase_url_env` | convention (stays TRUE) | 98% | gcash-receipt-ocr |
| `reads_service_role_env` | convention (stays TRUE) | 98% | gcash-receipt-ocr |
| `imports_cors_shared` | convention (stays TRUE) | 96% | gcash-receipt-inbound, gcash-receipt-ocr |
| `uses_get_cors_headers` | convention (stays TRUE) | 95% | gcash-receipt-inbound, gcash-receipt-ocr, visual-defect-capture |
| `uses_error_envelope` | convention (stays TRUE) | 95% | gcash-receipt-inbound, gcash-receipt-ocr, notify-push |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `has_try_catch` | 100% | 60 / 60 |
| `imports_supabase_esm` | 98% | 59 / 60 |
| `handles_options` | 98% | 59 / 60 |
| `sets_content_type_json` | 98% | 59 / 60 |
| `reads_supabase_url_env` | 98% | 59 / 60 |
| `reads_service_role_env` | 98% | 59 / 60 |
| `imports_cors_shared` | 96% | 58 / 60 |
| `uses_get_cors_headers` | 95% | 57 / 60 |
| `uses_error_envelope` | 95% | 57 / 60 |
| `ends_with_serve_close` | 81% | 49 / 60 |
| `imports_rate_limit` | 73% | 44 / 60 |
| `responses_spread_cors_headers` | 73% | 44 / 60 |
| `memoizes_supabase_client` | 70% | 42 / 60 |
| `has_jsdoc_header` | 61% | 37 / 60 |
| `returns_400_on_bad_input` | 61% | 37 / 60 |
| `uses_wh_env_prefix` | 60% | 36 / 60 |
| `imports_ai_chain` | 45% | 27 / 60 |
| `has_skills_consulted` | 45% | 27 / 60 |
| `calls_callai` | 43% | 26 / 60 |
| `imports_cost_log` | 40% | 24 / 60 |
| `rejects_wrong_method` | 40% | 24 / 60 |
| `has_capability_tag` | 31% | 19 / 60 |
| `uses_abortsignal_timeout` | 23% | 14 / 60 |
| `binds_jwt_identity` | 21% | 13 / 60 |
| `imports_redact_pii` | 10% | 6 / 60 |
| `imports_memory` | 10% | 6 / 60 |
| `logs_with_fn_name_prefix` | 10% | 6 / 60 |
| `has_any_console_error` | 5% | 3 / 60 |
| `imports_validate_contract` | 3% | 2 / 60 |
| `uses_abort_controller` | 1% | 1 / 60 |
| `imports_serve_std` | 0% | 0 / 60 |
| `wraps_in_serve` | 0% | 0 / 60 |
| `cors_headers_first_in_handler` | 0% | 0 / 60 |
| `wraps_handler_in_try` | 0% | 0 / 60 |
| `createclient_in_handler` | 0% | 0 / 60 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
