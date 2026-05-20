# AI Extraction Triage Report

**Total proposals scored:** 825
**Accepted (score >= 25):** 22
**Borderline (15-24):** 65
**Rejected (< 15):** 738

## Accepted -- ready to merge into manifest

| Score | Rule ID | Sev | Conf | Files | Reason |
|---:|---|---|---:|---:|---|
| 38 | `ai_engineer_edge_fn_env_api_key` | critical | 0.898 | 49 | Edge functions must read API keys from Deno.env. |
| 38 | `tcg_expert_no_hardcoded_card_data` | critical | 0.667 | 24 | No hardcoded card data |
| 33 | `architect_hive-scope-params` | high | 0.688 | 16 | Helpers must parameterize hiveIds instead of hardcoding |
| 33 | `performance-index-on-filtered-columns` | high | 0.667 | 3 | Index columns used in filters |
| 31 | `platform_guardian_valid_platform_health_json` | critical | 0.292 | 24 | platform_health.json must be valid JSON |
| 30 | `architect_realtime-pub-opt-in` | critical | 0.095 | 147 | Migrations must add tables to supabase_realtime publication |
| 30 | `data_engineer_child_table_queries` | critical | 0.042 | 24 | Scope child queries by hive_id |
| 30 | `realtime_engineer_realtime_publication_opt_in` | critical | 0.095 | 147 | Opt-in tables for realtime publication |
| 29 | `pm_validator_freq_days_alignment` | high | 0.333 | 6 | FREQ_DAYS keys must match freqOrder array |
| 28 | `performance_no_render_blocking_scripts` | high | 0.917 | 36 | No render-blocking scripts in <head> |
| 28 | `data_engineer_limit_50_enforced` | high | 0.875 | 24 | List queries must use .limit(50) and not other limits |
| 28 | `assistant_validator_no_hvac_disciplines` | high | 0.917 | 24 | floating-ai.js must NOT contain 'HVAC' or 'Civil/Structural' in the discipline l |
| 28 | `platform_guardian_style_script_scoped_checks` | high | 0.944 | 36 | Validator checks for CSS/JS patterns must be scoped to <style> or <script> block |
| 27 | `multitenant_engineer_auth_uid_in_rls` | critical | 0.028 | 36 | RLS policies must use auth.uid() for authentication |
| 27 | `multitenant_engineer_no_string_matching_in_rls` | critical | 0.083 | 36 | Never bypass auth migration by string-matching in RLS |
| 26 | `data-engineer-cross-page-insert-pm-completions-worker-name` | high | 0.333 | 3 | Cross-page inserts into pm_completions must include 'worker_name' column |
| 25 | `ai_engineer_conditional_prompt` | high | 0.889 | 36 | Use conditional prompts for accurate output |
| 25 | `ai_engineer_use_number_wrappers` | high | 0.556 | 36 | Use Number() wrappers on prompt-embedded math to guard against undefined produci |
| 25 | `multitenant_engineer_hive-id-eq-query` | high | 0.1 | 10 | Supabase queries on hive-scoped data must include .eq('hive_id', HIVE_ID) |
| 25 | `pm_validator_pm_templates_coverage` | high | 0.167 | 6 | PM_TEMPLATES categories must be in PM_CAT_TO_LOG_CAT |
| 25 | `pm_validator_pm_cat_to_log_cat_values` | high | 0.167 | 6 | PM_CAT_TO_LOG_CAT values must be valid logbook categories |
| 25 | `standards_validator_no_ai_sources` | high | 0.708 | 24 | Do not use AI output as references; use primary documents or human-authored publ |

## Borderline -- review individually

