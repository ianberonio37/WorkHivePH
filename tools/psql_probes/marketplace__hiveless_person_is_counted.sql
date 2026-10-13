-- hiveless_person_is_counted (marketplace-listing-assist, ai-orchestrator, analytics-orchestrator, every solo AI fn):
-- a signed-in person with no hive is limited on THEIR OWN bucket, the bucket counts, the person cannot reset it, and
-- a hive member is untouched by it.
--
-- THIS IS A REGRESSION LOCK. Until 2026-10-08 marketplace-listing-assist passed a hive-less seller's AUTH UID to
-- checkAIRateLimit, which upserts ai_rate_limits.hive_id - a column with a foreign key to hives. Part 1 below is that
-- exact write: it fails 23503, the function never read the error, no bucket row ever existed, and every call saw an
-- empty bucket. The fix keys the person on ai_user_rate_limits (user_id = the VERIFIED uid) with the budget a
-- single-person hive gets (50 an hour, 300 a day); Part 2 runs that limiter's statements as the edge runs them
-- (service_role) for the identity auth.uid() resolves as `authenticated`, and call 51 is refused.
-- Part 3 is the hole found proving it: the bucket's policy was FOR ALL and authenticated held UPDATE/DELETE, so the
-- person could zero their own count over PostgREST. Migration 20261008000006 made it read-only to them.
-- Part 4: the hive member's person bucket and hive bucket are not touched, and the member cannot see the other bucket.
-- Everything runs inside BEGIN ... ROLLBACK: nothing is left behind.
-- expect: violates foreign key constraint "ai_rate_limits_hive_id_fkey"
-- expect: uid_as_hive_key_rows \| 0
-- expect: verified_identity_is_the_person \| t
-- expect: hiveless_person_refused_at_call \| 51
-- expect: person_reads_own_bucket \| 50
-- expect: person_update_own_bucket \| refused
-- expect: person_delete_own_bucket \| refused
-- expect: person_insert_own_bucket \| refused
-- expect: person_bucket_still_at_cap \| 50
-- expect: member_person_bucket_unchanged \| t
-- expect: member_hive_bucket_unchanged \| t
-- expect: member_sees_other_persons_bucket \| 0
-- forbid: \| allowed

BEGIN;
CREATE TEMP TABLE _p ON COMMIT DROP AS
SELECT (SELECT u.id FROM auth.users u
          WHERE NOT EXISTS (SELECT 1 FROM hive_members hm WHERE hm.auth_uid = u.id AND hm.status = 'active')
          ORDER BY u.created_at LIMIT 1) AS solo_uid,
       (SELECT hm.auth_uid FROM hive_members hm WHERE hm.status = 'active' AND hm.auth_uid IS NOT NULL
          ORDER BY hm.joined_at NULLS LAST, hm.auth_uid LIMIT 1) AS member_uid,
       NULL::uuid AS member_hive;
UPDATE _p SET member_hive = (SELECT hive_id FROM hive_members
                               WHERE auth_uid = _p.member_uid AND status = 'active'
                               ORDER BY joined_at NULLS LAST, hive_id LIMIT 1);
CREATE TEMP TABLE _before ON COMMIT DROP AS
SELECT (SELECT row_to_json(r)::text FROM ai_user_rate_limits r WHERE r.user_id = (SELECT member_uid::text FROM _p)) AS member_person_bucket,
       (SELECT row_to_json(r)::text FROM ai_rate_limits r WHERE r.hive_id = (SELECT member_hive FROM _p))      AS member_hive_bucket;
GRANT SELECT ON _p, _before TO authenticated, service_role;
-- a clean count for the hive-less person (inside the transaction; rolled back with it)
DELETE FROM ai_user_rate_limits WHERE user_id = (SELECT solo_uid::text FROM _p);

-- Part 1: the OLD key - the person's auth uid as a hive limiter's key, written as the edge writes it
SAVEPOINT old_key;
SET LOCAL ROLE service_role;
INSERT INTO ai_rate_limits (hive_id, call_count, window_start, day_count, day_window_start)
SELECT solo_uid, 1, now(), 1, now() FROM _p
ON CONFLICT (hive_id) DO UPDATE SET call_count = ai_rate_limits.call_count + 1;
ROLLBACK TO SAVEPOINT old_key;
SELECT 'uid_as_hive_key_rows | ' || count(*) FROM ai_rate_limits WHERE hive_id::text = (SELECT solo_uid::text FROM _p);

