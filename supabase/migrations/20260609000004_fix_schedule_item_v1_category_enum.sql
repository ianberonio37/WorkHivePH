-- Fix the schedule_item_v1 capture contract — its category enum never matched
-- the dayplanner the contract governs, so saving any categorized schedule item
-- failed client-side validation.
--
-- The contract (20260512000018) declared category enum
-- ["planning","execution","review","admin"] — a generic day-planner taxonomy.
-- But dayplanner.html's #m-category select emits maintenance categories
-- (PM/CM/Inspection/Training/Admin/Meeting/Other), and all 78 existing
-- schedule_items rows carry exactly those values. Because wh-capture-validate.js
-- fetches contract_schema from this table and validates client-side
-- (validates_at='client'), every real user "Schedule Item" save with a category
-- hit `[capture-violation] schedule_item_v1` and was blocked with a "Cannot
-- save: contract violation" toast — only the seed rows (inserted directly,
-- bypassing the client gate) ever persisted. Found by operating the dayplanner
-- schedule flow and watching the DB row never appear.
--
-- The form + the data are the source of truth here; the contract was authored
-- with the wrong vocabulary. Align the contract's category enum to the real
-- values. Forward-only UPDATE of both the human-readable `fields` and the
-- validated `contract_schema`.

UPDATE public.canonical_capture_contracts
SET
  contract_schema = jsonb_set(
    contract_schema,
    '{properties,category,enum}',
    '["PM","CM","Inspection","Training","Admin","Meeting","Other",null]'::jsonb
  ),
  fields = (
    SELECT jsonb_agg(
      CASE WHEN elem->>'name' = 'category'
        THEN elem || '{"values":["PM","CM","Inspection","Training","Admin","Meeting","Other"]}'::jsonb
        ELSE elem
      END
    )
    FROM jsonb_array_elements(fields) elem
  )
WHERE capture_id = 'schedule_item_v1';
