-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Bind the author on pm_assets, so its delete guard can key on the identity (BRP-A)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Third in the series that began with Ian's 2026-10-04 report of an empty "select an asset" dropdown.
-- pm-scheduler.html deletes a PM asset with `.eq('id', …).eq('worker_name', WORKER_NAME)`, a display-name
-- guard that matches nothing once the name drifts - and PostgREST answers a delete that matched nothing
-- with no error, so the person is told it worked. The fix is to guard on auth_uid, which is what the row
-- is actually bound to. That is only safe at FULL coverage: 20 of 120 pm_assets rows carried auth_uid
-- NULL, and tightening first would have made those 20 undeletable by their own owners - the precise
-- defect 20261004000002 repaired on logbook, re-introduced from the other side.
--
-- All 20 resolve from the roster by (hive_id, worker_name) to EXACTLY ONE auth_uid; zero ambiguous, zero
-- unmatched. Measured before this was written, not assumed.
--
-- TRIGGERS OFF FOR THE DURATION, same reasoning as 20261004000002: a pure identity backfill must change
-- who owns a row and nothing else, and an unguarded touch_updated_at or notification trigger firing over
-- 20 rows would rewrite history or send mail about a column nobody touched. Transactional, re-enabled
-- below, and the verification block refuses to commit if any trigger is left disabled.
--
-- NOT backfilled here, deliberately, because they do NOT resolve: community_xp (10 rows) and
-- skill_profiles (1) have no roster row for their stored name. Their reads take the identity-OR-name
-- union instead, which needs no backfill, and inventing an owner for them would be worse than leaving
-- them unbound.

BEGIN;

CREATE TEMP TABLE _pm_before ON COMMIT DROP AS
SELECT count(*) AS n, count(auth_uid) AS have_uid FROM public.pm_assets;

ALTER TABLE public.pm_assets DISABLE TRIGGER USER;

UPDATE public.pm_assets a
   SET auth_uid = r.uid
  FROM (SELECT a2.id,
               (SELECT m.auth_uid FROM public.hive_members m
                 WHERE m.hive_id = a2.hive_id AND m.worker_name = a2.worker_name
                   AND m.auth_uid IS NOT NULL LIMIT 1) AS uid
          FROM public.pm_assets a2
         WHERE a2.auth_uid IS NULL
           AND (SELECT count(DISTINCT m.auth_uid) FROM public.hive_members m
                 WHERE m.hive_id = a2.hive_id AND m.worker_name = a2.worker_name
                   AND m.auth_uid IS NOT NULL) = 1) r
 WHERE a.id = r.id AND a.auth_uid IS NULL AND r.uid IS NOT NULL;

ALTER TABLE public.pm_assets ENABLE TRIGGER USER;

DO $$
DECLARE n_disabled int; n_now int; n_before int; n_left int;
BEGIN
  SELECT count(*) INTO n_disabled
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
   WHERE NOT t.tgisinternal AND c.relname = 'pm_assets' AND t.tgenabled = 'D';
  IF n_disabled > 0 THEN
    RAISE EXCEPTION '% trigger(s) left DISABLED on pm_assets - refusing to commit', n_disabled;
  END IF;

  SELECT count(auth_uid) INTO n_now FROM public.pm_assets;
  SELECT have_uid INTO n_before FROM _pm_before;
  IF n_now < n_before THEN
    RAISE EXCEPTION 'pm_assets LOST owners: % -> %', n_before, n_now;
  END IF;

  SELECT count(*) INTO n_left FROM public.pm_assets WHERE auth_uid IS NULL;
  RAISE NOTICE 'pm_assets: auth_uid bound on % of % rows (was %); left unbound: %',
               n_now, (SELECT n FROM _pm_before), n_before, n_left;
END $$;

COMMIT;
