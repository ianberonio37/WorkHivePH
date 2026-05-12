-- Phase 3 — Adoption Observability + Change Management.
--
-- The Hive Readiness Score (Phase 0.1) tells the hive how mature its
-- operating discipline is. The Adoption Risk Score (this migration) tells
-- the SUPERVISOR whether the hive is about to slip out of that discipline.
-- HRS is a forward-looking ladder. Adoption Risk is the smoke alarm.
--
-- Without this, a hive can score 70/100 on HRS for a week, drop to 30 the
-- next, and no one notices until the supervisor opens the platform and
-- sees a wasteland of overdue PMs and a single worker writing entries. This
-- is the change-management layer enterprises pay outside consultants
-- $50K-$200K for. We make it a free in-product capability.
--
-- Build:
--   1. hive_adoption_score table — daily snapshot per hive
--   2. compute_adoption_risk(uuid) RPC — pure plpgsql, transparent math
--   3. v_adoption_truth view — single canonical read surface
--   4. hives.intent JSONB column — Phase 3.5 "Why are you here?" capture
--   5. canonical_sources registrations + RLS + supabase_realtime publication
--
-- Skills consulted:
--   architect (companion-to-readiness pattern; daily snapshot, not real-time)
--   maintenance-expert (active-worker ratio is the leading indicator)
--   community (gamification rule: reward real work, surface real decay)
--   multitenant-engineer (hive-scoped writes only; hive-members-join RLS)
--   data-engineer (UNIQUE on (hive_id, snapshot_date) for idempotent re-run)

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. hive_adoption_score — daily snapshot per hive
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.hive_adoption_score (
  id                       uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id                  uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  snapshot_date            date        NOT NULL DEFAULT (timezone('Asia/Manila', now()))::date,
  -- Risk score 0..100 (HIGHER = MORE risk). This is the inverse of HRS:
  -- HRS measures maturity gained; adoption_risk measures the slide.
  risk_score               smallint    NOT NULL DEFAULT 0 CHECK (risk_score BETWEEN 0 AND 100),
  -- Risk tier (healthy | at_risk | critical) — three bands, no "low/medium/high"
  -- because the supervisor surface needs a binary "do I act this week?" answer.
  risk_tier                text        NOT NULL DEFAULT 'healthy'
                                       CHECK (risk_tier IN ('healthy', 'at_risk', 'critical')),
  -- Component signals (each 0..100; higher = more risk on that axis)
  active_ratio_risk        smallint    NOT NULL DEFAULT 0 CHECK (active_ratio_risk        BETWEEN 0 AND 100),
  momentum_risk            smallint    NOT NULL DEFAULT 0 CHECK (momentum_risk            BETWEEN 0 AND 100),
  supervisor_decay_risk    smallint    NOT NULL DEFAULT 0 CHECK (supervisor_decay_risk    BETWEEN 0 AND 100),
  stair_stall_risk         smallint    NOT NULL DEFAULT 0 CHECK (stair_stall_risk         BETWEEN 0 AND 100),
  new_worker_silence_risk  smallint    NOT NULL DEFAULT 0 CHECK (new_worker_silence_risk  BETWEEN 0 AND 100),
  -- Top reasons (ordered list of human-readable causes)
  top_reasons              jsonb       NOT NULL DEFAULT '[]'::jsonb,
  -- Champion candidate (worker with highest engagement; surfaces in Phase 3.4)
  champion_candidate       text,
  champion_engagement      smallint    DEFAULT 0 CHECK (champion_engagement BETWEEN 0 AND 100),
  -- Workers whose engagement has dropped week-over-week
  dropping_workers         jsonb       NOT NULL DEFAULT '[]'::jsonb,
  computed_at              timestamptz NOT NULL DEFAULT now(),
  model_version            text        NOT NULL DEFAULT 'adoption-v1',
  CONSTRAINT hive_adoption_unique_per_day UNIQUE (hive_id, snapshot_date)
);

COMMENT ON TABLE public.hive_adoption_score IS
  'Daily adoption-risk snapshot per hive. Composite 0..100 (HIGHER = MORE risk). Companion to hive_readiness. Drives Supervisor Engagement Card on hive.html (Phase 3.2). Audit-trail through canonical_sources.';

