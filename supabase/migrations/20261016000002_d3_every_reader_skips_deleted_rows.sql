-- D3 (2026-10-16), part 2: every reader that bypasses row-level security skips deleted rows.
--
-- 20261016000001 hides a deleted row from every read that runs AS THE PERSON (pages, invoker views, invoker
-- RPCs) with one restrictive policy per table. Three kinds of reader never consult that policy, because the
-- table owner and the service role bypass row-level security:
--   * the truth views when a security-definer function or a service-role edge function reads them - 111 of the
--     edge functions' reads of these tables go through the 13 views below;
--   * security-definer functions that read the tables directly (readiness, adoption risk, anomaly signals,
--     OEE, the hive board, stock moves, the marketplace match, the PM-asset bridge);
--   * service-role edge functions that read the tables directly (patched in the same change, in TypeScript).
-- Each now says "deleted_at IS NULL" itself. A row that hangs off a deleted one (an FMEA mode, a sensor
-- reading, a stock-ledger line, a PM scope item or completion of a deleted asset, part or PM asset) is hidden
-- with it, the way the person sees it, and comes back with it on restore.
-- Counters that must keep counting deleted rows are left as they were: the logbook rate limit and hive quota
-- (a deleted row still occupies the hive until the purge), the photo storage stats, the data export, and
-- delete_worker_data. Forward-only; idempotent (CREATE OR REPLACE).

create or replace view public.v_asset_truth with (security_invoker = true) as
SELECT id AS asset_id,
    hive_id,
    auth_uid,
    parent_id,
    level,
    tag,
    name,
    iso_class,
    criticality,
    location,
    manufacturer,
    model,
    serial_no,
    install_date,
    external_ids,
    legacy_asset_id,
    pm_asset_id,
    status,
    submitted_by,
    approved_by,
    approved_at,
    created_at,
    updated_at,
    ( SELECT count(*) AS count
           FROM logbook l
          WHERE NOT l.hive_id IS DISTINCT FROM n.hive_id AND l.asset_node_id = n.id AND l.deleted_at IS NULL) AS lifetime_logbook_entries,
    ( SELECT max(l.created_at) AS max
           FROM logbook l
          WHERE NOT l.hive_id IS DISTINCT FROM n.hive_id AND l.asset_node_id = n.id AND l.deleted_at IS NULL AND l.maintenance_type = 'Breakdown / Corrective'::text) AS last_failure_at,
    ( SELECT count(*) AS count
           FROM pm_completions pc
          WHERE NOT pc.hive_id IS DISTINCT FROM n.hive_id AND pc.asset_id = n.pm_asset_id AND pc.status = 'done'::text) AS pm_completed_count,
    ( SELECT count(*) AS count
           FROM asset_edges e
          WHERE NOT e.hive_id IS DISTINCT FROM n.hive_id AND (e.from_node_id = n.id OR e.to_node_id = n.id)) AS edge_count,
    ( SELECT count(*) AS count
           FROM pm_completions pc
          WHERE NOT pc.hive_id IS DISTINCT FROM n.hive_id AND pc.asset_id = n.pm_asset_id AND pc.status = 'skipped'::text) AS pm_skipped_count
   FROM asset_nodes n
  WHERE n.status = 'approved'::text AND n.deleted_at IS NULL;

create or replace view public.v_logbook_truth with (security_invoker = true) as
SELECT l.id,
    l.hive_id,
    l.worker_name,
    l.created_at,
    l.closed_at,
    l.date,
    l.status,
    l.maintenance_type,
    l.category,
    l.machine,
    l.problem,
    l.action,
    l.root_cause,
    l.failure_consequence,
    l.downtime_hours,
    l.production_output,
    l.parts_used,
    l.readings_json,
    l.knowledge,
    l.tasklist_acknowledged,
    l.tasklist_note,
    l.photo,
    l.pm_completion_id,
    l.wo_state,
    l.wo_assigned_to,
    l.asset_node_id,
    n.tag AS asset_tag,
    n.name AS asset_node_name,
    n.iso_class AS asset_iso_class,
    n.criticality AS asset_criticality,
    n.location AS asset_location,
    l.maintenance_type ~* '(corrective|breakdown)'::text AS is_corrective,
    l.loto_applied,
    l.permit_reference,
    l.auth_uid
   FROM logbook l
     LEFT JOIN asset_nodes n ON n.id = l.asset_node_id AND n.deleted_at IS NULL
  WHERE l.deleted_at IS NULL;

create or replace view public.v_fmea_truth with (security_invoker = true) as
SELECT m.id AS fmea_mode_id,
    m.hive_id,
    m.asset_id,
    n.tag AS asset_tag,
    n.name AS asset_name,
    n.iso_class,
    n.criticality AS asset_criticality,
    m.function_text,
    m.failure_mode,
    m.effect_text,
    m.cause_text,
    m.severity,
    m.occurrence,
    m.detection,
    m.rpn,
    m.consequence_class,
    m.source,
    m.ai_confidence,
    m.created_at,
    m.updated_at,
    m.approved_at,
    m.approved_by
   FROM rcm_fmea_modes m
     LEFT JOIN asset_nodes n ON n.id = m.asset_id AND n.deleted_at IS NULL
  WHERE m.approved_at IS NOT NULL AND (m.asset_id IS NULL OR n.id IS NOT NULL);

create or replace view public.v_hives_truth with (security_invoker = true) as
SELECT id,
    name,
    invite_code,
    created_by,
    created_at,
    intent,
    preferred_persona,
    ( SELECT count(*)::integer AS count
           FROM hive_members hm
          WHERE hm.hive_id = h.id AND hm.status = 'active'::text) AS member_count,
    ( SELECT count(*)::integer AS count
           FROM asset_nodes an
          WHERE an.hive_id = h.id AND an.status = 'approved'::text AND an.deleted_at IS NULL) AS asset_count,
    ( SELECT min(hm.joined_at) AS min
           FROM hive_members hm
          WHERE hm.hive_id = h.id AND hm.status = 'active'::text) AS first_member_joined_at,
    intent = '{}'::jsonb AS intent_not_captured,
    updated_at
   FROM hives h;