-- Part 2: who the request is for, as the platform resolves it (authenticated), then the limiter (service_role)
SELECT set_config('request.jwt.claims', json_build_object('sub', solo_uid, 'role', 'authenticated')::text, true) FROM _p;
SET LOCAL ROLE authenticated;
SELECT 'verified_identity_is_the_person | ' || (auth.uid() = (SELECT solo_uid FROM _p));
RESET ROLE;
SET LOCAL ROLE service_role;
DO $$
DECLARE
  k text := (SELECT solo_uid::text FROM _p);
  cap_h int := 50;    -- the hourly budget a single-person hive gets (checkAIRateLimit default)
  cap_d int := 300;   -- and its daily one
  r record; got boolean; hc int; dc int; hf boolean; df boolean; refused_at int; i int;
BEGIN
  FOR i IN 1..60 LOOP
    -- checkSoloRateLimit -> bumpSoloBucket, statement for statement
    SELECT call_count, window_start, day_count, day_window_start INTO r FROM ai_user_rate_limits WHERE user_id = k;
    got := FOUND;
    hf := got AND r.window_start >= now() - interval '1 hour';
    df := got AND r.day_window_start IS NOT NULL AND r.day_window_start >= now() - interval '1 day';
    hc := CASE WHEN hf THEN r.call_count ELSE 0 END;
    dc := CASE WHEN df THEN coalesce(r.day_count, 0) ELSE 0 END;
    IF dc >= cap_d OR hc >= cap_h THEN refused_at := i; EXIT; END IF;
    INSERT INTO ai_user_rate_limits (user_id, hive_id, call_count, window_start, day_count, day_window_start)
    VALUES (k, NULL, hc + 1, CASE WHEN hf THEN r.window_start ELSE now() END,
            dc + 1, CASE WHEN df THEN r.day_window_start ELSE now() END)
    ON CONFLICT (user_id) DO UPDATE SET call_count = EXCLUDED.call_count, window_start = EXCLUDED.window_start,
                                        day_count = EXCLUDED.day_count, day_window_start = EXCLUDED.day_window_start;
  END LOOP;
  RAISE NOTICE 'hiveless_person_refused_at_call | %', coalesce(refused_at::text, 'never');
END $$;

-- Part 3: the person, as authenticated, can read their bucket and cannot reset it
RESET ROLE;
SET LOCAL ROLE authenticated;
SELECT 'person_reads_own_bucket | ' || coalesce((SELECT call_count FROM ai_user_rate_limits WHERE user_id = auth.uid()::text), -1);
DO $$ DECLARE n int; BEGIN
  UPDATE public.ai_user_rate_limits SET call_count = 0, day_count = 0 WHERE user_id = auth.uid()::text;
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE 'person_update_own_bucket | allowed (% row)', n;
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'person_update_own_bucket | refused';
END $$;
DO $$ DECLARE n int; BEGIN
  DELETE FROM public.ai_user_rate_limits WHERE user_id = auth.uid()::text;
  GET DIAGNOSTICS n = ROW_COUNT;
  RAISE NOTICE 'person_delete_own_bucket | allowed (% row)', n;
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'person_delete_own_bucket | refused';
END $$;
DO $$ BEGIN
  -- a fresh bucket for themselves (the row the delete above would have cleared)
  INSERT INTO public.ai_user_rate_limits (user_id, call_count, window_start, day_count, day_window_start)
  VALUES (auth.uid()::text, 0, now(), 0, now())
  ON CONFLICT (user_id) DO UPDATE SET call_count = 0, day_count = 0;
  RAISE NOTICE 'person_insert_own_bucket | allowed';
EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'person_insert_own_bucket | refused';
END $$;
SELECT 'person_bucket_still_at_cap | ' || coalesce((SELECT call_count FROM ai_user_rate_limits WHERE user_id = auth.uid()::text), -1);

-- Part 4: the hive member is untouched, and cannot see the other person's bucket
RESET ROLE;
SELECT 'member_person_bucket_unchanged | ' || (
  (SELECT row_to_json(r)::text FROM ai_user_rate_limits r WHERE r.user_id = (SELECT member_uid::text FROM _p))
  IS NOT DISTINCT FROM (SELECT member_person_bucket FROM _before));
SELECT 'member_hive_bucket_unchanged | ' || (
  (SELECT row_to_json(r)::text FROM ai_rate_limits r WHERE r.hive_id = (SELECT member_hive FROM _p))
  IS NOT DISTINCT FROM (SELECT member_hive_bucket FROM _before));
SELECT set_config('request.jwt.claims', json_build_object('sub', member_uid, 'role', 'authenticated')::text, true) FROM _p;
SET LOCAL ROLE authenticated;
SELECT 'member_sees_other_persons_bucket | ' || count(*) FROM ai_user_rate_limits WHERE user_id = (SELECT solo_uid::text FROM _p);
ROLLBACK;
