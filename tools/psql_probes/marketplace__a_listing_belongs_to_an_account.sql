-- expect: PASS every listing policy keys ownership on the account, none on a name
-- expect: PASS the namesake's update and delete leave the owner's listing untouched
-- expect: PASS the namesake sees none of the owner's drafts, through the table or the public view
-- expect: PASS the owner edits their own listing
-- expect: PASS a new listing is stamped with the lister's account
-- expect: PASS is_mine marks the owner's listings and only theirs
-- expect: PASS another member cannot read the owner key
-- expect: PASS the owner key cannot be rewritten through the API
-- expect: PASS an insert naming another account as owner is refused
-- expect: PASS nothing persisted after the rollback
-- forbid: FAIL
-- a_listing_belongs_to_an_account (2026-10-08, migration 20261008000060). Before it, every marketplace_listings policy
-- asked whether seller_name was among auth_worker_names(), and any signed-in person can hold any name (found a hive,
-- join it under that name - 20261008000031). This probe makes such a NAMESAKE inside one rolled-back transaction - an
-- account whose only tie to Bryan Garcia (91e0d1eb, a seller) is a membership named "Bryan Garcia" in a hive Bryan
-- is not in - and acts as the person (role authenticated + JWT claims).
-- accounts by EMAIL, resolved before any role switch (literal uids rotted when accounts were recreated, 2026-10-27)
CREATE TEMP TABLE IF NOT EXISTS _probe_acct AS SELECT
  (SELECT id FROM auth.users WHERE email = 'bryangarcia@auth.workhiveph.com') AS bryan,
  (SELECT id FROM auth.users WHERE email = 'junvanowner@auth.workhiveph.com') AS jun;
GRANT SELECT ON _probe_acct TO authenticated;
BEGIN;
SELECT CASE WHEN NOT EXISTS (
         SELECT 1 FROM pg_policy p WHERE p.polrelid = 'public.marketplace_listings'::regclass AND p.polcmd IN ('r', 'w', 'd')
            AND coalesce(pg_get_expr(p.polqual, p.polrelid), '') ILIKE '%auth_worker_names%')
        AND (SELECT count(*) FROM pg_policy p WHERE p.polrelid = 'public.marketplace_listings'::regclass
              AND (coalesce(pg_get_expr(p.polqual, p.polrelid), '') || coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '')) ~* 'auth_uid = (\( SELECT )?auth\.uid\(\)') >= 4
       THEN 'PASS' ELSE 'FAIL' END || ' every listing policy keys ownership on the account, none on a name';
SELECT set_config('probe.listing', (SELECT id::text FROM public.marketplace_listings
  WHERE auth_uid = (SELECT bryan FROM _probe_acct) ORDER BY created_at, id LIMIT 1), true);
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, created_at, updated_at)
VALUES ('00000000-0000-4000-8000-00000000b0b0', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
        'namesake.probe@auth.workhiveph.com', '', now(), now(), now());
INSERT INTO public.hive_members (hive_id, worker_name, auth_uid, role, status)
SELECT h.id, 'Bryan Garcia', '00000000-0000-4000-8000-00000000b0b0', 'worker', 'active' FROM public.hives h
 WHERE h.id NOT IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = (SELECT bryan FROM _probe_acct))
 ORDER BY h.name LIMIT 1;
-- the namesake, signed in as themselves
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000b0b0","role":"authenticated"}', true);
UPDATE public.marketplace_listings SET title = title || ' [namesake]' WHERE id = current_setting('probe.listing')::uuid;
DELETE FROM public.marketplace_listings WHERE id = current_setting('probe.listing')::uuid;
CREATE TEMP TABLE _seen AS SELECT
  (SELECT count(*) FROM public.marketplace_listings WHERE seller_name = 'Bryan Garcia' AND status <> 'published') AS tbl,
  (SELECT count(*) FROM public.v_marketplace_listings_public WHERE seller_name = 'Bryan Garcia' AND status <> 'published') AS pub,
  (SELECT count(*) FROM public.v_marketplace_listings_truth WHERE is_mine) AS mine;
RESET ROLE;
SELECT CASE WHEN (SELECT count(*) FROM public.marketplace_listings WHERE id = current_setting('probe.listing')::uuid
                    AND title NOT LIKE '%[namesake]') = 1
            THEN 'PASS' ELSE 'FAIL' END || ' the namesake''s update and delete leave the owner''s listing untouched';