create or replace view public.v_risk_truth with (security_invoker = true) as
SELECT DISTINCT ON (rs.hive_id, rs.asset_name) n.id AS asset_id,
    rs.hive_id,
    rs.asset_name,
    rs.risk_score,
    rs.risk_level,
    rs.health_score,
    rs.mtbf_days,
    rs.days_until_failure,
    rs.top_factors,
    rs.components,
    rs.model_version,
    rs.generated_at
   FROM asset_risk_scores rs
     LEFT JOIN asset_nodes n ON n.hive_id = rs.hive_id AND (lower(n.tag) = lower(rs.asset_name) OR lower(n.name) = lower(rs.asset_name)) AND n.status = 'approved'::text AND n.deleted_at IS NULL
  ORDER BY rs.hive_id, rs.asset_name, rs.generated_at DESC;

create or replace view public.v_sensor_recent with (security_invoker = true) as
SELECT sr.id,
    sr.hive_id,
    sr.asset_id,
    sr.parameter,
    sr.value,
    sr.recorded_at,
    sr.source,
    sr.meta,
    n.tag AS asset_tag,
    n.name AS asset_name,
    n.iso_class,
    sr.unit
   FROM sensor_readings sr
     LEFT JOIN asset_nodes n ON n.id = sr.asset_id AND n.deleted_at IS NULL
  WHERE sr.recorded_at >= (now() - '30 days'::interval) AND (sr.asset_id IS NULL OR n.id IS NOT NULL);

create or replace view public.v_inventory_items_truth with (security_invoker = true) as
SELECT id,
    hive_id,
    worker_name,
    part_number,
    part_name,
    category,
    unit,
    qty_on_hand,
    min_qty,
    min_qty AS reorder_point,
    bin_location,
    linked_asset_node_ids,
    notes,
    photo,
    status,
    submitted_by,
    approved_by,
    approved_at,
    created_at,
    updated_at,
    qty_on_hand <= 0::numeric AS is_out_of_stock,
    qty_on_hand <= 0::numeric OR min_qty > 0::numeric AND qty_on_hand <= min_qty AS is_low_stock,
    min_qty > 0::numeric AND qty_on_hand <= (min_qty / 2.0) AS is_critical_low,
    lead_time_days,
    rejection_reason,
    auth_uid
   FROM inventory_items i
  WHERE i.deleted_at IS NULL;

create or replace view public.v_inventory_transactions_truth with (security_invoker = true) as
SELECT t.id,
    t.hive_id,
    t.worker_name,
    t.auth_uid,
    t.item_id,
    t.type,
    t.qty_change,
    t.qty_after,
    t.note,
    t.job_ref,
    t.created_at,
    i.part_name AS item_part_name,
    i.part_number AS item_part_number,
    i.category AS item_category,
    i.unit AS item_unit,
    t.type = 'consume'::text AS is_consume,
    t.type = 'restock'::text AS is_restock,
    t.type = 'adjust'::text AS is_adjust,
        CASE
            WHEN t.type = 'consume'::text THEN - abs(t.qty_change)
            ELSE abs(t.qty_change)
        END AS qty_delta
   FROM inventory_transactions t
     LEFT JOIN inventory_items i ON i.id = t.item_id AND i.deleted_at IS NULL
  WHERE t.item_id IS NULL OR i.id IS NOT NULL;

create or replace view public.v_pm_compliance_truth with (security_invoker = true) as
SELECT pa.hive_id,
    pa.id AS pm_asset_id,
    pa.asset_name,
    pa.tag_id,
    pa.category,
    pa.criticality,
    pa.location,
    pa.last_anchor_date,
        CASE
            WHEN max(pc.completed_at) FILTER (WHERE pc.status = 'done'::text) IS NULL THEN NULL::integer
            ELSE now()::date - max(pc.completed_at) FILTER (WHERE pc.status = 'done'::text)::date
        END AS days_since_last_completion,
    count(pc.id) FILTER (WHERE pc.status = 'done'::text) AS lifetime_completions,
    count(pc.id) FILTER (WHERE pc.status = 'done'::text AND pc.completed_at >= (now() - '30 days'::interval)) AS completions_30d,
    count(pc.id) FILTER (WHERE pc.status = 'done'::text AND pc.completed_at >= (now() - '90 days'::interval)) AS completions_90d,
    count(pc.id) FILTER (WHERE pc.status = 'done'::text AND pc.completed_at >= (now() - '365 days'::interval)) AS completions_365d,
    max(pc.completed_at) FILTER (WHERE pc.status = 'done'::text) AS last_completion_at,
        CASE
            WHEN pa.last_anchor_date IS NULL THEN true
            WHEN pa.last_anchor_date < (now()::date - '30 days'::interval)::date THEN true
            ELSE false
        END AS is_due,
    count(pc.id) FILTER (WHERE pc.status = 'skipped'::text) AS lifetime_skips,
    count(pc.id) FILTER (WHERE pc.status = 'skipped'::text AND pc.completed_at >= (now() - '30 days'::interval)) AS skips_30d,
    count(pc.id) FILTER (WHERE pc.status = 'skipped'::text AND pc.completed_at >= (now() - '90 days'::interval)) AS skips_90d,
    max(pc.completed_at) FILTER (WHERE pc.status = 'skipped'::text) AS last_skip_at
   FROM pm_assets pa
     LEFT JOIN pm_completions pc ON pc.asset_id = pa.id AND pc.hive_id = pa.hive_id
  WHERE pa.deleted_at IS NULL
  GROUP BY pa.hive_id, pa.id, pa.asset_name, pa.tag_id, pa.category, pa.criticality, pa.location, pa.last_anchor_date;

