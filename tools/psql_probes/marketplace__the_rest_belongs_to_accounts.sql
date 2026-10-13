-- expect: PASS no marketplace policy decides access by a name alone
-- expect: PASS a namesake of the buyer neither reads nor changes the order
-- expect: PASS the order's buyer and its listing's seller both read it
-- expect: PASS a namesake of the reviewer can neither edit nor delete the review
-- expect: PASS a namesake reads none of a person's saved searches or watchlist
-- expect: PASS the reviewer's account key is not readable by anyone browsing reviews
-- expect: PASS a new watchlist row is stamped with the person's account, whatever was sent
-- expect: PASS nothing persisted after the rollback
-- forbid: FAIL
-- the_rest_belongs_to_accounts (2026-10-08, migration 20261008000062). Orders, disputes, reviews, saved searches and
-- the watchlist used the same name test as listings and inquiries did. For each party a NAMESAKE is made inside one
-- rolled-back transaction - an account whose only tie is a hive membership under that party's name. Fixtures (looked
-- up, not typed): Romeo Beltran's order of Bryan Garcia's listing; Leonardo Romero's review; Isidro Suarez's watchlist
-- row; Hector Salvador's saved search.
BEGIN;
SELECT CASE WHEN NOT EXISTS (
         SELECT 1 FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid WHERE c.relname LIKE 'marketplace%'
            AND (coalesce(pg_get_expr(p.polqual, p.polrelid), '') || coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '')) ILIKE '%auth_worker_names%'
            AND (coalesce(pg_get_expr(p.polqual, p.polrelid), '') || coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '')) NOT ILIKE '%auth.uid()%')
       THEN 'PASS' ELSE 'FAIL' END || ' no marketplace policy decides access by a name alone';
SELECT set_config('probe.order', (SELECT o.id::text FROM public.marketplace_orders o JOIN public.marketplace_listings l ON l.id = o.listing_id
  WHERE o.buyer_name = 'Romeo Beltran' AND l.auth_uid = '91e0d1eb-cd96-43ee-af5f-0ff2714b3923' ORDER BY o.created_at LIMIT 1), true);
SELECT set_config('probe.buyer', (SELECT buyer_auth_uid::text FROM public.marketplace_orders WHERE id = current_setting('probe.order')::uuid), true);
SELECT set_config('probe.review', (SELECT id::text FROM public.marketplace_reviews WHERE reviewer_name = 'Leonardo Romero' AND request_id IS NULL ORDER BY created_at LIMIT 1), true);
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, created_at, updated_at)
SELECT v.id::uuid, '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', v.email, '', now(), now(), now()
  FROM (VALUES ('00000000-0000-4000-8000-00000000c001', 'ns.romeo.probe@auth.workhiveph.com'),
               ('00000000-0000-4000-8000-00000000c002', 'ns.leonardo.probe@auth.workhiveph.com'),
               ('00000000-0000-4000-8000-00000000c003', 'ns.isidro.probe@auth.workhiveph.com'),
               ('00000000-0000-4000-8000-00000000c004', 'ns.hector.probe@auth.workhiveph.com')) v(id, email);
INSERT INTO public.hive_members (hive_id, worker_name, auth_uid, role, status)
SELECT (SELECT h.id FROM public.hives h WHERE h.id NOT IN (SELECT hive_id FROM public.hive_members WHERE worker_name = v.nm) ORDER BY h.name LIMIT 1),
       v.nm, v.id::uuid, 'worker', 'active'
  FROM (VALUES ('Romeo Beltran', '00000000-0000-4000-8000-00000000c001'), ('Leonardo Romero', '00000000-0000-4000-8000-00000000c002'),
               ('Isidro Suarez', '00000000-0000-4000-8000-00000000c003'), ('Hector Salvador', '00000000-0000-4000-8000-00000000c004')) v(nm, id);
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000c001","role":"authenticated"}', true);
CREATE TEMP TABLE _o AS SELECT (SELECT count(*) FROM public.marketplace_orders WHERE id = current_setting('probe.order')::uuid) AS seen;
UPDATE public.marketplace_orders SET currency = 'XXX' WHERE id = current_setting('probe.order')::uuid;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000c002","role":"authenticated"}', true);
UPDATE public.marketplace_reviews SET comment = 'namesake edit' WHERE id = current_setting('probe.review')::uuid;
DELETE FROM public.marketplace_reviews WHERE id = current_setting('probe.review')::uuid;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000c003","role":"authenticated"}', true);
CREATE TEMP TABLE _w AS SELECT (SELECT count(*) FROM public.marketplace_watchlist) AS seen;
DELETE FROM public.marketplace_watchlist WHERE true;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000c004","role":"authenticated"}', true);
CREATE TEMP TABLE _s AS SELECT (SELECT count(*) FROM public.marketplace_saved_searches) AS seen;
RESET ROLE;
SELECT CASE WHEN (SELECT seen FROM _o) = 0
             AND (SELECT count(*) FROM public.marketplace_orders WHERE id = current_setting('probe.order')::uuid AND currency = 'XXX') = 0
            THEN 'PASS' ELSE 'FAIL' END || ' a namesake of the buyer neither reads nor changes the order';
