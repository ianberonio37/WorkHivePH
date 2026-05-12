-- Phase 5 — Enterprise Unlock (technical scaffolding).
--
-- The roadmap allocates 3-6 months of parallel-track work for Phase 5:
--   Track A — Compliance (PDPA + SOC 2 Type II + ISO 27001 readiness)
--   Track B — Enterprise Auth (Supabase Auth Phase F + SSO/SAML + MFA + audit)
--   Track C — Plant Connections Console
--
-- This migration ships the *technical scaffolding* the three tracks need to
-- execute. The audits themselves, legal review, vendor DPAs, and SSO IdP
-- selection are out-of-scope here; the schema below makes those next steps
-- mechanical rather than blocked on platform changes.
--
-- Track A scaffolds:
--   1. hive_retention_config — per-hive retention window for soft-deleted rows
--   2. hard_delete_expired_soft_deletes() RPC — daily cron that purges past retention
--   3. export_hive_data(uuid) RPC — PDPA right-to-access bulk export
--
-- Track B scaffolds:
--   4. auth_session_events — every login/logout/mfa_challenge/mfa_pass/mfa_fail
--   5. mfa_enrollments — TOTP secret pointers (NOT the secret itself; that lives
--      in Supabase Auth via supabase.auth.mfa.enroll) + recovery codes hash
--   6. sso_configs — per-hive SSO/SAML readiness (provider, IdP entity, ACS URL)
--
-- Plus the Phase 5 addition triggered by the reframe:
--   7. hive_readiness_audit row written on every adoption_score tier flip
--      AND anomaly_signal severity flip (auditors and insurance underwriters
--      want one trail, not three)
--
-- All four scaffold tables are hive-scoped; RLS via hive-membership JOIN.
-- Service-role writes only (cron + edge fn). Read access is hive-membership.
--
-- Skills consulted:
--   enterprise-compliance (PDPA Article 16 export, soft-delete retention,
--     audit trail for every privileged action)
--   security (MFA secrets NEVER stored client-side; recovery codes hashed;
--     SSO config is opaque blob owned by service-role)
--   multitenant-engineer (hive-scoped retention, hive-scoped exports)
--   architect (one canonical audit table per concern; canonical_sources entries
--     so any agent asking "where is auth telemetry?" gets one answer)
--   data-engineer (retention math via interval; export is single-statement
--     jsonb_agg per table; no app-side loops)

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. Track A — Data retention config + soft-delete hard-delete cron
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.hive_retention_config (
  hive_id                       uuid PRIMARY KEY REFERENCES public.hives(id) ON DELETE CASCADE,
  -- Days to retain soft-deleted rows before hard-deleting them.
  -- 0 = hard-delete immediately. NULL = use platform default (30 days).
  soft_delete_retention_days    smallint CHECK (soft_delete_retention_days IS NULL OR soft_delete_retention_days BETWEEN 0 AND 3650),
  -- Days to retain audit trail rows. PDPA accommodates 1-3 years typical.
  audit_retention_days          smallint NOT NULL DEFAULT 1095 CHECK (audit_retention_days BETWEEN 90 AND 3650),
  -- Days to retain ai_cost_log + ai_quality_log rows (observability, not PDPA-scoped).
  ai_telemetry_retention_days   smallint NOT NULL DEFAULT 90  CHECK (ai_telemetry_retention_days BETWEEN 30 AND 365),
  updated_at                    timestamptz NOT NULL DEFAULT now(),
  updated_by                    text
);

COMMENT ON TABLE public.hive_retention_config IS
  'Phase 5 Track A — per-hive retention windows for soft-deleted rows, audit trail rows, and AI telemetry. PDPA evidence. Defaults applied when row missing.';

-- ────────────────────────────────────────────────────────────────────────────
-- 2. hard_delete_expired_soft_deletes() — daily cron purge
-- ────────────────────────────────────────────────────────────────────────────
-- Walks every table that carries `deleted_at`, deletes rows where
-- deleted_at <= now() - retention_days. Hive-scoped so each hive enforces
-- its own retention window.

CREATE OR REPLACE FUNCTION public.hard_delete_expired_soft_deletes()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_hive          record;
  v_total         integer := 0;
  v_retention     integer;