create or replace view public.v_project_truth with (security_invoker = true) as
SELECT id AS project_id,
    hive_id,
    project_code,
    name,
    project_type,
    status,
    priority,
    owner_name,
    start_date,
    end_date AS target_end_date,
    closed_at AS actual_end_at,
    created_at,
    updated_at,
    ( SELECT count(*) AS count
           FROM project_items pi
          WHERE pi.project_id = p.id) AS item_count,
    ( SELECT count(*) AS count
           FROM project_items pi
          WHERE pi.project_id = p.id AND pi.status = 'done'::text) AS items_done,
    ( SELECT COALESCE(sum(pi.estimated_hours), 0::numeric) AS "coalesce"
           FROM project_items pi
          WHERE pi.project_id = p.id) AS estimated_total_hours,
    ( SELECT COALESCE(sum(pi.actual_hours), 0::numeric) AS "coalesce"
           FROM project_items pi
          WHERE pi.project_id = p.id) AS actual_total_hours,
    ( SELECT max(ppl.created_at) AS max
           FROM project_progress_logs ppl
          WHERE ppl.project_id = p.id) AS last_progress_at,
    ( SELECT count(*) AS count
           FROM project_change_orders pco
          WHERE pco.project_id = p.id AND pco.status = 'approved'::text) AS approved_change_orders,
    ( SELECT COALESCE(sum(pco.cost_impact_php), 0::numeric) AS "coalesce"
           FROM project_change_orders pco
          WHERE pco.project_id = p.id AND pco.status = 'approved'::text) AS approved_co_cost_php,
    ( SELECT count(*) AS count
           FROM project_links pl
          WHERE pl.project_id = p.id AND pl.deleted_at IS NULL) AS link_count,
        CASE
            WHEN project_type = ANY (ARRAY['capex'::text, 'contractor'::text]) THEN 'project'::text
            WHEN project_type = 'shutdown'::text THEN 'preventive'::text
            WHEN project_type = 'workorder'::text AND (EXISTS ( SELECT 1
               FROM project_links pl
              WHERE pl.project_id = p.id AND pl.link_type = 'logbook'::text AND pl.deleted_at IS NULL)) THEN 'reactive'::text
            WHEN project_type = 'workorder'::text AND (EXISTS ( SELECT 1
               FROM project_links pl
              WHERE pl.project_id = p.id AND pl.link_type = 'pm_completion'::text AND pl.deleted_at IS NULL)) THEN 'preventive'::text
            ELSE 'reactive'::text
        END AS maintenance_nature
   FROM projects p
  WHERE deleted_at IS NULL AND status <> 'archived'::text;

create or replace view public.v_hive_value_summary with (security_invoker = true) as
SELECT id AS hive_id,
    name AS hive_name,
    ( SELECT count(*) AS count
           FROM pm_completions pc
          WHERE pc.hive_id = h.id AND pc.status = 'done'::text) AS pms_kept,
    ( SELECT count(*) AS count
           FROM logbook lb
          WHERE lb.hive_id = h.id AND lb.status = 'Closed'::text AND lb.deleted_at IS NULL) AS faults_resolved,
    ( SELECT count(*) AS count
           FROM fault_knowledge fk
          WHERE fk.hive_id = h.id) AS knowledge_written
   FROM hives h;

create or replace view public.v_worker_assignment_truth with (security_invoker = true) as
WITH recent_logbook AS (
         SELECT logbook.hive_id,
            logbook.worker_name,
            count(*) AS jobs_30d,
            count(*) FILTER (WHERE logbook.status = ANY (ARRAY['Open'::text, 'In Progress'::text])) AS open_jobs,
            max(logbook.created_at) AS last_job_at,
            count(DISTINCT logbook.asset_node_id) AS assets_touched_30d,
            sum(COALESCE(logbook.downtime_hours, 0::numeric)) AS total_downtime_hours_30d,
            (array_agg(logbook.category ORDER BY logbook.created_at DESC))[1] AS last_category
           FROM logbook
          WHERE logbook.created_at >= (now() - '30 days'::interval) AND logbook.deleted_at IS NULL
          GROUP BY logbook.hive_id, logbook.worker_name
        ), recent_pm AS (
         SELECT pm_completions.hive_id,
            pm_completions.worker_name,
            count(*) AS pms_30d,
            max(pm_completions.completed_at) AS last_pm_at
           FROM pm_completions
          WHERE pm_completions.completed_at >= (now() - '30 days'::interval)
          GROUP BY pm_completions.hive_id, pm_completions.worker_name
        )
 SELECT wih.hive_id,
    wih.worker_name,
    wih.role,
    wih.joined_at,
    COALESCE(rl.jobs_30d, 0::bigint) AS jobs_30d,
    COALESCE(rl.open_jobs, 0::bigint) AS open_jobs,
    COALESCE(rl.assets_touched_30d, 0::bigint) AS assets_touched_30d,
    COALESCE(rl.total_downtime_hours_30d, 0::numeric) AS total_downtime_hours_30d,
    rl.last_category,
    rl.last_job_at,
    COALESCE(rp.pms_30d, 0::bigint) AS pms_30d,
    rp.last_pm_at,
        CASE
            WHEN COALESCE(rl.open_jobs, 0::bigint) > 5 THEN 'overloaded'::text
            WHEN COALESCE(rl.jobs_30d, 0::bigint) = 0 THEN 'idle'::text
            WHEN COALESCE(rl.open_jobs, 0::bigint) >= 1 AND COALESCE(rl.open_jobs, 0::bigint) <= 5 THEN 'available'::text
            ELSE 'free'::text
        END AS capacity_signal
   FROM hive_members wih
     LEFT JOIN recent_logbook rl ON rl.hive_id = wih.hive_id AND rl.worker_name = wih.worker_name
     LEFT JOIN recent_pm rp ON rp.hive_id = wih.hive_id AND rp.worker_name = wih.worker_name
  WHERE wih.status = 'active'::text;

