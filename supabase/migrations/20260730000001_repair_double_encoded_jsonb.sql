-- 20260730000001_repair_double_encoded_jsonb.sql
--
-- THE DEFECT (surfaced by the `intelligence-jsonb-shape` gate, 2026-07-30): a jsonb column holding a
-- STRING instead of an array. The value looks right in a dump and is invisible to every type check:
--
--     top_factors = "[\"pm_overdue\", \"repeat_fault\", \"mtbf_approaching\"]"   -- a jsonb STRING
--     top_factors =  ["pm_overdue", "repeat_fault", "mtbf_approaching"]          -- what a reader needs
--
-- A consumer doing `top_factors.map(...)` gets NOTHING from the first one. The asset does not render
-- "no risk factors" — it renders an empty list beside a real risk score, which reads as *this asset
-- has no explanation for its risk*. Silent by construction: no error, no null, no empty column
-- ([[feedback_jsonb_double_encode_reads_empty]], the class this gate was built for).
--
-- SCOPE, attributed rather than guessed: 2 of 352 `asset_risk_scores` rows, both `model_version =
-- rules-v1` generated 2026-07-20, and 1 of 4 `parts_staging_recommendations` rows whose payload names
-- `item_id: demo-1`. Legacy residue from specific runs — the current writer (rules-v2) produces proper
-- arrays, and rules-v1 rows are mostly fine too, so this was one bad path and not an ongoing one.
--
-- The repair is IDEMPOTENT and shape-guarded: it only touches rows whose jsonb_typeof is 'string', and
-- `#>> '{}'` unwraps the jsonb string to its text so it can be re-parsed as the array it always meant.
-- Re-running changes nothing. Recurrence is caught by the gate, which is why the fix here is data and
-- not another guard.
UPDATE public.asset_risk_scores
   SET top_factors = (top_factors #>> '{}')::jsonb
 WHERE jsonb_typeof(top_factors) = 'string'
   AND left(top_factors #>> '{}', 1) = '[';      -- only a payload that really is an encoded array

UPDATE public.parts_staging_recommendations
   SET parts = (parts #>> '{}')::jsonb
 WHERE jsonb_typeof(parts) = 'string'
   AND left(parts #>> '{}', 1) = '[';