SELECT CASE WHEN (SELECT count(*) FROM public.marketplace_reviews WHERE id = current_setting('probe.review')::uuid AND comment IS DISTINCT FROM 'namesake edit') = 1
            THEN 'PASS' ELSE 'FAIL' END || ' a namesake of the reviewer can neither edit nor delete the review';
SELECT CASE WHEN (SELECT seen FROM _w) = 0 AND (SELECT seen FROM _s) = 0
             AND (SELECT count(*) FROM public.marketplace_watchlist WHERE worker_name = 'Isidro Suarez') >= 1
            THEN 'PASS' ELSE 'FAIL' END || ' a namesake reads none of a person''s saved searches or watchlist';
-- the real parties
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', current_setting('probe.buyer'), 'role', 'authenticated')::text, true);
CREATE TEMP TABLE _b AS SELECT (SELECT count(*) FROM public.marketplace_orders WHERE id = current_setting('probe.order')::uuid) AS seen;
INSERT INTO public.marketplace_watchlist (worker_name, listing_id, auth_uid)
SELECT 'Romeo Beltran', (SELECT id FROM public.marketplace_listings WHERE status = 'published' ORDER BY created_at LIMIT 1), '00000000-0000-4000-8000-00000000c003';
SELECT set_config('request.jwt.claims', '{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
CREATE TEMP TABLE _sl AS SELECT (SELECT count(*) FROM public.marketplace_orders WHERE id = current_setting('probe.order')::uuid) AS seen;
RESET ROLE;
SELECT CASE WHEN (SELECT seen FROM _b) = 1 AND (SELECT seen FROM _sl) = 1
            THEN 'PASS' ELSE 'FAIL' END || ' the order''s buyer and its listing''s seller both read it';
SELECT CASE WHEN (SELECT auth_uid::text FROM public.marketplace_watchlist WHERE worker_name = 'Romeo Beltran' ORDER BY created_at DESC LIMIT 1) = current_setting('probe.buyer')
            THEN 'PASS' ELSE 'FAIL' END || ' a new watchlist row is stamped with the person''s account, whatever was sent';
SAVEPOINT k1;
SET LOCAL ROLE anon;
DO $$ BEGIN
  PERFORM reviewer_auth_uid FROM public.marketplace_reviews LIMIT 1;
  RAISE NOTICE 'FAIL the reviewer''s account key is not readable by anyone browsing reviews (anon read it)';
EXCEPTION WHEN insufficient_privilege THEN
  BEGIN
    SET LOCAL ROLE authenticated;
    PERFORM set_config('request.jwt.claims', '{"sub":"91e0d1eb-cd96-43ee-af5f-0ff2714b3923","role":"authenticated"}', true);
    PERFORM reviewer_auth_uid FROM public.marketplace_reviews LIMIT 1;
    RAISE NOTICE 'FAIL the reviewer''s account key is not readable by anyone browsing reviews (a member read it)';
  EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS the reviewer''s account key is not readable by anyone browsing reviews';
  END;
END $$;
ROLLBACK TO SAVEPOINT k1;
RESET ROLE;
ROLLBACK;
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM auth.users WHERE email LIKE 'ns.%.probe@auth.workhiveph.com')
             AND NOT EXISTS (SELECT 1 FROM public.marketplace_orders WHERE currency = 'XXX')
             AND NOT EXISTS (SELECT 1 FROM public.marketplace_reviews WHERE comment = 'namesake edit')
             AND (SELECT count(*) FROM public.marketplace_watchlist WHERE worker_name = 'Romeo Beltran') = 0
            THEN 'PASS' ELSE 'FAIL' END || ' nothing persisted after the rollback';
