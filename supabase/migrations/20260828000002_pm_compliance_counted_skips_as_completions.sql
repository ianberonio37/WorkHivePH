-- T189 (2026-08-28): v_pm_compliance_truth counted a SKIPPED PM as a completion.
--
-- The view joined pm_completions with NO filter on `status`, so every counter it exposes —
-- lifetime_completions, completions_30d/90d/365d — and both derived clocks —
-- last_completion_at, days_since_last_completion — treated a PM that was explicitly NOT DONE
-- exactly like one that was. Measured on the local fixture: 78 skipped rows, 63 of them inside
-- the 90-day window, and 1 asset whose "last completion" was a skip — an asset reading as
-- recently serviced because someone recorded that the service did not happen.
--
-- ★THIS IS THE EXACT FAILURE THE ORIGINAL MIGRATION SET OUT TO PREVENT. 20260509000004 opens by
-- explaining that it exists to end a 4-way compliance math drift, warns in its own prose that
-- "mixing all-time completions with period-scoped scheduled counts inflates compliance", and
-- writes a compliance_math_rule into its canonical_sources contract to guard that. It guarded the
-- DENOMINATOR carefully and left a door open in the NUMERATOR. Compliance inflation arrived
-- through the one entrance the author had not thought to check.
--
-- Why it matters beyond arithmetic: this is the number a supervisor defends to management (T22,
-- T47), and PM compliance is a safety-adjacent claim in a maintenance system. A metric that
-- cannot distinguish "we did the work" from "we recorded that we did not do the work" is not
-- measuring compliance; it is measuring data entry. Deferral honesty is a rule this platform
-- already holds at the row level (the deferred_not_completed recipe) — the truth view simply did
-- not honor it.
--
-- THE FIX, in two halves, because deleting the skips would be its own dishonesty:
--   1. every completion counter and both clocks now count status='done' ONLY
--   2. skips become VISIBLE in their own columns rather than silently vanishing, so a supervisor
--      can see the non-performance the old view was hiding inside the completion count
--
-- `= 'done'` rather than `<> 'skipped'` is deliberate: should a third status ever appear, the
-- conservative direction for a compliance numerator is to EXCLUDE what it does not recognise.
-- A future 'partial' must be counted on purpose, not inherited by accident.
--
-- ★security_invoker IS RE-DECLARED BELOW AND THAT IS LOAD-BEARING. CREATE OR REPLACE VIEW silently
-- DROPS reloptions, and this view currently carries security_invoker=true; losing it would run the
-- view with OWNER rights and quietly bypass RLS on pm_assets/pm_completions — a tenant-isolation
-- hole opened by a metric fix. (See the D4 floor and validate_truth_view_security_invoker.)
--
-- ADDITIVE FOR CONSUMERS: no column is removed or renamed, so all 72 referencing files keep
-- reading the same names. The VALUES move, which is the entire point — they move toward being true.

BEGIN;

