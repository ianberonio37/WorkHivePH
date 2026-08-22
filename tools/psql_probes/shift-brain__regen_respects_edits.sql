-- regen_respects_edits: a re-run cannot undo a supervisor's decision, and the protection sits in
-- the DATABASE (tg_shift_plans_forward_status): the orchestrator upserts status='draft'
-- unconditionally, so a published plan must REFUSE the draft regression — forward-only
-- draft -> published -> archived. The seed holds no published plan, so the probe PROMOTES a draft
-- inside its own transaction first (missing data is a fixture to build, not a blocker), then
-- attempts the regression; the raise aborts that txn, and a second txn proves the forward
-- direction still works. Counts restored.
-- expect: guard_trigger_live \| t
-- expect: promoted_fixture \| t
-- expect: cannot regress status
-- expect: forward_promotion_allowed \| t
-- expect: restored \| t
SELECT 'guard_trigger_live | ' || EXISTS (
  SELECT 1 FROM pg_trigger WHERE tgrelid='shift_plans'::regclass
   AND tgname='tg_shift_plans_forward_status' AND tgenabled <> 'D');
CREATE TEMP TABLE _rg AS
SELECT (SELECT id FROM shift_plans WHERE status='draft' LIMIT 1) AS draft_id,
       (SELECT count(*) FROM shift_plans WHERE status='published') AS pub0;
BEGIN;
UPDATE shift_plans SET status='published' WHERE id = (SELECT draft_id FROM _rg);
SELECT 'promoted_fixture | ' ||
  ((SELECT status FROM shift_plans WHERE id = (SELECT draft_id FROM _rg)) = 'published');
UPDATE shift_plans SET status='draft' WHERE id = (SELECT draft_id FROM _rg);
ROLLBACK;
BEGIN;
UPDATE shift_plans SET status='published' WHERE id = (SELECT draft_id FROM _rg);
SELECT 'forward_promotion_allowed | ' ||
  ((SELECT status FROM shift_plans WHERE id = (SELECT draft_id FROM _rg)) = 'published');
ROLLBACK;
SELECT 'restored | ' ||
  ((SELECT count(*) FROM shift_plans WHERE status='published') = (SELECT pub0 FROM _rg));
DROP TABLE _rg;
