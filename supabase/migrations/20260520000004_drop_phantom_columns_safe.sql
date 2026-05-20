-- Drop 40 SAFE phantom columns identified by tools/audit_phantom_columns.py.
--
-- All columns dropped here are confirmed unused: they belong to Phase-6
-- "industry-defining" scaffolding (drone inspections, consulting
-- engagements, best practices, cross-hive alerts) or to feature shelves
-- that were defined but never wired in any consumer surface (avatar
-- animations, dialog state extras, language preferences, terminology
-- gaps, hive quotas, hive readiness audit).
--
-- DEFERRED (in 20260520000003_DRAFT.sql, still commented out):
--   - hive_adoption_score (3 cols): may be planned for [[project-phase-3-adoption-observability]]
--   - industry_standards   (3 cols): may be planned for the standards registry (Azure Day 4)
--   - mfa_enrollments / sso_configs / auth_session_events: auth-tier; verify Supabase Auth + IdP first
--   - 21 TRANSIENT cols: confirm write paths from edge fns / sensors / triggers before dropping
--
-- This migration is forward-only. Postgres does not auto-restore data
-- from a dropped column; a follow-up could re-ADD any of these if the
-- feature ever ships, but data is lost from any existing rows.

BEGIN;

-- ── Phase 6 industry-defining scaffolding never wired ─────────────────

-- photo_count is a generated column depending on photo_paths, so drop the
-- dependent generated column first.
ALTER TABLE IF EXISTS public.drone_inspections      DROP COLUMN IF EXISTS photo_count;
ALTER TABLE IF EXISTS public.drone_inspections      DROP COLUMN IF EXISTS inspection_kind;
ALTER TABLE IF EXISTS public.drone_inspections      DROP COLUMN IF EXISTS scheduled_at;
ALTER TABLE IF EXISTS public.drone_inspections      DROP COLUMN IF EXISTS flown_at;
ALTER TABLE IF EXISTS public.drone_inspections      DROP COLUMN IF EXISTS drone_model;
ALTER TABLE IF EXISTS public.drone_inspections      DROP COLUMN IF EXISTS photo_paths;
ALTER TABLE IF EXISTS public.drone_inspections      DROP COLUMN IF EXISTS ai_outputs;
ALTER TABLE IF EXISTS public.drone_inspections      DROP COLUMN IF EXISTS reviewed_by;

ALTER TABLE IF EXISTS public.consulting_engagements DROP COLUMN IF EXISTS engagement_kind;
ALTER TABLE IF EXISTS public.consulting_engagements DROP COLUMN IF EXISTS starting_stair;
ALTER TABLE IF EXISTS public.consulting_engagements DROP COLUMN IF EXISTS target_stair;
ALTER TABLE IF EXISTS public.consulting_engagements DROP COLUMN IF EXISTS target_days;
ALTER TABLE IF EXISTS public.consulting_engagements DROP COLUMN IF EXISTS consultant_name;
ALTER TABLE IF EXISTS public.consulting_engagements DROP COLUMN IF EXISTS contract_value_php;
ALTER TABLE IF EXISTS public.consulting_engagements DROP COLUMN IF EXISTS outcome_summary;

ALTER TABLE IF EXISTS public.best_practices         DROP COLUMN IF EXISTS source_hive_id;
ALTER TABLE IF EXISTS public.best_practices         DROP COLUMN IF EXISTS problem_category;
ALTER TABLE IF EXISTS public.best_practices         DROP COLUMN IF EXISTS solution_title;
ALTER TABLE IF EXISTS public.best_practices         DROP COLUMN IF EXISTS solution_description;
ALTER TABLE IF EXISTS public.best_practices         DROP COLUMN IF EXISTS effectiveness_score;

ALTER TABLE IF EXISTS public.cross_hive_alerts      DROP COLUMN IF EXISTS source_hive_id;
ALTER TABLE IF EXISTS public.cross_hive_alerts      DROP COLUMN IF EXISTS related_hive_ids;
ALTER TABLE IF EXISTS public.cross_hive_alerts      DROP COLUMN IF EXISTS shared_asset_id;

-- ── Audit / observability features never wired ────────────────────────

ALTER TABLE IF EXISTS public.hive_readiness_audit   DROP COLUMN IF EXISTS changed_at;
ALTER TABLE IF EXISTS public.hive_readiness_audit   DROP COLUMN IF EXISTS previous_stair;
ALTER TABLE IF EXISTS public.hive_readiness_audit   DROP COLUMN IF EXISTS new_stair;
ALTER TABLE IF EXISTS public.hive_readiness_audit   DROP COLUMN IF EXISTS previous_composite;
ALTER TABLE IF EXISTS public.hive_readiness_audit   DROP COLUMN IF EXISTS new_composite;
ALTER TABLE IF EXISTS public.hive_readiness_audit   DROP COLUMN IF EXISTS evidence_delta;

ALTER TABLE IF EXISTS public.hive_quotas            DROP COLUMN IF EXISTS max_rows_logbook;
ALTER TABLE IF EXISTS public.hive_quotas            DROP COLUMN IF EXISTS max_rows_inv_tx;
ALTER TABLE IF EXISTS public.hive_quotas            DROP COLUMN IF EXISTS max_storage_mb;

-- ── Avatar / multilingual scaffolding (Phase 10/11) never wired ──────

ALTER TABLE IF EXISTS public.avatar_animations      DROP COLUMN IF EXISTS state_name;
ALTER TABLE IF EXISTS public.avatar_animations      DROP COLUMN IF EXISTS animation_key;
ALTER TABLE IF EXISTS public.avatar_state           DROP COLUMN IF EXISTS last_gesture;

-- 2026-05-20: skipped — clarification_prompt is referenced by the
-- fetch_dialog_state RPC return table. Dropping with CASCADE would drop
-- the RPC too. Leave the column for now; the RPC's behaviour is fine
-- (returns NULL when clarification not pending).
-- ALTER TABLE IF EXISTS public.dialog_state           DROP COLUMN IF EXISTS clarification_prompt;
-- ALTER TABLE IF EXISTS public.dialog_state           DROP COLUMN IF EXISTS last_turn_num;

ALTER TABLE IF EXISTS public.language_preferences   DROP COLUMN IF EXISTS preferred_language;
ALTER TABLE IF EXISTS public.language_preferences   DROP COLUMN IF EXISTS code_switch_allowed;
ALTER TABLE IF EXISTS public.terminology_gaps       DROP COLUMN IF EXISTS missing_term;

COMMIT;