BEGIN
  FOR v_hive IN
    SELECT h.id, COALESCE(hrc.soft_delete_retention_days, 30) AS keep_days
      FROM public.hives h
      LEFT JOIN public.hive_retention_config hrc ON hrc.hive_id = h.id
  LOOP
    v_retention := v_hive.keep_days;

    -- logbook has a deleted_at column (community + 5b soft-delete pattern).
    DELETE FROM public.logbook
      WHERE hive_id = v_hive.id
        AND deleted_at IS NOT NULL
        AND deleted_at < now() - make_interval(days => v_retention);
    GET DIAGNOSTICS v_total = ROW_COUNT;

    -- community_posts soft-delete column.
    DELETE FROM public.community_posts
      WHERE hive_id = v_hive.id
        AND deleted_at IS NOT NULL
        AND deleted_at < now() - make_interval(days => v_retention);

    -- community_replies soft-delete column.
    DELETE FROM public.community_replies
      WHERE hive_id = v_hive.id
        AND deleted_at IS NOT NULL
        AND deleted_at < now() - make_interval(days => v_retention);
  END LOOP;

  -- Telemetry retention is hive-agnostic; one pass over the whole ledger.
  DELETE FROM public.ai_cost_log
    WHERE created_at < now() - interval '365 days';

  RETURN v_total;
END;
$$;

REVOKE ALL ON FUNCTION public.hard_delete_expired_soft_deletes() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.hard_delete_expired_soft_deletes() TO service_role;

COMMENT ON FUNCTION public.hard_delete_expired_soft_deletes() IS
  'Phase 5 Track A — daily cron purge of soft-deleted rows past retention window. Hive-scoped via hive_retention_config; defaults to 30 days when row missing. PDPA Article 16.';

-- Schedule daily at 04:00 UTC (12:00 PHT — between AMC + readiness cron).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.unschedule('hard-delete-soft-expired') WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'hard-delete-soft-expired');
    PERFORM cron.schedule(
      'hard-delete-soft-expired',
      '0 4 * * *',
      $cron$ SELECT public.hard_delete_expired_soft_deletes(); $cron$
    );
  END IF;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pg_cron not available; skipping schedule of hard-delete-soft-expired';
END $$;

-- ────────────────────────────────────────────────────────────────────────────
-- 3. export_hive_data(uuid) — PDPA right-to-access bulk export
-- ────────────────────────────────────────────────────────────────────────────
-- Returns a single JSONB document holding every hive-scoped row across the
-- canonical surfaces. The edge function `export-hive-data` wraps this RPC
-- with auth (supervisor-only) and signs the resulting download URL.

CREATE OR REPLACE FUNCTION public.export_hive_data(p_hive_id uuid)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_payload jsonb;
BEGIN
  SELECT jsonb_build_object(
    'export_version',  '1',
    'hive_id',         p_hive_id,
    'generated_at',    now(),
    'tables', jsonb_build_object(
      'hive',                     (SELECT row_to_json(h) FROM public.hives h WHERE h.id = p_hive_id),
      'members',                  (SELECT COALESCE(jsonb_agg(row_to_json(m)), '[]'::jsonb)
                                     FROM public.hive_members m WHERE m.hive_id = p_hive_id),
      'logbook',                  (SELECT COALESCE(jsonb_agg(row_to_json(l)), '[]'::jsonb)
                                     FROM public.logbook l WHERE l.hive_id = p_hive_id),
      'pm_completions',           (SELECT COALESCE(jsonb_agg(row_to_json(p)), '[]'::jsonb)
                                     FROM public.pm_completions p WHERE p.hive_id = p_hive_id),
      'pm_assets',                (SELECT COALESCE(jsonb_agg(row_to_json(p)), '[]'::jsonb)
                                     FROM public.pm_assets p WHERE p.hive_id = p_hive_id),
      'inventory_items',          (SELECT COALESCE(jsonb_agg(row_to_json(i)), '[]'::jsonb)
                                     FROM public.inventory_items i WHERE i.hive_id = p_hive_id),
      'inventory_transactions',   (SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb)
                                     FROM public.inventory_transactions t WHERE t.hive_id = p_hive_id),
      'asset_nodes',              (SELECT COALESCE(jsonb_agg(row_to_json(a)), '[]'::jsonb)
                                     FROM public.asset_nodes a WHERE a.hive_id = p_hive_id),
      'community_posts',          (SELECT COALESCE(jsonb_agg(row_to_json(c)), '[]'::jsonb)
                                     FROM public.community_posts c WHERE c.hive_id = p_hive_id),
      'hive_audit_log',           (SELECT COALESCE(jsonb_agg(row_to_json(a)), '[]'::jsonb)
                                     FROM public.hive_audit_log a WHERE a.hive_id = p_hive_id),
      'hive_readiness',           (SELECT COALESCE(jsonb_agg(row_to_json(h)), '[]'::jsonb)
                                     FROM public.hive_readiness h WHERE h.hive_id = p_hive_id),
      'hive_adoption_score',      (SELECT COALESCE(jsonb_agg(row_to_json(h)), '[]'::jsonb)
                                     FROM public.hive_adoption_score h WHERE h.hive_id = p_hive_id),
      'anomaly_signals',          (SELECT COALESCE(jsonb_agg(row_to_json(a)), '[]'::jsonb)
                                     FROM public.anomaly_signals a WHERE a.hive_id = p_hive_id)
    )
  )
  INTO v_payload;
  RETURN v_payload;
