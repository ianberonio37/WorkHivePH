-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- ★A DAY IN WORKHIVE IS THE PHILIPPINE DAY (UFAI LXP838/879/912, walked 2026-10-09)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- The PM truth view counted days with CURRENT_DATE, which is the database's clock: UTC locally and on Supabase. So a
-- PM's "Due today", "Overdue" and "Due soon" flipped at UTC midnight - 08:00 in the Philippines - and from midnight to
-- eight in the morning a technician read yesterday's statuses: a PM due today still said "Due in 1 day", one due
-- yesterday was not overdue yet. The rest of the platform keys its day on Asia/Manila (19 conversions across the
-- migrations, the analytics snapshots, alert-hub's shift day). Found by the analytics page naming "Today" with no clock:
-- its PM list comes from this view, and it could not honestly say PHT while the view meant UTC.
-- The four crew-facing objects that still read CURRENT_DATE now read the Philippine date; nothing else changes.
-- (ai_eval_bench_ensure keeps CURRENT_DATE: an internal bench key, not a day anyone works by.)
BEGIN;
-- v_pm_scope_items_truth: 4 CURRENT_DATE -> the Philippine date
CREATE OR REPLACE VIEW public.v_pm_scope_items_truth WITH (security_invoker = true) AS
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
    next_due_date - (now() AT TIME ZONE 'Asia/Manila')::date AS days_until_due,
        CASE
            WHEN interval_kind <> 'meter'::text THEN next_due_date < (now() AT TIME ZONE 'Asia/Manila')::date
            ELSE false
        END OR interval_km IS NOT NULL AND current_km IS NOT NULL AND current_km >= next_due_km AS is_overdue,
        CASE
            WHEN interval_kind <> 'meter'::text THEN next_due_date >= (now() AT TIME ZONE 'Asia/Manila')::date AND next_due_date <= ((now() AT TIME ZONE 'Asia/Manila')::date + '14 days'::interval)::date
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
                     LEFT JOIN pm_assets pa ON pa.id = s.asset_id
                     LEFT JOIN LATERAL ( SELECT n.vehicle_meta
                           FROM asset_nodes n
                          WHERE n.pm_asset_id = pa.id AND n.vehicle_meta IS NOT NULL
                          ORDER BY n.created_at
                         LIMIT 1) veh ON true
                     LEFT JOIN LATERAL ( SELECT pc.completed_at AS last_completed_at,
                            pc.worker_name AS last_completed_by,
                            pc.meter_at_completion AS last_meter
                           FROM pm_completions pc
                          WHERE pc.scope_item_id = s.id AND pc.status = 'done'::text
                          ORDER BY pc.completed_at DESC
                         LIMIT 1) last_pc ON true) base) sub;

-- v_project_items_truth: 2 CURRENT_DATE -> the Philippine date
CREATE OR REPLACE VIEW public.v_project_items_truth WITH (security_invoker = true) AS
SELECT i.id,
    i.project_id,
    i.hive_id,
    i.wbs_code,
    i.title,
    i.owner_name,
    i.status,
    i.pct_complete,
    i.planned_start,
    i.planned_end,
    i.actual_start,
    i.actual_end,
    i.predecessors,
    i.estimated_hours,
    i.actual_hours,
    i.notes,
    i.sort_order,
    i.created_at,
    i.updated_at,
    p.name AS project_name,
    p.project_code,
    p.status AS project_status,
    i.status = 'pending'::text AS is_pending,
    i.status = 'in_progress'::text AS is_in_progress,
    i.status = 'done'::text AS is_done,
    i.status = 'blocked'::text AS is_blocked,
    i.status = 'skipped'::text AS is_skipped,
    i.planned_end IS NOT NULL AND i.planned_end < (now() AT TIME ZONE 'Asia/Manila')::date AND (i.status <> ALL (ARRAY['done'::text, 'skipped'::text])) AS is_overdue,
    i.planned_start IS NOT NULL AND i.planned_start <= (now() AT TIME ZONE 'Asia/Manila')::date AND i.actual_start IS NULL AND i.status = 'pending'::text AS is_late_start
   FROM project_items i
     LEFT JOIN projects p ON p.id = i.project_id;

-- get_hive_dashboard: 1 CURRENT_DATE -> the Philippine date
CREATE OR REPLACE FUNCTION public.get_hive_dashboard(p_hive_id uuid, p_day_start timestamp with time zone DEFAULT date_trunc('day'::text, now()))
 RETURNS jsonb
 LANGUAGE plpgsql
 STABLE SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_is_member boolean;
  v_result    jsonb;
