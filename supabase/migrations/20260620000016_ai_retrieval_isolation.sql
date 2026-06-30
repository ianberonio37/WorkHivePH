-- Arc H H1 — close the cross-tenant DEFINER read-IDOR class (OWASP LLM08 + read-path RLS bypass).
--
-- A class of 8 SECURITY DEFINER functions filtered by a CLIENT-supplied p_hive_id with NO membership
-- check, GRANTed to anon+authenticated. DEFINER bypasses RLS, so any user/anon could pass ANOTHER hive's
-- id and read its data cross-tenant. The Arc-G validate_definer_tenant_gate only checked MUTATIONS, so the
-- read path was missed. Found by tools/validate_ai_retrieval_isolation.py; PROVEN live two-tenant
-- (Pablo, hive A, called get_oee_by_machine(hiveB) → 30 of hive B's rows).
--
-- The 8: export_hive_data (whole-hive dump!), get_oee_by_machine, match_procedural_memories,
-- fetch_active_alerts, get_hive_readiness_current, get_adoption_risk_current, semantic_search_kb,
-- semantic_search_kg_facts. Callers: the first 3 are EDGE-ONLY (ai-gateway/analytics via service_role,
-- BYPASSRLS, server-resolved hive) → revoke client roles. The other 5 are FRONTEND-called with the
-- user's JWT (hive.html / voice-handler.js) → add a membership self-gate + revoke anon.
--
-- VERIFIED LIVE (two-tenant) — see the validator + the proof in the session handoff.

-- shared gate: caller is the trusted edge/cron service_role, OR a member of p_hive_id.
create or replace function public.user_can_access_hive(p_hive_id uuid)
returns boolean
language sql
stable
security definer
set search_path to 'public'
as $fn$
  select coalesce(nullif(current_setting('request.jwt.claims', true), '')::json ->> 'role', '') = 'service_role'
      or (p_hive_id is not null and p_hive_id in (select public.user_hive_ids()));
$fn$;
revoke all on function public.user_can_access_hive(uuid) from public;
grant execute on function public.user_can_access_hive(uuid) to anon, authenticated, service_role;

-- ── the 5 FRONTEND-called fns: add the membership self-gate (legit own-hive call passes; cross-hive empty) ──

create or replace function public.fetch_active_alerts(p_hive_id uuid)
 returns table(alert_id bigint, alert_type text, severity text, description text, action_suggested text, deviation_percent real, detected_at timestamp with time zone)
 language plpgsql security definer set search_path to 'public'
as $function$
begin
  if not public.user_can_access_hive(p_hive_id) then return; end if;
  return query
  select aa.id, aa.alert_type, aa.severity, aa.description, aa.action_suggested, aa.deviation_percent, aa.detected_at
  from anomaly_alerts aa
  where aa.hive_id = p_hive_id
    and (aa.suppressed_until is null or aa.suppressed_until < now())
    and aa.acknowledged_at is null
  order by case when aa.severity = 'critical' then 1 when aa.severity = 'high' then 2 when aa.severity = 'medium' then 3 else 4 end,
           aa.detected_at desc
  limit 10;
end;
$function$;

create or replace function public.get_hive_readiness_current(p_hive_id uuid)
 returns hive_readiness language sql security definer set search_path to 'public', 'pg_temp'
as $function$
  select * from public.hive_readiness
  where hive_id = p_hive_id and public.user_can_access_hive(p_hive_id)
  order by snapshot_date desc, computed_at desc limit 1;
$function$;

create or replace function public.get_adoption_risk_current(p_hive_id uuid)
 returns hive_adoption_score language sql stable security definer set search_path to 'public', 'pg_temp'
as $function$
  select * from public.hive_adoption_score
  where hive_id = p_hive_id and public.user_can_access_hive(p_hive_id)
  order by snapshot_date desc limit 1;
$function$;

create or replace function public.semantic_search_kb(p_hive_id uuid, p_query_embedding vector, p_similarity_threshold real default 0.7, p_limit integer default 5)
 returns table(chunk_id bigint, doc_id bigint, doc_title text, chunk_text text, similarity_score real)
 language plpgsql security definer set search_path to 'public'
as $function$
begin
  if not public.user_can_access_hive(p_hive_id) then return; end if;
  return query
  select kc.id, kc.doc_id, kd.title, kc.text, (kc.embedding <=> p_query_embedding) as sim
  from kb_chunks kc join kb_documents kd on kc.doc_id = kd.id
  where kd.hive_id = p_hive_id and kc.embedding is not null
    and (kc.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  order by kc.embedding <=> p_query_embedding
  limit p_limit;
end;
$function$;

create or replace function public.semantic_search_kg_facts(p_hive_id uuid, p_query_embedding vector, p_similarity_threshold real default 0.5, p_limit integer default 5, p_min_confidence real default 0.5)
 returns table(fact_id uuid, subject_ref text, predicate text, object_ref text, claim_text text, confidence numeric, source_type text, source_ref text, similarity_score real)
 language plpgsql security definer set search_path to 'public'
as $function$
begin
  if not public.user_can_access_hive(p_hive_id) then return; end if;
  return query
  select f.id as fact_id, f.subject_ref, f.predicate, f.object_ref, f.claim_text, f.confidence, f.source_type, f.source_ref,
         (f.embedding <=> p_query_embedding)::real as similarity_score
  from public.knowledge_graph_facts f
  where f.hive_id = p_hive_id and f.active = true and f.embedding is not null and f.confidence >= p_min_confidence
    and (f.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  order by f.embedding <=> p_query_embedding
  limit p_limit;
end;
$function$;

-- revoke anon on the 5 frontend fns (logged-in only; the membership gate handles cross-hive)
revoke execute on function public.fetch_active_alerts(uuid) from anon;
revoke execute on function public.get_hive_readiness_current(uuid) from anon;
revoke execute on function public.get_adoption_risk_current(uuid) from anon;
revoke execute on function public.semantic_search_kb(uuid, vector, real, integer) from anon;
revoke execute on function public.semantic_search_kg_facts(uuid, vector, real, integer, real) from anon;

-- ── the 3 EDGE-ONLY fns: only service_role/cron calls them (via the edge, BYPASSRLS). They have large
-- bodies, so instead of an inline gate we REVOKE EXECUTE from PUBLIC + anon + authenticated (Postgres
-- grants functions to PUBLIC by DEFAULT — revoking only anon/authenticated leaves PUBLIC, so a direct
-- authenticated PostgREST call still worked; PUBLIC is the real fix) and GRANT only service_role back. ──
revoke execute on function public.export_hive_data(uuid) from public, anon, authenticated;
revoke execute on function public.get_oee_by_machine(uuid, integer) from public, anon, authenticated;
revoke execute on function public.match_procedural_memories(vector, uuid, text, integer, real) from public, anon, authenticated;
grant execute on function public.export_hive_data(uuid) to service_role;
grant execute on function public.get_oee_by_machine(uuid, integer) to service_role;
grant execute on function public.match_procedural_memories(vector, uuid, text, integer, real) to service_role;

-- compute_hive_readiness — FRONTEND-called (hive.html, user JWT) DEFINER that WRITES
-- hive_readiness + audit by a client p_hive_id with PUBLIC EXECUTE + no gate = cross-tenant
-- WRITE IDOR (the Arc-G mutation gate missed it via the PUBLIC-default blind spot). Add the
-- membership self-gate (own-hive compute passes; cross-hive returns NULL = no write) + revoke anon.
-- (Full body is the live definition with the guard spliced after BEGIN.)
CREATE OR REPLACE FUNCTION public.compute_hive_readiness(p_hive_id uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
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
  if not public.user_can_access_hive(p_hive_id) then return null; end if;
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
$function$;
revoke execute on function public.compute_hive_readiness(uuid) from anon;

-- increment_community_xp — server-side XP helper (no frontend/edge caller) taking a CLIENT p_amount
-- = leaderboard fraud for any worker in any hive. Arc-G ...000001 revoked anon/authenticated but
-- NOT PUBLIC (the same default-grant blind spot), so it stayed callable. Revoke PUBLIC; keep service_role.
revoke execute on function public.increment_community_xp(text, uuid, integer) from public, anon, authenticated;
grant execute on function public.increment_community_xp(text, uuid, integer) to service_role;
