-- Fix v_pm_scope_items_truth.frequency_days — seeder-vocabulary drift (2026-06-10)
-- ============================================================================
-- BUG: the frequency_days CASE matched the labels {Monthly, Quarterly,
-- Semi-Annual, Yearly} but the actual pm_scope_items.frequency vocabulary the
-- seeder + UI produce is {Weekly, Monthly, Quarterly, Semi-annual, Annual}.
-- Result (live, hive Baguio Textile):
--   Weekly      -> ELSE 90  (should be 7)   — 35 items
--   Semi-annual -> ELSE 90  (should be 180) —  8 items  ('Semi-annual' != 'Semi-Annual')
--   Annual      -> ELSE 90  (should be 365) — 31 items  ('Annual' != 'Yearly')
-- Only Monthly (30) was right by value; Quarterly (90) right by coincidence of
-- the ELSE default. Because next_due_date / days_until_due / is_overdue /
-- is_due_soon are ALL derived from this number, every PM-due surface
-- (pm-scheduler, hive board, alert-hub, analytics-orchestrator) inherited wrong
-- due dates: a Weekly PM showed "next due in 90 days" instead of 7, never
-- flagged "due soon", and could run ~83 extra days before flagging overdue.
--
-- descriptive.py:191 already documented + fixed this exact class for the SMRP
-- compliance calc ("Accept the case variants the seeder produces") but the fix
-- was never carried into the canonical VIEW. This migration does that.
--
-- FIX: case-insensitive map over the real vocabulary, and derive next_due_date
-- from the single frequency_days value so the two CASEs can never diverge again.
-- ============================================================================

CREATE OR REPLACE VIEW public.v_pm_scope_items_truth AS
SELECT
  scope_item_id,
  scope_item_id AS id,             -- drop-in compat for `.eq('id', ...)` callers
  hive_id,
  pm_asset_id,
  pm_asset_id   AS asset_id,        -- drop-in compat for `.in('asset_id', ...)` callers
  item_text, frequency, anchor_date,
  is_custom, created_at,
  asset_name, asset_tag, asset_category, asset_criticality, asset_location,
  frequency_days,
  last_completed_at, last_completed_by,
  next_due_date,
  (next_due_date - CURRENT_DATE)                            AS days_until_due,
  (next_due_date < CURRENT_DATE)                            AS is_overdue,
  (next_due_date BETWEEN CURRENT_DATE
                    AND (CURRENT_DATE + INTERVAL '14 days')::date) AS is_due_soon
FROM (
  SELECT
    base.scope_item_id,
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
    base.last_completed_at,
    base.last_completed_by,
    -- next due = last completion (or anchor, or created) + ONE frequency interval.
    -- Derived from frequency_days so it can never drift from the day-count again.
    (COALESCE(base.last_completed_at::date, base.anchor_date, base.created_at::date)
       + (base.frequency_days * INTERVAL '1 day'))::date    AS next_due_date
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
      -- Case-insensitive over the REAL vocabulary (seeder + UI emit
      -- Weekly / Semi-annual / Annual; older rows may carry Semi-Annual / Yearly).
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
        ELSE 30   -- safe Monthly default (matches descriptive.py calc_pm_compliance)
      END             AS frequency_days,
      last_pc.last_completed_at,
      last_pc.last_completed_by
    FROM public.pm_scope_items s
    LEFT JOIN public.pm_assets pa ON pa.id = s.asset_id
    LEFT JOIN LATERAL (
      SELECT pc.completed_at AS last_completed_at,
             pc.worker_name  AS last_completed_by
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
  'Canonical pm_scope_items view: every column + bridge to pm_assets + frequency_days mapping (case-insensitive: Daily=1, Weekly=7, Monthly=30, Quarterly=90, Semi-annual=180, Annual/Yearly=365, default 30) + LATERAL last_completed_at/by + next_due_date / days_until_due / is_overdue / is_due_soon derived columns (next_due_date is derived from frequency_days). Registered in canonical_sources as pm_scope_items_truth.';
