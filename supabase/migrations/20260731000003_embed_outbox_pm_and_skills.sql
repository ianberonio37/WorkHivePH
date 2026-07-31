-- 20260731000003_embed_outbox_pm_and_skills.sql
--
-- AUTO-EMBED P2 — make the two remaining HANDLED surfaces UPSERTABLE, which is what they were missing.
--
-- CHECKING THE PREMISE CHANGED THIS MIGRATION COMPLETELY. It was going to attach the generic trigger to
-- `pm_completions` and `skill_badges` the way P1 did for `logbook`. Reading `embed-entry` first showed that
-- would have made things WORSE: only the fault branch sets a `conflictKey` ("logbook_id"), so the other two
-- fall through to a plain `insert`. Firing on UPDATE would therefore ADD a knowledge row per edit instead of
-- replacing one.
--
-- That is not hypothetical — it has already happened. `skill_knowledge` holds **28 rows for 4 distinct
-- (hive_id, worker_name, discipline)**: ~86% duplicates, the same worker's skill embedded over and over, all
-- of it competing with itself in every semantic search. The RAG index has been quietly accumulating stale
-- copies. `pm_knowledge` shows 0 only because every one of its writes 500'd on the FK bug (below), so it
-- never got the chance.
--
-- THE ORDER THAT MATTERS: a surface must be UPSERTABLE **before** it is wired, or wiring it corrupts the
-- corpus faster. So this migration establishes the keys and de-duplicates; the triggers land with the
-- function change that passes `conflictKey`, and NOT before.
--
-- WHY pm_completions IS AT 0% DESPITE 1,591 ROWS: `pm_knowledge.asset_id` is an `asset_nodes.id` FK while the
-- webhook payload's `record.asset_id` is a `pm_ASSETS` id, so every insert violated
-- `pm_knowledge_asset_id_fkey` — the function's own comment calls it a "silent RAG starve". The resolution
-- through `v_asset_truth` is already in the code; nothing ever re-ran the rows.
--
-- THE NATURAL KEYS, read from the data rather than assumed from the names:
--   pm_knowledge     is one row per ASSET (asset_id, asset_name, category, overdue_count, last_completed) —
--                    an asset-level summary, NOT a per-completion record. Key: (hive_id, asset_id).
--   skill_knowledge  is one row per worker-discipline (worker_name, discipline, level, primary_skill).
--                    Key: (hive_id, worker_name, discipline).

BEGIN;

-- ── de-duplicate before constraining, keeping the NEWEST row per key ────────────────────────────────────
-- Newest wins because these are summaries: the most recent embed reflects the current level/primary_skill.
-- Deleting the older copies is the point — they are the stale contenders that were polluting retrieval.
DELETE FROM public.skill_knowledge s
 USING public.skill_knowledge keep
 WHERE s.hive_id     IS NOT DISTINCT FROM keep.hive_id
   AND s.worker_name IS NOT DISTINCT FROM keep.worker_name
   AND s.discipline  IS NOT DISTINCT FROM keep.discipline
   AND s.id <> keep.id
   AND (keep.updated_at, keep.id) > (s.updated_at, s.id);

DELETE FROM public.pm_knowledge p
 USING public.pm_knowledge keep
 WHERE p.hive_id  IS NOT DISTINCT FROM keep.hive_id
   AND p.asset_id IS NOT DISTINCT FROM keep.asset_id
   AND p.id <> keep.id
   AND (keep.updated_at, keep.id) > (p.updated_at, p.id);

-- ── the keys that make a re-embed REPLACE instead of accumulate ─────────────────────────────────────────
-- Same discipline as the fault corpus's uidx (20260708000002), which is why logbook never grew duplicates.
CREATE UNIQUE INDEX IF NOT EXISTS skill_knowledge_one_per_worker_discipline
  ON public.skill_knowledge (hive_id, worker_name, discipline);
CREATE UNIQUE INDEX IF NOT EXISTS pm_knowledge_one_per_asset
  ON public.pm_knowledge (hive_id, asset_id);

-- ── register the surfaces (inactive until the function upserts) ─────────────────────────────────────────
-- `active=false` is the registry earning its keep: the config can land, be reviewed and be version
-- controlled while the surface stays switched OFF, and enabling it later is an UPDATE rather than DDL.
-- min_chars is 0 because embed-entry composes these from LOOKUPS (asset name, category, dates), not from the
-- row's own columns — any composition stated here would be a guess that could skip a row the function would
-- have embedded. The function is the authority on its own skip rule.
INSERT INTO public.embedding_registry
  (source_table, target_table, conflict_key, min_chars, embedding_model, text_fields, visibility, active)
VALUES
  ('pm_completions', 'pm_knowledge',    'hive_id,asset_id',                 0,
   'bge-small-en-v1.5', '[]'::jsonb, 'mirror_source', false),
  ('skill_badges',   'skill_knowledge', 'hive_id,worker_name,discipline',   0,
   'bge-small-en-v1.5', '[]'::jsonb, 'mirror_source', false)
ON CONFLICT (source_table) DO UPDATE
  SET target_table = EXCLUDED.target_table,
      conflict_key = EXCLUDED.conflict_key;

-- NOTE: the triggers are deliberately NOT attached here. `enqueue_for_embedding()` already no-ops for an
-- inactive registry row, so attaching them would be harmless — but leaving them off keeps the migration
-- honest about what is live, and they land in the same change that teaches embed-entry to pass conflictKey.

COMMIT;
