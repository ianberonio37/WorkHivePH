# Edge-Function Pattern Mining Report

- Functions scanned: **49**
- Features extracted: **31**
- Promotion threshold: >= 80% conformance, <= 6 outliers
- Promotion candidates: **5**

## Promotion candidates (sweet spot)

These are emergent patterns ready to graduate into Layer 0 validators.
Review each: write a real validator from the outlier list, or allowlist them.

| Feature | Type | Conformance | Outliers (divergent fns) |
|---|---|---:|---|
| `cors_headers_first_in_handler` | convention (stays TRUE) | 98% | walkthrough-analyzer |
| `has_try_catch` | convention (stays TRUE) | 89% | marketplace-checkout, marketplace-connect-onboard, marketplace-connect-status, marketplace-release, marketplace-webhook |
| `imports_supabase_esm` | convention (stays TRUE) | 87% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |
| `reads_supabase_url_env` | convention (stays TRUE) | 87% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |
| `reads_service_role_env` | convention (stays TRUE) | 87% | engineering-bom-sow, engineering-calc-agent, voice-embeddings, voice-model-call, voice-transcribe, walkthrough-analyzer |

## Full conformance ranking

| Feature | Conformance | Positive / Total |
|---|---:|---|
| `imports_serve_std` | 100% | 49 / 49 |
| `wraps_in_serve` | 100% | 49 / 49 |
| `handles_options` | 100% | 49 / 49 |
| `uses_get_cors_headers` | 100% | 49 / 49 |
| `uses_error_envelope` | 100% | 49 / 49 |
| `sets_content_type_json` | 100% | 49 / 49 |
| `cors_headers_first_in_handler` | 98% | 48 / 49 |
| `has_try_catch` | 89% | 44 / 49 |
| `imports_supabase_esm` | 87% | 43 / 49 |
| `reads_supabase_url_env` | 87% | 43 / 49 |
| `reads_service_role_env` | 87% | 43 / 49 |
| `imports_cors_shared` | 85% | 42 / 49 |
| `memoizes_supabase_client` | 83% | 41 / 49 |
| `createclient_in_handler` | 83% | 41 / 49 |
| `ends_with_serve_close` | 77% | 38 / 49 |
| `has_jsdoc_header` | 65% | 32 / 49 |
| `returns_400_on_bad_input` | 55% | 27 / 49 |
| `has_any_console_error` | 51% | 25 / 49 |
| `imports_ai_chain` | 38% | 19 / 49 |
| `imports_cost_log` | 36% | 18 / 49 |
| `calls_callai` | 36% | 18 / 49 |
| `logs_with_fn_name_prefix` | 34% | 17 / 49 |
| `has_skills_consulted` | 34% | 17 / 49 |
| `uses_abort_controller` | 34% | 17 / 49 |
| `rejects_wrong_method` | 32% | 16 / 49 |
| `has_capability_tag` | 30% | 15 / 49 |
| `imports_rate_limit` | 14% | 7 / 49 |
| `imports_redact_pii` | 12% | 6 / 49 |
| `imports_memory` | 12% | 6 / 49 |
| `binds_jwt_identity` | 10% | 5 / 49 |
| `imports_validate_contract` | 4% | 2 / 49 |

## How to act on this report

1. Pick a promotion candidate.
2. Look at the outlier fns -- are they legitimate exceptions or real bugs?
3a. **Real rule, real bugs** -> write `validate_<rule>.py`, register in `run_platform_checks.py`, fix the outliers.
3b. **Real rule, legit exceptions** -> write the validator with an allowlist of the outlier fns.
3c. **Accidental pattern** -> drop it; not a real rule.
