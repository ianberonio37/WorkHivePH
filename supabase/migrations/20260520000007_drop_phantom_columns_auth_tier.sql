-- Drop the auth-tier phantom columns (11 cols / 3 tables).
--
-- Vetted 2026-05-20: each column confirmed to have ZERO references in
-- application code (HTML / JS / TS / edge fns) via grep. The auth-tier
-- tables themselves (mfa_enrollments, sso_configs, auth_session_events)
-- were custom Phase 5 enterprise scaffolding — Supabase Auth has its own
-- auth.mfa_factors + GoTrue SAML handling and never reads these tables.
--
-- sso_configs retains its 6 active columns (provider, status,
-- idp_entity_id, enforced, activated_at, notes) which plant-connections
-- loadSsoConfig() actually reads. The 3 phantom SP-specific columns
-- (acs_url, metadata_url, cert_thumbprint) have no consumer.
--
-- Forward-only; no data preservation. Any future SAML SP integration
-- can re-ADD these via a fresh migration.

BEGIN;

-- ── MFA scaffolding (Supabase Auth uses auth.mfa_factors, not this) ──
ALTER TABLE IF EXISTS public.mfa_enrollments       DROP COLUMN IF EXISTS factor_id;
ALTER TABLE IF EXISTS public.mfa_enrollments       DROP COLUMN IF EXISTS factor_type;
ALTER TABLE IF EXISTS public.mfa_enrollments       DROP COLUMN IF EXISTS enrolled_at;
ALTER TABLE IF EXISTS public.mfa_enrollments       DROP COLUMN IF EXISTS recovery_hashes;
ALTER TABLE IF EXISTS public.mfa_enrollments       DROP COLUMN IF EXISTS recovery_used_count;
ALTER TABLE IF EXISTS public.mfa_enrollments       DROP COLUMN IF EXISTS required_for_role;

-- ── SSO SP-specific config fields never wired into any edge fn ──────
ALTER TABLE IF EXISTS public.sso_configs           DROP COLUMN IF EXISTS acs_url;
ALTER TABLE IF EXISTS public.sso_configs           DROP COLUMN IF EXISTS metadata_url;
ALTER TABLE IF EXISTS public.sso_configs           DROP COLUMN IF EXISTS cert_thumbprint;

-- ── Auth session audit fields never surfaced in any page or edge fn ──
ALTER TABLE IF EXISTS public.auth_session_events   DROP COLUMN IF EXISTS user_agent_hash;
ALTER TABLE IF EXISTS public.auth_session_events   DROP COLUMN IF EXISTS occurred_at;

COMMIT;
