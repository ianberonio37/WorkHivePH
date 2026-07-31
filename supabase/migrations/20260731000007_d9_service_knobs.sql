-- 20260731000007_d9_service_knobs.sql
--
-- D9 CONFIGURABILITY — the knobs TB-A345's A3 has been owed on since the arc began. Ian chose ALL THREE
-- groups (hail timing + reach, abuse caps, trust thresholds), so this makes the service flow's hardcoded
-- constants per-hive settings with platform defaults.
--
-- ONE CONCERN, STATED AND DESIGNED AROUND rather than silently dropped: per-hive TRUST thresholds are a
-- forgery vector. If a hive could set gold@1, it would mint its own gold sellers and the tier ladder would
-- stop meaning anything platform-wide — the same self-dealing shape the marketplace trust guards exist to
-- stop. So trust thresholds are TIGHTEN-ONLY: a hive may RAISE the bar (demand more sales for a tier), never
-- lower it. Configurable, as asked, without becoming a way to counterfeit reputation.
--
-- ABUSE CAPS ARE NOT DUPLICATED HERE. `hive_quotas` already carries them per hive (max_rows_logbook,
-- max_rows_logbook_per_user, max_rows_community, max_rows_inv_tx, max_rows_pm_comp, max_storage_mb,
-- enforce_blocking) with its own RLS. A second config surface for the same concept is how two sources of
-- truth start disagreeing; this table takes only the knobs that had NO home.
--
-- The resolver is the point: callers ask for an EFFECTIVE value and never branch on whether a row exists.
-- A missing hive row is not a missing setting — it is the platform default.

BEGIN;

CREATE TABLE IF NOT EXISTS public.hive_service_settings (
  hive_id                   uuid PRIMARY KEY REFERENCES public.hives(id) ON DELETE CASCADE,

  -- HAIL TIMING + REACH: how long an offer lives and how far it looks. These decide whether a worker in a
  -- sparse area is ever matched, which is why they are the most defensible per-hive knob.
  instant_ttl_seconds       integer NOT NULL DEFAULT 120     CHECK (instant_ttl_seconds  BETWEEN 30 AND 3600),
  quote_ttl_seconds         integer NOT NULL DEFAULT 86400   CHECK (quote_ttl_seconds    BETWEEN 3600 AND 604800),
  broadcast_radius_start_m  integer NOT NULL DEFAULT 5000    CHECK (broadcast_radius_start_m BETWEEN 500 AND 100000),
  broadcast_radius_max_m    integer NOT NULL DEFAULT 100000  CHECK (broadcast_radius_max_m   BETWEEN 1000 AND 300000),
  broadcast_widen_rounds    integer NOT NULL DEFAULT 2       CHECK (broadcast_widen_rounds BETWEEN 0 AND 5),

  -- TRUST THRESHOLDS — tighten-only. The CHECK floors are the platform ladder (silver 11, gold 51); a hive
  -- may demand MORE, never fewer. Without these floors this table would be a reputation printer.
  tier_silver_sales         integer NOT NULL DEFAULT 11      CHECK (tier_silver_sales >= 11),
  tier_gold_sales           integer NOT NULL DEFAULT 51      CHECK (tier_gold_sales   >= 51),

  updated_at                timestamptz NOT NULL DEFAULT now(),
  created_at                timestamptz NOT NULL DEFAULT now(),

  -- gold must still outrank silver whatever a hive chooses
  CONSTRAINT hive_service_settings_tier_order CHECK (tier_gold_sales > tier_silver_sales),
  -- a radius that starts above its own ceiling would widen to nothing
  CONSTRAINT hive_service_settings_radius_order CHECK (broadcast_radius_max_m >= broadcast_radius_start_m)
);

COMMENT ON TABLE public.hive_service_settings IS
  'D9 configurability: per-hive service knobs with platform defaults. Trust thresholds are TIGHTEN-ONLY - a '
  'hive may raise a tier bar, never lower it, or the ladder becomes a reputation printer. Abuse caps live in '
  'hive_quotas and are deliberately not duplicated here.';

-- ── the resolver ───────────────────────────────────────────────────────────────────────────────────────
-- Callers ask for an EFFECTIVE value. A hive with no row is not unconfigured, it is on the defaults, and no
-- caller should have to know the difference. STABLE so it can be used in queries and index-friendly contexts.
CREATE OR REPLACE FUNCTION public.service_knob(p_hive uuid, p_key text)
RETURNS integer
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $fn$
  SELECT COALESCE(
    (SELECT CASE p_key
              WHEN 'instant_ttl_seconds'      THEN s.instant_ttl_seconds
              WHEN 'quote_ttl_seconds'        THEN s.quote_ttl_seconds
              WHEN 'broadcast_radius_start_m' THEN s.broadcast_radius_start_m
              WHEN 'broadcast_radius_max_m'   THEN s.broadcast_radius_max_m
              WHEN 'broadcast_widen_rounds'   THEN s.broadcast_widen_rounds
              WHEN 'tier_silver_sales'        THEN s.tier_silver_sales
              WHEN 'tier_gold_sales'          THEN s.tier_gold_sales
            END
       FROM public.hive_service_settings s WHERE s.hive_id = p_hive),
    -- platform defaults, stated ONCE here so the table default and the fallback cannot drift apart
    CASE p_key
      WHEN 'instant_ttl_seconds'      THEN 120
      WHEN 'quote_ttl_seconds'        THEN 86400
      WHEN 'broadcast_radius_start_m' THEN 5000
      WHEN 'broadcast_radius_max_m'   THEN 100000
      WHEN 'broadcast_widen_rounds'   THEN 2
      WHEN 'tier_silver_sales'        THEN 11
      WHEN 'tier_gold_sales'          THEN 51
    END);
$fn$;

COMMENT ON FUNCTION public.service_knob(uuid, text) IS
  'Effective value of a D9 service knob for a hive: the hive override, else the platform default. A missing '
  'row is not a missing setting.';

-- ── RLS, mirroring hive_quotas ─────────────────────────────────────────────────────────────────────────
-- Readable by the hive's members; writable by a supervisor of that hive. A knob that any member could
-- change is a knob an abuser can change.
ALTER TABLE public.hive_service_settings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.hive_service_settings FROM anon;
GRANT SELECT, INSERT, UPDATE ON public.hive_service_settings TO authenticated;

DROP POLICY IF EXISTS hive_service_settings_read ON public.hive_service_settings;
CREATE POLICY hive_service_settings_read ON public.hive_service_settings
  FOR SELECT TO authenticated
  USING (hive_id IN (SELECT hm.hive_id FROM public.hive_members hm
                      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'));

DROP POLICY IF EXISTS hive_service_settings_write ON public.hive_service_settings;
CREATE POLICY hive_service_settings_write ON public.hive_service_settings
  FOR ALL TO authenticated
  USING (hive_id IN (SELECT hm.hive_id FROM public.hive_members hm
                      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
                        AND hm.role = 'supervisor'))
  WITH CHECK (hive_id IN (SELECT hm.hive_id FROM public.hive_members hm
                           WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
                             AND hm.role = 'supervisor'));

COMMIT;
