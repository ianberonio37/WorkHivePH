-- ============================================================================
-- Bind community_replies authorship to the JWT identity (deep-walk, 2026-07-07).
--
-- community_replies had NO auth_uid column (unlike its sibling community_posts), so reply
-- authorship rode solely on the client-supplied, SPOOFABLE `author_name`. Add auth_uid with
-- DEFAULT auth.uid() so every new reply is auto-attributed from the authenticated session (the
-- DB sets it, not the client -> un-spoofable) with no client-code change. Best-effort backfill
-- of existing rows via the hive_members worker_name -> auth_uid map where it resolves.
-- ============================================================================

ALTER TABLE public.community_replies
  ADD COLUMN IF NOT EXISTS auth_uid uuid DEFAULT auth.uid();

UPDATE public.community_replies r
   SET auth_uid = hm.auth_uid
  FROM public.hive_members hm
 WHERE r.auth_uid IS NULL
   AND hm.hive_id = r.hive_id
   AND hm.worker_name = r.author_name;
