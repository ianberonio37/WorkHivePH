-- DRAFT MIGRATION — DO NOT RUN AS-IS
-- ===================================
-- Generated 2026-05-20 from `tools/audit_phantom_columns.py` baseline.
-- 78 columns flagged as "defined but never read" by static analysis.
--
-- Each DROP is COMMENTED OUT. To accept a drop, uncomment the line
-- AFTER:
--   1. Confirming no external system (Supabase Auth, CMMS push, SAP sync,
--      regulatory archival) reads the column.
--   2. Running the auditor with the change to confirm no other table's
--      consumer disappears.
--   3. Adding a sibling DOWN migration if you want to be able to roll
--      back. (Postgres doesn't auto-restore data from a dropped column.)
--
-- Columns are grouped by safety class:
--   SAFE       — Phase-6 / vestigial scaffolding. Drop freely.
--   RISKY      — Auth/security/external — verify Supabase / IdP usage first.
--   TRANSIENT  — Might be written by edge fns / sensors even if no surface
--                .select()s them. Confirm write paths before dropping.
--
-- Rename this file (strip _DRAFT) once you've vetted the drops.

BEGIN;

-- ╔══════════════════════════════════════════════════════════════════╗
-- ║ SAFE — Phase-6 industry-defining scaffolding never wired         ║
-- ║ (drone_inspections, consulting_engagements, best_practices,      ║
-- ║  cross_hive_alerts, hive_readiness_audit, hive_quotas)           ║
-- ╚══════════════════════════════════════════════════════════════════╝

-- ALTER TABLE public.drone_inspections        DROP COLUMN IF EXISTS inspection_kind;
-- ALTER TABLE public.drone_inspections        DROP COLUMN IF EXISTS scheduled_at;
-- ALTER TABLE public.drone_inspections        DROP COLUMN IF EXISTS flown_at;
-- ALTER TABLE public.drone_inspections        DROP COLUMN IF EXISTS drone_model;
-- ALTER TABLE public.drone_inspections        DROP COLUMN IF EXISTS photo_paths;
-- ALTER TABLE public.drone_inspections        DROP COLUMN IF EXISTS photo_count;
-- ALTER TABLE public.drone_inspections        DROP COLUMN IF EXISTS ai_outputs;
-- ALTER TABLE public.drone_inspections        DROP COLUMN IF EXISTS reviewed_by;

-- ALTER TABLE public.consulting_engagements   DROP COLUMN IF EXISTS engagement_kind;
-- ALTER TABLE public.consulting_engagements   DROP COLUMN IF EXISTS starting_stair;
-- ALTER TABLE public.consulting_engagements   DROP COLUMN IF EXISTS target_stair;
-- ALTER TABLE public.consulting_engagements   DROP COLUMN IF EXISTS target_days;
-- ALTER TABLE public.consulting_engagements   DROP COLUMN IF EXISTS consultant_name;
-- ALTER TABLE public.consulting_engagements   DROP COLUMN IF EXISTS contract_value_php;
-- ALTER TABLE public.consulting_engagements   DROP COLUMN IF EXISTS outcome_summary;

-- ALTER TABLE public.best_practices           DROP COLUMN IF EXISTS source_hive_id;
-- ALTER TABLE public.best_practices           DROP COLUMN IF EXISTS problem_category;
-- ALTER TABLE public.best_practices           DROP COLUMN IF EXISTS solution_title;
-- ALTER TABLE public.best_practices           DROP COLUMN IF EXISTS solution_description;
-- ALTER TABLE public.best_practices           DROP COLUMN IF EXISTS effectiveness_score;

-- ALTER TABLE public.cross_hive_alerts        DROP COLUMN IF EXISTS source_hive_id;
-- ALTER TABLE public.cross_hive_alerts        DROP COLUMN IF EXISTS related_hive_ids;
-- ALTER TABLE public.cross_hive_alerts        DROP COLUMN IF EXISTS shared_asset_id;

-- ALTER TABLE public.hive_readiness_audit     DROP COLUMN IF EXISTS changed_at;
-- ALTER TABLE public.hive_readiness_audit     DROP COLUMN IF EXISTS previous_stair;
-- ALTER TABLE public.hive_readiness_audit     DROP COLUMN IF EXISTS new_stair;
-- ALTER TABLE public.hive_readiness_audit     DROP COLUMN IF EXISTS previous_composite;
-- ALTER TABLE public.hive_readiness_audit     DROP COLUMN IF EXISTS new_composite;
-- ALTER TABLE public.hive_readiness_audit     DROP COLUMN IF EXISTS evidence_delta;

-- ALTER TABLE public.hive_quotas              DROP COLUMN IF EXISTS max_rows_logbook;
-- ALTER TABLE public.hive_quotas              DROP COLUMN IF EXISTS max_rows_inv_tx;
-- ALTER TABLE public.hive_quotas              DROP COLUMN IF EXISTS max_storage_mb;

-- ALTER TABLE public.hive_adoption_score      DROP COLUMN IF EXISTS supervisor_decay_risk;
-- ALTER TABLE public.hive_adoption_score      DROP COLUMN IF EXISTS stair_stall_risk;
-- ALTER TABLE public.hive_adoption_score      DROP COLUMN IF EXISTS new_worker_silence_risk;

-- ALTER TABLE public.industry_standards       DROP COLUMN IF EXISTS current_version;
-- ALTER TABLE public.industry_standards       DROP COLUMN IF EXISTS effective_year;
-- ALTER TABLE public.industry_standards       DROP COLUMN IF EXISTS planned_review_at;

-- ALTER TABLE public.avatar_animations        DROP COLUMN IF EXISTS state_name;
-- ALTER TABLE public.avatar_animations        DROP COLUMN IF EXISTS animation_key;
-- ALTER TABLE public.avatar_state             DROP COLUMN IF EXISTS last_gesture;

-- ALTER TABLE public.dialog_state             DROP COLUMN IF EXISTS clarification_prompt;
-- ALTER TABLE public.dialog_state             DROP COLUMN IF EXISTS last_turn_num;

-- ALTER TABLE public.language_preferences     DROP COLUMN IF EXISTS preferred_language;
-- ALTER TABLE public.language_preferences     DROP COLUMN IF EXISTS code_switch_allowed;
-- ALTER TABLE public.terminology_gaps         DROP COLUMN IF EXISTS missing_term;

-- ╔══════════════════════════════════════════════════════════════════╗
-- ║ RISKY — auth / security / external systems may read these         ║
-- ║ DO NOT DROP without confirming Supabase Auth + IdP usage          ║
-- ╚══════════════════════════════════════════════════════════════════╝

-- ALTER TABLE public.mfa_enrollments          DROP COLUMN IF EXISTS factor_id;
-- ALTER TABLE public.mfa_enrollments          DROP COLUMN IF EXISTS factor_type;
-- ALTER TABLE public.mfa_enrollments          DROP COLUMN IF EXISTS enrolled_at;
-- ALTER TABLE public.mfa_enrollments          DROP COLUMN IF EXISTS recovery_hashes;
-- ALTER TABLE public.mfa_enrollments          DROP COLUMN IF EXISTS recovery_used_count;
-- ALTER TABLE public.mfa_enrollments          DROP COLUMN IF EXISTS required_for_role;

-- ALTER TABLE public.sso_configs              DROP COLUMN IF EXISTS acs_url;
-- ALTER TABLE public.sso_configs              DROP COLUMN IF EXISTS metadata_url;
-- ALTER TABLE public.sso_configs              DROP COLUMN IF EXISTS cert_thumbprint;

-- ALTER TABLE public.auth_session_events      DROP COLUMN IF EXISTS user_agent_hash;
-- ALTER TABLE public.auth_session_events      DROP COLUMN IF EXISTS occurred_at;

-- ╔══════════════════════════════════════════════════════════════════╗
-- ║ TRANSIENT — may be written by edge fns / sensors / triggers        ║
-- ║ Confirm write paths before dropping                              ║
-- ╚══════════════════════════════════════════════════════════════════╝

-- ALTER TABLE public.ai_quality_log           DROP COLUMN IF EXISTS run_at;
-- ALTER TABLE public.amc_briefings            DROP COLUMN IF EXISTS approved_notes;
-- ALTER TABLE public.anomaly_alerts           DROP COLUMN IF EXISTS last_notified_at;
-- ALTER TABLE public.agent_memory             DROP COLUMN IF EXISTS turn_text;
-- ALTER TABLE public.canonical_sources        DROP COLUMN IF EXISTS last_validated;
-- ALTER TABLE public.fallback_model_faq       DROP COLUMN IF EXISTS question_embedding;
-- ALTER TABLE public.fallback_model_faq       DROP COLUMN IF EXISTS accuracy_score;
-- ALTER TABLE public.hive_route_calls         DROP COLUMN IF EXISTS hour_bucket;
-- ALTER TABLE public.hive_route_quotas        DROP COLUMN IF EXISTS hourly_cap;
-- ALTER TABLE public.kb_chunks                DROP COLUMN IF EXISTS relevance_score;
-- ALTER TABLE public.kb_documents             DROP COLUMN IF EXISTS file_size_bytes;
-- ALTER TABLE public.offline_snapshot_cache   DROP COLUMN IF EXISTS cached_at;
-- ALTER TABLE public.parts_staged_reservations DROP COLUMN IF EXISTS reserved_at;
-- ALTER TABLE public.project_items            DROP COLUMN IF EXISTS actual_start;
-- ALTER TABLE public.project_items            DROP COLUMN IF EXISTS actual_end;
-- ALTER TABLE public.rcm_strategies           DROP COLUMN IF EXISTS weibull_fit_id;
-- ALTER TABLE public.sensor_readings          DROP COLUMN IF EXISTS sensor_type;
-- ALTER TABLE public.sensor_readings          DROP COLUMN IF EXISTS ingested_at;
-- ALTER TABLE public.sensor_topic_map         DROP COLUMN IF EXISTS offset_value;
-- ALTER TABLE public.tts_cache                DROP COLUMN IF EXISTS audio_data;
-- ALTER TABLE public.tts_cache                DROP COLUMN IF EXISTS audio_format;

COMMIT;
