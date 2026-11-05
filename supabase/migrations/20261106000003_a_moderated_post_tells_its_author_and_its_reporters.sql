-- ★A MODERATED POST TOLD NOBODY (2026-11-06, GJ M9 G-MOD hand-offs 2-3).
--
-- A supervisor's decision on a reported post was a plain write: "Unflag post" cleared the flag, "Delete post" sent it to
-- Recently deleted, and each wrote one line in the supervisor-only trail. The person who wrote the post learned the
-- outcome only by noticing their post vanish (or reappear); the person who reported it learned nothing at all - their
-- report simply went quiet. Both are told now, in words and by push, and both can read it again later:
--
--   1. community_posts carries the decision: moderated_by / moderated_at / moderation_outcome (kept | removed) /
--      moderation_note. Only moderate_reported_post writes them; tg_community_posts_moderation_fields pins them against
--      every client write (a supervisor included - a decision record a supervisor can rewrite is not a record).
--   2. every audit line carries its actor's ACCOUNT, not only their display name (meta.actor_auth_uid, stamped by
--      wh_bind_audit_actor). A report is an audit line, so "who reported this" becomes a person the platform can tell,
--      instead of a name it would have to match (a name is not an identity). Older lines stay name-only.
--   3. moderate_reported_post(post, keep, note): a supervisor of the post's hive, on someone else's post. Keep clears the
--      flag; remove is the same soft delete as wh_trash (Recently deleted, restorable). The author and every reporter are
--      pushed; the trail gets the decision; the author is never told who reported them.
--   4. my_moderation_news(): what a person may read back - their own posts a supervisor decided on, and the posts they
--      reported with what became of each (or that it still waits) - for 30 days.

BEGIN;

ALTER TABLE public.community_posts
  ADD COLUMN IF NOT EXISTS moderated_by       text,
  ADD COLUMN IF NOT EXISTS moderated_at       timestamptz,
  ADD COLUMN IF NOT EXISTS moderation_outcome text,
  ADD COLUMN IF NOT EXISTS moderation_note    text;

ALTER TABLE public.community_posts DROP CONSTRAINT IF EXISTS community_posts_moderation_outcome_check;
ALTER TABLE public.community_posts ADD CONSTRAINT community_posts_moderation_outcome_check
  CHECK (moderation_outcome IS NULL OR moderation_outcome IN ('kept', 'removed'));

-- 1. the decision record is the platform's: pinned against every client write
CREATE OR REPLACE FUNCTION public.tg_community_posts_moderation_fields()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
BEGIN
  IF auth.uid() IS NULL OR current_user <> 'authenticated' THEN
    RETURN NEW;                       -- server-side context, or a definer function acting for the platform
  END IF;

  IF TG_OP = 'INSERT' THEN
    NEW.moderated_by := NULL;         -- a new post carries no moderation decision
    NEW.moderated_at := NULL;
    NEW.moderation_outcome := NULL;
    NEW.moderation_note := NULL;
    IF NOT (NEW.hive_id IN (SELECT public.user_supervisor_hive_ids())) THEN
      NEW.pinned := false;            -- a member's new post starts unpinned and inside the hive
      NEW.public := false;
    END IF;
    RETURN NEW;
  END IF;

  -- the record of a moderation decision is written by moderate_reported_post only, never by a client (2026-11-06)
  NEW.moderated_by := OLD.moderated_by;
  NEW.moderated_at := OLD.moderated_at;
  NEW.moderation_outcome := OLD.moderation_outcome;
  NEW.moderation_note := OLD.moderation_note;

  IF OLD.auth_uid IS DISTINCT FROM auth.uid() THEN
    NEW.content   := OLD.content;     -- nobody else's words go out under this author's name
    NEW.category  := OLD.category;
    NEW.mentions  := OLD.mentions;
    NEW.edited_at := OLD.edited_at;
  END IF;

  IF NEW.hive_id IN (SELECT public.user_supervisor_hive_ids()) THEN
    RETURN NEW;                       -- a supervisor of THIS hive may moderate and share
  END IF;

  -- Raising a flag is reporting and is allowed; lowering one is clearing and is not.
  IF OLD.flagged AND NOT NEW.flagged THEN
    NEW.flagged := OLD.flagged;
  END IF;
  NEW.pinned := OLD.pinned;
  NEW.public := OLD.public;
  RETURN NEW;
