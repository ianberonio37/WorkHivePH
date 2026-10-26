-- expect: PASS every inquiry policy keys its parties on accounts, none on a name
-- expect: PASS a namesake of the buyer neither reads nor rewrites the conversation
-- expect: PASS a namesake of the seller neither reads nor rewrites the conversation
-- expect: PASS the seller reads the inquiry as addressed to them and can reply
-- expect: PASS the buyer reads the inquiry as their own
-- expect: PASS the seller cannot read the buyer's account key
-- expect: PASS a new inquiry is stamped with the sender's account, whatever was sent
-- expect: PASS nothing persisted after the rollback
-- forbid: FAIL
-- an_inquiry_belongs_to_its_two_accounts (2026-10-08, migration 20261008000061). An inquiry is a private conversation
-- between a buyer and a listing's owner. Before, every policy asked buyer_name / seller_name IN auth_worker_names(),
-- and any signed-in person can hold any name. Fixture: Romeo Beltran's inquiry about a listing its seller owns (read from the row).
-- Two NAMESAKES are made inside one rolled-back transaction, each an account whose only tie to the party is a hive
-- membership under that party's name, in a hive the party is not in.
-- accounts by EMAIL, resolved before any role switch (literal uids rotted when accounts were recreated, 2026-10-27)
CREATE TEMP TABLE IF NOT EXISTS _probe_acct AS SELECT
  -- the SELLER of Romeo Beltran's own row (whoever the seed made it), not a pinned person
  (SELECT l.auth_uid FROM public.marketplace_inquiries i JOIN public.marketplace_listings l ON l.id = i.listing_id
     WHERE i.buyer_name = 'Romeo Beltran' AND l.auth_uid IS NOT NULL ORDER BY i.created_at LIMIT 1) AS seller,
  (SELECT id FROM auth.users WHERE email = 'junvanowner@auth.workhiveph.com') AS jun;
GRANT SELECT ON _probe_acct TO authenticated;
BEGIN;
SELECT CASE WHEN NOT EXISTS (
         SELECT 1 FROM pg_policy p WHERE p.polrelid = 'public.marketplace_inquiries'::regclass
            AND (coalesce(pg_get_expr(p.polqual, p.polrelid), '') || coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '')) ILIKE '%seller_name%')
        AND (SELECT count(*) FROM pg_policy p WHERE p.polrelid = 'public.marketplace_inquiries'::regclass
              AND (coalesce(pg_get_expr(p.polqual, p.polrelid), '') || coalesce(pg_get_expr(p.polwithcheck, p.polrelid), '')) ~* 'buyer_auth_uid = (\( SELECT )?auth\.uid\(\)') = 3
       THEN 'PASS' ELSE 'FAIL' END || ' every inquiry policy keys its parties on accounts, none on a name';
SELECT set_config('probe.inq', (SELECT i.id::text FROM public.marketplace_inquiries i JOIN public.marketplace_listings l ON l.id = i.listing_id
  WHERE i.buyer_name = 'Romeo Beltran' AND l.auth_uid = (SELECT seller FROM _probe_acct) ORDER BY i.created_at LIMIT 1), true);
SELECT set_config('probe.buyer', (SELECT buyer_auth_uid::text FROM public.marketplace_inquiries WHERE id = current_setting('probe.inq')::uuid), true);
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, created_at, updated_at) VALUES
  ('00000000-0000-4000-8000-00000000b001', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'namesake.buyer.probe@auth.workhiveph.com', '', now(), now(), now()),
  ('00000000-0000-4000-8000-00000000b002', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated', 'namesake.seller.probe@auth.workhiveph.com', '', now(), now(), now());
INSERT INTO public.hive_members (hive_id, worker_name, auth_uid, role, status)
SELECT h.id, 'Romeo Beltran', '00000000-0000-4000-8000-00000000b001', 'worker', 'active' FROM public.hives h
 WHERE h.id NOT IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = current_setting('probe.buyer')::uuid) ORDER BY h.name LIMIT 1;
INSERT INTO public.hive_members (hive_id, worker_name, auth_uid, role, status)
SELECT h.id, (SELECT display_name FROM public.worker_profiles WHERE auth_uid = (SELECT seller FROM _probe_acct) LIMIT 1), '00000000-0000-4000-8000-00000000b002', 'worker', 'active' FROM public.hives h
 WHERE h.id NOT IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = (SELECT seller FROM _probe_acct)) ORDER BY h.name LIMIT 1;