create or replace view public.v_pm_scope_items_truth with (security_invoker = true) as
SELECT scope_item_id,
    scope_item_id AS id,
    hive_id,
    pm_asset_id,
    pm_asset_id AS asset_id,
    item_text,
    frequency,
    anchor_date,
    is_custom,
    created_at,
    asset_name,
    asset_tag,
    asset_category,
    asset_criticality,
    asset_location,
    frequency_days,
    last_completed_at,
    last_completed_by,
    next_due_date,
    next_due_date - (now() AT TIME ZONE 'Asia/Manila'::text)::date AS days_until_due,
        CASE
            WHEN interval_kind <> 'meter'::text THEN next_due_date < (now() AT TIME ZONE 'Asia/Manila'::text)::date
            ELSE false
        END OR interval_km IS NOT NULL AND current_km IS NOT NULL AND current_km >= next_due_km AS is_overdue,
        CASE
            WHEN interval_kind <> 'meter'::text THEN next_due_date >= (now() AT TIME ZONE 'Asia/Manila'::text)::date AND next_due_date <= ((now() AT TIME ZONE 'Asia/Manila'::text)::date + '14 days'::interval)::date
            ELSE false
        END OR interval_km IS NOT NULL AND current_km IS NOT NULL AND current_km >= (next_due_km - 500::numeric) AND current_km < next_due_km AS is_due_soon,
    interval_km,
    interval_kind,
    next_due_km,
    current_km,
        CASE
            WHEN interval_km IS NOT NULL AND current_km IS NOT NULL THEN next_due_km - current_km
            ELSE NULL::numeric
        END AS km_until_due
   FROM ( SELECT base.scope_item_id,
            base.hive_id,
            base.pm_asset_id,
            base.item_text,
            base.frequency,
            base.anchor_date,
            base.is_custom,
            base.created_at,
            base.asset_name,
            base.asset_tag,
            base.asset_category,
            base.asset_criticality,
            base.asset_location,
            base.frequency_days,
            base.interval_km,
            base.interval_kind,
            base.last_completed_at,
            base.last_completed_by,
            base.last_meter,
            base.current_km,
            base.baseline_km,
            (COALESCE(base.last_completed_at::date, base.anchor_date, base.created_at::date) + base.frequency_days::double precision * '1 day'::interval)::date AS next_due_date,
                CASE
                    WHEN base.interval_km IS NOT NULL THEN COALESCE(base.last_meter, base.baseline_km, 0::numeric) + base.interval_km
                    ELSE NULL::numeric
                END AS next_due_km
           FROM ( SELECT s.id AS scope_item_id,
                    s.hive_id,
                    s.asset_id AS pm_asset_id,
                    s.item_text,
                    s.frequency,
                    s.anchor_date,
                    s.is_custom,
                    s.created_at,
                    pa.asset_name,
                    pa.tag_id AS asset_tag,
                    pa.category AS asset_category,
                    pa.criticality AS asset_criticality,
                    pa.location AS asset_location,
                        CASE lower(TRIM(BOTH FROM s.frequency))
                            WHEN 'daily'::text THEN 1
                            WHEN 'weekly'::text THEN 7
                            WHEN 'biweekly'::text THEN 14
                            WHEN 'fortnightly'::text THEN 14
                            WHEN 'monthly'::text THEN 30
                            WHEN 'quarterly'::text THEN 90
                            WHEN 'semi-annual'::text THEN 180
                            WHEN 'semiannual'::text THEN 180
                            WHEN 'semi annual'::text THEN 180
                            WHEN 'annual'::text THEN 365
                            WHEN 'yearly'::text THEN 365
                            ELSE 30
                        END AS frequency_days,
                    s.interval_km,
                    s.interval_kind,
                    last_pc.last_completed_at,
                    last_pc.last_completed_by,
                    last_pc.last_meter,
                    NULLIF(veh.vehicle_meta ->> 'odometer_km'::text, ''::text)::numeric AS current_km,
                    NULLIF(veh.vehicle_meta ->> 'odometer_baseline_km'::text, ''::text)::numeric AS baseline_km
                   FROM pm_scope_items s
                     LEFT JOIN pm_assets pa ON pa.id = s.asset_id AND pa.deleted_at IS NULL
                     LEFT JOIN LATERAL ( SELECT n.vehicle_meta
                           FROM asset_nodes n
                          WHERE n.pm_asset_id = pa.id AND n.vehicle_meta IS NOT NULL AND n.deleted_at IS NULL
                          ORDER BY n.created_at
                         LIMIT 1) veh ON true
                     LEFT JOIN LATERAL ( SELECT pc.completed_at AS last_completed_at,
                            pc.worker_name AS last_completed_by,
                            pc.meter_at_completion AS last_meter
                           FROM pm_completions pc
                          WHERE pc.scope_item_id = s.id AND pc.status = 'done'::text
                          ORDER BY pc.completed_at DESC
                         LIMIT 1) last_pc ON true
                  WHERE s.asset_id IS NULL OR pa.id IS NOT NULL) base) sub;

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
        WHERE lb.hive_id = p_hive_id AND lb.deleted_at IS NULL
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
        WHERE an.hive_id = p_hive_id AND an.deleted_at IS NULL
          AND an.status = 'approved'
          AND an.name IS NOT NULL
    ),
    logbook_cluster AS (
      SELECT lb.machine,
             count(*) AS n,
             LEAST(100, count(*) * 20)::smallint AS score,
             jsonb_agg(jsonb_build_object('date', lb.created_at, 'category', lb.category) ORDER BY lb.created_at DESC) AS items
        FROM public.logbook lb
        WHERE lb.hive_id = p_hive_id AND lb.deleted_at IS NULL
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
        LEFT JOIN public.asset_nodes an ON an.id = sr.asset_id AND an.deleted_at IS NULL
        WHERE sr.hive_id = p_hive_id AND (sr.asset_id IS NULL OR an.id IS NOT NULL)
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
      COALESCE((SELECT jsonb_agg(elem ORDER BY (elem->>'score')::int DESC)
         FROM jsonb_array_elements(jsonb_build_array(
           jsonb_build_object('signal', 'logbook_cluster',   'score', v_row.logbook_cluster_score,   'label', 'Repeated faults this fortnight'),
           jsonb_build_object('signal', 'sensor_zscore',     'score', v_row.sensor_zscore_score,     'label', 'Sensor readings drifting out of band'),
           jsonb_build_object('signal', 'pm_drift',          'score', v_row.pm_drift_score,          'label', 'PM overdue past category baseline'),
           jsonb_build_object('signal', 'parts_spend',       'score', v_row.parts_spend_score,       'label', 'Parts consumption climbing'),
           jsonb_build_object('signal', 'failure_signature', 'score', v_row.failure_signature_score, 'label', 'Failure signature alert active')
         )) elem
         WHERE (elem->>'score')::int >= 35
      ), '[]'::jsonb),
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

CREATE OR REPLACE FUNCTION public.get_oee_by_machine(p_hive_id uuid, p_period_days integer DEFAULT 90)
 RETURNS TABLE(machine text, availability_pct numeric, performance_pct numeric, quality_pct numeric, oee_pct numeric, is_partial boolean)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
  WITH params AS (
    SELECT (p_period_days * 8.0)::numeric AS total_hours
  ),
  downtime AS (
    SELECT l.machine, COALESCE(SUM(NULLIF(l.downtime_hours::text, '')::numeric), 0) AS dt_hours
    FROM public.logbook l
    WHERE l.hive_id = p_hive_id AND l.deleted_at IS NULL AND l.maintenance_type = 'Breakdown / Corrective'
      AND l.created_at >= NOW() - (p_period_days || ' days')::interval
    GROUP BY l.machine
  ),
  quality AS (
    SELECT l.machine,
      AVG(
        CASE
          WHEN (l.production_output ->> 'quality_pct') ~ '^[0-9]+(\.[0-9]+)?$'
            THEN (l.production_output ->> 'quality_pct')::numeric
          -- Derive from good/total when explicit quality_pct is missing (matches
          -- descriptive.calc_oee; seeders/UI write this shape, not quality_pct).
          WHEN (l.production_output ->> 'good_units')  ~ '^[0-9]+(\.[0-9]+)?$'
           AND (l.production_output ->> 'total_units') ~ '^[0-9]+(\.[0-9]+)?$'
           AND (l.production_output ->> 'total_units')::numeric > 0
            THEN ROUND((l.production_output ->> 'good_units')::numeric / (l.production_output ->> 'total_units')::numeric * 100.0, 1)
          ELSE NULL
        END
      ) AS quality_avg,
      SUM(CASE WHEN (l.production_output ->> 'units_produced') ~ '^[0-9]+(\.[0-9]+)?$'
               THEN (l.production_output ->> 'units_produced')::numeric ELSE 0 END) AS units_total
    FROM public.logbook l
    WHERE l.hive_id = p_hive_id AND l.deleted_at IS NULL
      AND l.maintenance_type = 'Breakdown / Corrective'   -- corrective-scoped, matches the Python engine
      AND l.created_at >= NOW() - (p_period_days || ' days')::interval
    GROUP BY l.machine
  ),
  rate AS (
    SELECT n.tag AS machine, n.ideal_cycle_time_seconds AS ideal_sec
    FROM public.asset_nodes n
    WHERE n.hive_id = p_hive_id AND n.deleted_at IS NULL AND n.ideal_cycle_time_seconds IS NOT NULL
  ),
  combined AS (
    SELECT COALESCE(d.machine, q.machine, r.machine) AS machine,
      ROUND(GREATEST(0, LEAST(100,
        ((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0))
        / NULLIF((SELECT total_hours FROM params), 0) * 100))::numeric, 1) AS availability_pct,
      CASE
        WHEN r.ideal_sec IS NOT NULL AND q.units_total IS NOT NULL AND q.units_total > 0
         AND ((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0)) > 0
        THEN ROUND(LEAST(100,
          (r.ideal_sec * q.units_total)
          / (((SELECT total_hours FROM params) - COALESCE(d.dt_hours, 0)) * 3600) * 100)::numeric, 1)
        ELSE NULL
      END AS performance_pct,
      ROUND(LEAST(100, COALESCE(q.quality_avg, NULL))::numeric, 1) AS quality_pct,
      r.ideal_sec
    FROM downtime d
    FULL OUTER JOIN quality q ON d.machine = q.machine
    FULL OUTER JOIN rate    r ON COALESCE(d.machine, q.machine) = r.machine
  )
  SELECT c.machine, c.availability_pct, c.performance_pct, c.quality_pct,
    CASE
      WHEN c.performance_pct IS NOT NULL AND c.availability_pct IS NOT NULL AND c.quality_pct IS NOT NULL
        THEN ROUND((c.availability_pct * c.performance_pct * c.quality_pct / 10000)::numeric, 1)
      WHEN c.availability_pct IS NOT NULL AND c.quality_pct IS NOT NULL
        THEN ROUND((c.availability_pct * c.quality_pct / 100)::numeric, 1)
      ELSE NULL
    END AS oee_pct,
    (c.performance_pct IS NULL) AS is_partial
  FROM combined c
  WHERE c.machine IS NOT NULL
  ORDER BY c.machine;
$function$;

CREATE OR REPLACE FUNCTION public.get_marketplace_parts_for_my_assets(p_hive_id uuid)
 RETURNS TABLE(listing_id uuid, title text, part_number text, category text, price numeric, location text, seller_name text)
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO ''
AS $function$
  SELECT DISTINCT ON (l.id)
    l.id, l.title, l.part_number, l.category, l.price, l.location, l.seller_name
  FROM public.marketplace_listings l
  JOIN public.inventory_items i
    ON  i.hive_id = p_hive_id
    AND i.deleted_at IS NULL
    AND i.part_number IS NOT NULL
    AND l.part_number IS NOT NULL
    AND upper(btrim(i.part_number)) = upper(btrim(l.part_number))
  WHERE l.status = 'published'
    AND l.section = 'parts'
    AND l.hive_id IS DISTINCT FROM p_hive_id            -- never recommend the viewer's own listings
    AND EXISTS (                                        -- caller must be an active member of p_hive_id
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = p_hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  ORDER BY l.id, l.created_at DESC
  LIMIT 24;
$function$;

CREATE OR REPLACE FUNCTION public.inventory_restock(p_item_id text, p_qty numeric, p_note text DEFAULT NULL::text, p_txn_id text DEFAULT NULL::text)
 RETURNS numeric
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_qty numeric; v_hive uuid; v_worker text; v_uid uuid := auth.uid();
BEGIN
  IF p_qty IS NULL OR p_qty <= 0 THEN
    RAISE EXCEPTION 'inventory_restock: qty must be > 0' USING ERRCODE = '22023';
  END IF;
  SELECT qty_on_hand, hive_id, worker_name INTO v_qty, v_hive, v_worker
    FROM public.inventory_items WHERE id = p_item_id AND deleted_at IS NULL FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'inventory_restock: item % not found', p_item_id USING ERRCODE = 'P0002';
  END IF;
  -- Tenancy self-scope (DEFINER bypasses RLS, so re-check membership here).
  IF v_hive IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = v_hive AND hm.auth_uid = v_uid AND hm.status = 'active') THEN
    RAISE EXCEPTION 'inventory_restock: caller is not an active member of the item''s hive'
      USING ERRCODE = '42501';
  END IF;
  v_qty := v_qty + p_qty;
  UPDATE public.inventory_items SET qty_on_hand = v_qty, updated_at = now() WHERE id = p_item_id;
  INSERT INTO public.inventory_transactions
    (id, item_id, worker_name, hive_id, qty_change, qty_after, type, note, auth_uid)
  VALUES
    (COALESCE(p_txn_id, gen_random_uuid()::text), p_item_id, COALESCE(v_worker, 'system'),
     v_hive, p_qty, v_qty, 'restock', p_note, v_uid);
  RETURN v_qty;
END; $function$;

CREATE OR REPLACE FUNCTION public.inventory_deduct(p_item_id text, p_qty numeric, p_note text DEFAULT NULL::text, p_job_ref text DEFAULT NULL::text, p_type text DEFAULT 'use'::text, p_txn_id text DEFAULT NULL::text)
 RETURNS numeric
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_qty    numeric;
  v_hive   uuid;
  v_worker text;
  v_actor  text;
  v_before numeric;
  v_moved  numeric;
  v_uid    uuid := auth.uid();
BEGIN
  IF p_qty IS NULL OR p_qty < 0 THEN
    RAISE EXCEPTION 'inventory_deduct: qty must be >= 0' USING ERRCODE = '22023';
  END IF;

  SELECT qty_on_hand, hive_id, worker_name
    INTO v_qty, v_hive, v_worker
    FROM public.inventory_items
   WHERE id = p_item_id AND deleted_at IS NULL
   FOR UPDATE;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'inventory_deduct: item % not found', p_item_id USING ERRCODE = 'P0002';
  END IF;

  IF v_hive IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM public.hive_members hm
         WHERE hm.hive_id = v_hive
           AND hm.auth_uid = v_uid
           AND hm.status = 'active'
     ) THEN
    RAISE EXCEPTION 'inventory_deduct: caller is not an active member of the item''s hive'
      USING ERRCODE = '42501';
  END IF;

  -- T11 fix: attribute to the ACTOR, resolved from their auth_uid in the item's hive (the
  -- same JWT->name mapping the XP/exam paths use). Fall back to the item owner only for a
  -- system/service write with no member name (v_uid null or unresolved).
  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.hive_id = v_hive AND hm.auth_uid = v_uid AND hm.status = 'active'
   LIMIT 1;

  v_before := v_qty;
  v_qty    := GREATEST(0, v_qty - p_qty);
  v_moved  := v_before - v_qty;

  UPDATE public.inventory_items
     SET qty_on_hand = v_qty, updated_at = now()
   WHERE id = p_item_id;

  INSERT INTO public.inventory_transactions
    (id, item_id, worker_name, hive_id, qty_change, qty_after, type, note, job_ref, auth_uid)
  VALUES
    (COALESCE(p_txn_id, gen_random_uuid()::text), p_item_id, COALESCE(v_actor, v_worker, 'system'),
     v_hive, -v_moved, v_qty, COALESCE(p_type, 'use'), p_note, p_job_ref, v_uid);

  RETURN v_qty;