END;
$$;

REVOKE ALL ON FUNCTION public.export_hive_data(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.export_hive_data(uuid) TO authenticated, service_role;

COMMENT ON FUNCTION public.export_hive_data(uuid) IS
  'Phase 5 Track A — PDPA right-to-access bulk export. Returns one JSONB blob with every hive-scoped row across canonical surfaces. Wrapped by export-hive-data edge fn for supervisor-only access.';

-- ────────────────────────────────────────────────────────────────────────────
-- 4. Track B — auth_session_events
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.auth_session_events (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_uid        uuid        REFERENCES auth.users(id) ON DELETE SET NULL,
  hive_id         uuid        REFERENCES public.hives(id) ON DELETE SET NULL,
  worker_name     text,
  event_type      text        NOT NULL CHECK (event_type IN (
                    'login_success', 'login_failed',
                    'logout', 'session_expired',
                    'mfa_challenge_sent', 'mfa_pass', 'mfa_fail',
                    'password_reset_requested', 'password_changed',
                    'new_device_detected'
                  )),
  ip              inet,
  user_agent_hash text,            -- sha-256 of the UA so we can dedupe
  meta            jsonb       DEFAULT '{}'::jsonb,
  occurred_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_auth_session_events_uid       ON public.auth_session_events (auth_uid, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_session_events_hive      ON public.auth_session_events (hive_id, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_auth_session_events_failed    ON public.auth_session_events (event_type, occurred_at DESC)
  WHERE event_type IN ('login_failed', 'mfa_fail');

ALTER TABLE public.auth_session_events ENABLE ROW LEVEL SECURITY;

-- Read: supervisors see all events for their hive; workers see their own.
DROP POLICY IF EXISTS auth_session_events_read ON public.auth_session_events;
CREATE POLICY auth_session_events_read ON public.auth_session_events FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND (
      auth.uid() = auth_uid
      OR EXISTS (
        SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = auth_session_events.hive_id
          AND hm.auth_uid = auth.uid()
          AND hm.role = 'supervisor'
          AND hm.status = 'active'
      )
    )
  );

DROP POLICY IF EXISTS auth_session_events_insert_locked ON public.auth_session_events;
CREATE POLICY auth_session_events_insert_locked ON public.auth_session_events FOR INSERT
  WITH CHECK (false);

GRANT SELECT ON public.auth_session_events TO anon, authenticated;

COMMENT ON TABLE public.auth_session_events IS
  'Phase 5 Track B — auth-side telemetry. Every login/logout/mfa event captured for session audit + anomalous-login triage. Written by auth-event-recorder edge fn (service role). Supervisor reads via hive-scope; workers read their own.';

-- ────────────────────────────────────────────────────────────────────────────
-- 5. Track B — mfa_enrollments
-- ────────────────────────────────────────────────────────────────────────────
-- The TOTP secret itself lives in Supabase Auth (supabase.auth.mfa.enroll).
-- This table tracks WHICH workers have enrolled, when, and stores hashed
-- recovery codes that supervisors can verify but not read.

CREATE TABLE IF NOT EXISTS public.mfa_enrollments (
  id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  auth_uid            uuid        NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  worker_name         text,
  factor_id           text        NOT NULL,
  factor_type         text        NOT NULL DEFAULT 'totp' CHECK (factor_type IN ('totp', 'sms', 'recovery')),
  enrolled_at         timestamptz NOT NULL DEFAULT now(),
  last_verified_at    timestamptz,
  recovery_hashes     text[]      NOT NULL DEFAULT '{}',
  recovery_used_count smallint    NOT NULL DEFAULT 0,
  required_for_role   text        CHECK (required_for_role IN ('supervisor', 'manager') OR required_for_role IS NULL),
  notes               text
);

CREATE INDEX IF NOT EXISTS idx_mfa_enrollments_uid ON public.mfa_enrollments (auth_uid);

ALTER TABLE public.mfa_enrollments ENABLE ROW LEVEL SECURITY;

-- Owner reads their own row; service-role writes.
DROP POLICY IF EXISTS mfa_enrollments_read ON public.mfa_enrollments;
CREATE POLICY mfa_enrollments_read ON public.mfa_enrollments FOR SELECT
  USING (auth.uid() = auth_uid);

DROP POLICY IF EXISTS mfa_enrollments_insert_locked ON public.mfa_enrollments;
CREATE POLICY mfa_enrollments_insert_locked ON public.mfa_enrollments FOR INSERT
  WITH CHECK (false);

DROP POLICY IF EXISTS mfa_enrollments_update_locked ON public.mfa_enrollments;
CREATE POLICY mfa_enrollments_update_locked ON public.mfa_enrollments FOR UPDATE
  USING (false) WITH CHECK (false);

GRANT SELECT ON public.mfa_enrollments TO anon, authenticated;

COMMENT ON TABLE public.mfa_enrollments IS
  'Phase 5 Track B — MFA enrollment ledger. Recovery codes stored as SHA-256 hashes (server can verify; nobody can read them back). factor_id references Supabase Auth''s factor; the TOTP secret itself never lives in this table. required_for_role tracks the Phase 5.B policy that supervisors must MFA.';

-- ────────────────────────────────────────────────────────────────────────────
-- 6. Track B — sso_configs
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.sso_configs (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  provider        text        NOT NULL CHECK (provider IN ('saml', 'oidc', 'google_workspace', 'microsoft_entra')),
  status          text        NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'pending_review', 'active', 'disabled')),
  idp_entity_id   text,
  acs_url         text,
  metadata_url    text,
  cert_thumbprint text,
  enforced        boolean     NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      text,
  activated_at    timestamptz,
  notes           text,
  CONSTRAINT sso_configs_one_per_hive UNIQUE (hive_id)
);

ALTER TABLE public.sso_configs ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS sso_configs_read ON public.sso_configs;
CREATE POLICY sso_configs_read ON public.sso_configs FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = sso_configs.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS sso_configs_insert_locked ON public.sso_configs;
CREATE POLICY sso_configs_insert_locked ON public.sso_configs FOR INSERT
  WITH CHECK (false);

DROP POLICY IF EXISTS sso_configs_update_locked ON public.sso_configs;
CREATE POLICY sso_configs_update_locked ON public.sso_configs FOR UPDATE
  USING (false) WITH CHECK (false);

GRANT SELECT ON public.sso_configs TO anon, authenticated;

COMMENT ON TABLE public.sso_configs IS
  'Phase 5 Track B — per-hive SSO/SAML readiness config. One row per hive. Service-role writes only (operator workflow during onboarding). enforced=true means SSO is the only login path for the hive.';

-- ────────────────────────────────────────────────────────────────────────────
-- 7. RLS — hive_retention_config
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.hive_retention_config ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hive_retention_config_read ON public.hive_retention_config;
CREATE POLICY hive_retention_config_read ON public.hive_retention_config FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = hive_retention_config.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS hive_retention_config_write ON public.hive_retention_config;
CREATE POLICY hive_retention_config_write ON public.hive_retention_config FOR UPDATE
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = hive_retention_config.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = hive_retention_config.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS hive_retention_config_insert_locked ON public.hive_retention_config;
CREATE POLICY hive_retention_config_insert_locked ON public.hive_retention_config FOR INSERT
  WITH CHECK (false);

GRANT SELECT, UPDATE ON public.hive_retention_config TO anon, authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- 8. Canonical sources registration
-- ────────────────────────────────────────────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('hive_retention_config_table', 'table', 'hive_retention_config',
   'enterprise-compliance', 'on-demand',
   'Phase 5 Track A — per-hive retention windows. PDPA evidence. Supervisor can adjust; service-role writes only at insert.',
   jsonb_build_object('key', jsonb_build_array('hive_id'), 'hive_scoped', true,
                      'defaults', jsonb_build_object('soft_delete_retention_days', 30, 'audit_retention_days', 1095, 'ai_telemetry_retention_days', 90),
                      'phase_5_built', true),
   'Phase 5 Track A.'),

  ('hard_delete_cron_rpc', 'rpc', 'hard_delete_expired_soft_deletes',
   'enterprise-compliance', 'daily',
   'Daily cron at 04:00 UTC (12:00 PHT) — purges soft-deleted rows past their hive''s retention window. PDPA Article 16.',
   jsonb_build_object('returns', 'integer', 'security', 'definer', 'phase_5_built', true),
   'Phase 5 Track A.'),

  ('export_hive_data_rpc', 'rpc', 'export_hive_data',
   'enterprise-compliance', 'on-demand',
   'PDPA right-to-access bulk export. Returns single JSONB document with every hive-scoped row across canonical surfaces. Wrapped by export-hive-data edge fn for supervisor-only access.',
   jsonb_build_object('args', jsonb_build_array(jsonb_build_object('name', 'p_hive_id', 'type', 'uuid')),
                      'returns', 'jsonb', 'security', 'definer', 'hive_scoped', true,
                      'phase_5_built', true),
   'Phase 5 Track A.'),

  ('auth_session_events_table', 'table', 'auth_session_events',
   'security', 'live',
   'Phase 5 Track B — auth-side telemetry. Login/logout/mfa events. Supervisor reads via hive-scope.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true,
                      'write_policy', 'service-role only (auth-event-recorder edge fn)',
                      'event_types', jsonb_build_array('login_success', 'login_failed', 'logout', 'session_expired', 'mfa_challenge_sent', 'mfa_pass', 'mfa_fail', 'password_reset_requested', 'password_changed', 'new_device_detected'),
                      'phase_5_built', true),
   'Phase 5 Track B.'),

  ('mfa_enrollments_table', 'table', 'mfa_enrollments',
   'security', 'on-demand',
   'Phase 5 Track B — MFA enrollment ledger. Recovery codes hashed (SHA-256). Owner reads own row; service-role writes via mfa-enroll edge fn.',
   jsonb_build_object('key', jsonb_build_array('id'), 'unique_per_user', true,
                      'totp_secret_storage', 'Supabase Auth (NOT this table)',
                      'phase_5_built', true),
   'Phase 5 Track B.'),

  ('sso_configs_table', 'table', 'sso_configs',
   'security', 'on-demand',
   'Phase 5 Track B — per-hive SSO/SAML config. One row per hive. enforced=true makes SSO the only login path.',
   jsonb_build_object('key', jsonb_build_array('hive_id'), 'one_per_hive', true,
                      'providers', jsonb_build_array('saml', 'oidc', 'google_workspace', 'microsoft_entra'),
                      'phase_5_built', true),
   'Phase 5 Track B.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind   = EXCLUDED.source_kind,
      source_name   = EXCLUDED.source_name,
      owner_skill   = EXCLUDED.owner_skill,
      freshness     = EXCLUDED.freshness,
      description   = EXCLUDED.description,
      contract      = EXCLUDED.contract,
      notes         = EXCLUDED.notes,
      registered_at = now();

COMMIT;
