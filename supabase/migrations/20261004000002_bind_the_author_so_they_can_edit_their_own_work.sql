-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Bind the author, so a person can edit their own work (BRP, the severe half)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- FOUND WHILE FIXING THE LOGBOOK ASSET PICKER (Ian, 2026-10-04: "in the select an asset there is
-- nothing there, but I can see it in my asset hub"). The picker bug was a display-name-vs-identity
-- mismatch. Measuring how far that class reached turned up something much worse than an empty dropdown.
--
-- ★27,420 OF 31,241 LOGBOOK ENTRIES (87.8%) CANNOT BE EDITED OR DELETED BY THE PEOPLE WHO WROTE THEM.
-- The write policies are:
--     logbook_update : (auth.uid() IS NOT NULL) AND (auth_uid = auth.uid())
--     logbook_delete : (auth.uid() IS NOT NULL) AND (auth_uid = auth.uid())
-- and those rows carry auth_uid NULL, so `NULL = auth.uid()` is NULL, never true. There is no second
-- permissive policy for UPDATE or DELETE, so there is no other path. PROVEN by impersonation, not
-- inferred: acting as the resolved author of one such entry (role authenticated +
-- request.jwt.claims.sub), the entry was READABLE (1 row) while UPDATE returned 0 rows and DELETE
-- returned 0 rows. A 0-row UPDATE raises no error, so a worker amends an entry, sees nothing go wrong,
-- and the amendment is simply gone. Same shape on inventory_items (10 rows) and asset_nodes (24), whose
-- *_write policies key on auth_uid the same way.
--
-- THE REPAIR IS RECOVERABLE AND UNAMBIGUOUS, MEASURED BEFORE IT IS WRITTEN. For every NULL row the
-- author is resolvable from the roster by (hive_id, worker_name): logbook 27,420 of 27,420 resolve to
-- EXACTLY ONE auth_uid, inventory_items 10 of 10, asset_nodes 5 of 24. Zero ambiguous (no two people
-- share a display name inside one hive). The 19 asset_nodes rows with no roster match are LEFT NULL and
-- counted in the notice - guessing an owner is worse than leaving one unbound.
--
-- ★WHY EVERY TRIGGER IS DISABLED FOR THE DURATION. This is a pure identity backfill: it must change who
-- OWNS a row and nothing else. Three UPDATE triggers on logbook carry no change guard and would each do
-- real damage over 27,420 rows:
--   touch_logbook_updated_at           unconditional `NEW.updated_at := now()` - it would stamp every
--                                      historical entry as edited today, destroying the real edit times
--   audit_logbook_post_close_amendment no IS DISTINCT FROM guard - 27,420 phantom "amendment" audit rows
--   enqueue_for_embedding              no change guard - 27,420 rows queued for PAID re-embedding
-- (trg_logbook_achievement_xp does guard on change, and is disabled anyway for the same reason.) The
-- sibling tables add approval guards, pending-submission notifications and approved_by rebinding, none
-- of which should fire for a column the person never touched. DISABLE TRIGGER USER is transactional and
-- re-enabled below, and the verification block FAILS the migration if any trigger is left disabled.
-- It takes an ACCESS EXCLUSIVE lock, so on production this is a brief table lock, not an online change.

BEGIN;

-- ── before ───────────────────────────────────────────────────────────────────────────────────────
CREATE TEMP TABLE _before ON COMMIT DROP AS
SELECT 'logbook' AS rel, count(*) AS n, count(auth_uid) AS have_uid FROM public.logbook
UNION ALL SELECT 'inventory_items', count(*), count(auth_uid) FROM public.inventory_items
UNION ALL SELECT 'asset_nodes', count(*), count(auth_uid) FROM public.asset_nodes;

-- A fingerprint of the edit history, so the verification can prove updated_at was NOT churned.
CREATE TEMP TABLE _before_touch ON COMMIT DROP AS
SELECT id, updated_at FROM public.logbook WHERE auth_uid IS NULL ORDER BY id LIMIT 500;

CREATE TEMP TABLE _audit_before ON COMMIT DROP AS SELECT count(*) AS n FROM public.hive_audit_log;

ALTER TABLE public.logbook         DISABLE TRIGGER USER;
ALTER TABLE public.inventory_items DISABLE TRIGGER USER;
ALTER TABLE public.asset_nodes     DISABLE TRIGGER USER;

-- ── the backfill · unambiguous resolutions only ──────────────────────────────────────────────────
UPDATE public.logbook l
   SET auth_uid = r.uid
  FROM (SELECT l2.id,
               (SELECT m.auth_uid FROM public.hive_members m
                 WHERE m.hive_id = l2.hive_id AND m.worker_name = l2.worker_name
                   AND m.auth_uid IS NOT NULL LIMIT 1) AS uid
          FROM public.logbook l2
         WHERE l2.auth_uid IS NULL
           AND (SELECT count(DISTINCT m.auth_uid) FROM public.hive_members m
                 WHERE m.hive_id = l2.hive_id AND m.worker_name = l2.worker_name
                   AND m.auth_uid IS NOT NULL) = 1) r
 WHERE l.id = r.id AND l.auth_uid IS NULL AND r.uid IS NOT NULL;

UPDATE public.inventory_items i
   SET auth_uid = r.uid
  FROM (SELECT i2.id,
               (SELECT m.auth_uid FROM public.hive_members m
                 WHERE m.hive_id = i2.hive_id AND m.worker_name = i2.worker_name
                   AND m.auth_uid IS NOT NULL LIMIT 1) AS uid
          FROM public.inventory_items i2
         WHERE i2.auth_uid IS NULL
           AND (SELECT count(DISTINCT m.auth_uid) FROM public.hive_members m
                 WHERE m.hive_id = i2.hive_id AND m.worker_name = i2.worker_name
                   AND m.auth_uid IS NOT NULL) = 1) r
 WHERE i.id = r.id AND i.auth_uid IS NULL AND r.uid IS NOT NULL;

UPDATE public.asset_nodes a
   SET auth_uid = r.uid
  FROM (SELECT a2.id,
               (SELECT m.auth_uid FROM public.hive_members m
                 WHERE m.hive_id = a2.hive_id AND m.worker_name = a2.worker_name
                   AND m.auth_uid IS NOT NULL LIMIT 1) AS uid
          FROM public.asset_nodes a2
         WHERE a2.auth_uid IS NULL
           AND (SELECT count(DISTINCT m.auth_uid) FROM public.hive_members m
                 WHERE m.hive_id = a2.hive_id AND m.worker_name = a2.worker_name
                   AND m.auth_uid IS NOT NULL) = 1) r
 WHERE a.id = r.id AND a.auth_uid IS NULL AND r.uid IS NOT NULL;

ALTER TABLE public.logbook         ENABLE TRIGGER USER;
ALTER TABLE public.inventory_items ENABLE TRIGGER USER;
ALTER TABLE public.asset_nodes     ENABLE TRIGGER USER;

-- ── verify in the same transaction ───────────────────────────────────────────────────────────────
DO $$
DECLARE
  r record;
  n_disabled int;
  n_churned int;
  n_audit_new int;
  n_left_null int;
BEGIN
  -- 1 · every trigger is back on. A migration that silently leaves triggers disabled is far worse
  --     than the bug it fixed: the next ordinary write would skip every audit and guard.
  SELECT count(*) INTO n_disabled
    FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
   WHERE NOT t.tgisinternal
     AND c.relname IN ('logbook', 'inventory_items', 'asset_nodes')
     AND t.tgenabled = 'D';
  IF n_disabled > 0 THEN
    RAISE EXCEPTION '% trigger(s) left DISABLED - refusing to commit', n_disabled;
  END IF;

  -- 2 · the edit history was not churned: updated_at is byte-identical on the sampled rows
  SELECT count(*) INTO n_churned
    FROM _before_touch b JOIN public.logbook l ON l.id = b.id
   WHERE l.updated_at IS DISTINCT FROM b.updated_at;
  IF n_churned > 0 THEN
    RAISE EXCEPTION '% sampled row(s) had updated_at rewritten - the touch trigger fired', n_churned;
  END IF;

  -- 3 · no phantom amendment audit rows
  SELECT (SELECT count(*) FROM public.hive_audit_log) - (SELECT n FROM _audit_before) INTO n_audit_new;
  IF n_audit_new <> 0 THEN
    RAISE EXCEPTION 'the backfill wrote % audit row(s); it must write none', n_audit_new;
  END IF;

  -- 4 · coverage moved the way the measurement said it would, and nothing lost an owner
  FOR r IN SELECT b.rel, b.n, b.have_uid AS before_uid,
                  CASE b.rel WHEN 'logbook' THEN (SELECT count(auth_uid) FROM public.logbook)
                             WHEN 'inventory_items' THEN (SELECT count(auth_uid) FROM public.inventory_items)
                             ELSE (SELECT count(auth_uid) FROM public.asset_nodes) END AS after_uid
             FROM _before b LOOP
    IF r.after_uid < r.before_uid THEN
      RAISE EXCEPTION '% LOST owners: % -> %', r.rel, r.before_uid, r.after_uid;
    END IF;
    RAISE NOTICE '% : auth_uid bound on % of % rows (was %)', r.rel, r.after_uid, r.n, r.before_uid;
  END LOOP;

  -- 5 · what is deliberately left unbound, said out loud rather than silently
  SELECT count(*) INTO n_left_null FROM public.asset_nodes WHERE auth_uid IS NULL;
  RAISE NOTICE 'asset_nodes left unbound (no roster match for the stored name - NOT guessed): %',
               n_left_null;
  SELECT count(*) INTO n_left_null FROM public.logbook WHERE auth_uid IS NULL;
  RAISE NOTICE 'logbook left unbound: %', n_left_null;
END $$;

COMMIT;