END;
$function$;

CREATE OR REPLACE FUNCTION public.ensure_pm_asset_for_node(p_node_id uuid)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_node   public.asset_nodes%ROWTYPE;
  v_target text;
  v_id     uuid;
BEGIN
  SELECT * INTO v_node FROM public.asset_nodes WHERE id = p_node_id AND deleted_at IS NULL;
  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  -- Caller must be an active member of the node's hive. auth.uid() IS NULL = server-to-server.
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id  = v_node.hive_id
          AND hm.auth_uid = auth.uid()
          AND hm.status   = 'active'
     ) THEN
    RAISE EXCEPTION 'ensure_pm_asset_for_node: caller is not an active member of that hive'
      USING ERRCODE = '42501';
  END IF;

  IF v_node.pm_asset_id IS NOT NULL THEN
    RETURN v_node.pm_asset_id;
  END IF;

  v_target := NULLIF(btrim(COALESCE(v_node.tag, v_node.name, '')), '');

  -- Prefer an existing asset with the same name in the same hive, and link the node to it.
  IF v_target IS NOT NULL THEN
    SELECT pa.id INTO v_id
      FROM public.pm_assets pa
     WHERE pa.hive_id = v_node.hive_id
       AND pa.deleted_at IS NULL
       AND pa.asset_name = v_target
     LIMIT 1;
  END IF;

  -- Otherwise create one FROM THE NODE. Every value is read here, not supplied by the caller.
  IF v_id IS NULL THEN
    INSERT INTO public.pm_assets
      (hive_id, worker_name, auth_uid, asset_name, tag_id, location, category, criticality)
    VALUES
      (v_node.hive_id,
       COALESCE(v_node.worker_name, 'system'),
       v_node.auth_uid,
       COALESCE(v_target, 'Untitled asset'),
       v_node.tag,
       v_node.location,
       COALESCE(v_node.iso_class, 'Other'),
       COALESCE(v_node.criticality, 'Major'))
    RETURNING id INTO v_id;
  END IF;

  UPDATE public.asset_nodes SET pm_asset_id = v_id
   WHERE id = p_node_id AND hive_id = v_node.hive_id;

  RETURN v_id;
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_hive_board_dashboard(p_hive_id uuid)
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_role      text;
  v_is_sup    boolean;
  v_caller    text;
  v_readiness jsonb;
  v_adoption  jsonb;
  v_result    jsonb;
