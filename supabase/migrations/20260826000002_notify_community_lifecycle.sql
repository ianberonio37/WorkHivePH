-- T108 (2026-08-26): extinguish the THREE remaining badge-only rows of the someone-to-you
-- registry, all of them community events where a person is addressed by name and never told.
--
-- WHAT WAS SILENT, per the registry's own findings:
--   * "community mention (@name)" — parseMentions runs on BOTH the create and the edit path and
--     the array is stored and rendered (renderContentWithMentions), so being named is a first-
--     class fact in the data. Nobody tells the person named. The nav-hub badge counts posts
--     generally, which is not the same signal at all.
--   * "reply to my post" — T31's finding: the asker had no way to learn an answer arrived except
--     by coming back to look.
--   * "best answer chosen" — the reply author's answer is accepted, the XP ledger records it, and
--     the author discovers it by revisiting.
--
-- Same guarded-wrapper shape as notify_wo_assigned (mig 004) and notify_submission_decided
-- (mig 003), for the same reason: the CALLER names a row, never a recipient and never the copy.
-- A client that could pass an auth_uid and a body would be a push cannon pointed at the hive.
--
-- Shared guards in all three:
--   * the subject row resolves hive + recipient SERVER-side from the id;
--   * the caller must be an ACTIVE MEMBER of that row's hive;
--   * acting on your own thing pushes nothing (you know what you just did);
--   * a recipient with no active membership or no auth_uid is an honest no-op, not an error;
--   * copy composed here, deep link points at community.html?post=<id> (the page's own
--     history-state param, so the tap lands on the thread rather than the feed's top).
--
-- Reach honesty, recorded not hidden: push reaches opt-in subscribers only, and mentions are
-- matched on worker_name, so an @name that matches no active member resolves to nobody —
-- the same free-text limit wo_assigned_to carries. Re-runnable.

-- ── 1. someone named you in a post ───────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.notify_post_mentions(p_post_id text)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_hive uuid; v_author text; v_mentions text[]; v_caller text; v_uids uuid[]; v_snippet text;
BEGIN
  SELECT hive_id, author_name, mentions, left(btrim(content), 90)
    INTO v_hive, v_author, v_mentions, v_snippet
  FROM public.community_posts WHERE id::text = p_post_id AND deleted_at IS NULL;
  IF v_hive IS NULL OR v_mentions IS NULL OR array_length(v_mentions, 1) IS NULL THEN RETURN; END IF;

  SELECT hm.worker_name INTO v_caller
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive
    AND hm.worker_name IN (SELECT public.auth_worker_names())
    AND hm.status = 'active'
  LIMIT 1;
  IF v_caller IS NULL THEN
    RAISE EXCEPTION 'only an active member of the post''s hive may notify';
  END IF;

  -- every named member EXCEPT the person doing the naming
  SELECT array_agg(DISTINCT hm.auth_uid) INTO v_uids
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive
    AND hm.status = 'active'
    AND hm.auth_uid IS NOT NULL
    AND lower(hm.worker_name) <> lower(v_caller)
    AND lower(hm.worker_name) IN (
      SELECT lower(btrim(m)) FROM unnest(v_mentions) AS m
    );
  IF v_uids IS NULL OR array_length(v_uids, 1) IS NULL THEN RETURN; END IF;

  PERFORM public.enqueue_user_push(
    v_uids,
    v_caller || ' mentioned you',
    COALESCE(v_snippet, 'A post in your hive names you.') || ' - open the Hive Community to reply.',
    '/community.html?post=' || p_post_id
  );
END $$;

-- ── 2. someone replied to your post ──────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.notify_reply_posted(p_reply_id text)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_hive uuid; v_post text; v_replier text; v_author text; v_caller text; v_uid uuid; v_snippet text;
BEGIN
  SELECT r.hive_id, r.post_id::text, r.author_name, left(btrim(r.content), 90)
    INTO v_hive, v_post, v_replier, v_snippet
  FROM public.community_replies r WHERE r.id::text = p_reply_id;
  IF v_hive IS NULL OR v_post IS NULL THEN RETURN; END IF;

  SELECT p.author_name INTO v_author
  FROM public.community_posts p WHERE p.id::text = v_post AND p.deleted_at IS NULL;
  IF v_author IS NULL THEN RETURN; END IF;   -- the thread is gone; nothing to point at

  SELECT hm.worker_name INTO v_caller
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive
    AND hm.worker_name IN (SELECT public.auth_worker_names())
    AND hm.status = 'active'
  LIMIT 1;
  IF v_caller IS NULL THEN
    RAISE EXCEPTION 'only an active member of the reply''s hive may notify';
  END IF;
  IF lower(btrim(v_author)) = lower(v_caller) THEN RETURN; END IF;  -- replying to yourself

  SELECT auth_uid INTO v_uid FROM public.hive_members
  WHERE hive_id = v_hive AND lower(worker_name) = lower(btrim(v_author))
    AND status = 'active' AND auth_uid IS NOT NULL
  LIMIT 1;
  IF v_uid IS NULL THEN RETURN; END IF;

  PERFORM public.enqueue_user_push(
    ARRAY[v_uid],
    COALESCE(v_replier, 'Someone') || ' answered your question',
    COALESCE(v_snippet, 'A new reply is waiting on your post.') || ' - open it to read the answer.',
    '/community.html?post=' || v_post
  );
END $$;

-- ── 3. your reply was chosen as the best answer ──────────────────────────────
CREATE OR REPLACE FUNCTION public.notify_reply_accepted(p_reply_id text)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_hive uuid; v_post text; v_replier text; v_caller text; v_uid uuid;
BEGIN
  SELECT r.hive_id, r.post_id::text, r.author_name
    INTO v_hive, v_post, v_replier
  FROM public.community_replies r WHERE r.id::text = p_reply_id AND r.is_accepted IS TRUE;
  IF v_hive IS NULL OR v_replier IS NULL THEN RETURN; END IF;  -- not accepted: nothing to announce

  SELECT hm.worker_name INTO v_caller
  FROM public.hive_members hm
  WHERE hm.hive_id = v_hive
    AND hm.worker_name IN (SELECT public.auth_worker_names())
    AND hm.status = 'active'
  LIMIT 1;
  IF v_caller IS NULL THEN
    RAISE EXCEPTION 'only an active member of the reply''s hive may notify';
  END IF;
  IF lower(btrim(v_replier)) = lower(v_caller) THEN RETURN; END IF;  -- accepting your own reply

  SELECT auth_uid INTO v_uid FROM public.hive_members
  WHERE hive_id = v_hive AND lower(worker_name) = lower(btrim(v_replier))
    AND status = 'active' AND auth_uid IS NOT NULL
  LIMIT 1;
  IF v_uid IS NULL THEN RETURN; END IF;

  PERFORM public.enqueue_user_push(
    ARRAY[v_uid],
    'Your answer was chosen',
    v_caller || ' marked your reply as the best answer. Open the thread to see it.',
    '/community.html?post=' || v_post
  );
END $$;

GRANT EXECUTE ON FUNCTION public.notify_post_mentions(text)  TO authenticated;
GRANT EXECUTE ON FUNCTION public.notify_reply_posted(text)   TO authenticated;
GRANT EXECUTE ON FUNCTION public.notify_reply_accepted(text) TO authenticated;

NOTIFY pgrst, 'reload schema';
