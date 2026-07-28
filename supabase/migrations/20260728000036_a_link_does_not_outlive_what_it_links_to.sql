-- ─────────────────────────────────────────────────────────────────────────────
-- A project link outlives the thing it points at, and keeps showing its name.
--
-- FOUND BY THE PJ11 WALK (2026-07-28) — the journey asks whether links survive deletion. They do,
-- which is the problem.
--
-- `project_links` binds a project to the logbook entries, PM completions, inventory parts, design
-- calcs and asset nodes behind it — the traceability the whole surface exists for. `link_id` is
-- TEXT and `link_type` chooses the table, so there is no foreign key to lean on. The only FK on the
-- table is project_id -> projects. Proven live, in a rolled-back transaction:
--
--     DELETE one linked logbook entry  ->  2 project_links rows orphaned, no error, no cleanup
--
-- And nothing shows it. The link pill renders `label || link_id`, so a deleted logbook entry keeps
-- displaying its old title on the project forever — a reference that reads as evidence and points
-- at nothing. That is worse than an absent link: someone reviewing a shutdown sees the work cited.
--
-- (The same walk found the seeded asset links had NEVER resolved — they carried the seeder's
-- in-memory `asset-9fbe0f6f4022` ids, which are written to no table. Fixed in the seeder, and the
-- data tier now asserts every link resolves. This migration handles the other direction: links that
-- resolved once and stopped.)
--
-- WHY AFTER DELETE TRIGGERS RATHER THAN A FOREIGN KEY. A polymorphic reference cannot have one — a
-- single text column pointing into five different tables is exactly what an FK cannot express.
-- Rewriting it as five nullable typed columns would be the textbook fix, and would rewrite every
-- reader and writer on the surface. One shared trigger function, installed on each target table
-- with its link_type as the argument, gets the same guarantee at a fraction of the blast radius.
--
-- DELETE rather than mark-as-broken, because the link is a pointer, not a record: the project's own
-- history lives in its progress logs and change orders, which are separately immutable. A pointer
-- to nothing has nothing to preserve. Deletions of the parent PROJECT are already handled by the
-- existing project_id FK.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.cleanup_project_links_on_target_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
BEGIN
  -- TG_ARGV[0] is the link_type this table backs. Scoped by BOTH type and id so a uuid that
  -- coincidentally appears under another type is never touched.
  DELETE FROM public.project_links
   WHERE link_type = TG_ARGV[0]
     AND link_id   = OLD.id::text;
  RETURN OLD;
END;
$function$;

COMMENT ON FUNCTION public.cleanup_project_links_on_target_delete() IS
  'AFTER DELETE on a project_links target table: removes links that pointed at the deleted row. '
  'link_id is a polymorphic TEXT reference so no foreign key can express this. Proven live before '
  'the fix — deleting one linked logbook entry orphaned 2 links, which kept rendering the deleted '
  'entry''s title on the project. PJ11, 2026-07-28.';

DO $$
DECLARE
  t record;
BEGIN
  FOR t IN
    SELECT * FROM (VALUES
      ('logbook',           'logbook'),
      ('pm_completions',    'pm_completion'),
      ('inventory_items',   'inventory_item'),
      ('engineering_calcs', 'engineering_calc'),
      ('asset_nodes',       'asset')
    ) AS v(tbl, link_type)
  LOOP
    IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = t.tbl AND c.relkind = 'r') THEN
      EXECUTE format('DROP TRIGGER IF EXISTS trg_cleanup_project_links ON public.%I', t.tbl);
      EXECUTE format(
        'CREATE TRIGGER trg_cleanup_project_links AFTER DELETE ON public.%I '
        'FOR EACH ROW EXECUTE FUNCTION public.cleanup_project_links_on_target_delete(%L)',
        t.tbl, t.link_type);
    ELSE
      RAISE NOTICE 'skipping %, table not present', t.tbl;
    END IF;
  END LOOP;
END $$;
