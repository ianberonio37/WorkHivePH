-- BEST ANSWER NEVER RECORDED WHO CHOSE IT.
--
-- Found 2026-08-20 walking community's CI domain-truth `best_answer_names_chooser` ("best answer
-- names who chose it").
--
-- community_replies carries is_accepted and nothing else: no chooser, no timestamp. The page renders
-- a green "✓ Best answer" chip with no attribution, and there was no way to add one, because the
-- fact was never stored.
--
-- It cannot be derived either, which is the part worth stating. The page comment beside the control
-- reads "who asked — gates who can mark the best answer", and if that were the whole rule the chooser
-- would always be the thread's author and no column would be needed. set_community_best_answer is
-- broader than its caller's comment: it authorises the post's author OR any active supervisor of the
-- hive. So on any thread with a supervisor present, "accepted" has two possible authors and the row
-- records neither.
--
-- That distinction is the whole point of the oracle. A member reading "best answer" is being told
-- this reply solved the problem; whether that judgement came from the person who actually had the
-- problem or from a supervisor who was not in it changes how much the badge is worth.
--
-- accepted_by stores the resolved worker_name rather than auth.uid() so the surface can render it
-- without a second lookup and without exposing an auth id. Un-accepting clears both fields: a stale
-- chooser on an unaccepted reply would be a claim about a decision that no longer stands.

ALTER TABLE public.community_replies
  ADD COLUMN IF NOT EXISTS accepted_by text,
  ADD COLUMN IF NOT EXISTS accepted_at timestamptz;

COMMENT ON COLUMN public.community_replies.accepted_by IS
  'worker_name of whoever marked this reply as the best answer: the post author or a hive supervisor. Cleared when the acceptance is withdrawn.';

CREATE OR REPLACE FUNCTION public.set_community_best_answer(p_reply_id uuid, p_accepted boolean)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_post_id       uuid;
  v_hive_id       uuid;
  v_post_author   text;
  v_is_authorized boolean;
  v_actor         text;
BEGIN
  SELECT r.post_id, r.hive_id INTO v_post_id, v_hive_id
  FROM public.community_replies r WHERE r.id = p_reply_id;
  IF v_post_id IS NULL THEN
    RAISE EXCEPTION 'reply not found';
  END IF;

  SELECT p.author_name INTO v_post_author
  FROM public.community_posts p WHERE p.id = v_post_id;

  -- authorized = the caller is the post's author, OR an active supervisor of the hive.
  -- The actor's own worker_name comes from the SAME membership row that authorises them, so the
  -- name recorded is the one the platform verified, never one supplied by the caller.
  SELECT hm.worker_name INTO v_actor
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive_id AND hm.auth_uid = auth.uid()
    AND hm.status = 'active'
    AND (hm.worker_name = v_post_author OR hm.role = 'supervisor')
  LIMIT 1;

  v_is_authorized := v_actor IS NOT NULL;
  IF NOT v_is_authorized THEN
    RAISE EXCEPTION 'only the person who asked or a supervisor can mark the best answer';
  END IF;

  IF p_accepted THEN
    -- clear any prior accepted answer on this post, then set this one (atomic, index-safe)
    UPDATE public.community_replies
       SET is_accepted = false, accepted_by = NULL, accepted_at = NULL
     WHERE post_id = v_post_id AND is_accepted AND id <> p_reply_id;
    UPDATE public.community_replies
       SET is_accepted = true,  accepted_by = v_actor, accepted_at = now()
     WHERE id = p_reply_id;
  ELSE
    UPDATE public.community_replies
       SET is_accepted = false, accepted_by = NULL, accepted_at = NULL
     WHERE id = p_reply_id;
  END IF;
END;
$$;