-- the buyer's namesake, then the seller's namesake
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000b001","role":"authenticated"}', true);
CREATE TEMP TABLE _nb AS SELECT (SELECT count(*) FROM public.v_marketplace_inquiries_truth WHERE id = current_setting('probe.inq')::uuid) AS seen;
UPDATE public.marketplace_inquiries SET message = message || ' [namesake]' WHERE id = current_setting('probe.inq')::uuid;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000b002","role":"authenticated"}', true);
CREATE TEMP TABLE _ns AS SELECT (SELECT count(*) FROM public.v_marketplace_inquiries_truth WHERE id = current_setting('probe.inq')::uuid) AS seen;
UPDATE public.marketplace_inquiries SET reply_text = 'namesake reply' WHERE id = current_setting('probe.inq')::uuid;
RESET ROLE;
SELECT CASE WHEN (SELECT seen FROM _nb) = 0 AND (SELECT count(*) FROM public.marketplace_inquiries
                   WHERE id = current_setting('probe.inq')::uuid AND message LIKE '%[namesake]') = 0
            THEN 'PASS' ELSE 'FAIL' END || ' a namesake of the buyer neither reads nor rewrites the conversation';
SELECT CASE WHEN (SELECT seen FROM _ns) = 0 AND (SELECT count(*) FROM public.marketplace_inquiries
                   WHERE id = current_setting('probe.inq')::uuid AND reply_text = 'namesake reply') = 0
            THEN 'PASS' ELSE 'FAIL' END || ' a namesake of the seller neither reads nor rewrites the conversation';
-- the seller (the listing's owner)
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT seller FROM _probe_acct)::text, 'role', 'authenticated')::text, true);
CREATE TEMP TABLE _sel AS SELECT to_me, from_me FROM public.v_marketplace_inquiries_truth WHERE id = current_setting('probe.inq')::uuid;
UPDATE public.marketplace_inquiries SET reply_text = 'probe reply 61', status = 'replied', replied_at = now() WHERE id = current_setting('probe.inq')::uuid;
-- the buyer
SELECT set_config('request.jwt.claims', json_build_object('sub', current_setting('probe.buyer'), 'role', 'authenticated')::text, true);
CREATE TEMP TABLE _buy AS SELECT to_me, from_me FROM public.v_marketplace_inquiries_truth WHERE id = current_setting('probe.inq')::uuid;
INSERT INTO public.marketplace_inquiries (listing_id, buyer_name, message, status, buyer_auth_uid)
SELECT listing_id, 'Romeo Beltran', 'probe inquiry 61', 'pending', (SELECT seller FROM _probe_acct)
  FROM public.marketplace_inquiries WHERE id = current_setting('probe.inq')::uuid;
RESET ROLE;
SELECT CASE WHEN (SELECT to_me AND NOT from_me FROM _sel)
             AND (SELECT count(*) FROM public.marketplace_inquiries WHERE id = current_setting('probe.inq')::uuid AND reply_text = 'probe reply 61') = 1
            THEN 'PASS' ELSE 'FAIL' END || ' the seller reads the inquiry as addressed to them and can reply';
SELECT CASE WHEN (SELECT from_me AND NOT to_me FROM _buy)
            THEN 'PASS' ELSE 'FAIL' END || ' the buyer reads the inquiry as their own';
SELECT CASE WHEN (SELECT buyer_auth_uid::text FROM public.marketplace_inquiries WHERE message = 'probe inquiry 61') = current_setting('probe.buyer')
            THEN 'PASS' ELSE 'FAIL' END || ' a new inquiry is stamped with the sender''s account, whatever was sent';
SAVEPOINT k1;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', json_build_object('sub', (SELECT seller FROM _probe_acct)::text, 'role', 'authenticated')::text, true);
DO $$ BEGIN
  PERFORM buyer_auth_uid FROM public.marketplace_inquiries LIMIT 1;
  RAISE NOTICE 'FAIL the seller cannot read the buyer''s account key (it was readable)';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS the seller cannot read the buyer''s account key';
END $$;
ROLLBACK TO SAVEPOINT k1;
RESET ROLE;
ROLLBACK;
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM public.marketplace_inquiries WHERE message LIKE '%probe inquiry 61%' OR message LIKE '%[namesake]'
                               OR reply_text IN ('probe reply 61', 'namesake reply'))
             AND NOT EXISTS (SELECT 1 FROM auth.users WHERE email LIKE 'namesake.%.probe@auth.workhiveph.com')
            THEN 'PASS' ELSE 'FAIL' END || ' nothing persisted after the rollback';
