-- ============================================================================
-- Best-answer / "solved" primitive (Community PDDA 7th, U durable-knowledge)
-- ----------------------------------------------------------------------------
-- Community posts were ephemeral feed items — a question answered in a thread had no way to be marked
-- "solved," so the fix never became durable, searchable knowledge (the whole point of a community of
-- practice). This adds an accepted-answer flag on replies. Authority: ONLY the post's author (the person
-- who asked) or a supervisor of the hive can mark an answer — enforced by a SECURITY DEFINER RPC, never
-- a client write. One accepted answer per post (partial unique index = DB-level guard).
-- ============================================================================

ALTER TABLE public.community_replies
  ADD COLUMN IF NOT EXISTS is_accepted boolean NOT NULL DEFAULT false;

-- At most one accepted answer per post.
CREATE UNIQUE INDEX IF NOT EXISTS community_replies_one_accepted_per_post
  ON public.community_replies (post_id) WHERE is_accepted;

-- Toggle the accepted answer. DEFINER: gates to post-author or hive supervisor, and keeps
-- "one accepted per post" atomic (clears any prior accepted reply before setting the new one).
CREATE OR REPLACE FUNCTION public.set_community_best_answer(p_reply_id uuid, p_accepted boolean)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  v_post_id uuid;
  v_hive_id uuid;
  v_post_author text;
  v_is_authorized boolean;
BEGIN
  SELECT r.post_id, r.hive_id INTO v_post_id, v_hive_id
  FROM public.community_replies r WHERE r.id = p_reply_id;
  IF v_post_id IS NULL THEN
    RAISE EXCEPTION 'reply not found';
  END IF;

  SELECT p.author_name INTO v_post_author
  FROM public.community_posts p WHERE p.id = v_post_id;

  -- authorized = the caller is the post's author, OR an active supervisor of the hive
  v_is_authorized := (
    EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = v_hive_id AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
        AND (hm.worker_name = v_post_author OR hm.role = 'supervisor')
    )
  );
  IF NOT v_is_authorized THEN
    RAISE EXCEPTION 'only the person who asked or a supervisor can mark the best answer';
  END IF;

  IF p_accepted THEN
    -- clear any prior accepted answer on this post, then set this one (atomic, index-safe)
    UPDATE public.community_replies SET is_accepted = false
      WHERE post_id = v_post_id AND is_accepted AND id <> p_reply_id;
    UPDATE public.community_replies SET is_accepted = true  WHERE id = p_reply_id;
  ELSE
    UPDATE public.community_replies SET is_accepted = false WHERE id = p_reply_id;
  END IF;
END;
$function$;

COMMENT ON FUNCTION public.set_community_best_answer(uuid, boolean) IS
  'Mark/unmark a reply as the accepted answer. Post-author or hive-supervisor only; one accepted per post. Community PDDA 7th durable-knowledge.';

GRANT EXECUTE ON FUNCTION public.set_community_best_answer(uuid, boolean) TO authenticated;
