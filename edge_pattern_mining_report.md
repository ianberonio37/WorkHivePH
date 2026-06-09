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
| `imports_cors_shared` | convention (stays TRUE) | 98% | marketplace-webhook |
| `cors_headers_first_in_handler` | convention (stays TRUE) | 98% | walkthrough-analyzer |
| `wraps_handler_in_try` | convention (stays TRUE) | 96% | marketplace-webhook, walkthrough-analyzer |
| `imports_supabase_esm` | convention (stays TRUE) | 89% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |
| `reads_supabase_url_env` | convention (stays TRUE) | 89% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |
| `reads_service_role_env` | convention (stays TRUE) | 89% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_serve_std` | 100% | 59 / 59 |
| `wraps_in_serve` | 100% | 59 / 59 |
| `handles_options` | 100% | 59 / 59 |
| `uses_get_cors_headers` | 100% | 59 / 59 |
| `uses_error_envelope` | 100% | 59 / 59 |
| `sets_content_type_json` | 100% | 59 / 59 |
| `has_try_catch` | 100% | 59 / 59 |
| `imports_cors_shared` | 98% | 58 / 59 |
| `cors_headers_first_in_handler` | 98% | 58 / 59 |
| `wraps_handler_in_try` | 96% | 57 / 59 |
| `imports_supabase_esm` | 89% | 53 / 59 |
| `reads_supabase_url_env` | 89% | 53 / 59 |
| `reads_service_role_env` | 89% | 53 / 59 |
| `createclient_in_handler` | 86% | 51 / 59 |
| `ends_with_serve_close` | 81% | 48 / 59 |
| `memoizes_supabase_client` | 79% | 47 / 59 |
| `responses_spread_cors_headers` | 78% | 46 / 59 |
| `has_jsdoc_header` | 69% | 41 / 59 |
| `uses_wh_env_prefix` | 69% | 41 / 59 |
| `returns_400_on_bad_input` | 59% | 35 / 59 |
| `imports_ai_chain` | 42% | 25 / 59 |
| `has_any_console_error` | 42% | 25 / 59 |
| `has_skills_consulted` | 42% | 25 / 59 |
| `rejects_wrong_method` | 40% | 24 / 59 |
| `logs_with_fn_name_prefix` | 40% | 24 / 59 |
| `calls_callai` | 40% | 24 / 59 |
| `imports_cost_log` | 37% | 22 / 59 |
| `uses_abortsignal_timeout` | 30% | 18 / 59 |
| `has_capability_tag` | 27% | 16 / 59 |
| `imports_rate_limit` | 16% | 10 / 59 |
| `binds_jwt_identity` | 13% | 8 / 59 |
| `imports_redact_pii` | 10% | 6 / 59 |
| `imports_memory` | 10% | 6 / 59 |
| `imports_validate_contract` | 3% | 2 / 59 |
| `uses_abort_controller` | 1% | 1 / 59 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
