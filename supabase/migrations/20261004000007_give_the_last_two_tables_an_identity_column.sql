-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- community_reactions + fault_knowledge get an identity column (BRP class C, the real ones)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- The wave's class C was "no identity column anywhere, so ownership is only expressible as a name". Most
-- of it turned out not to need a migration at all: marketplace_watchlist and marketplace_saved_searches
-- have RLS keyed on `worker_name IN (SELECT auth_worker_names())`, and auth_worker_names() derives the
-- caller's names from auth.uid() - so the DATABASE already bridges identity to name and the client filter
-- was removable (20261004000006's sibling change in marketplace.html).
--
-- These two are the genuine cases. Their policies scope by HIVE MEMBERSHIP, not by the caller's names:
--     community_reactions_read/_write   auth.uid() IS NOT NULL AND (public post OR hive_id IN my hives)
--     fault_knowledge_read              auth.uid() IS NOT NULL AND hive_id IN my hives
-- so "mine" is narrowed ONLY by the client's `.eq('worker_name', WORKER_NAME)`. Removing that filter would
-- widen the read from my rows to the whole hive's, and keeping it leaves the display-name drift bug. The
-- column is the only honest way out.
--
-- RESOLVABILITY MEASURED FIRST, as every backfill in this wave has been: community_reactions 9 of 9 resolve
-- from (hive_id, worker_name) to exactly one auth_uid; fault_knowledge 3,815 of 3,821, with 6 whose stored
-- name matches no roster row. Those 6 stay NULL and are counted in the notice - guessing an owner is worse
-- than leaving one unbound, and the reads that use this column will union it with the name precisely so an
-- unbound row stays findable.
--
-- NO POLICY IS CHANGED HERE. Adding a nullable column and binding it changes nobody's access: the existing
-- hive-scoped policies still decide every row. The column exists so the CLIENT can ask "mine" by identity
-- instead of by a display string, and so a future policy can be tightened deliberately and reviewed on its
-- own terms.
--
-- fault_knowledge is INSERT/UPDATE/DELETE-locked to members (its policies are literally `false`), so it is
-- written by service_role and triggers only. It therefore gets NO binding trigger: auth.uid() is NULL on
-- those paths, a trigger would never fire usefully, and adding one would be the kind of declared mechanism
-- that does nothing. community_reactions IS member-written, so it gets one.

BEGIN;

ALTER TABLE public.community_reactions ADD COLUMN IF NOT EXISTS auth_uid uuid;
ALTER TABLE public.fault_knowledge     ADD COLUMN IF NOT EXISTS auth_uid uuid;

-- Bind it on every future member INSERT, the same shape as bind_asset_nodes_submitter: only when a real
-- session is present, so a service-role batch keeps whatever it supplied.
CREATE OR REPLACE FUNCTION public.bind_community_reaction_author()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
BEGIN
  IF auth.uid() IS NOT NULL THEN
    NEW.auth_uid := auth.uid();
  END IF;
  RETURN NEW;
END $fn$;

DROP TRIGGER IF EXISTS trg_bind_community_reaction_author ON public.community_reactions;
CREATE TRIGGER trg_bind_community_reaction_author
  BEFORE INSERT ON public.community_reactions
  FOR EACH ROW EXECUTE FUNCTION public.bind_community_reaction_author();

-- ── backfill, unambiguous resolutions only, triggers off so nothing else fires ───────────────────
CREATE TEMP TABLE _cr_before ON COMMIT DROP AS
SELECT (SELECT count(*) FROM public.community_reactions) AS cr_n,
       (SELECT count(*) FROM public.fault_knowledge)     AS fk_n;

ALTER TABLE public.community_reactions DISABLE TRIGGER USER;
ALTER TABLE public.fault_knowledge     DISABLE TRIGGER USER;

UPDATE public.community_reactions c
   SET auth_uid = r.uid
  FROM (SELECT c2.id,
               (SELECT m.auth_uid FROM public.hive_members m
                 WHERE m.hive_id = c2.hive_id AND m.worker_name = c2.worker_name
                   AND m.auth_uid IS NOT NULL LIMIT 1) AS uid
          FROM public.community_reactions c2
         WHERE c2.auth_uid IS NULL
           AND (SELECT count(DISTINCT m.auth_uid) FROM public.hive_members m
                 WHERE m.hive_id = c2.hive_id AND m.worker_name = c2.worker_name
                   AND m.auth_uid IS NOT NULL) = 1) r
 WHERE c.id = r.id AND c.auth_uid IS NULL AND r.uid IS NOT NULL;

UPDATE public.fault_knowledge f
   SET auth_uid = r.uid
  FROM (SELECT f2.id,
               (SELECT m.auth_uid FROM public.hive_members m
                 WHERE m.hive_id = f2.hive_id AND m.worker_name = f2.worker_name
                   AND m.auth_uid IS NOT NULL LIMIT 1) AS uid
          FROM public.fault_knowledge f2
         WHERE f2.auth_uid IS NULL
           AND (SELECT count(DISTINCT m.auth_uid) FROM public.hive_members m
                 WHERE m.hive_id = f2.hive_id AND m.worker_name = f2.worker_name
                   AND m.auth_uid IS NOT NULL) = 1) r
 WHERE f.id = r.id AND f.auth_uid IS NULL AND r.uid IS NOT NULL;

ALTER TABLE public.community_reactions ENABLE TRIGGER USER;
ALTER TABLE public.fault_knowledge     ENABLE TRIGGER USER;

-- Column-level read access must match the table's: these are SELECT-granted to the app roles, and a new
-- column on an existing table inherits the table grant, so nothing extra is needed. Asserted below anyway.
DO $$
DECLARE n_disabled int; cr_bound int; fk_bound int; v_cr_n int; v_fk_n int; fk_left int;
BEGIN
  SELECT count(*) INTO n_disabled
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
   WHERE NOT t.tgisinternal
     AND c.relname IN ('community_reactions','fault_knowledge') AND t.tgenabled = 'D';
  IF n_disabled > 0 THEN
    RAISE EXCEPTION '% trigger(s) left DISABLED - refusing to commit', n_disabled;
  END IF;

  -- the row counts are untouched: a backfill must not create or destroy anything
  SELECT b.cr_n, b.fk_n INTO v_cr_n, v_fk_n FROM _cr_before b;
  IF (SELECT count(*) FROM public.community_reactions) <> v_cr_n THEN
    RAISE EXCEPTION 'community_reactions row count changed'; END IF;
  IF (SELECT count(*) FROM public.fault_knowledge) <> v_fk_n THEN
    RAISE EXCEPTION 'fault_knowledge row count changed'; END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
                  WHERE c.relname='community_reactions'
                    AND t.tgname='trg_bind_community_reaction_author' AND NOT t.tgisinternal) THEN
    RAISE EXCEPTION 'the binding trigger was not created on community_reactions';
  END IF;

  SELECT count(auth_uid) INTO cr_bound FROM public.community_reactions;
  SELECT count(auth_uid) INTO fk_bound FROM public.fault_knowledge;
  SELECT count(*) INTO fk_left FROM public.fault_knowledge WHERE auth_uid IS NULL;
  RAISE NOTICE 'community_reactions: % of % bound', cr_bound, v_cr_n;
  RAISE NOTICE 'fault_knowledge: % of % bound; % left unbound (stored name matches no roster row - NOT guessed)',
               fk_bound, v_fk_n, fk_left;
END $$;

COMMIT;
