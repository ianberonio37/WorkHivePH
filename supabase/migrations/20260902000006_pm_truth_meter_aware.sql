-- VEHICLE SEED M4 (2026-09-02): the truth view learns MILEAGE. v_pm_scope_items_truth stays the
-- single due-engine every surface reads (pm-scheduler, hive tiles, alert engine, compliance RPCs
-- key off is_overdue/is_due_soon) — so teaching THIS view the meter makes km-based PMs light up
-- platform-wide with no downstream edits. Every existing column keeps its name, type and position
-- (CREATE OR REPLACE constraint); the meter columns append at the end.
--
-- The due semantics (approved plan):
--   next_due_km  = COALESCE(meter at last done, vehicle baseline km, 0) + interval_km
--   current_km   = the asset's vehicle_meta.odometer_km (rolled forward by trg_roll_vehicle_odometer)
--   is_overdue   = the date half (unless interval_kind='meter')  OR  current_km >= next_due_km
--   is_due_soon  = the date half OR within 500 km of next_due_km
-- A calendar-only item (interval_km NULL) computes exactly as before — bit-for-bit.

CREATE OR REPLACE VIEW public.v_pm_scope_items_truth AS
SELECT
  scope_item_id,
  scope_item_id AS id,
  hive_id,
  pm_asset_id,
  pm_asset_id   AS asset_id,
  item_text, frequency, anchor_date,
  is_custom, created_at,
  asset_name, asset_tag, asset_category, asset_criticality, asset_location,
  frequency_days,
  last_completed_at, last_completed_by,
  next_due_date,
  (next_due_date - CURRENT_DATE)                            AS days_until_due,
  (
    (CASE WHEN interval_kind <> 'meter' THEN next_due_date < CURRENT_DATE ELSE false END)
    OR (interval_km IS NOT NULL AND current_km IS NOT NULL AND current_km >= next_due_km)
  )                                                         AS is_overdue,
  (
    (CASE WHEN interval_kind <> 'meter'
          THEN next_due_date BETWEEN CURRENT_DATE AND (CURRENT_DATE + INTERVAL '14 days')::date
          ELSE false END)
    OR (interval_km IS NOT NULL AND current_km IS NOT NULL
        AND current_km >= (next_due_km - 500) AND current_km < next_due_km)
  )                                                         AS is_due_soon,
  interval_km,
  interval_kind,
  next_due_km,
  current_km,
  (CASE WHEN interval_km IS NOT NULL AND current_km IS NOT NULL
        THEN (next_due_km - current_km) END)                AS km_until_due
FROM (
  SELECT
    base.*,
    (COALESCE(base.last_completed_at::date, base.anchor_date, base.created_at::date)
       + (base.frequency_days * INTERVAL '1 day'))::date    AS next_due_date,
    (CASE WHEN base.interval_km IS NOT NULL
          THEN COALESCE(base.last_meter, base.baseline_km, 0) + base.interval_km END) AS next_due_km
  FROM (
    SELECT
      s.id            AS scope_item_id,
      s.hive_id,
      s.asset_id      AS pm_asset_id,
      s.item_text,
      s.frequency,
      s.anchor_date,
      s.is_custom,
      s.created_at,
      pa.asset_name,
      pa.tag_id       AS asset_tag,
      pa.category     AS asset_category,
      pa.criticality  AS asset_criticality,
      pa.location     AS asset_location,
      CASE lower(trim(s.frequency))
        WHEN 'daily'        THEN 1
        WHEN 'weekly'       THEN 7
        WHEN 'biweekly'     THEN 14
        WHEN 'fortnightly'  THEN 14
        WHEN 'monthly'      THEN 30
        WHEN 'quarterly'    THEN 90
        WHEN 'semi-annual'  THEN 180
        WHEN 'semiannual'   THEN 180
        WHEN 'semi annual'  THEN 180
        WHEN 'annual'       THEN 365
        WHEN 'yearly'       THEN 365
        ELSE 30
      END             AS frequency_days,
      s.interval_km,
      s.interval_kind,
      last_pc.last_completed_at,
      last_pc.last_completed_by,
      last_pc.last_meter,
      NULLIF(veh.vehicle_meta->>'odometer_km','')::numeric          AS current_km,
      NULLIF(veh.vehicle_meta->>'odometer_baseline_km','')::numeric AS baseline_km
    FROM public.pm_scope_items s
    LEFT JOIN public.pm_assets pa ON pa.id = s.asset_id
    -- LIMIT 1 lateral, not a bare join: two nodes bridging one pm_asset must never fan the view out
    LEFT JOIN LATERAL (
      SELECT n.vehicle_meta
      FROM public.asset_nodes n
      WHERE n.pm_asset_id = pa.id AND n.vehicle_meta IS NOT NULL
      ORDER BY n.created_at
      LIMIT 1
    ) veh ON TRUE
    LEFT JOIN LATERAL (
      SELECT pc.completed_at        AS last_completed_at,
             pc.worker_name         AS last_completed_by,
             pc.meter_at_completion AS last_meter
      FROM public.pm_completions pc
      WHERE pc.scope_item_id = s.id
        AND pc.status = 'done'
      ORDER BY pc.completed_at DESC
      LIMIT 1
    ) last_pc ON TRUE
  ) base
) sub;

GRANT SELECT ON public.v_pm_scope_items_truth TO anon, authenticated;

COMMENT ON VIEW public.v_pm_scope_items_truth IS
  'Canonical pm_scope_items view, METER-AWARE (2026-09-02): all prior columns unchanged (frequency_days mapping, LATERAL last-completion, next_due_date derivations) + interval_km/interval_kind/next_due_km/current_km/km_until_due; is_overdue and is_due_soon consider BOTH the calendar half (unless interval_kind=meter) and the odometer half (500 km due-soon window). current_km reads asset_nodes.vehicle_meta rolled forward by trg_roll_vehicle_odometer. Registered in canonical_sources as pm_scope_items_truth.';
