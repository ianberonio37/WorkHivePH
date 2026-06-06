-- ============================================================================
-- 20260607000005  SECURITY DEFINER hive-membership gates (Group A, batch 2)
-- ============================================================================
-- The validate_definer_membership_gate.py validator built alongside ...0003
-- surfaced 5 MORE SECURITY DEFINER, hive-scoped functions that bypass RLS but
-- did not re-check the caller's hive membership (the initial manual scan's
-- looser heuristic -- hive_members OR auth.uid() -- missed them; the validator
-- requires BOTH, matching a real gate). All 5 are browser-callable (user JWT):
--   compute_adoption_risk   -> hive.html (writes hive_adoption_score)
--   compute_hive_readiness  -> hive.html (writes hive_readiness)
--   export_hive_data        -> hive.html + export-hive-data edge fn  *** the
--       worst: dumps an ENTIRE foreign hive (members/logbook/PM/assets...) to
--       JSON for any authenticated caller passing a foreign p_hive_id ***
--   store_memory_turn       -> voice-handler.js (writes agent_memory; foreign
--                              hive_id poisons another hive's AI context)
--   update_dialog_state     -> voice-handler.js (writes dialog_state)
--
-- Fix = the same in-function gate as ...0003 (service_role bypass for the
-- export edge fn). No return-type changes. Deploy PENDING.
--
-- NOTE: export_hive_data is now membership-gated; making it SUPERVISOR-only is
-- a reasonable follow-up (whole-hive export is sensitive) but is a product
-- decision beyond this isolation fix.
-- ============================================================================

BEGIN;

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
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'compute_adoption_risk: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

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

CREATE OR REPLACE FUNCTION public.compute_hive_readiness(p_hive_id uuid)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  v_asset_count               integer;
  v_pm_template_count         integer;
  v_logbook_30d               integer;
  v_fmea_modes_approved       integer;
  v_logbook_with_knowledge    integer;

  v_active_workers_7d         integer;
  v_total_members             integer;
  v_supervisor_actions_7d     integer;
  v_audit_writes_30d          integer;
  v_supervisor_count          integer;
  v_pm_compliance_30d         numeric;

  v_has_sensor_readings       boolean;
  v_offline_queue_evidence    boolean;
  v_voice_journal_30d         integer;

  v_history_days              integer;
  v_logbook_hygiene_pct       numeric;
  v_audit_compliant           boolean;
  v_benchmarks_opted_in       boolean;
  v_rcm_strategies_approved   integer;

  v_process_score             smallint;
  v_data_score                smallint;
  v_resilience_score          smallint;
  v_leadership_score          smallint;
  v_cultural_score            smallint;
  v_composite                 smallint;
  v_stair                     smallint;
  v_blocker                   text;
  v_evidence                  jsonb;

  v_today                     date := (timezone('Asia/Manila', now()))::date;
  v_prev                      record;
  v_id                        uuid;
BEGIN
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'compute_hive_readiness: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

  -- ─── Process maturity inputs ──────────────────────────────────────────────
  SELECT count(*) INTO v_asset_count
    FROM public.asset_nodes
    WHERE hive_id = p_hive_id AND status = 'approved';

  SELECT count(DISTINCT pa.id) INTO v_pm_template_count
    FROM public.pm_assets pa
    WHERE pa.hive_id = p_hive_id;

  SELECT count(*) INTO v_logbook_with_knowledge
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND knowledge IS NOT NULL
      AND char_length(trim(knowledge)) > 20;

  SELECT count(*) INTO v_fmea_modes_approved
    FROM public.rcm_fmea_modes
    WHERE hive_id = p_hive_id AND approved_at IS NOT NULL;

  v_process_score := LEAST(100, GREATEST(0, (
      LEAST(40, v_asset_count * 4)                        -- 10 assets = 40 pts
    + LEAST(30, v_pm_template_count * 6)                  -- 5 templates = 30 pts
    + LEAST(20, v_logbook_with_knowledge * 2)             -- 10 SOPs = 20 pts
    + LEAST(10, v_fmea_modes_approved * 1)                -- 10 FMEAs = 10 pts
  )));

  -- ─── Cultural / leadership inputs (logbook-driven) ───────────────────────
  SELECT count(DISTINCT worker_name) INTO v_active_workers_7d
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '7 days';

  SELECT count(*) INTO v_total_members
    FROM public.hive_members
    WHERE hive_id = p_hive_id AND status = 'active';

  SELECT count(*) INTO v_supervisor_count
    FROM public.hive_members
    WHERE hive_id = p_hive_id AND status = 'active' AND role = 'supervisor';

  -- ─── Leadership engagement inputs ────────────────────────────────────────
  SELECT count(*) INTO v_supervisor_actions_7d
    FROM public.hive_audit_log
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '7 days'
      AND action IN ('approve', 'reject', 'kick', 'assign', 'verify');

  SELECT count(*) INTO v_audit_writes_30d
    FROM public.hive_audit_log
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '30 days';

  v_leadership_score := LEAST(100, GREATEST(0, (
      LEAST(50, v_supervisor_actions_7d * 10)             -- 5 approvals/week = 50 pts
    + LEAST(30, v_audit_writes_30d)                       -- 30 writes/month = 30 pts
    + CASE WHEN v_supervisor_count >= 1 THEN 20 ELSE 0 END
  )));

  -- ─── PM compliance (from canonical view) ─────────────────────────────────
  SELECT
    CASE
      WHEN sum(CASE WHEN is_due THEN 1 ELSE 0 END) = 0 THEN 100
      ELSE 100.0 * (1.0 - sum(CASE WHEN is_due THEN 1 ELSE 0 END)::numeric / count(*)::numeric)
    END
  INTO v_pm_compliance_30d
  FROM public.v_pm_compliance_truth
  WHERE hive_id = p_hive_id;
  v_pm_compliance_30d := COALESCE(v_pm_compliance_30d, 0);

  -- ─── Data quality inputs ─────────────────────────────────────────────────
  SELECT count(*) INTO v_logbook_30d
    FROM public.logbook
    WHERE hive_id = p_hive_id
      AND created_at >= now() - interval '30 days';

  -- Logbook hygiene: % with non-empty problem AND root_cause AND action
  IF v_logbook_30d > 0 THEN
    SELECT 100.0 * count(*) / v_logbook_30d INTO v_logbook_hygiene_pct
      FROM public.logbook
      WHERE hive_id = p_hive_id
        AND created_at >= now() - interval '30 days'
        AND problem    IS NOT NULL AND char_length(trim(problem))    > 0
        AND root_cause IS NOT NULL AND char_length(trim(root_cause)) > 0
        AND action     IS NOT NULL AND char_length(trim(action))     > 0;
  ELSE
    v_logbook_hygiene_pct := 0;
  END IF;

  v_data_score := LEAST(100, GREATEST(0, (
      LEAST(40, (v_logbook_hygiene_pct * 0.4)::int)       -- hygiene 100% = 40 pts
    + LEAST(30, v_logbook_30d)                            -- 30 entries/month = 30 pts
    + LEAST(30, (v_pm_compliance_30d * 0.3)::int)         -- 100% PM compliance = 30 pts
  )));

  -- ─── Infrastructure resilience inputs ────────────────────────────────────
  SELECT EXISTS (
    SELECT 1 FROM public.sensor_readings WHERE hive_id = p_hive_id LIMIT 1
  ) INTO v_has_sensor_readings;

  SELECT count(*) > 0 INTO v_offline_queue_evidence
  FROM public.logbook
  WHERE hive_id = p_hive_id
    AND created_at >= now() - interval '30 days'
    AND COALESCE((sync_meta->>'offline_queued')::boolean, false) = true;

  SELECT count(*) INTO v_voice_journal_30d
    FROM public.voice_journal_entries vje
    WHERE vje.hive_id = p_hive_id
      AND vje.created_at >= now() - interval '30 days';

  v_resilience_score := LEAST(100, GREATEST(0, (
      CASE WHEN v_has_sensor_readings    THEN 40 ELSE 0 END
    + CASE WHEN v_offline_queue_evidence THEN 30 ELSE 0 END
    + LEAST(30, v_voice_journal_30d * 3)                  -- 10 voice entries = 30 pts
  )));

  -- ─── Cultural adoption inputs ────────────────────────────────────────────
  v_cultural_score := LEAST(100, GREATEST(0, (
      CASE
        WHEN v_total_members = 0 THEN 0
        WHEN v_total_members > 0 THEN LEAST(60, (100.0 * v_active_workers_7d / v_total_members)::int * 60 / 100)
      END
    + LEAST(40, v_logbook_30d * 2)                        -- 20 entries/month per hive = 40 pts
  )));

  -- ─── History + edge gates for Stair 3+ ───────────────────────────────────
  SELECT EXTRACT(DAY FROM (now() - min(created_at)))::int INTO v_history_days
    FROM public.logbook
    WHERE hive_id = p_hive_id;
  v_history_days := COALESCE(v_history_days, 0);

  SELECT count(*) INTO v_rcm_strategies_approved
    FROM public.rcm_strategies
    WHERE hive_id = p_hive_id AND approved_at IS NOT NULL;

  v_audit_compliant := (v_audit_writes_30d >= 10);  -- placeholder; full compliance audit later
  v_benchmarks_opted_in := false;                    -- Phase 5/6 work; false by default

  -- ─── Composite (weighted) ────────────────────────────────────────────────
  v_composite := LEAST(100, GREATEST(0, (
      (v_process_score    * 25
    +  v_data_score       * 20
    +  v_resilience_score * 15
    +  v_leadership_score * 25
    +  v_cultural_score   * 15) / 100
  )));

  -- ─── Stair derivation (the epistemic gate) ──────────────────────────────
  IF v_asset_count < 10 OR v_composite < 20 THEN
    v_stair := 0;
    v_blocker := format(
      'Register %s more asset(s) and document 1 SOP to unlock Stair 1.',
      GREATEST(0, 10 - v_asset_count)
    );
  ELSIF v_active_workers_7d < 5 OR v_pm_template_count < 5 THEN
    v_stair := 1;
    v_blocker := format(
      '%s of 5 active workers writing entries this week; %s of 5 PM templates registered.',
      v_active_workers_7d, v_pm_template_count
    );
  ELSIF v_pm_compliance_30d < 70 OR v_logbook_hygiene_pct < 80 OR v_supervisor_actions_7d < 5 THEN
    v_stair := 2;
    v_blocker := format(
      'PM compliance %s%% (need 70%%), logbook hygiene %s%% (need 80%%), supervisor actions %s/week (need 5).',
      round(v_pm_compliance_30d)::text, round(v_logbook_hygiene_pct)::text, v_supervisor_actions_7d
    );
  ELSIF v_history_days < 90 AND NOT v_has_sensor_readings THEN
    v_stair := 3;
    v_blocker := format(
      'Either accumulate %s more days of logbook history OR connect a sensor bridge to unlock predictive analytics.',
      GREATEST(0, 90 - v_history_days)
    );
  ELSIF v_rcm_strategies_approved < 10 OR NOT v_audit_compliant OR NOT v_benchmarks_opted_in OR NOT v_has_sensor_readings THEN
    v_stair := 3;
    v_blocker := 'Need all four of: sensor pipeline live, 10+ approved RCM strategies, audit-trail compliant, federated PH benchmarks opted-in.';
  ELSE
    v_stair := 4;
    v_blocker := 'Top of the stack. Maintain the four pillars and consider federated benchmark export.';
  END IF;

  -- ─── Evidence JSONB (for UI + audit replay) ─────────────────────────────
  v_evidence := jsonb_build_object(
    'computed_at',              now(),
    'inputs',                   jsonb_build_object(
      'asset_count',                v_asset_count,
      'pm_template_count',          v_pm_template_count,
      'logbook_with_knowledge',     v_logbook_with_knowledge,
      'fmea_modes_approved',        v_fmea_modes_approved,
      'active_workers_7d',          v_active_workers_7d,
      'total_members',              v_total_members,
      'supervisor_count',           v_supervisor_count,
      'supervisor_actions_7d',      v_supervisor_actions_7d,
      'audit_writes_30d',           v_audit_writes_30d,
      'pm_compliance_30d_pct',      round(v_pm_compliance_30d, 1),
      'logbook_30d',                v_logbook_30d,
      'logbook_hygiene_pct',        round(v_logbook_hygiene_pct, 1),
      'has_sensor_readings',        v_has_sensor_readings,
      'offline_queue_evidence',     v_offline_queue_evidence,
      'voice_journal_30d',          v_voice_journal_30d,
      'history_days',               v_history_days,
      'rcm_strategies_approved',    v_rcm_strategies_approved,
      'audit_compliant',            v_audit_compliant,
      'benchmarks_opted_in',        v_benchmarks_opted_in
    ),
    'scores',                   jsonb_build_object(
      'process_maturity',           v_process_score,
      'data_quality',               v_data_score,
      'infrastructure_resilience',  v_resilience_score,
      'leadership_engagement',      v_leadership_score,
      'cultural_adoption',          v_cultural_score,
      'composite',                  v_composite
    ),
    'thresholds_for_next_stair', CASE v_stair
      WHEN 0 THEN jsonb_build_object('need_assets', 10, 'need_sops', 1)
      WHEN 1 THEN jsonb_build_object('need_active_workers', 5, 'need_pm_templates', 5)
      WHEN 2 THEN jsonb_build_object('need_pm_compliance_pct', 70, 'need_logbook_hygiene_pct', 80, 'need_supervisor_actions_week', 5)
      WHEN 3 THEN jsonb_build_object('need_history_days', 90, 'or_sensors_live', true, 'need_rcm_approved', 10)
      ELSE        jsonb_build_object('maintain', true)
    END
  );

  -- ─── Capture previous snapshot for audit trail ───────────────────────────
  SELECT new_stair AS new_stair, new_composite AS new_composite
    INTO v_prev
    FROM public.hive_readiness_audit
    WHERE hive_id = p_hive_id
    ORDER BY changed_at DESC
    LIMIT 1;

  -- ─── Upsert today's snapshot ─────────────────────────────────────────────
  INSERT INTO public.hive_readiness (
    hive_id, snapshot_date,
    process_maturity_score, data_quality_score, infrastructure_resilience_score,
    leadership_engagement_score, cultural_adoption_score, composite_score,
    current_stair, evidence, blocker_summary, model_version
  ) VALUES (
    p_hive_id, v_today,
    v_process_score, v_data_score, v_resilience_score,
    v_leadership_score, v_cultural_score, v_composite,
    v_stair, v_evidence, v_blocker, 'hrs-v1'
  )
  ON CONFLICT (hive_id, snapshot_date) DO UPDATE SET
    process_maturity_score          = EXCLUDED.process_maturity_score,
    data_quality_score              = EXCLUDED.data_quality_score,
    infrastructure_resilience_score = EXCLUDED.infrastructure_resilience_score,
    leadership_engagement_score     = EXCLUDED.leadership_engagement_score,
    cultural_adoption_score         = EXCLUDED.cultural_adoption_score,
    composite_score                 = EXCLUDED.composite_score,
    current_stair                   = EXCLUDED.current_stair,
    evidence                        = EXCLUDED.evidence,
    blocker_summary                 = EXCLUDED.blocker_summary,
    computed_at                     = now()
  RETURNING id INTO v_id;

  -- ─── Audit-log any stair OR composite jump ≥10 points ───────────────────
  IF v_prev IS NULL
     OR v_prev.new_stair     <> v_stair
     OR abs(v_prev.new_composite - v_composite) >= 10 THEN
    INSERT INTO public.hive_readiness_audit (
      hive_id, previous_stair, new_stair,
      previous_composite, new_composite, reason, evidence_delta
    ) VALUES (
      p_hive_id,
      v_prev.new_stair,     v_stair,
      v_prev.new_composite, v_composite,
      v_blocker,
      v_evidence->'inputs'
    );
  END IF;

  RETURN v_id;
END;
$$;

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
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'export_hive_data: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

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

create or replace function store_memory_turn(
  p_hive_id uuid,
  p_session_id text,
  p_turn_num int,
  p_user_input text,
  p_assistant_response text,
  p_intent text,
  p_confidence real,
  p_response_time_ms int
)
returns json as $$
declare
  v_hash text;
begin
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'store_memory_turn: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

  v_hash := md5(p_user_input);

  insert into agent_memory (
    hive_id, worker_id, session_id, turn_num,
    user_input, user_input_hash, assistant_response,
    intent_classification, intent_confidence, response_time_ms,
    expires_at
  )
  values (
    p_hive_id, auth.uid(), p_session_id, p_turn_num,
    p_user_input, v_hash, p_assistant_response,
    p_intent, p_confidence, p_response_time_ms,
    now() + interval '24 hours'
  );

  return json_build_object(
    'ok', true,
    'turn_num', p_turn_num,
    'session_id', p_session_id
  );
end;
$$ language plpgsql security definer set search_path = public;

create or replace function update_dialog_state(
  p_hive_id uuid,
  p_session_id text,
  p_turn_num int,
  p_intent text,
  p_confidence real,
  p_context_slots jsonb,
  p_clarification_pending boolean default false,
  p_clarification_prompt text default null
)
returns json as $$
declare
  v_exists boolean;
begin
  -- HIVE MEMBERSHIP GATE (cross-hive read/write prevention) --------------
  -- SECURITY DEFINER bypasses RLS, so this fn re-authenticates the caller:
  -- an authenticated user must be an ACTIVE member of p_hive_id. service_role
  -- (trusted edge backend) bypasses; anon has no auth.uid() so it is denied;
  -- NULL hive (solo) skips -- no tenant to leak. See security + multitenant
  -- skills: "SECURITY DEFINER RPCs Must Self-Enforce Hive Membership".
  IF p_hive_id IS NOT NULL
     AND auth.role() <> 'service_role'
     AND NOT EXISTS (
       SELECT 1 FROM public.hive_members
       WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active'
     ) THEN
    RAISE EXCEPTION 'update_dialog_state: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;

  select exists(
    select 1 from dialog_state
    where session_id = p_session_id and worker_id = auth.uid()
  ) into v_exists;

  if v_exists then
    update dialog_state
    set
      current_intent = p_intent,
      intent_confidence = p_confidence,
      context_slots = coalesce(p_context_slots, context_slots),
      clarification_pending = p_clarification_pending,
      clarification_prompt = p_clarification_prompt,
      last_turn_num = p_turn_num,
      updated_at = now()
    where session_id = p_session_id and worker_id = auth.uid();
  else
    insert into dialog_state (
      hive_id, worker_id, session_id, current_intent, intent_confidence,
      context_slots, clarification_pending, clarification_prompt, last_turn_num
    )
    values (
      p_hive_id, auth.uid(), p_session_id, p_intent, p_confidence,
      p_context_slots, p_clarification_pending, p_clarification_prompt, p_turn_num
    );
  end if;

  return json_build_object(
    'ok', true,
    'session_id', p_session_id,
    'intent', p_intent,
    'confidence', p_confidence
  );
end;
$$ language plpgsql security definer set search_path = public;

-- Grant tightening: drop the leftover anon/PUBLIC reach on the three that
-- still had it (the in-function gate already denies anon, but removing the
-- grant shrinks the attack surface). Members are gated above; service_role is
-- the trusted backend (export-hive-data edge fn).
REVOKE EXECUTE ON FUNCTION public.compute_hive_readiness(uuid) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.compute_hive_readiness(uuid) TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.store_memory_turn(uuid, text, int, text, text, text, real, int) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.store_memory_turn(uuid, text, int, text, text, text, real, int) TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.update_dialog_state(uuid, text, int, text, real, jsonb, boolean, text) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.update_dialog_state(uuid, text, int, text, real, jsonb, boolean, text) TO authenticated, service_role;

COMMIT;
