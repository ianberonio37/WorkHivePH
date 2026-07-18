-- Forward fix (2026-06-09): Stair-1 readiness blocker listed SATISFIED criteria
-- as blockers (e.g. '30 of 5 PM templates registered' when 30>=5 is met).
-- Re-defines compute_hive_readiness to emit only UNMET clauses. Body copied
-- from 20260513000001_hive_readiness.sql with the Stair-1 blocker corrected.

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
  -- â”€â”€â”€ Process maturity inputs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  -- â”€â”€â”€ Cultural / leadership inputs (logbook-driven) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  -- â”€â”€â”€ Leadership engagement inputs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  -- â”€â”€â”€ PM compliance (from canonical view) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  SELECT
    CASE
      WHEN sum(CASE WHEN is_due THEN 1 ELSE 0 END) = 0 THEN 100
      ELSE 100.0 * (1.0 - sum(CASE WHEN is_due THEN 1 ELSE 0 END)::numeric / count(*)::numeric)
    END
  INTO v_pm_compliance_30d
  FROM public.v_pm_compliance_truth
  WHERE hive_id = p_hive_id;
  v_pm_compliance_30d := COALESCE(v_pm_compliance_30d, 0);

  -- â”€â”€â”€ Data quality inputs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  -- â”€â”€â”€ Infrastructure resilience inputs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  -- â”€â”€â”€ Cultural adoption inputs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  v_cultural_score := LEAST(100, GREATEST(0, (
      CASE
        WHEN v_total_members = 0 THEN 0
        WHEN v_total_members > 0 THEN LEAST(60, (100.0 * v_active_workers_7d / v_total_members)::int * 60 / 100)
      END
    + LEAST(40, v_logbook_30d * 2)                        -- 20 entries/month per hive = 40 pts
  )));

  -- â”€â”€â”€ History + edge gates for Stair 3+ â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  SELECT EXTRACT(DAY FROM (now() - min(created_at)))::int INTO v_history_days
    FROM public.logbook
    WHERE hive_id = p_hive_id;
  v_history_days := COALESCE(v_history_days, 0);

  SELECT count(*) INTO v_rcm_strategies_approved
    FROM public.rcm_strategies
    WHERE hive_id = p_hive_id AND approved_at IS NOT NULL;

  v_audit_compliant := (v_audit_writes_30d >= 10);  -- placeholder; full compliance audit later
  v_benchmarks_opted_in := false;                    -- Phase 5/6 work; false by default

  -- â”€â”€â”€ Composite (weighted) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  v_composite := LEAST(100, GREATEST(0, (
      (v_process_score    * 25
    +  v_data_score       * 20
    +  v_resilience_score * 15
    +  v_leadership_score * 25
    +  v_cultural_score   * 15) / 100
  )));

  -- â”€â”€â”€ Stair derivation (the epistemic gate) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  IF v_asset_count < 10 OR v_composite < 20 THEN
    v_stair := 0;
    v_blocker := format(
      'Register %s more asset(s) and document 1 SOP to unlock Stair 1.',
      GREATEST(0, 10 - v_asset_count)
    );
  ELSIF v_active_workers_7d < 5 OR v_pm_template_count < 5 THEN
    v_stair := 1;
    -- Only list the criteria that are actually UNMET. Hardcoding both clauses
    -- surfaced a satisfied criterion as a blocker (e.g. "30 of 5 PM templates
    -- registered" when 30 >= 5 is met), which reads as nonsense in the UI.
    v_blocker := nullif(trim(concat_ws(' ',
      CASE WHEN v_active_workers_7d < 5
        THEN format('%s of 5 active workers writing entries this week.', v_active_workers_7d) END,
      CASE WHEN v_pm_template_count < 5
        THEN format('%s of 5 PM templates registered.', v_pm_template_count) END
    )), '');
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

  -- â”€â”€â”€ Evidence JSONB (for UI + audit replay) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  -- â”€â”€â”€ Capture previous snapshot for audit trail â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  SELECT new_stair AS new_stair, new_composite AS new_composite
    INTO v_prev
    FROM public.hive_readiness_audit
    WHERE hive_id = p_hive_id
    ORDER BY changed_at DESC
    LIMIT 1;

  -- â”€â”€â”€ Upsert today's snapshot â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  -- â”€â”€â”€ Audit-log any stair OR composite jump â‰¥10 points â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
