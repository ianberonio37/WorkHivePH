# Edge-Function Pattern Mining Report

- Functions scanned: **61**
- Features extracted: **35**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **7**

## Promotion candidates (sweet spot)

These are emergent patterns ready to graduate into Layer 0 validators.
Review each: write a real validator from the outlier list, or allowlist them.

| Feature | Type | Conformance | Outliers (divergent fns) |
|---|---|---:|---|
| `imports_supabase_esm` | convention (stays TRUE) | 98% | gcash-receipt-ocr |
| `handles_options` | convention (stays TRUE) | 98% | visual-defect-capture |
| `uses_get_cors_headers` | convention (stays TRUE) | 98% | visual-defect-capture |
| `reads_supabase_url_env` | convention (stays TRUE) | 98% | gcash-receipt-ocr |
| `reads_service_role_env` | convention (stays TRUE) | 98% | gcash-receipt-ocr |
| `uses_error_envelope` | convention (stays TRUE) | 93% | gcash-receipt-inbound, gcash-receipt-ocr, notify-push, resend-webhook-receiver |
| `sets_content_type_json` | convention (stays TRUE) | 93% | gcash-receipt-inbound, gcash-receipt-ocr, notify-push, resend-webhook-receiver |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_cors_shared` | 100% | 61 / 61 |
| `has_try_catch` | 100% | 61 / 61 |
| `imports_supabase_esm` | 98% | 60 / 61 |
| `handles_options` | 98% | 60 / 61 |
| `uses_get_cors_headers` | 98% | 60 / 61 |
| `reads_supabase_url_env` | 98% | 60 / 61 |
| `reads_service_role_env` | 98% | 60 / 61 |
| `uses_error_envelope` | 93% | 57 / 61 |
| `sets_content_type_json` | 93% | 57 / 61 |
| `ends_with_serve_close` | 82% | 50 / 61 |
| `responses_spread_cors_headers` | 73% | 45 / 61 |
| `imports_rate_limit` | 72% | 44 / 61 |
| `memoizes_supabase_client` | 68% | 42 / 61 |
| `has_jsdoc_header` | 62% | 38 / 61 |
| `returns_400_on_bad_input` | 62% | 38 / 61 |
| `uses_wh_env_prefix` | 59% | 36 / 61 |
| `imports_ai_chain` | 44% | 27 / 61 |
| `has_skills_consulted` | 44% | 27 / 61 |
| `calls_callai` | 42% | 26 / 61 |
| `imports_cost_log` | 39% | 24 / 61 |
| `rejects_wrong_method` | 39% | 24 / 61 |
| `has_capability_tag` | 31% | 19 / 61 |
| `uses_abortsignal_timeout` | 23% | 14 / 61 |
| `binds_jwt_identity` | 21% | 13 / 61 |
| `imports_redact_pii` | 9% | 6 / 61 |
| `imports_memory` | 9% | 6 / 61 |
| `logs_with_fn_name_prefix` | 9% | 6 / 61 |
| `has_any_console_error` | 4% | 3 / 61 |
| `imports_validate_contract` | 3% | 2 / 61 |
| `uses_abort_controller` | 1% | 1 / 61 |
| `imports_serve_std` | 0% | 0 / 61 |
| `wraps_in_serve` | 0% | 0 / 61 |
| `cors_headers_first_in_handler` | 0% | 0 / 61 |
| `wraps_handler_in_try` | 0% | 0 / 61 |
| `createclient_in_handler` | 0% | 0 / 61 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