SELECT CASE WHEN (SELECT tbl = 0 AND pub = 0 FROM _seen)
            THEN 'PASS' ELSE 'FAIL' END || ' the namesake sees none of the owner''s drafts, through the table or the public view';
-- the owner
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT bryan FROM _probe_acct)::text, 'role', 'authenticated')::text, true);
UPDATE public.marketplace_listings SET title = title || ' [owner]' WHERE id = current_setting('probe.listing')::uuid;
CREATE TEMP TABLE _owner AS SELECT
  (SELECT count(*) FROM public.v_marketplace_listings_truth WHERE is_mine) AS mine,
  (SELECT count(*) FROM public.v_marketplace_listings_truth WHERE is_mine AND seller_name <> 'Bryan Garcia') AS foreign_mine;
INSERT INTO public.marketplace_listings (section, title, seller_name, status, category, price, hive_id)
VALUES ('parts', 'probe listing 60', 'Bryan Garcia', 'draft', 'Bearings', 100,
        (SELECT hive_id FROM public.hive_members WHERE auth_uid = (SELECT bryan FROM _probe_acct) AND status = 'active' LIMIT 1));
RESET ROLE;
SELECT CASE WHEN (SELECT count(*) FROM public.marketplace_listings WHERE id = current_setting('probe.listing')::uuid AND title LIKE '%[owner]') = 1
            THEN 'PASS' ELSE 'FAIL' END || ' the owner edits their own listing';
SELECT CASE WHEN (SELECT auth_uid = (SELECT bryan FROM _probe_acct) FROM public.marketplace_listings WHERE title = 'probe listing 60')
            THEN 'PASS' ELSE 'FAIL' END || ' a new listing is stamped with the lister''s account';
SELECT CASE WHEN (SELECT mine FROM _owner) = (SELECT count(*) FROM public.marketplace_listings WHERE auth_uid = (SELECT bryan FROM _probe_acct) AND title <> 'probe listing 60')
             AND (SELECT mine FROM _owner) > 0 AND (SELECT foreign_mine FROM _owner) = 0 AND (SELECT mine FROM _seen) = 0
            THEN 'PASS' ELSE 'FAIL' END || ' is_mine marks the owner''s listings and only theirs';
SAVEPOINT k1;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000b0b0","role":"authenticated"}', true);
DO $$ BEGIN
  PERFORM auth_uid FROM public.marketplace_listings LIMIT 1;
  RAISE NOTICE 'FAIL another member cannot read the owner key (it was readable)';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS another member cannot read the owner key';
END $$;
ROLLBACK TO SAVEPOINT k1;
SAVEPOINT k2;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT bryan FROM _probe_acct)::text, 'role', 'authenticated')::text, true);
DO $$ BEGIN
  UPDATE public.marketplace_listings SET auth_uid = '00000000-0000-4000-8000-00000000b0b0' WHERE id = current_setting('probe.listing')::uuid;
  RAISE NOTICE 'FAIL the owner key cannot be rewritten through the API (it was rewritten)';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS the owner key cannot be rewritten through the API';
END $$;
ROLLBACK TO SAVEPOINT k2;
SAVEPOINT k3;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000b0b0","role":"authenticated"}', true);
DO $$ BEGIN
  INSERT INTO public.marketplace_listings (section, title, seller_name, status, category, price, auth_uid)
  VALUES ('parts', 'probe spoof 60', 'Bryan Garcia', 'draft', 'Bearings', 100, (SELECT bryan FROM _probe_acct));
  IF EXISTS (SELECT 1 FROM public.v_marketplace_listings_truth WHERE title = 'probe spoof 60' AND NOT is_mine) THEN
    RAISE NOTICE 'FAIL an insert naming another account as owner is refused (it landed on the other account)';
  ELSE
    RAISE NOTICE 'PASS an insert naming another account as owner is refused';   -- the bind trigger re-stamped the inserter
  END IF;
EXCEPTION WHEN insufficient_privilege OR check_violation OR raise_exception THEN RAISE NOTICE 'PASS an insert naming another account as owner is refused';
END $$;
ROLLBACK TO SAVEPOINT k3;
RESET ROLE;
ROLLBACK;
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM public.marketplace_listings WHERE title LIKE 'probe %60' OR title LIKE '%[namesake]' OR title LIKE '%[owner]')
             AND NOT EXISTS (SELECT 1 FROM auth.users WHERE email = 'namesake.probe@auth.workhiveph.com')
            THEN 'PASS' ELSE 'FAIL' END || ' nothing persisted after the rollback';
