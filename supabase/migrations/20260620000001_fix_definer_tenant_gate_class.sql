-- Arc G (Data/DB UFAI) G1 — close the DEFINER tenant-gate CLASS the acknowledge/suppress_alert fix surfaced.
--
-- The per-DEFINER sweep (validate_definer_tenant_gate.py) found a CLASS of SECURITY DEFINER functions that
-- mutate a hive-scoped table, are user-callable (anon/authenticated EXECUTE), and DO NOT self-gate tenancy —
-- and since DEFINER bypasses RLS with FORCE-RLS=0, each is a cross-tenant abuse vector. Triaged by evidence:
--   * compute_adoption_risk(p_hive_id), compute_anomaly_signals(p_hive_id): frontend-called (hive.html /
--     alert-hub.html) per-hive computes -> add a membership gate (a non-member could recompute/overwrite a
--     victim hive's adoption/anomaly scores + trigger cross-hive compute). service_role/cron bypasses.
--   * store_memory_turn(p_hive_id, ...): voice-handler.js -> writes agent_memory with a CLIENT p_hive_id
--     (worker_id is honestly auth.uid()); gate p_hive_id so a user can't write into another hive's memory.
--   * hard_delete_expired_soft_deletes, increment_community_xp: 0 app callers (server-side helpers; the latter
--     takes a client-controlled XP amount = leaderboard fraud) -> REVOKE anon/authenticated (least privilege).
-- The compute_hive_readiness precedent (20260619000000) revoked ONE sibling; this completes the class.

-- ── compute_adoption_risk: + membership gate ──
CREATE OR REPLACE FUNCTION public.compute_adoption_risk(p_hive_id uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
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
  -- Arc G tenant-gate: authenticated callers may only act on a hive they actively belong to;
  -- service_role (cron/edge) bypasses. anon/non-members/spoofers are blocked (auth.uid() NULL -> no match).
  if coalesce(nullif(current_setting('request.jwt.claims', true), '')::json ->> 'role', '') <> 'service_role'
     and not exists (select 1 from hive_members hm
                     where hm.hive_id = p_hive_id and hm.auth_uid = auth.uid() and hm.status = 'active') then
    raise exception 'not authorized for hive %', p_hive_id using errcode = '42501';
  end if;

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
$function$;

-- ── compute_anomaly_signals: + membership gate ──
CREATE OR REPLACE FUNCTION public.compute_anomaly_signals(p_hive_id uuid)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_today      date := (timezone('Asia/Manila', now()))::date;
  v_count      integer := 0;
  v_row        record;
BEGIN
  -- Arc G tenant-gate: authenticated callers may only act on a hive they actively belong to;
  -- service_role (cron/edge) bypasses. anon/non-members/spoofers are blocked (auth.uid() NULL -> no match).
  if coalesce(nullif(current_setting('request.jwt.claims', true), '')::json ->> 'role', '') <> 'service_role'
     and not exists (select 1 from hive_members hm
                     where hm.hive_id = p_hive_id and hm.auth_uid = auth.uid() and hm.status = 'active') then
    raise exception 'not authorized for hive %', p_hive_id using errcode = '42501';
  end if;

  FOR v_row IN
    WITH base_machines AS (
      SELECT DISTINCT lb.machine
        FROM public.logbook lb
        WHERE lb.hive_id = p_hive_id
          AND lb.machine IS NOT NULL
          AND char_length(trim(lb.machine)) > 0
          AND lb.created_at >= now() - interval '60 days'
      UNION
      SELECT DISTINCT fsa.machine
        FROM public.failure_signature_alerts fsa
        WHERE fsa.hive_id = p_hive_id
          AND fsa.status = 'active'
      UNION
      SELECT DISTINCT an.name AS machine
        FROM public.asset_nodes an
        WHERE an.hive_id = p_hive_id
          AND an.status = 'approved'
          AND an.name IS NOT NULL
    ),
    logbook_cluster AS (
      SELECT lb.machine,
             count(*) AS n,
             LEAST(100, count(*) * 20)::smallint AS score,
             jsonb_agg(jsonb_build_object('date', lb.created_at, 'category', lb.category) ORDER BY lb.created_at DESC) AS items
        FROM public.logbook lb
        WHERE lb.hive_id = p_hive_id
          AND lb.created_at >= now() - interval '14 days'
        GROUP BY lb.machine
        HAVING count(*) >= 3
    ),
    sensor_z AS (
      -- Walkthrough fix: column is `value`, not `reading_value`.
      SELECT sr.asset_id,
             an.name AS machine,
             count(*) AS n_alerts,
             LEAST(100, count(*) * 25)::smallint AS score,
             max(sr.value) AS peak
        FROM public.sensor_readings sr
        LEFT JOIN public.asset_nodes an ON an.id = sr.asset_id
        WHERE sr.hive_id = p_hive_id
          AND sr.recorded_at >= now() - interval '7 days'
          AND sr.value IS NOT NULL
        GROUP BY sr.asset_id, an.name
    ),
    pm_drift AS (
      SELECT pct.asset_name AS machine,
             pct.days_since_last_completion AS days_over,
             LEAST(100, (pct.days_since_last_completion / 7)::int * 10)::smallint AS score
        FROM public.v_pm_compliance_truth pct
        WHERE pct.hive_id = p_hive_id
          AND pct.is_due = true
          AND pct.days_since_last_completion >= 14
    ),
    parts_spend AS (
      -- Walkthrough fix: inventory_transactions has no FK to logbook
      -- (its actual columns are item_id + job_ref text), so we cannot bind
      -- a parts-spend signal to a specific machine without a heuristic
      -- text-match on job_ref. Leaving this CTE empty until the schema
      -- gains a stronger FK or we add an asset_id column to
      -- inventory_transactions. Anomaly Engine 2.0 continues with the
      -- other 4 sources (logbook cluster + sensor zscore + pm drift +
      -- failure signature) which is still meaningful.
      SELECT NULL::text AS machine,
             0::integer AS recent_uses,
             0::smallint AS score
      WHERE false
    ),
    failure_sig AS (
      SELECT fsa.machine,
             count(*) AS active_count,
             LEAST(100, max(CASE WHEN fsa.severity = 'critical' THEN 90
                                 WHEN fsa.severity = 'warning'  THEN 60
                                 ELSE 30 END))::smallint AS score
        FROM public.failure_signature_alerts fsa
        WHERE fsa.hive_id = p_hive_id
          AND fsa.status = 'active'
        GROUP BY fsa.machine
    ),
    fused AS (
      SELECT bm.machine,
             COALESCE(lc.score, 0) AS logbook_cluster_score,
             COALESCE(sz.score, 0) AS sensor_zscore_score,
             COALESCE(pd.score, 0) AS pm_drift_score,
             COALESCE(ps.score, 0) AS parts_spend_score,
             COALESCE(fs.score, 0) AS failure_signature_score,
             COALESCE(sz.asset_id, NULL) AS asset_node_id,
             jsonb_strip_nulls(jsonb_build_object(
               'logbook_cluster',   CASE WHEN lc.score IS NOT NULL THEN jsonb_build_object('n', lc.n, 'recent', lc.items) END,
               'sensor_zscore',     CASE WHEN sz.score IS NOT NULL THEN jsonb_build_object('n_alerts', sz.n_alerts, 'peak', sz.peak) END,
               'pm_drift',          CASE WHEN pd.score IS NOT NULL THEN jsonb_build_object('days_over', pd.days_over) END,
               'parts_spend',       CASE WHEN ps.score IS NOT NULL THEN jsonb_build_object('recent_uses', ps.recent_uses) END,
               'failure_signature', CASE WHEN fs.score IS NOT NULL THEN jsonb_build_object('active_count', fs.active_count) END
             )) AS evidence
        FROM base_machines bm
        LEFT JOIN logbook_cluster lc USING (machine)
        LEFT JOIN sensor_z       sz USING (machine)
        LEFT JOIN pm_drift       pd USING (machine)
        LEFT JOIN parts_spend    ps USING (machine)
        LEFT JOIN failure_sig    fs USING (machine)
    )
    SELECT f.*,
           GREATEST(0, LEAST(100, (
                f.logbook_cluster_score    * 30
              + f.sensor_zscore_score      * 25
              + f.pm_drift_score           * 20
              + f.parts_spend_score        * 15
              + f.failure_signature_score  * 10
           ) / 100))::smallint AS composite_score,
           ( (CASE WHEN f.logbook_cluster_score   >= 35 THEN 1 ELSE 0 END)
           + (CASE WHEN f.sensor_zscore_score     >= 35 THEN 1 ELSE 0 END)
           + (CASE WHEN f.pm_drift_score          >= 35 THEN 1 ELSE 0 END)
           + (CASE WHEN f.parts_spend_score       >= 35 THEN 1 ELSE 0 END)
           + (CASE WHEN f.failure_signature_score >= 35 THEN 1 ELSE 0 END)
           )::smallint AS source_count
      FROM fused f
      WHERE f.logbook_cluster_score + f.sensor_zscore_score
          + f.pm_drift_score + f.parts_spend_score
          + f.failure_signature_score > 0
  LOOP
    INSERT INTO public.anomaly_signals (
      hive_id, snapshot_date, machine, asset_node_id,
      composite_score,
      logbook_cluster_score, sensor_zscore_score, pm_drift_score,
      parts_spend_score, failure_signature_score,
      source_count, severity,
      top_reasons, evidence
    ) VALUES (
      p_hive_id, v_today, v_row.machine, v_row.asset_node_id,
      v_row.composite_score,
      v_row.logbook_cluster_score, v_row.sensor_zscore_score, v_row.pm_drift_score,
      v_row.parts_spend_score, v_row.failure_signature_score,
      v_row.source_count,
      CASE
        WHEN v_row.composite_score >= 75 THEN 'critical'
        WHEN v_row.composite_score >= 50 THEN 'warning'
        WHEN v_row.composite_score >= 25 THEN 'watch'
        ELSE 'info'
      END,
      (SELECT jsonb_agg(elem ORDER BY (elem->>'score')::int DESC)
         FROM jsonb_array_elements(jsonb_build_array(
           jsonb_build_object('signal', 'logbook_cluster',   'score', v_row.logbook_cluster_score,   'label', 'Repeated faults this fortnight'),
           jsonb_build_object('signal', 'sensor_zscore',     'score', v_row.sensor_zscore_score,     'label', 'Sensor readings drifting out of band'),
           jsonb_build_object('signal', 'pm_drift',          'score', v_row.pm_drift_score,          'label', 'PM overdue past category baseline'),
           jsonb_build_object('signal', 'parts_spend',       'score', v_row.parts_spend_score,       'label', 'Parts consumption climbing'),
           jsonb_build_object('signal', 'failure_signature', 'score', v_row.failure_signature_score, 'label', 'Failure signature alert active')
         )) elem
         WHERE (elem->>'score')::int >= 35
      ),
      v_row.evidence
    )
    ON CONFLICT (hive_id, machine, snapshot_date) DO UPDATE
      SET composite_score          = EXCLUDED.composite_score,
          logbook_cluster_score    = EXCLUDED.logbook_cluster_score,
          sensor_zscore_score      = EXCLUDED.sensor_zscore_score,
          pm_drift_score           = EXCLUDED.pm_drift_score,
          parts_spend_score        = EXCLUDED.parts_spend_score,
          failure_signature_score  = EXCLUDED.failure_signature_score,
          source_count             = EXCLUDED.source_count,
          severity                 = EXCLUDED.severity,
          top_reasons              = EXCLUDED.top_reasons,
          evidence                 = EXCLUDED.evidence,
          asset_node_id            = EXCLUDED.asset_node_id,
          computed_at              = now();
    v_count := v_count + 1;
  END LOOP;

  RETURN v_count;
END;
$function$;

-- ── store_memory_turn: + membership gate ──
CREATE OR REPLACE FUNCTION public.store_memory_turn(p_hive_id uuid, p_session_id text, p_turn_num integer, p_user_input text, p_assistant_response text, p_intent text, p_confidence real, p_response_time_ms integer)
 RETURNS json
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_hash text;
begin
  -- Arc G tenant-gate: authenticated callers may only act on a hive they actively belong to;
  -- service_role (cron/edge) bypasses. anon/non-members/spoofers are blocked (auth.uid() NULL -> no match).
  if coalesce(nullif(current_setting('request.jwt.claims', true), '')::json ->> 'role', '') <> 'service_role'
     and not exists (select 1 from hive_members hm
                     where hm.hive_id = p_hive_id and hm.auth_uid = auth.uid() and hm.status = 'active') then
    raise exception 'not authorized for hive %', p_hive_id using errcode = '42501';
  end if;

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
$function$;

-- server-side-only helpers: drop the over-broad user EXECUTE grants
revoke execute on function public.hard_delete_expired_soft_deletes() from anon, authenticated;
revoke execute on function public.increment_community_xp(text, uuid, integer) from anon, authenticated;