BEGIN
  SELECT role INTO v_role
  FROM public.hive_members
  WHERE hive_id = p_hive_id AND auth_uid = auth.uid() AND status = 'active';

  IF v_role IS NULL THEN
    RAISE EXCEPTION
      'get_hive_board_dashboard: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';
  END IF;
  v_is_sup := (v_role = 'supervisor');

  -- Caller identity for worker-scoped reads (spoof-proof: from the JWT, not a param).
  SELECT display_name INTO v_caller FROM public.worker_profiles WHERE auth_uid = auth.uid();

  -- Readiness/adoption snapshots — compose existing RPCs, degrade to null on error.
  BEGIN
    SELECT to_jsonb(r) INTO v_readiness FROM public.get_hive_readiness_current(p_hive_id) r LIMIT 1;
  EXCEPTION WHEN OTHERS THEN v_readiness := NULL;
  END;
  BEGIN
    SELECT to_jsonb(a) INTO v_adoption FROM public.get_adoption_risk_current(p_hive_id) a LIMIT 1;
  EXCEPTION WHEN OTHERS THEN v_adoption := NULL;
  END;

  SELECT jsonb_build_object(

    -- ── All members ──────────────────────────────────────────────────
    'members', COALESCE((SELECT jsonb_agg(m) FROM (
        -- id: a member action (remove, supervisor hand-over) updates ONE row; a display-name match updated every
        -- namesake. is_me: "which row is mine" from the JWT, so a drifted device name cannot make a supervisor
        -- count themselves as someone else (2026-10-14). NULL for a row with no auth_uid; the page then falls back
        -- to the name, as before.
        SELECT id, worker_name, role, status, (auth_uid = auth.uid()) AS is_me FROM public.hive_members
        WHERE hive_id = p_hive_id AND status <> 'kicked' ORDER BY joined_at, id) m), '[]'::jsonb),
    'open_jobs_workers', COALESCE((SELECT jsonb_agg(w) FROM (
        SELECT worker_name FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id AND status = 'Open') w), '[]'::jsonb),
    'feed_logbook', COALESCE((SELECT jsonb_agg(l) FROM (
        SELECT id, worker_name, date, machine, category, problem, status, created_at
        FROM public.v_logbook_truth WHERE hive_id = p_hive_id
        ORDER BY created_at DESC NULLS LAST LIMIT 40) l), '[]'::jsonb),
    'open_count', (SELECT count(*) FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id AND status = 'Open'),
    'feed_pm', COALESCE((SELECT jsonb_agg(p) FROM (
        SELECT pc.id, pc.worker_name, pc.asset_id, pc.scope_item_id, pc.status,
               pc.completed_at, pa.asset_name, psi.item_text, psi.frequency
        FROM public.pm_completions pc
        LEFT JOIN public.pm_assets      pa  ON pa.id  = pc.asset_id AND pa.deleted_at IS NULL
        LEFT JOIN public.pm_scope_items psi ON psi.id = pc.scope_item_id
        WHERE pc.hive_id = p_hive_id AND pc.status = 'done' AND (pc.asset_id IS NULL OR pa.id IS NOT NULL)
        ORDER BY pc.completed_at DESC NULLS LAST LIMIT 20) p), '[]'::jsonb),
    'pm_scope', COALESCE((SELECT jsonb_agg(s) FROM (
        SELECT scope_item_id, pm_asset_id, asset_name, is_overdue, is_due_soon
        FROM public.v_pm_scope_items_truth WHERE hive_id = p_hive_id) s), '[]'::jsonb),

    -- ── Worker-scoped (caller's own; derived identity) ───────────────
    'own_inventory', COALESCE((SELECT jsonb_agg(i) FROM (
        SELECT part_name, qty_on_hand, min_qty FROM public.v_inventory_items_truth
        WHERE worker_name = v_caller AND status = 'approved') i), '[]'::jsonb),
    'own_old_wos', COALESCE((SELECT jsonb_agg(w) FROM (
        SELECT machine, date, created_at FROM public.v_logbook_truth
        WHERE worker_name = v_caller AND status = 'Open'
          AND created_at < (now() - interval '48 hours')
          AND (hive_id = p_hive_id OR hive_id IS NULL)
        ORDER BY created_at DESC LIMIT 5) w), '[]'::jsonb),

    -- ── Analytics cards (all members) ────────────────────────────────
    'ai_reports', jsonb_build_object(
      'failure_digest', (SELECT to_jsonb(x) FROM (SELECT summary, report_json, generated_at, report_type
        FROM public.v_ai_reports_truth WHERE hive_id = p_hive_id AND report_type = 'failure_digest'
        ORDER BY generated_at DESC LIMIT 1) x),
      'predictive', (SELECT to_jsonb(x) FROM (SELECT summary, report_json, generated_at, report_type
        FROM public.v_ai_reports_truth WHERE hive_id = p_hive_id AND report_type = 'predictive'
        ORDER BY generated_at DESC LIMIT 1) x),
      'pm_overdue', (SELECT to_jsonb(x) FROM (SELECT summary, report_json, generated_at, report_type
        FROM public.v_ai_reports_truth WHERE hive_id = p_hive_id AND report_type = 'pm_overdue'
        ORDER BY generated_at DESC LIMIT 1) x)),
    'pattern_alerts', COALESCE((SELECT jsonb_agg(a) FROM (
        SELECT machine, category, title, detail, severity, rule_id, detected_at
        FROM public.v_alert_truth
        WHERE hive_id = p_hive_id AND alert_kind = 'signature' AND status = 'active'
        ORDER BY severity DESC, detected_at DESC LIMIT 5) a), '[]'::jsonb),
    'benchmarks', jsonb_build_object(
      'hive', COALESCE((SELECT jsonb_agg(h) FROM (SELECT equipment_category, mtbf_days, failure_count, sample_machines
        FROM public.hive_benchmarks WHERE hive_id = p_hive_id ORDER BY failure_count DESC LIMIT 5) h), '[]'::jsonb),
      'network', COALESCE((SELECT jsonb_agg(n) FROM (SELECT equipment_category, avg_mtbf_days, p75_mtbf_days, sample_hives
        FROM public.network_benchmarks ORDER BY sample_hives DESC LIMIT 10) n), '[]'::jsonb)),

    -- ── Readiness + adoption snapshots (initial read only) ───────────
    'readiness', v_readiness,
    'adoption',  CASE WHEN v_is_sup THEN v_adoption ELSE NULL END,

    -- ── Supervisor-only keys (NULL for non-supervisors) ──────────────
    'team_inventory', CASE WHEN v_is_sup THEN COALESCE((SELECT jsonb_agg(i) FROM (
        SELECT worker_name, part_name, qty_on_hand, min_qty FROM public.v_inventory_items_truth
        WHERE hive_id = p_hive_id AND status = 'approved') i), '[]'::jsonb) ELSE NULL END,
    'pending_assets', CASE WHEN v_is_sup THEN COALESCE((SELECT jsonb_agg(a) FROM (
        SELECT id, tag AS asset_id, name, iso_class AS type, location, criticality,
               hive_id, worker_name, status, submitted_by, created_at
        FROM public.asset_nodes WHERE hive_id = p_hive_id AND status = 'pending' AND deleted_at IS NULL) a), '[]'::jsonb) ELSE NULL END,
    'pending_parts', CASE WHEN v_is_sup THEN COALESCE((SELECT jsonb_agg(p) FROM (
        SELECT id, part_number, part_name, qty_on_hand, category, submitted_by, worker_name, status, created_at
        FROM public.v_inventory_items_truth WHERE hive_id = p_hive_id AND status = 'pending') p), '[]'::jsonb) ELSE NULL END,
    'audit_log', CASE WHEN v_is_sup THEN COALESCE((SELECT jsonb_agg(a) FROM (
        SELECT id, action, actor, target_name, target_type, target_id, meta, created_at
        FROM public.hive_audit_log WHERE hive_id = p_hive_id
        ORDER BY created_at DESC LIMIT 50) a), '[]'::jsonb) ELSE NULL END

  ) INTO v_result;

  RETURN v_result;
END;
$function$;

CREATE OR REPLACE FUNCTION public.my_personal_history_count()
 RETURNS integer
 LANGUAGE sql
 STABLE SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
  SELECT CASE WHEN auth.uid() IS NULL THEN 0 ELSE
    (SELECT count(*)::int FROM public.logbook WHERE auth_uid = auth.uid() AND hive_id IS NULL AND deleted_at IS NULL) END;
$function$;

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
    WHERE deleted_at IS NULL AND hive_id = p_hive_id AND status = 'approved';

  SELECT count(DISTINCT pa.id) INTO v_pm_template_count
    FROM public.pm_assets pa
    WHERE pa.deleted_at IS NULL AND pa.hive_id = p_hive_id;

  SELECT count(*) INTO v_logbook_with_knowledge
    FROM public.logbook
    WHERE deleted_at IS NULL AND hive_id = p_hive_id
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
    WHERE deleted_at IS NULL AND hive_id = p_hive_id
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
    WHERE deleted_at IS NULL AND hive_id = p_hive_id
      AND created_at >= now() - interval '30 days';

  -- Logbook hygiene: % with non-empty problem AND root_cause AND action
  IF v_logbook_30d > 0 THEN
    SELECT 100.0 * count(*) / v_logbook_30d INTO v_logbook_hygiene_pct
      FROM public.logbook
      WHERE deleted_at IS NULL AND hive_id = p_hive_id
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
  WHERE deleted_at IS NULL AND hive_id = p_hive_id
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
    WHERE deleted_at IS NULL AND hive_id = p_hive_id;
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
        THEN format('%s of 5 active workers writing entries in the last 7 days.', v_active_workers_7d) END,
      CASE WHEN v_pm_template_count < 5
        THEN format('%s of 5 PM templates registered.', v_pm_template_count) END
    )), '');
  ELSIF v_pm_compliance_30d < 70 OR v_logbook_hygiene_pct < 80 OR v_supervisor_actions_7d < 5 THEN
    v_stair := 2;
    v_blocker := format(
      'PM compliance %s%% (need 70%%), logbook hygiene %s%% (need 80%%), supervisor sign-offs %s in the last 7 days (need 5).',
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
    WHERE deleted_at IS NULL AND hive_id = p_hive_id
      AND created_at >= now() - interval '7 days';

  SELECT count(*) INTO v_writes_this_week
    FROM public.logbook
    WHERE deleted_at IS NULL AND hive_id = p_hive_id AND created_at >= now() - interval '7 days';

  SELECT count(*) INTO v_writes_last_week
    FROM public.logbook
    WHERE deleted_at IS NULL AND hive_id = p_hive_id
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
        WHERE lb.deleted_at IS NULL AND lb.hive_id = p_hive_id
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
    WHERE deleted_at IS NULL AND hive_id = p_hive_id
      AND created_at >= now() - interval '30 days'
    GROUP BY worker_name
    ORDER BY count(*) DESC
    LIMIT 1;

  -- ─── Dropping workers: this-week writes < 50% of last-week's writes ─────
  WITH this_week AS (
    SELECT worker_name, count(*) AS n
      FROM public.logbook
      WHERE deleted_at IS NULL AND hive_id = p_hive_id AND created_at >= now() - interval '7 days'
      GROUP BY worker_name
  ),
  last_week AS (
    SELECT worker_name, count(*) AS n
      FROM public.logbook
      WHERE deleted_at IS NULL AND hive_id = p_hive_id
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
