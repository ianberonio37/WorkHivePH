-- plan_attributable (shift-brain): a generated plan records which orchestrator run, which inputs,
-- which model. Every write on this page is AI-authored, and an AI write with no accountability record
-- is the AI6 class - so this asserts what IS recorded and, just as deliberately, what is NOT.
--
-- ★MEASURED, AND THE ORACLE IS ONLY PARTLY SATISFIED (2026-09-10). All 135 plans carry `generated_by`
-- ('shift-planner-orchestrator') and `generated_at`, so WHAT produced it and WHEN are on every row,
-- and `payload.degraded` + `payload.fetch_errors` record whether its INPUTS were healthy - that is
-- real provenance and it is asserted below. But the payload keys are exactly
--   assignments, caps, carry_forward, degraded, fetch_errors, parts_prestage, pms_due,
--   projects_today, risk_top
-- with NO model, NO run id and NO input manifest. And the planner writes NO `wh_traces` row at all
-- (0 for any route matching shift/plan), so the model is not recorded beside the plan either.
--
-- ★THE MECHANISM EXISTS AND ONE ROUTE USES IT. `wh_traces.model_chain` is populated 20/20 for
-- `ai-gateway` and 0 for every other AI route - ai-orchestrator (37 traces), analytics-orchestrator
-- (18), voice-transcribe (9), engineering-bom-sow (5), scheduled-agents (4), embed-entry (3),
-- send-report-email (3). So "which model" is a platform-wide accountability gap, not a shift-brain
-- one, and it is expensive: eleven of the eighteen entries in the shared model chain turned out to be
-- names their providers no longer serve, and the ONE route that records which model answered is the
-- one that could have said so. Asserted here as a fact rather than left as a comment, so the day the
-- planner starts recording a model this recipe FAILS and someone updates the claim deliberately.
-- expect: plans_present \| [1-9][0-9]*
-- expect: every_plan_names_its_producer \| t
-- expect: every_plan_names_its_time \| t
-- expect: plans_missing_input_health \| [0-5]
-- expect: input_health_within_ratchet \| t
-- expect: plan_records_no_model \| t
-- expect: planner_writes_no_trace \| t
-- expect: model_chain_mechanism_works_somewhere \| t
SELECT 'plans_present | ' || (SELECT count(*) FROM shift_plans);

SELECT 'every_plan_names_its_producer | ' || (
  (SELECT count(*) FROM shift_plans WHERE generated_by IS NULL) = 0);
SELECT 'every_plan_names_its_time | ' || (
  (SELECT count(*) FROM shift_plans WHERE generated_at IS NULL) = 0);

-- Input provenance: the plan says whether the reads it rests on succeeded. NOT universal, and the
-- first draft asserted it was - because the key survey used `distinct` across ALL plans and so
-- returned the UNION of keys, which reads exactly like "every plan has these". Measured per row:
-- 130 of 135 carry both `degraded` and `fetch_errors`; FIVE do not, and only one of those five is the
-- test seed - so FOUR real orchestrator plans record nothing about the health of their inputs.
-- Ratcheted rather than asserted true: the count is printed, and the bound only ever moves down.
SELECT 'plans_missing_input_health | ' || (
  SELECT count(*) FROM shift_plans
   WHERE payload IS NOT NULL AND NOT (payload ? 'degraded' AND payload ? 'fetch_errors'));
SELECT 'input_health_within_ratchet | ' || (
  (SELECT count(*) FROM shift_plans
    WHERE payload IS NOT NULL AND NOT (payload ? 'degraded' AND payload ? 'fetch_errors')) <= 5);

-- the gap, asserted so it cannot drift silently in either direction
SELECT 'plan_records_no_model | ' || NOT EXISTS (
  SELECT 1 FROM shift_plans p, LATERAL jsonb_object_keys(p.payload) k
   WHERE p.payload IS NOT NULL AND k ILIKE '%model%');
SELECT 'planner_writes_no_trace | ' || (
  (SELECT count(*) FROM wh_traces WHERE route ILIKE '%shift%' OR route ILIKE '%plan%') = 0);

-- and the mechanism it would use is proven to work elsewhere, so this is an adoption gap, not a
-- missing capability - the distinction that decides whether it is a fix or a build
SELECT 'model_chain_mechanism_works_somewhere | ' || EXISTS (
  SELECT 1 FROM wh_traces WHERE model_chain IS NOT NULL AND array_length(model_chain, 1) > 0);