- `devops_pg_cron_uncommented_schedule` (score 24, conf 0.98): pg_cron schedule calls must be inside a block comment
- `performance_no_synchronous_local_storage` (score 24, conf 0.458): No synchronous localStorage reads blocking render
- `architect-hive-role-let-declaration` (score 24, conf 0.958): HIVE_ID and HIVE_ROLE must be declared as let
- `engineering_calc_validator_validate_integration_results_field_null` (score 24, conf 0.98): Results field is null
- `multitenant_engineer_no_rls_on_hive_scoped_tables` (score 24, conf 0.98): Do not enable RLS on hive-scoped tables without Supabase Auth
- `multitenant_engineer_hive_role-db-validation` (score 23, conf 0.818): Do not rely on localStorage for HIVE_ROLE; validate from DB
- `performance_animations_use_transform_and_opacity` (score 23, conf 0.786): Animations use only transform and opacity
- `performance-analytics-postgres-views` (score 23, conf 0.667): Use Postgres views or RPCs for aggregating more than 200 rows
- `ai_engineer_python_calc_handlers` (score 21, conf 0.417): Ensure Python returned keys match renderer field names exactly
- `architect-db-column-defaults` (score 20, conf 0.088): JSONB columns must have DEFAULT '[]' or DEFAULT NULL
- `ai_engineer_use_Promise_allSettled` (score 20, conf 0.125): Use Promise.allSettled, not Promise.all
- `ai_engineer_always_set_max_tokens` (score 20, conf 0.028): Set max_tokens explicitly on every Groq call that produces structured documents.
- `ai_engineer_groq_api_key_in_header` (score 20, conf 0.02): Use GROQ_API_KEY in Authorization header
- `devops_abort_signal_timeout` (score 20, conf 0.02): Use AbortSignal.timeout in edge function fetch() calls
- `data_engineer_solo_delete_must_issue_db_delete` (score 20, conf 0.167): Solo delete must call db.delete() explicitly
- `ai_engineer_always_set_max_tokens` (score 20, conf 0.028): Set max_tokens explicitly on every Groq call that produces structured documents.
- `ai_engineer_cache_analytics_results` (score 20, conf 0.056): Check cache first before re-fetching analytics data
- `ai_engineer_edge_function_timeout` (score 20, conf 0.061): Set a 90s timeout minimum for edge functions calling Render/Railway free-tier Python APIs
- `architect_realtime-publication-should-appear` (score 20, conf 0.095): Migration must include ALTER PUBLICATION supabase_realtime ADD TABLE for new tables.
- `assistant_validator_path_includes_logbook` (score 20, conf 0.042): floating-ai.js must contain path.includes('logbook') in detectPageContext()
- `assistant_validator_path_includes_assistant` (score 20, conf 0.042): floating-ai.js must contain path.includes('assistant') in detectPageContext()
- `assistant_validator_path_includes_dayplanner` (score 20, conf 0.042): floating-ai.js must contain path.includes('dayplanner') in detectPageContext()
- `assistant_validator_path_includes_pm-scheduler` (score 20, conf 0.042): floating-ai.js must contain path.includes('pm-scheduler') in detectPageContext()
- `assistant_validator_path_includes_hive` (score 20, conf 0.042): floating-ai.js must contain path.includes('hive') in detectPageContext()
- `assistant_validator_path_includes_inventory` (score 20, conf 0.042): floating-ai.js must contain path.includes('inventory') in detectPageContext()
- `assistant_validator_path_includes_skillmatrix` (score 20, conf 0.042): floating-ai.js must contain path.includes('skillmatrix') in detectPageContext()
- `assistant_validator_path_includes_engineering-design` (score 20, conf 0.042): floating-ai.js must contain path.includes('engineering-design') in detectPageContext()
- `assistant_validator_include_facilities_management` (score 20, conf 0.083): floating-ai.js must include 'Facilities Management' in the discipline list
- `assistant_validator_calc_count_46` (score 20, conf 0.083): assistant.html must state 46 calculation types
- `assistant_validator_platform_tools_engineering_design` (score 20, conf 0.083): floating-ai.js must list engineering-design.html in the PLATFORM TOOLS section