CREATE OR REPLACE VIEW public.v_pm_compliance_truth
WITH (security_invoker = true) AS
SELECT
  pa.hive_id,
  pa.id                                                   AS pm_asset_id,
  pa.asset_name,
  pa.tag_id,
  pa.category,
  pa.criticality,
  pa.location,
  pa.last_anchor_date,
  -- Days since the last COMPLETED scope item. A skip must not reset this clock: the whole
  -- purpose of the number is "how long since this asset was actually serviced".
  CASE WHEN max(pc.completed_at) FILTER (WHERE pc.status = 'done') IS NULL
       THEN NULL
       ELSE (now()::date - (max(pc.completed_at) FILTER (WHERE pc.status = 'done'))::date)
  END                                                     AS days_since_last_completion,
  -- Period-scoped counts, now genuinely counting completions.
  count(pc.id) FILTER (WHERE pc.status = 'done')          AS lifetime_completions,
  count(pc.id) FILTER (WHERE pc.status = 'done'
                         AND pc.completed_at >= now() - interval '30 days')   AS completions_30d,
  count(pc.id) FILTER (WHERE pc.status = 'done'
                         AND pc.completed_at >= now() - interval '90 days')   AS completions_90d,
  count(pc.id) FILTER (WHERE pc.status = 'done'
                         AND pc.completed_at >= now() - interval '365 days')  AS completions_365d,
  max(pc.completed_at) FILTER (WHERE pc.status = 'done')  AS last_completion_at,
  -- Unchanged: never completed, OR last_anchor_date older than 30 days.
  CASE
    WHEN pa.last_anchor_date IS NULL THEN true
    WHEN pa.last_anchor_date < (now()::date - interval '30 days')::date THEN true
    ELSE false
  END                                                     AS is_due,
  -- The other half of the fix: skips are now VISIBLE instead of hiding inside the completion
  -- count. Removing them from the numerator without surfacing them anywhere would trade an
  -- overstatement for a blind spot — a supervisor needs to see that work was skipped.
  --
  -- ★APPENDED AFTER is_due, NOT SLOTTED BESIDE THE COUNTERS THEY BELONG WITH. CREATE OR REPLACE
  -- VIEW may only ADD columns at the END of the list; inserting them before is_due reads to
  -- Postgres as RENAMING is_due, which it refuses outright ("cannot change name of view column").
  -- Grouping beats ordering here only if the statement allows it, and it does not.
  count(pc.id) FILTER (WHERE pc.status = 'skipped')       AS lifetime_skips,
  count(pc.id) FILTER (WHERE pc.status = 'skipped'
                         AND pc.completed_at >= now() - interval '30 days')   AS skips_30d,
  count(pc.id) FILTER (WHERE pc.status = 'skipped'
                         AND pc.completed_at >= now() - interval '90 days')   AS skips_90d,
  max(pc.completed_at) FILTER (WHERE pc.status = 'skipped') AS last_skip_at
FROM public.pm_assets pa
LEFT JOIN public.pm_completions pc
       ON pc.asset_id = pa.id
      AND pc.hive_id  = pa.hive_id
GROUP BY
  pa.hive_id, pa.id, pa.asset_name, pa.tag_id, pa.category, pa.criticality,
  pa.location, pa.last_anchor_date;

COMMENT ON VIEW public.v_pm_compliance_truth IS
  'Canonical PM compliance per asset. Completion counters and both clocks count status=''done'' ONLY — a skipped PM is recorded non-performance and must never read as a completion (T189, 2026-08-28). Skips are surfaced separately in lifetime_skips / skips_30d / skips_90d / last_skip_at. Source of truth for analytics-orchestrator phase 1, shift-planner-orchestrator PMs Due, hive.html PM Health card, and predictive.html PM-overdue factor.';

GRANT SELECT ON public.v_pm_compliance_truth TO anon, authenticated;

UPDATE public.canonical_sources
   SET description = 'PM compliance per asset across multiple time windows (lifetime, 30d, 90d, 365d) plus is_due flag. Completion counters count status=''done'' only; skipped PMs are surfaced separately and never counted as completions.',
       contract = jsonb_build_object(
         'key', jsonb_build_array('hive_id', 'pm_asset_id'),
         'hive_scoped', true,
         'period_columns', jsonb_build_array(
           'completions_30d', 'completions_90d', 'completions_365d', 'lifetime_completions'
         ),
         'skip_columns', jsonb_build_array(
           'lifetime_skips', 'skips_30d', 'skips_90d', 'last_skip_at'
         ),
         'derived_columns', jsonb_build_array(
           'days_since_last_completion', 'last_completion_at', 'is_due'
         ),
         'compliance_math_rule', 'When computing compliance %, ALWAYS pair period completions with period-scoped due counts. Mixing lifetime completions with period-scoped due counts inflates compliance (data-engineer skill rule).',
         'completion_status_rule', 'Completion counters and clocks count pm_completions.status = ''done'' ONLY. A skipped PM is recorded NON-PERFORMANCE: counting it as a completion inflates compliance and resets days_since_last_completion on an asset that was never serviced. Read the skip_columns to surface deferral rather than hiding it in the numerator.'
       ),
       notes = 'Phase A.4 contract. is_due flag uses 30-day floor; consumers needing category-specific frequencies read last_anchor_date + category and apply their own threshold. T189 (2026-08-28): status filter added — the view previously counted skipped PMs as completions.',
       registered_at = now()
 WHERE domain = 'pm_compliance_truth';

COMMIT;