BEGIN
  -- â”€â”€ Hive isolation gate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  SELECT EXISTS (
    SELECT 1 FROM public.hive_members
    WHERE hive_id  = p_hive_id
      AND auth_uid = auth.uid()
      AND status   = 'active'
  ) INTO v_is_member;

  IF NOT v_is_member THEN
    RAISE EXCEPTION
      'get_hive_dashboard: caller is not an active member of hive %', p_hive_id
      USING ERRCODE = '42501';  -- insufficient_privilege
  END IF;

  -- â”€â”€ Consolidated board payload (mirrors index.html dashboard loader) â”€â”€
  SELECT jsonb_build_object(

    -- Open jobs: top-5 detail + true count (count drives the tile)
    'open_jobs', COALESCE((
      SELECT jsonb_agg(j) FROM (
        SELECT id, machine, category, maintenance_type, status, created_at, date
        FROM public.v_logbook_truth
        WHERE hive_id = p_hive_id AND status = 'Open'
        ORDER BY created_at DESC NULLS LAST
        LIMIT 5
      ) j
    ), '[]'::jsonb),
    'open_jobs_count', (
      SELECT count(*) FROM public.v_logbook_truth
      WHERE hive_id = p_hive_id AND status = 'Open'
    ),

    -- Risk alerts: top-5 critical/high detail + true count
    'risks', COALESCE((
      SELECT jsonb_agg(r) FROM (
        SELECT asset_name, risk_level, risk_score, mtbf_days, generated_at
        FROM public.v_risk_truth
        WHERE hive_id = p_hive_id AND risk_level IN ('critical','high')
        ORDER BY risk_score DESC NULLS LAST
        LIMIT 5
      ) r
    ), '[]'::jsonb),
    'risks_count', (
      SELECT count(*) FROM public.v_risk_truth
      WHERE hive_id = p_hive_id AND risk_level IN ('critical','high')
    ),

    -- Low stock: the canonical is_low_stock rows themselves (capped at 100 to
    -- mirror the client's old limit(100) inventory fetch). The client derives
    -- BOTH the tile count (.length) AND the out-of-stock candidate
    -- (.filter(qty_on_hand <= 0)) from this array â€” same as the old
    -- invRaw.filter(is_low_stock) path, so behavior is parity-equal.
    'low_stock_items', COALESCE((
      SELECT jsonb_agg(i) FROM (
        SELECT part_name, qty_on_hand, reorder_point
        FROM public.v_inventory_items_truth
        WHERE hive_id = p_hive_id AND is_low_stock = true
        LIMIT 100
      ) i
    ), '[]'::jsonb),

    -- PM overdue: DISTINCT assets with â‰¥1 OVERDUE scope item, read from the
    -- frequency-aware canonical per-scope-item view so this matches
    -- pm-scheduler.html #stat-overdue EXACTLY. (Was count(is_due) from
    -- v_pm_compliance_truth â€” a flat-30-day anchor proxy that over-counted.)
    'low_stock_count', (
      SELECT count(*) FROM public.v_inventory_items_truth
      WHERE hive_id = p_hive_id AND is_low_stock
    ),

    'pm_overdue_count', (
      SELECT count(DISTINCT pm_asset_id) FROM public.v_pm_scope_items_truth
      WHERE hive_id = p_hive_id AND is_overdue = true
    ),

    -- The denominator for pm_overdue_count. Without it the tile states a bare 28, which a reader
    -- cannot tell from 28-of-500 (a backlog) or 28-of-30 (a stopped PM programme).
    'pm_asset_total', (
      SELECT count(DISTINCT pm_asset_id) FROM public.v_pm_scope_items_truth
      WHERE hive_id = p_hive_id
    ),

    -- Top CRITICAL asset with an overdue scope item (most-overdue first),
    -- drives the home "Critical PM Overdue" Today's-One-Thing nudge. Added
    -- 2026-06-07: the nudge was dead on the RPC path because the client only
    -- had this signal in its legacy pmAssets fallback list.
    'critical_pm_overdue', (
      SELECT to_jsonb(c) FROM (
        SELECT asset_name, asset_tag, pm_asset_id, min(days_until_due) AS worst_days_until_due
        FROM public.v_pm_scope_items_truth
        WHERE hive_id = p_hive_id AND is_overdue = true
          AND lower(asset_criticality) = 'critical'  -- seed casing is title-case ('Critical')
        GROUP BY asset_name, asset_tag, pm_asset_id
        ORDER BY worst_days_until_due ASC
        LIMIT 1
      ) c
    ),

    -- Hive Activity Today
    'closed_today', (
      SELECT count(*) FROM public.v_logbook_truth
      WHERE hive_id = p_hive_id AND status = 'Closed' AND closed_at >= p_day_start
    ),
    'pm_done_today', (
      SELECT count(*) FROM public.pm_completions
      WHERE hive_id = p_hive_id AND status = 'done' AND completed_at >= p_day_start
    ),

    -- Today's One Thing signals (latest single row each, or null)
    'amc_pending', (
      SELECT to_jsonb(a) FROM (
        SELECT amc_id, shift_date, summary, headline, status
        FROM public.v_amc_truth
        WHERE hive_id = p_hive_id AND status = 'pending' AND shift_date >= (now() AT TIME ZONE 'Asia/Manila')::date
        ORDER BY shift_date ASC
        LIMIT 1
      ) a
    ),
    'sensor_anomaly', (
      SELECT to_jsonb(s) FROM (
        SELECT asset_id, parameter, quality_flag, recorded_at, is_anomaly
        FROM public.v_sensor_truth
        WHERE hive_id = p_hive_id AND is_anomaly = true
          AND recorded_at >= now() - interval '24 hours'
        ORDER BY recorded_at DESC
        LIMIT 1
      ) s
    ),
    'signature_alert', (
      SELECT to_jsonb(g) FROM (
        SELECT alert_id, machine, title, severity, detected_at
        FROM public.v_alert_truth
        WHERE hive_id = p_hive_id AND alert_kind = 'signature' AND severity = 'critical'
        ORDER BY detected_at DESC
        LIMIT 1
      ) g
    )
  ) INTO v_result;

  RETURN v_result;
