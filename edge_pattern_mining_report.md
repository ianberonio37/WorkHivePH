# Edge-Function Pattern Mining Report

- Functions scanned: **56**
- Features extracted: **35**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **6**

## Promotion candidates (sweet spot)

These are emergent patterns ready to graduate into Layer 0 validators.
Review each: write a real validator from the outlier list, or allowlist them.

| Feature | Type | Conformance | Outliers (divergent fns) |
|---|---|---:|---|
| `imports_cors_shared` | convention (stays TRUE) | 98% | marketplace-webhook |
| `cors_headers_first_in_handler` | convention (stays TRUE) | 98% | walkthrough-analyzer |
| `wraps_handler_in_try` | convention (stays TRUE) | 96% | marketplace-webhook, walkthrough-analyzer |
| `imports_supabase_esm` | convention (stays TRUE) | 89% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |
| `reads_supabase_url_env` | convention (stays TRUE) | 89% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |
| `reads_service_role_env` | convention (stays TRUE) | 89% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_serve_std` | 100% | 56 / 56 |
| `wraps_in_serve` | 100% | 56 / 56 |
| `handles_options` | 100% | 56 / 56 |
| `uses_get_cors_headers` | 100% | 56 / 56 |
| `uses_error_envelope` | 100% | 56 / 56 |
| `sets_content_type_json` | 100% | 56 / 56 |
| `has_try_catch` | 100% | 56 / 56 |
| `imports_cors_shared` | 98% | 55 / 56 |
| `cors_headers_first_in_handler` | 98% | 55 / 56 |
| `wraps_handler_in_try` | 96% | 54 / 56 |
| `imports_supabase_esm` | 89% | 50 / 56 |
| `reads_supabase_url_env` | 89% | 50 / 56 |
| `reads_service_role_env` | 89% | 50 / 56 |
| `createclient_in_handler` | 85% | 48 / 56 |
| `memoizes_supabase_client` | 82% | 46 / 56 |
| `ends_with_serve_close` | 80% | 45 / 56 |
| `responses_spread_cors_headers` | 76% | 43 / 56 |
| `uses_wh_env_prefix` | 73% | 41 / 56 |
| `has_jsdoc_header` | 67% | 38 / 56 |
| `returns_400_on_bad_input` | 60% | 34 / 56 |
| `has_any_console_error` | 44% | 25 / 56 |
| `logs_with_fn_name_prefix` | 42% | 24 / 56 |
| `rejects_wrong_method` | 41% | 23 / 56 |
| `imports_ai_chain` | 39% | 22 / 56 |
| `has_skills_consulted` | 39% | 22 / 56 |
| `imports_cost_log` | 37% | 21 / 56 |
| `calls_callai` | 37% | 21 / 56 |
| `uses_abortsignal_timeout` | 32% | 18 / 56 |
| `has_capability_tag` | 28% | 16 / 56 |
| `imports_rate_limit` | 12% | 7 / 56 |
| `imports_redact_pii` | 10% | 6 / 56 |
| `imports_memory` | 10% | 6 / 56 |
| `binds_jwt_identity` | 8% | 5 / 56 |
| `imports_validate_contract` | 3% | 2 / 56 |
| `uses_abort_controller` | 1% | 1 / 56 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
