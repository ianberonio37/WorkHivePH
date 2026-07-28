-- ─────────────────────────────────────────────────────────────────────────────
-- Deleting a PM asset destroys its compliance history. Gate it, and record it.
--
-- FOUND BY THE PM12 WALK (2026-07-28, PM_DEEPWALK_EXPANSION_ROADMAP):
-- pm_completions.asset_id and pm_scope_items.asset_id both CASCADE from pm_assets. Probed live in a
-- rolled-back transaction as a WORKER: deleting one asset ("Caterpillar 3516B") took 31 completion
-- records and 8 scope items with it, and left ZERO audit rows at the database.
--
-- Those 31 rows are not incidental. Each is a record that a named person did a named job on a date;
-- together they are the compliance evidence, and they feed compliance %, on-time delivery and every
-- downstream reliability figure. Deleting an asset therefore changes HISTORICAL compliance
-- retroactively, and until now did so with nothing to show it had happened.
--
-- TWO SEPARATE HOLES, both closed here:
--
-- 1. AUTHORIZATION. pm-scheduler gates the Delete button to a supervisor, or to the member who
--    created the asset — it even toasts "Only supervisors can delete other members' assets." But
--    that rule lived ONLY in the page. `pm_assets_write` is a single ALL policy whose USING clause
--    is satisfied by ANY active member of the hive, so a worker writing through the db client
--    directly deletes a supervisor's asset and its whole history. A UI-only authorization gate is
--    bypassable by definition; the rule has to exist where the write lands.
--    Closed with a RESTRICTIVE DELETE policy, which ANDs with the existing permissive one rather
--    than replacing it — the smallest change that cannot accidentally widen anything else.
--
-- 2. EVIDENCE. There was no DELETE trigger on pm_assets at all. The only record was a row the PAGE
--    wrote after the fact, which any write that does not go through the page skips — the same
--    reasoning as trg_pm_completion_amendment_audit (20260728000004) and the logbook arc's
--    post-close trigger. The trigger below fires BEFORE the cascade, so it can still count what is
--    about to be destroyed, and records those counts: "deleted an asset with 31 completions" is the
--    sentence an auditor needs, and it cannot be reconstructed afterwards.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Authorization: match the rule the UI already states ───────────────────
DROP POLICY IF EXISTS pm_assets_delete_guard ON public.pm_assets;
CREATE POLICY pm_assets_delete_guard
  ON public.pm_assets
  AS RESTRICTIVE
  FOR DELETE
  USING (
    -- Solo (hive-less) assets: only their own author.
    (hive_id IS NULL AND auth_uid = auth.uid())
    -- In a hive: a supervisor, or the member who created this asset.
    OR (hive_id IS NOT NULL AND (
          auth_uid = auth.uid()
          OR EXISTS (
            SELECT 1 FROM public.hive_members hm
             WHERE hm.hive_id  = pm_assets.hive_id
               AND hm.auth_uid = auth.uid()
               AND hm.status   = 'active'
               AND hm.role     = 'supervisor'
          )
       ))
    -- Server-to-server (service_role / psql) keeps its existing reach; RLS is not the tool for
    -- restraining trusted backends, and the seeders legitimately delete.
    OR auth.uid() IS NULL
  );

-- ── 2. Evidence: record the deletion, and what went with it ──────────────────
CREATE OR REPLACE FUNCTION public.audit_pm_asset_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_actor  text;
  v_comps  integer;
  v_scope  integer;
  v_oldest timestamptz;
BEGIN
  -- BEFORE DELETE: the cascade has not run yet, so the children are still countable. After the
  -- statement completes this information no longer exists anywhere.
  SELECT count(*), min(completed_at) INTO v_comps, v_oldest
    FROM public.pm_completions WHERE asset_id = OLD.id;
  SELECT count(*) INTO v_scope
    FROM public.pm_scope_items WHERE asset_id = OLD.id;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.auth_uid = auth.uid()
     AND (OLD.hive_id IS NULL OR hm.hive_id = OLD.hive_id)
   LIMIT 1;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (
    OLD.hive_id,
    COALESCE(v_actor, OLD.worker_name, 'unknown'),
    'delete_pm_asset',
    'pm_assets',
    OLD.id::text,
    COALESCE(OLD.asset_name, '(unnamed asset)'),
    jsonb_build_object(
      'criticality',            OLD.criticality,
      'category',               OLD.category,
      -- What the deletion actually cost, which is the part nobody could see.
      'completions_destroyed',  v_comps,
      'scope_items_destroyed',  v_scope,
      'history_began',          v_oldest,
      'source',                 'db_trigger'
    )
  );

  RETURN OLD;
END;
$function$;

DROP TRIGGER IF EXISTS trg_pm_asset_delete_audit ON public.pm_assets;
CREATE TRIGGER trg_pm_asset_delete_audit
  BEFORE DELETE ON public.pm_assets
  FOR EACH ROW
  EXECUTE FUNCTION public.audit_pm_asset_delete();