END;
$function$;

-- sweep_pm_auto_hail: 1 CURRENT_DATE -> the Philippine date
CREATE OR REPLACE FUNCTION public.sweep_pm_auto_hail()
 RETURNS TABLE(filed integer, skipped_no_category integer)
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
declare
  v_filed int := 0;
  v_skipped int := 0;
  r record;
  v_catalog_id uuid;
  v_req_id uuid;
begin
  -- system-authored writes: the same GUC the seeders/backends use, so guard_service_request_status
  -- accepts a request nobody clicked for.
  perform set_config('workhive.service_system_write', 'on', true);

  for r in
    select t.scope_item_id, t.hive_id, t.item_text, t.asset_name, t.asset_tag,
           t.asset_location, t.next_due_date, si.auto_hail_category
      from public.v_pm_scope_items_truth t
      join public.pm_scope_items si on si.id = t.scope_item_id
     where si.auto_hail = true
       and t.next_due_date is not null
       and t.next_due_date <= (now() AT TIME ZONE 'Asia/Manila')::date          -- due or overdue
  loop
    -- structural idempotency: skip if this item already has an OPEN auto-hail
    if exists (
      select 1 from public.service_requests sr
       where sr.pm_scope_item_id = r.scope_item_id
         and sr.status in ('requested','broadcasting','accepted','en_route','on_site','in_progress')
    ) then
      continue;
    end if;

    select c.id into v_catalog_id
      from public.service_catalog c
     where c.active = true
       and c.segment = 'industrial'
       and (r.auto_hail_category is null or c.category = r.auto_hail_category)
     order by (c.category = coalesce(r.auto_hail_category, '')) desc, c.base_rate asc
     limit 1;

    if v_catalog_id is null then
      v_skipped := v_skipped + 1;      -- no rate-card match: skip honestly, never guess a service
      continue;
    end if;

    insert into public.service_requests
      (client_auth_uid, client_worker_name, hive_id, segment, mode, catalog_item_id,
       custom_scope, address, urgency, status, pm_scope_item_id)
    values
      ((select auth_uid from public.pm_assets pa
         join public.pm_scope_items s2 on s2.asset_id = pa.id
        where s2.id = r.scope_item_id and pa.auth_uid is not null limit 1),
       'PM auto-hail', r.hive_id, 'industrial', 'instant', v_catalog_id,
       'Recurring PM contract: ' || r.item_text || ' on ' || coalesce(r.asset_name, 'asset')
         || coalesce(' (' || r.asset_tag || ')', '') || ' - due ' || r.next_due_date::text,
       r.asset_location, 'normal', 'broadcasting', r.scope_item_id)
    returning id into v_req_id;

    insert into public.service_job_events (request_id, actor_uid, actor_role, from_state, to_state, note)
    values (v_req_id, null, 'system:pm-auto-hail', null, 'broadcasting',
            'Auto-filed by the recurring PM contract for scope item ' || r.scope_item_id::text);

    v_filed := v_filed + 1;
  end loop;

  perform set_config('workhive.service_system_write', 'off', true);
  return query select v_filed, v_skipped;
end $function$;

NOTIFY pgrst, 'reload schema';
COMMIT;