END;
$function$;

-- 2. an audit line carries its actor's account
CREATE OR REPLACE FUNCTION public.wh_bind_audit_actor()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE real_actor text;
BEGIN
  IF auth.uid() IS NOT NULL THEN
    SELECT display_name INTO real_actor FROM worker_profiles WHERE auth_uid = auth.uid() LIMIT 1;
    IF real_actor IS NULL THEN
      -- no worker_profiles row (nothing auto-creates one) -> fall back to the caller's server-bound
      -- hive_members name (NOT NULL, bound to auth_uid) so a profile-less member cannot forge actor.
      SELECT worker_name INTO real_actor FROM public.hive_members
        WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    END IF;
    NEW.actor := COALESCE(real_actor, '(unknown)');  -- always overwrite the client-supplied value
    -- the actor's ACCOUNT beside the name (2026-11-06): the person the line is about can be told, not guessed at
    NEW.meta := COALESCE(NEW.meta, '{}'::jsonb) || jsonb_build_object('actor_auth_uid', auth.uid());
  END IF;
  RETURN NEW;
END; $function$;

-- 3. the decision, told to the author and to everyone who reported it
CREATE OR REPLACE FUNCTION public.moderate_reported_post(p_post_id uuid, p_keep boolean, p_note text DEFAULT NULL)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  p public.community_posts%ROWTYPE;
  v_sup text;
  v_note text := nullif(btrim(left(coalesce(p_note, ''), 280)), '');
  v_words text;
  v_reporters uuid[];
  v_outcome text := CASE WHEN p_keep THEN 'kept' ELSE 'removed' END;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Sign in to review a post.' USING ERRCODE = '42501';
  END IF;
  SELECT * INTO p FROM public.community_posts WHERE id = p_post_id;
  IF NOT FOUND OR p.deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'That post is no longer there - it may have been removed already.' USING ERRCODE = 'P0001';
  END IF;
  SELECT worker_name INTO v_sup FROM public.hive_members
   WHERE hive_id = p.hive_id AND auth_uid = auth.uid() AND status = 'active' AND role = 'supervisor' LIMIT 1;
  IF v_sup IS NULL THEN
    RAISE EXCEPTION 'Only a supervisor of this hive can review its posts.' USING ERRCODE = '42501';
  END IF;
  IF p.auth_uid = auth.uid() THEN
    RAISE EXCEPTION 'This is your own post - edit or delete it instead.' USING ERRCODE = '22023';
  END IF;

  v_words := left(regexp_replace(coalesce(p.content, ''), '\s+', ' ', 'g'), 60);

  IF p_keep THEN
    UPDATE public.community_posts
       SET flagged = false, moderated_by = v_sup, moderated_at = now(), moderation_outcome = 'kept', moderation_note = v_note
     WHERE id = p_post_id;
  ELSE
    -- the same soft delete as everywhere else (Recently deleted, restorable for the hive's retention window)
    PERFORM public.wh_trash('community_posts', p_post_id::text);
    PERFORM set_config('workhive.trash_scope', 'on', true);
    UPDATE public.community_posts
       SET flagged = false, moderated_by = v_sup, moderated_at = now(), moderation_outcome = 'removed', moderation_note = v_note
     WHERE id = p_post_id;
    PERFORM set_config('workhive.trash_scope', '', true);
  END IF;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (p.hive_id, v_sup, CASE WHEN p_keep THEN 'keep_reported_post' ELSE 'remove_reported_post' END,
          'community_posts', p_post_id::text, '"' || left(v_words, 40) || '" by ' || coalesce(p.author_name, 'a member'),
          jsonb_build_object('target_id', p_post_id, 'page', 'community', 'outcome', v_outcome, 'note', v_note,
                             'author', p.author_name));

  -- the author (never told who reported them)
  IF p.auth_uid IS NOT NULL THEN
    PERFORM public.enqueue_user_push(
      ARRAY[p.auth_uid],
      CASE WHEN p_keep THEN 'Your post was reviewed and kept' ELSE 'Your post was removed' END,
      v_sup || CASE WHEN p_keep THEN ' kept your post "' ELSE ' removed your post "' END || v_words || '"'
        || coalesce(': ' || v_note, '.'),
      CASE WHEN p_keep THEN '/community.html?post=' || p_post_id ELSE '/community.html' END);
  END IF;

  -- everyone who reported it, by account (the report's audit line carries it since this migration)
  SELECT array_agg(DISTINCT (a.meta->>'actor_auth_uid')::uuid) INTO v_reporters
    FROM public.hive_audit_log a
   WHERE a.hive_id = p.hive_id AND a.action = 'report_post' AND a.target_id = p_post_id::text
     AND a.meta ? 'actor_auth_uid' AND (a.meta->>'actor_auth_uid') <> coalesce(p.auth_uid::text, '');
  IF v_reporters IS NOT NULL THEN
    PERFORM public.enqueue_user_push(
      v_reporters,
      'Your report was reviewed',
      v_sup || CASE WHEN p_keep THEN ' kept' ELSE ' removed' END || ' the post you reported ("' || v_words || '")'
        || coalesce(': ' || v_note, '.'),
      '/community.html');
  END IF;

  RETURN jsonb_build_object('post_id', p_post_id, 'outcome', v_outcome, 'by', v_sup,
                            'told_author', p.auth_uid IS NOT NULL, 'told_reporters', coalesce(array_length(v_reporters, 1), 0));
END;
$function$;

-- 4. what a person may read back: their own posts decided on, and their reports' outcomes
CREATE OR REPLACE FUNCTION public.my_moderation_news()
 RETURNS TABLE (kind text, post_id uuid, words text, outcome text, moderated_by text, moderated_at timestamptz, note text, reported_at timestamptz)
 LANGUAGE sql
 STABLE
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
  SELECT * FROM (
    SELECT 'your_post'::text AS kind, p.id AS post_id, left(regexp_replace(coalesce(p.content, ''), '\s+', ' ', 'g'), 60) AS words,
           p.moderation_outcome AS outcome, p.moderated_by, p.moderated_at, p.moderation_note AS note, NULL::timestamptz AS reported_at
      FROM public.community_posts p
     WHERE auth.uid() IS NOT NULL AND p.auth_uid = auth.uid()
       AND p.moderated_at > now() - interval '30 days'
    UNION ALL
    SELECT * FROM (
      SELECT DISTINCT ON (p.id) 'your_report'::text, p.id, left(regexp_replace(coalesce(p.content, ''), '\s+', ' ', 'g'), 60),
             p.moderation_outcome, p.moderated_by, p.moderated_at, p.moderation_note, a.created_at
        FROM public.hive_audit_log a
        JOIN public.community_posts p ON p.id::text = a.target_id
       WHERE auth.uid() IS NOT NULL AND a.action = 'report_post'
         AND a.meta->>'actor_auth_uid' = auth.uid()::text
         AND a.created_at > now() - interval '30 days'
       ORDER BY p.id, a.created_at DESC
    ) r
  ) x
  ORDER BY coalesce(x.moderated_at, x.reported_at) DESC
  LIMIT 20;
$function$;

REVOKE ALL ON FUNCTION public.moderate_reported_post(uuid, boolean, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.moderate_reported_post(uuid, boolean, text) TO authenticated;
REVOKE ALL ON FUNCTION public.my_moderation_news() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.my_moderation_news() TO authenticated;

COMMIT;
