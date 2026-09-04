# Edge-Function Pattern Mining Report

- Functions scanned: **62**
- Features extracted: **35**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **8**

## Promotion candidates (sweet spot)

These are emergent patterns ready to graduate into Layer 0 validators.
Review each: write a real validator from the outlier list, or allowlist them.

| Feature | Type | Conformance | Outliers (divergent fns) |
|---|---|---:|---|
| `imports_supabase_esm` | convention (stays TRUE) | 98% | gcash-receipt-ocr |
| `handles_options` | convention (stays TRUE) | 98% | vehicle-doc-extract |
| `uses_get_cors_headers` | convention (stays TRUE) | 98% | vehicle-doc-extract |
| `has_try_catch` | convention (stays TRUE) | 98% | vehicle-doc-extract |
| `reads_supabase_url_env` | convention (stays TRUE) | 96% | gcash-receipt-ocr, vehicle-doc-extract |
| `reads_service_role_env` | convention (stays TRUE) | 96% | gcash-receipt-ocr, vehicle-doc-extract |
| `uses_error_envelope` | convention (stays TRUE) | 93% | gcash-receipt-inbound, gcash-receipt-ocr, notify-push, vehicle-doc-extract |
| `sets_content_type_json` | convention (stays TRUE) | 91% | gcash-receipt-inbound, gcash-receipt-ocr, notify-push, resend-webhook-receiver, vehicle-doc-extract |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_cors_shared` | 100% | 62 / 62 |
| `imports_supabase_esm` | 98% | 61 / 62 |
| `handles_options` | 98% | 61 / 62 |
| `uses_get_cors_headers` | 98% | 61 / 62 |
| `has_try_catch` | 98% | 61 / 62 |
| `reads_supabase_url_env` | 96% | 60 / 62 |
| `reads_service_role_env` | 96% | 60 / 62 |
| `uses_error_envelope` | 93% | 58 / 62 |
| `sets_content_type_json` | 91% | 57 / 62 |
| `ends_with_serve_close` | 82% | 51 / 62 |
| `imports_rate_limit` | 72% | 45 / 62 |
| `responses_spread_cors_headers` | 72% | 45 / 62 |
| `memoizes_supabase_client` | 67% | 42 / 62 |
| `has_jsdoc_header` | 62% | 39 / 62 |
| `returns_400_on_bad_input` | 62% | 39 / 62 |
| `uses_wh_env_prefix` | 58% | 36 / 62 |
| `imports_ai_chain` | 45% | 28 / 62 |
| `has_skills_consulted` | 43% | 27 / 62 |
| `calls_callai` | 41% | 26 / 62 |
| `imports_cost_log` | 38% | 24 / 62 |
| `rejects_wrong_method` | 38% | 24 / 62 |
| `has_capability_tag` | 30% | 19 / 62 |
| `uses_abortsignal_timeout` | 22% | 14 / 62 |
| `binds_jwt_identity` | 21% | 13 / 62 |
| `imports_redact_pii` | 9% | 6 / 62 |
| `imports_memory` | 9% | 6 / 62 |
| `logs_with_fn_name_prefix` | 9% | 6 / 62 |
| `has_any_console_error` | 6% | 4 / 62 |
| `imports_validate_contract` | 3% | 2 / 62 |
| `uses_abort_controller` | 1% | 1 / 62 |
| `imports_serve_std` | 0% | 0 / 62 |
| `wraps_in_serve` | 0% | 0 / 62 |
| `cors_headers_first_in_handler` | 0% | 0 / 62 |
| `wraps_handler_in_try` | 0% | 0 / 62 |
| `createclient_in_handler` | 0% | 0 / 62 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
