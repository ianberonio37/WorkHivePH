-- The schedule_item_v1 contract's item_status enum never matched the data it governs,
-- and a fix made on 2026-09-15 turned that mismatch into a hard save block.
--
-- THIS IS THE SIBLING OF 20260609000004, ONE FIELD OVER. That migration's own header records the
-- identical failure on `category`: "the contract was authored with the wrong vocabulary … every real
-- user Schedule Item save with a category hit [capture-violation] and was blocked". The same class
-- has now been re-introduced on `item_status`, and the lesson is that a contract enum is a claim
-- about the data, which must be checked against the data.
--
-- WHAT THE CONTRACT SAYS (20260512000018):
--   item_status enum = ["pending","in_progress","done","blocked","skipped",null]
--
-- WHAT THE TABLE HOLDS (measured 2026-09-16):
--   planned 139 · done 46 · pending 30 · in_progress 14 · NULL 2      (231 rows)
--
-- `planned` is 60% of the table and appears in the contract nowhere. It is written by the
-- service-request flow (129 of the 139 carry source_kind='service_request'), which is a different
-- surface with its own vocabulary - exactly the situation the category migration describes.
--
-- WHY IT ONLY BECAME A BLOCK NOW. Until 2026-09-15 dayplanner.html silently rewrote the value:
-- `planned` displayed as `upcoming` and saved back as `pending`. That was a defect in the other
-- direction - a page quietly overwriting another surface's vocabulary on behalf of a reader who had
-- only edited a title - and it was fixed by carrying the row's original canonical value through
-- (`canonStatus`) and re-sending it untouched. The fix is correct. But wh-capture-validate.js
-- validates client-side against THIS enum before the write leaves the browser, so preserving the
-- honest value traded a silent rewrite for a permanent refusal:
--
--   db write calls reaching schedule_items : NONE
--   toast 1 : "Thermography sweep saved -> on your Jul 20 plan."
--   toast 2 : "Could not save that change. Your edit was undone - the item is as it was."
--   console : [capture-violation] schedule_item_v1: $.item_status value must be one of
--             ["pending","in_progress","done","blocked","skipped",null]; got "planned"
--
-- The reader is given no reason and no path: retrying is the one action that cannot work. Measured
-- blast radius by owner: Bryan Garcia 128 of 134 rows, Pablo Aguilar 10 of 18, David Velasco 1 of 7.
--
-- WHAT CHANGES. `planned` joins the enum, in both the human-readable `fields` array and the
-- validated `contract_schema`. Nothing is removed and no row is rewritten: every value already in the
-- contract keeps working, and the six canonical values plus null were verified to round-trip
-- correctly through the page before and after. Forward-only, idempotent (re-running sets the same
-- array), and it touches exactly one row of canonical_capture_contracts.
--
-- Pairs tools/prove_capture_enums_cover_the_data.py, added with this migration, which fails whenever
-- a column's live DISTINCT values are not a subset of the enum the contract claims - so a fourth
-- writer's vocabulary cannot silently re-break this a third time.

UPDATE public.canonical_capture_contracts
SET
  contract_schema = jsonb_set(
    contract_schema,
    '{properties,item_status,enum}',
    '["pending","in_progress","done","blocked","skipped","planned",null]'::jsonb
  ),
  fields = (
    SELECT jsonb_agg(
      CASE WHEN elem->>'name' = 'item_status'
        THEN elem || '{"values":["pending","in_progress","done","blocked","skipped","planned"]}'::jsonb
        ELSE elem
      END
    )
    FROM jsonb_array_elements(fields) elem
  )
WHERE capture_id = 'schedule_item_v1';
