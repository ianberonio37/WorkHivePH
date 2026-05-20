# Edge-Function Pattern Mining Report

- Functions scanned: **50**
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
| `imports_supabase_esm` | convention (stays TRUE) | 88% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |
| `reads_supabase_url_env` | convention (stays TRUE) | 88% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |
| `reads_service_role_env` | convention (stays TRUE) | 88% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_serve_std` | 100% | 50 / 50 |
| `wraps_in_serve` | 100% | 50 / 50 |
| `handles_options` | 100% | 50 / 50 |
| `uses_get_cors_headers` | 100% | 50 / 50 |
| `uses_error_envelope` | 100% | 50 / 50 |
| `sets_content_type_json` | 100% | 50 / 50 |
| `has_try_catch` | 100% | 50 / 50 |
| `imports_cors_shared` | 98% | 49 / 50 |
| `cors_headers_first_in_handler` | 98% | 49 / 50 |
| `wraps_handler_in_try` | 96% | 48 / 50 |
| `imports_supabase_esm` | 88% | 44 / 50 |
| `reads_supabase_url_env` | 88% | 44 / 50 |
| `reads_service_role_env` | 88% | 44 / 50 |
| `createclient_in_handler` | 84% | 42 / 50 |
| `memoizes_supabase_client` | 82% | 41 / 50 |
| `uses_wh_env_prefix` | 80% | 40 / 50 |
| `ends_with_serve_close` | 78% | 39 / 50 |
| `responses_spread_cors_headers` | 74% | 37 / 50 |
| `has_jsdoc_header` | 64% | 32 / 50 |
| `returns_400_on_bad_input` | 56% | 28 / 50 |
| `has_any_console_error` | 50% | 25 / 50 |
| `imports_ai_chain` | 38% | 19 / 50 |
| `imports_cost_log` | 36% | 18 / 50 |
| `logs_with_fn_name_prefix` | 36% | 18 / 50 |
| `calls_callai` | 36% | 18 / 50 |
| `has_skills_consulted` | 36% | 18 / 50 |
| `rejects_wrong_method` | 34% | 17 / 50 |
| `uses_abortsignal_timeout` | 34% | 17 / 50 |
| `has_capability_tag` | 32% | 16 / 50 |
| `imports_rate_limit` | 14% | 7 / 50 |
| `imports_redact_pii` | 12% | 6 / 50 |
| `imports_memory` | 12% | 6 / 50 |
| `binds_jwt_identity` | 10% | 5 / 50 |
| `imports_validate_contract` | 4% | 2 / 50 |
| `uses_abort_controller` | 2% | 1 / 50 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
