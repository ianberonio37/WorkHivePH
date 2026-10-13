-- expect: PASS a person who is not an active member cannot bring history in
-- expect: PASS a member brings in their OWN hive-less entries, matched by account, and only those
-- expect: PASS the knowledge rows move with the entries in the same transaction
-- expect: PASS the hive's audit log records it once, as the person's choice, and no closed entry reads as amended
-- expect: PASS a real amendment of a closed entry is still audited
-- expect: PASS nothing persisted after the rollback
-- forbid: FAIL
-- personal_history_comes_in_by_choice (2026-10-08, migration 20261008000064). Until 2026-10-07 hive.html moved every
-- hive-less entry of a member, matched by NAME, into the open hive on page load. Now a person's own history comes in
-- only through bring_personal_history_into_hive(), by their press, by account. Fixture: Jun Salvador (6daa77a1), a solo
-- owner with personal entries, made a Baguio member inside this rolled-back transaction; a NAMESAKE holding his name in
-- a hive he is not in must not be able to move his entries.
BEGIN;
CREATE TEMP TABLE _jun AS SELECT array_agg(id) AS ids, count(*) AS n FROM public.logbook
 WHERE auth_uid = '6daa77a1-bc07-4cef-b363-92ccdb4735e2' AND hive_id IS NULL;
-- not a member: refused
SAVEPOINT a;
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"6daa77a1-bc07-4cef-b363-92ccdb4735e2","role":"authenticated"}', true);
DO $$ BEGIN
  PERFORM public.bring_personal_history_into_hive('084c113b-99c0-45c6-a8e8-b4b8349da46d');
  RAISE NOTICE 'FAIL a person who is not an active member cannot bring history in (it was allowed)';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'PASS a person who is not an active member cannot bring history in';
END $$;
ROLLBACK TO SAVEPOINT a;
RESET ROLE;
-- a NAMESAKE: holds "Jun Salvador" in Baguio, a different account - they bring in THEIR entries (none), never Jun's
INSERT INTO auth.users (id, instance_id, aud, role, email, encrypted_password, email_confirmed_at, created_at, updated_at)
VALUES ('00000000-0000-4000-8000-00000000d064', '00000000-0000-0000-0000-000000000000', 'authenticated', 'authenticated',
        'namesake.jun.probe@auth.workhiveph.com', '', now(), now(), now());
INSERT INTO public.hive_members (hive_id, worker_name, auth_uid, role, status) VALUES
  ('084c113b-99c0-45c6-a8e8-b4b8349da46d', 'Jun Salvador', '00000000-0000-4000-8000-00000000d064', 'worker', 'active');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"00000000-0000-4000-8000-00000000d064","role":"authenticated"}', true);
CREATE TEMP TABLE _ns AS SELECT public.bring_personal_history_into_hive('084c113b-99c0-45c6-a8e8-b4b8349da46d') AS r;
RESET ROLE;
-- Jun himself, now a member
INSERT INTO public.hive_members (hive_id, worker_name, auth_uid, role, status) VALUES
  ('084c113b-99c0-45c6-a8e8-b4b8349da46d', 'Jun Salvador (probe)', '6daa77a1-bc07-4cef-b363-92ccdb4735e2', 'worker', 'active');
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claims', '{"sub":"6daa77a1-bc07-4cef-b363-92ccdb4735e2","role":"authenticated"}', true);
CREATE TEMP TABLE _me AS SELECT public.bring_personal_history_into_hive('084c113b-99c0-45c6-a8e8-b4b8349da46d') AS r;
RESET ROLE;
SELECT CASE WHEN (SELECT (r->>'moved')::int FROM _ns) = 0
             AND (SELECT (r->>'moved')::int FROM _me) = (SELECT n FROM _jun) AND (SELECT n FROM _jun) > 0
             AND (SELECT count(*) FROM public.logbook WHERE id IN (SELECT unnest(ids) FROM _jun)
                   AND hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d') = (SELECT n FROM _jun)
            THEN 'PASS' ELSE 'FAIL' END || ' a member brings in their OWN hive-less entries, matched by account, and only those';
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM public.fault_knowledge WHERE logbook_id IN (SELECT unnest(ids) FROM _jun)
                              AND hive_id IS DISTINCT FROM '084c113b-99c0-45c6-a8e8-b4b8349da46d')
            THEN 'PASS' ELSE 'FAIL' END || ' the knowledge rows move with the entries in the same transaction';
SELECT CASE WHEN (SELECT count(*) FROM public.hive_audit_log WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d'
                   AND action = 'personal_history_brought_in' AND created_at > now() - interval '1 minute') = 1
             AND (SELECT count(*) FROM public.hive_audit_log WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d'
                   AND action = 'amend_closed_logbook_entry' AND created_at > now() - interval '1 minute') = 0
            THEN 'PASS' ELSE 'FAIL' END || ' the hive''s audit log records it once, as the person''s choice, and no closed entry reads as amended';
UPDATE public.logbook SET problem = coalesce(problem, '') || ' (probe amendment)'
 WHERE id = (SELECT id FROM public.logbook WHERE id IN (SELECT unnest(ids) FROM _jun) AND status = 'Closed' LIMIT 1);
SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM public.logbook WHERE id IN (SELECT unnest(ids) FROM _jun) AND status = 'Closed')
             OR (SELECT count(*) FROM public.hive_audit_log WHERE hive_id = '084c113b-99c0-45c6-a8e8-b4b8349da46d'
                  AND action = 'amend_closed_logbook_entry' AND created_at > now() - interval '1 minute') = 1
            THEN 'PASS' ELSE 'FAIL' END || ' a real amendment of a closed entry is still audited';
ROLLBACK;
SELECT CASE WHEN (SELECT count(*) FROM public.logbook WHERE auth_uid = '6daa77a1-bc07-4cef-b363-92ccdb4735e2' AND hive_id IS NOT NULL) = 0
             AND NOT EXISTS (SELECT 1 FROM auth.users WHERE email = 'namesake.jun.probe@auth.workhiveph.com')
             AND NOT EXISTS (SELECT 1 FROM public.hive_members WHERE auth_uid = '6daa77a1-bc07-4cef-b363-92ccdb4735e2')
            THEN 'PASS' ELSE 'FAIL' END || ' nothing persisted after the rollback';
