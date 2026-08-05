-- THE GRANT EXISTED IN THE DATABASE AND IN NO MIGRATION.
--
-- `voice_response_queue` has RLS enabled and one policy — `voice_queue_own_rows`, SELECT, for
-- `authenticated`. The live database also carries `authenticated: SELECT`, so it works here. No
-- migration ever declares it, which means a database built from this repo alone would enable RLS,
-- create the policy, and grant nothing: PostgREST would answer 401 for every read while the policy
-- sat there looking correct. A permission that exists only because someone once typed it into a live
-- console is not a permission the project owns.
--
-- GRANTED TO MATCH THE POLICY, NOT TO MATCH THE WARNING. The idempotency gate's remediation text
-- suggests `GRANT SELECT,INSERT,UPDATE,DELETE ON voice_response_queue TO anon,authenticated` — that
-- is generic boilerplate, and following it literally would hand end-user roles three write verbs this
-- table has no write policy for. RLS would refuse the writes, so nothing would break loudly; the
-- table would simply carry standing privileges nobody checks, which is how the anon-write holes this
-- project has been closing all week were opened in the first place. The only verb with a policy
-- behind it is SELECT, so SELECT is the only verb granted. Writes reach this queue through the edge
-- function on the service role, which bypasses grants and RLS alike and needs nothing here.

BEGIN;

GRANT SELECT ON public.voice_response_queue TO authenticated;

-- Refuse to commit if this ever grants a verb no policy backs. A grant and a policy set that disagree
-- is the shape worth failing on: the grant is what PostgREST checks first, so an over-grant is a
-- standing privilege whose only remaining guard is a policy someone may later loosen.
DO $$
DECLARE v_extra text;
BEGIN
  SELECT string_agg(g.grantee || ':' || g.privilege_type, ', ')
    INTO v_extra
    FROM information_schema.role_table_grants g
   WHERE g.table_schema = 'public'
     AND g.table_name   = 'voice_response_queue'
     AND g.grantee IN ('anon', 'authenticated')
     AND g.privilege_type <> 'SELECT';
  IF v_extra IS NOT NULL THEN
    RAISE EXCEPTION 'voice_response_queue grants a verb no policy backs: %', v_extra;
  END IF;
  RAISE NOTICE 'voice_response_queue: SELECT granted to authenticated, matching its only policy';
END $$;

COMMIT;
