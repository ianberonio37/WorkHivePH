-- rpn_recomputed: RPN equals Severity x Occurrence x Detection EXACTLY, recomputed rather than trusted
-- from a stored column that can drift. The strongest possible answer turned out to be already in the
-- schema: `rpn` is GENERATED ALWAYS, so the database computes it and a wrong value cannot be written at
-- all - the class of drift this oracle exists to catch is structurally impossible, not merely absent.
-- That is worth ASSERTING rather than assuming: a later migration could drop the generation and leave a
-- plain column that silently accepts anything, and every row would still read correct on the day it changed.
-- Teeth: writing `rpn` directly must be REFUSED by Postgres. A guarantee nobody can violate on purpose is
-- the only kind worth calling a guarantee.
-- Self-grounding: the write attempt targets a live row, never an invented id.
-- expect: rpn_is_generated \| t
-- expect: modes_checked \| [1-9][0-9]*
-- expect: rpn_disagreements \| 0
-- expect: incomplete_factors \| 0
-- expect: can only be updated to DEFAULT
-- expect: is a generated column
-- expect: rows_restored_after_rollback \| t

SELECT 'rpn_is_generated | ' || (is_generated = 'ALWAYS')
FROM information_schema.columns
WHERE table_name = 'rcm_fmea_modes' AND column_name = 'rpn';

-- the invariant as it stands, population printed beside it (non-vacuity)
SELECT 'modes_checked | ' || count(*)::text
     || E'\nrpn_disagreements | ' || count(*) FILTER (WHERE rpn IS DISTINCT FROM severity * occurrence * detection)::text
     || E'\nincomplete_factors | ' || count(*) FILTER (WHERE severity IS NULL OR occurrence IS NULL OR detection IS NULL)::text
FROM rcm_fmea_modes;

CREATE TEMP TABLE _fix AS
SELECT id AS src_id, (SELECT count(*) FROM rcm_fmea_modes) AS n0 FROM rcm_fmea_modes LIMIT 1;

BEGIN;
-- TEETH: the generation must REFUSE a hand-written RPN, not silently keep or overwrite it
UPDATE rcm_fmea_modes SET rpn = 1 WHERE id = (SELECT src_id FROM _fix);
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || ((SELECT count(*) FROM rcm_fmea_modes) = (SELECT n0 FROM _fix));