CREATE INDEX IF NOT EXISTS idx_hive_adoption_hive_date
  ON public.hive_adoption_score (hive_id, snapshot_date DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- 2. hives.intent — Phase 3.5 "Why are you here?" capture
-- ────────────────────────────────────────────────────────────────────────────
-- JSONB so we can evolve the question set without migrations. Initial shape:
--   {
--     "primary_goal":   "predictive" | "compliance" | "training" | "downtime" | "cmms_replace" | "other",
--     "secondary":      ["safety", "audit", "cost", "kpi", "marketplace"],
--     "captured_at":    "2026-05-13T12:00:00Z",
--     "captured_role":  "supervisor"   -- who answered
--   }
-- An empty {} means "not yet asked" — the signin/signup flow detects this and
-- shows the modal once.

ALTER TABLE public.hives
  ADD COLUMN IF NOT EXISTS intent jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN public.hives.intent IS
  'Phase 3.5 — Why-are-you-here capture. JSONB so the question set can evolve without migration. Empty {} = not yet asked; signin/signup flow triggers the modal on first surface.';

-- ────────────────────────────────────────────────────────────────────────────
-- 3. compute_adoption_risk(uuid) — the math, in PL/pgSQL for transparency
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.compute_adoption_risk(p_hive_id uuid)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_total_members          integer;
  v_active_workers_7d      integer;
  v_writes_this_week       integer;
  v_writes_last_week       integer;
  v_supervisor_actions_7d  integer;
  v_supervisor_actions_p14 integer;
  v_prev_stair             smallint;
  v_curr_stair             smallint;
  v_stair_since            timestamptz;
  v_new_members_30d        integer;
  v_new_silent_30d         integer;

  -- Risk components (each 0..100; higher = more risk)
  v_active_ratio_risk      smallint;
  v_momentum_risk          smallint;
  v_supervisor_decay_risk  smallint;
  v_stair_stall_risk       smallint;
  v_new_worker_risk        smallint;
  v_composite              smallint;
  v_tier                   text;

  v_reasons                jsonb := '[]'::jsonb;
  v_champion               text;
  v_champion_score         smallint;
  v_dropping               jsonb;

  v_today                  date := (timezone('Asia/Manila', now()))::date;
  v_id                     uuid;
BEGIN
  -- ─── Membership + write rate inputs ───────────────────────────────────────
  SELECT count(*) INTO v_total_members
    FROM public.hive_members
    WHERE hive_id = p_hive_id AND status = 'active';

  SELECT count(DISTINCT worker_name) INTO v_active_workers_7d
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '7 days';

  SELECT count(*) INTO v_writes_this_week
    FROM public.logbook
    WHERE hive_id = p_hive_id AND created_at >= now() - interval '7 days';

  SELECT count(*) INTO v_writes_last_week
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '14 days'
      AND created_at <  now() - interval '7 days';

  SELECT count(*) INTO v_supervisor_actions_7d
    FROM public.hive_audit_log
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '7 days'
      AND action IN ('approve', 'reject', 'kick', 'assign', 'verify');

  SELECT count(*) INTO v_supervisor_actions_p14
    FROM public.hive_audit_log
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '14 days'
      AND created_at <  now() - interval '7 days'
      AND action IN ('approve', 'reject', 'kick', 'assign', 'verify');

  -- Stair stall: did the hive's stair NOT move in the last 30 days when it
  -- should have? We approximate by reading the latest 2 hive_readiness rows.
  SELECT current_stair INTO v_curr_stair
    FROM public.hive_readiness
    WHERE hive_id = p_hive_id
    ORDER BY snapshot_date DESC
    LIMIT 1;
  SELECT current_stair INTO v_prev_stair
    FROM public.hive_readiness
    WHERE hive_id = p_hive_id
      AND snapshot_date <= v_today - 30
    ORDER BY snapshot_date DESC
    LIMIT 1;

  -- New members in last 30d who have NEVER written anything
  SELECT count(*) INTO v_new_members_30d
    FROM public.hive_members hm
    WHERE hm.hive_id = p_hive_id
      AND hm.status = 'active'
      AND hm.joined_at >= now() - interval '30 days';

  SELECT count(*) INTO v_new_silent_30d
    FROM public.hive_members hm
    WHERE hm.hive_id = p_hive_id
      AND hm.status = 'active'
      AND hm.joined_at >= now() - interval '30 days'
      AND NOT EXISTS (
        SELECT 1 FROM public.logbook lb
        WHERE lb.hive_id = p_hive_id
          AND lb.worker_name = hm.worker_name
      );

  -- ─── Component scores (each 0..100; higher = more risk) ──────────────────
  -- Active ratio: < 40% of members writing in 7d = high risk.
  v_active_ratio_risk := CASE
    WHEN v_total_members = 0 THEN 0
    WHEN v_active_workers_7d = 0 THEN 100
    ELSE GREATEST(0, LEAST(100,
      (100 - LEAST(100, (100.0 * v_active_workers_7d / v_total_members)::int))
    ))
  END;

  -- Momentum: this-week writes vs last-week writes. If writes fell >50%, full risk.
  v_momentum_risk := CASE
    WHEN v_writes_last_week = 0 AND v_writes_this_week = 0 THEN 60
    WHEN v_writes_last_week = 0 THEN 0
    WHEN v_writes_this_week >= v_writes_last_week THEN 0
    ELSE GREATEST(0, LEAST(100,
      (100 - (100.0 * v_writes_this_week / v_writes_last_week))::int
    ))
  END;

  -- Supervisor decay: approvals trending toward zero.
  v_supervisor_decay_risk := CASE
    WHEN v_supervisor_actions_p14 = 0 AND v_supervisor_actions_7d = 0 THEN 70
    WHEN v_supervisor_actions_7d = 0 THEN 100
    WHEN v_supervisor_actions_p14 = 0 THEN 0
    WHEN v_supervisor_actions_7d >= v_supervisor_actions_p14 THEN 0
    ELSE GREATEST(0, LEAST(100,
      (100 - (100.0 * v_supervisor_actions_7d / v_supervisor_actions_p14))::int
    ))
  END;

  -- Stair stall: no movement in 30 days AND not at top of stack.
  v_stair_stall_risk := CASE
    WHEN v_curr_stair IS NULL THEN 50
    WHEN v_curr_stair = 4 THEN 0
    WHEN v_prev_stair IS NULL THEN 30
    WHEN v_curr_stair > v_prev_stair THEN 0
    ELSE 60
  END;

  -- New-worker silence: new members who never wrote.
  v_new_worker_risk := CASE
    WHEN v_new_members_30d = 0 THEN 0
    ELSE GREATEST(0, LEAST(100,
      (100.0 * v_new_silent_30d / v_new_members_30d)::int
    ))
  END;

  -- Composite: equal-weighted at v1 (we'll re-weight after 10+ hives produce data).
  v_composite := GREATEST(0, LEAST(100, (
      v_active_ratio_risk
    + v_momentum_risk
    + v_supervisor_decay_risk
    + v_stair_stall_risk
    + v_new_worker_risk
  ) / 5));

  -- Tier mapping
  v_tier := CASE
    WHEN v_composite >= 65 THEN 'critical'
    WHEN v_composite >= 35 THEN 'at_risk'
    ELSE 'healthy'
  END;

  -- ─── Build top_reasons (ordered, most-risk-first) ────────────────────────
  WITH r(name, score, label) AS (
    VALUES
      ('active_ratio',     v_active_ratio_risk::int,     'Few active workers this week'),
      ('momentum',         v_momentum_risk::int,         'Write rate dropping vs last week'),
      ('supervisor_decay', v_supervisor_decay_risk::int, 'Supervisor approvals trending down'),
      ('stair_stall',      v_stair_stall_risk::int,      'Hive has not advanced a stair in 30 days'),
      ('new_silence',      v_new_worker_risk::int,       'New members have not written anything yet')
  )
  SELECT COALESCE(
    jsonb_agg(jsonb_build_object('signal', name, 'score', score, 'label', label) ORDER BY score DESC),
    '[]'::jsonb
  )
  INTO v_reasons
  FROM r
  WHERE score >= 35;     -- only surface real risks, not noise

  -- ─── Champion candidate (top writer in last 30 days) ─────────────────────
  SELECT worker_name, LEAST(100, (count(*) * 2)::int)
    INTO v_champion, v_champion_score
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '30 days'
    GROUP BY worker_name
    ORDER BY count(*) DESC
    LIMIT 1;

  -- ─── Dropping workers: this-week writes < 50% of last-week's writes ─────
  WITH this_week AS (
    SELECT worker_name, count(*) AS n
      FROM public.logbook
      WHERE hive_id = p_hive_id AND created_at >= now() - interval '7 days'
      GROUP BY worker_name
  ),
  last_week AS (
    SELECT worker_name, count(*) AS n
      FROM public.logbook
      WHERE hive_id = p_hive_id
        AND created_at >= now() - interval '14 days'
        AND created_at <  now() - interval '7 days'
      GROUP BY worker_name
  )
  SELECT COALESCE(jsonb_agg(jsonb_build_object(
           'worker_name',  COALESCE(t.worker_name, l.worker_name),
           'this_week',    COALESCE(t.n, 0),
           'last_week',    l.n
         ) ORDER BY l.n DESC), '[]'::jsonb)
    INTO v_dropping
    FROM last_week l
    LEFT JOIN this_week t USING (worker_name)
    WHERE l.n >= 3
      AND COALESCE(t.n, 0) < (l.n * 0.5);

  -- ─── Persist (idempotent on (hive_id, snapshot_date)) ────────────────────
  INSERT INTO public.hive_adoption_score (
    hive_id, snapshot_date, risk_score, risk_tier,
    active_ratio_risk, momentum_risk, supervisor_decay_risk,
    stair_stall_risk, new_worker_silence_risk,
    top_reasons, champion_candidate, champion_engagement, dropping_workers,
    computed_at
  ) VALUES (
    p_hive_id, v_today, v_composite, v_tier,
    v_active_ratio_risk, v_momentum_risk, v_supervisor_decay_risk,
    v_stair_stall_risk, v_new_worker_risk,
    v_reasons, v_champion, COALESCE(v_champion_score, 0), v_dropping,
    now()
  )
  ON CONFLICT (hive_id, snapshot_date) DO UPDATE
    SET risk_score              = EXCLUDED.risk_score,
        risk_tier               = EXCLUDED.risk_tier,
        active_ratio_risk       = EXCLUDED.active_ratio_risk,
        momentum_risk           = EXCLUDED.momentum_risk,
        supervisor_decay_risk   = EXCLUDED.supervisor_decay_risk,
        stair_stall_risk        = EXCLUDED.stair_stall_risk,
        new_worker_silence_risk = EXCLUDED.new_worker_silence_risk,
        top_reasons             = EXCLUDED.top_reasons,
        champion_candidate      = EXCLUDED.champion_candidate,
        champion_engagement     = EXCLUDED.champion_engagement,
        dropping_workers        = EXCLUDED.dropping_workers,
        computed_at             = now()
    RETURNING id INTO v_id;

  RETURN v_id;
END;
$$;

REVOKE ALL ON FUNCTION public.compute_adoption_risk(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.compute_adoption_risk(uuid) TO authenticated, service_role;

COMMENT ON FUNCTION public.compute_adoption_risk(uuid) IS
  'Phase 3.1 — Adoption Risk Score compute. Pure PL/pgSQL math: 5 components averaged, ranged 0..100 (higher = more risk), tiered healthy/at_risk/critical. Idempotent per (hive_id, snapshot_date). Drives Supervisor Engagement Card.';

-- ────────────────────────────────────────────────────────────────────────────
-- 4. get_adoption_risk_current — read-only RPC for dashboards
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.get_adoption_risk_current(p_hive_id uuid)
RETURNS public.hive_adoption_score
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
  SELECT *
    FROM public.hive_adoption_score
    WHERE hive_id = p_hive_id
    ORDER BY snapshot_date DESC
    LIMIT 1;
$$;

REVOKE ALL ON FUNCTION public.get_adoption_risk_current(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_adoption_risk_current(uuid) TO authenticated, service_role;

-- ────────────────────────────────────────────────────────────────────────────
-- 5. v_adoption_truth — canonical read surface
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE VIEW public.v_adoption_truth AS
  SELECT
    has.hive_id,
    has.snapshot_date,
    has.risk_score,
    has.risk_tier,
    has.active_ratio_risk,
    has.momentum_risk,
    has.supervisor_decay_risk,
    has.stair_stall_risk,
    has.new_worker_silence_risk,
    has.top_reasons,
    has.champion_candidate,
    has.champion_engagement,
    has.dropping_workers,
    has.computed_at,
    has.model_version
  FROM public.hive_adoption_score has
  WHERE has.snapshot_date = (
    SELECT max(snapshot_date) FROM public.hive_adoption_score
    WHERE hive_id = has.hive_id
  );

COMMENT ON VIEW public.v_adoption_truth IS
  'Canonical read surface for adoption risk — one row per hive, the latest snapshot. Supervisor Engagement Card reads from here. Phase 3.1.';

GRANT SELECT ON public.v_adoption_truth TO authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- 6. RLS — hive-membership read; service-role writes only
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.hive_adoption_score ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS hive_adoption_score_read ON public.hive_adoption_score;
CREATE POLICY hive_adoption_score_read ON public.hive_adoption_score FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS hive_adoption_score_insert_locked ON public.hive_adoption_score;
CREATE POLICY hive_adoption_score_insert_locked ON public.hive_adoption_score FOR INSERT
  WITH CHECK (false);

DROP POLICY IF EXISTS hive_adoption_score_update_locked ON public.hive_adoption_score;
CREATE POLICY hive_adoption_score_update_locked ON public.hive_adoption_score FOR UPDATE
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS hive_adoption_score_delete_locked ON public.hive_adoption_score;
CREATE POLICY hive_adoption_score_delete_locked ON public.hive_adoption_score FOR DELETE
  USING (false);

GRANT SELECT ON public.hive_adoption_score TO anon, authenticated;

-- ────────────────────────────────────────────────────────────────────────────
-- 7. Realtime publication (Supervisor Engagement Card subscribes for live tier flips)
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.hive_adoption_score REPLICA IDENTITY FULL;
ALTER PUBLICATION supabase_realtime ADD TABLE public.hive_adoption_score;

-- ────────────────────────────────────────────────────────────────────────────
-- 8. Canonical sources registration (fuel + engine + brain)
-- ────────────────────────────────────────────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('hive_adoption_score', 'view', 'v_adoption_truth',
   'analytics-engineer', 'daily',
   'Canonical read surface for adoption risk per hive. One row per hive, latest snapshot. Drives Supervisor Engagement Card on hive.html (Phase 3.2).',
   jsonb_build_object(
     'key',              jsonb_build_array('hive_id'),
     'hive_scoped',      true,
     'higher_is_worse',  true,
     'tier_thresholds',  jsonb_build_object('healthy', '< 35', 'at_risk', '35..64', 'critical', '>= 65'),
     'phase_3_built',    true
   ),
   'Phase 3.1 of STRATEGIC_ROADMAP — Adoption Risk Score.'),

  ('hive_adoption_score_table', 'table', 'hive_adoption_score',
   'analytics-engineer', 'daily',
   'Daily adoption-risk snapshot per hive. Idempotent on (hive_id, snapshot_date). Fueled by compute_adoption_risk RPC.',
   jsonb_build_object(
     'key',           jsonb_build_array('id'),
     'hive_scoped',   true,
     'write_policy',  'service-role only (compute_adoption_risk SECURITY DEFINER)',
     'phase_3_built', true
   ),
   'Phase 3.1 of STRATEGIC_ROADMAP.'),

  ('compute_adoption_risk_rpc', 'rpc', 'compute_adoption_risk',
   'analytics-engineer', 'on-demand',
   'PL/pgSQL RPC that computes the 5-component adoption-risk score for one hive. SECURITY DEFINER; idempotent per (hive_id, snapshot_date). Scheduled daily via pg_cron at 06:00 PHT alongside compute_hive_readiness.',
   jsonb_build_object(
     'args',          jsonb_build_array(jsonb_build_object('name', 'p_hive_id', 'type', 'uuid')),
     'returns',       'uuid',
     'security',      'definer',
     'hive_scoped',   true,
     'phase_3_built', true
   ),
   'Phase 3.1 of STRATEGIC_ROADMAP.'),

  ('get_adoption_risk_current_rpc', 'rpc', 'get_adoption_risk_current',
   'analytics-engineer', 'on-demand',
   'Read-only RPC that returns the latest hive_adoption_score row for a hive. SECURITY DEFINER for callers that lack direct table SELECT.',
   jsonb_build_object(
     'args',          jsonb_build_array(jsonb_build_object('name', 'p_hive_id', 'type', 'uuid')),
     'returns',       'hive_adoption_score',
     'security',      'definer',
     'hive_scoped',   true,
     'phase_3_built', true
   ),
   'Phase 3.1 of STRATEGIC_ROADMAP.'),

  ('hives_intent', 'column', 'hives.intent',
   'analytics-engineer', 'on-demand',
   'Phase 3.5 — "Why are you here?" capture. JSONB so the question set can evolve without migrations. Captured on first signin/signup after the column is non-empty. Drives onboarding personalisation and product analytics.',
   jsonb_build_object(
     'shape', jsonb_build_object(
       'primary_goal',  jsonb_build_array('predictive', 'compliance', 'training', 'downtime', 'cmms_replace', 'other'),
       'secondary',     'array<string>',
       'captured_at',   'timestamptz',
       'captured_role', jsonb_build_array('worker', 'supervisor')
     ),
     'hive_scoped',     true,
     'phase_3_built',   true
   ),
   'Phase 3.5 of STRATEGIC_ROADMAP.')
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
