-- ★A REPORT A SUPERVISOR CANNOT SETTLE HAD NOWHERE TO GO (2026-11-06, GJ M10 G-ESC hand-offs 2-3).
--
-- A worker's report lands in the supervisor's Mod Queue with who, when and why (M8 G-ESC hand-off 1), and the
-- supervisor can Keep or Remove it (M9 G-MOD). Some reports are not theirs to settle: a post about the platform itself,
-- a dispute between members the supervisor is part of, something that may break the law. There was no road from the
-- Mod Queue to WorkHive - only the generic feedback button, which knows nothing about the post or who reported it, and
-- whose answer reaches the sender alone. Now:
--
--   1. escalate_reported_post(post, words): a supervisor of the post's hive hands a REPORTED post to WorkHive with their
--      own words. It files a platform_feedback item bound to that supervisor's account (the same row the feedback button
--      writes, so "Your reports" and the founder console already know it), labelled 'escalation', linked to the post
--      (ref_post_id) and carrying the post's words and the reports' reasons - never the reporters' names. A post already
--      waiting on WorkHive is not filed twice; the supervisor is told it is already there.
--   2. An escalation is never published. The roadmap board shows what WorkHive publishes, and this item holds a hive's
--      internal post: a CHECK keeps it private whoever edits it, the founder included.
--   3. WorkHive's answer reaches everyone who reported the post, not only the supervisor who sent it:
--      tg_platform_feedback_tell_sender pushes them too, and they read it back where each already reads their reports -
--      under "Your reports" in the feedback panel (my_feedback_outcomes) and in community's moderation news
--      (my_moderation_news, kind 'escalation'). The answer the founder writes goes to both, and the console says so.

BEGIN;

ALTER TABLE public.platform_feedback
  ADD COLUMN IF NOT EXISTS ref_post_id uuid REFERENCES public.community_posts(id) ON DELETE SET NULL;

ALTER TABLE public.platform_feedback DROP CONSTRAINT IF EXISTS platform_feedback_escalation_private;
ALTER TABLE public.platform_feedback ADD CONSTRAINT platform_feedback_escalation_private
  CHECK (ref_post_id IS NULL OR NOT is_public);

CREATE INDEX IF NOT EXISTS platform_feedback_ref_post_idx ON public.platform_feedback (ref_post_id)
  WHERE ref_post_id IS NOT NULL;

-- 1. the road from the Mod Queue to WorkHive
CREATE OR REPLACE FUNCTION public.escalate_reported_post(p_post_id uuid, p_words text)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  p public.community_posts%ROWTYPE;
  v_sup text;
  v_words text := nullif(btrim(left(coalesce(p_words, ''), 1000)), '');
  v_post text;
  v_reasons text;
  v_reports int;
  v_open uuid;
  v_id uuid;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Sign in to send a report to WorkHive.' USING ERRCODE = '42501';
  END IF;
  IF v_words IS NULL THEN
    RAISE EXCEPTION 'Say what you need WorkHive to look at.' USING ERRCODE = '22023';
  END IF;
  SELECT * INTO p FROM public.community_posts WHERE id = p_post_id;
  IF NOT FOUND OR p.deleted_at IS NOT NULL THEN
    RAISE EXCEPTION 'That post is no longer there - it may have been removed already.' USING ERRCODE = 'P0001';
  END IF;
  SELECT worker_name INTO v_sup FROM public.hive_members
   WHERE hive_id = p.hive_id AND auth_uid = auth.uid() AND status = 'active' AND role = 'supervisor' LIMIT 1;
  IF v_sup IS NULL THEN
    RAISE EXCEPTION 'Only a supervisor of this hive can send its reports to WorkHive.' USING ERRCODE = '42501';
  END IF;
  IF NOT p.flagged THEN
    RAISE EXCEPTION 'This post has no open report to send.' USING ERRCODE = '22023';
  END IF;

  -- one open escalation per post: a second tap points at the first
  SELECT f.id INTO v_open FROM public.platform_feedback f
   WHERE f.ref_post_id = p_post_id AND f.status IN ('new', 'triaged', 'in_progress')
   ORDER BY f.created_at DESC LIMIT 1;
  IF v_open IS NOT NULL THEN
    RETURN jsonb_build_object('escalated', false, 'reason', 'already_with_workhive', 'id', v_open);
  END IF;

  v_post := left(regexp_replace(coalesce(p.content, ''), '\s+', ' ', 'g'), 600);
  SELECT count(*), string_agg(DISTINCT coalesce(a.meta->>'reason', 'no reason given'), ', ')
    INTO v_reports, v_reasons
    FROM public.hive_audit_log a
   WHERE a.hive_id = p.hive_id AND a.action = 'report_post' AND a.target_id = p_post_id::text;

  INSERT INTO public.platform_feedback (hive_id, worker_name, kind, subject, body, page_url, is_public, labels, ref_post_id)
  VALUES (p.hive_id, v_sup, 'other',
          'Reported post: "' || left(regexp_replace(coalesce(p.content, ''), '\s+', ' ', 'g'), 50) || '"',
          v_words
            || E'\n\nThe post, by ' || coalesce(p.author_name, 'a member') || ' on ' || to_char(p.created_at, 'YYYY-MM-DD') || ':'
            || E'\n' || v_post
            || E'\n\nReports: ' || coalesce(v_reports, 0) || coalesce(' (' || v_reasons || ')', ''),
          '/community.html?post=' || p_post_id, false, ARRAY['escalation'], p_post_id)
  RETURNING id INTO v_id;

  INSERT INTO public.hive_audit_log (hive_id, actor, action, target_type, target_id, target_name, meta)
  VALUES (p.hive_id, v_sup, 'escalate_reported_post', 'community_posts', p_post_id::text,
          '"' || left(regexp_replace(coalesce(p.content, ''), '\s+', ' ', 'g'), 40) || '" by ' || coalesce(p.author_name, 'a member'),
          jsonb_build_object('target_id', p_post_id, 'page', 'community', 'feedback_id', v_id));

  RETURN jsonb_build_object('escalated', true, 'id', v_id);
END;
$function$;

REVOKE ALL ON FUNCTION public.escalate_reported_post(uuid, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.escalate_reported_post(uuid, text) TO authenticated;

-- 3a. WorkHive's answer reaches the sender and, for an escalation, everyone who reported the post
CREATE OR REPLACE FUNCTION public.tg_platform_feedback_tell_sender()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
DECLARE
  v_said text;
  v_reporters uuid[];
  v_from text := coalesce(NULLIF(NEW.page_url, ''), '/');
  -- where the push lands: the panel's "Your reports", opened (?reports=1). An escalation's answer lands on WorkHive's own
  -- board, where both the supervisor and the reporters read it; any other report's, on the page it was sent from.
  v_url text := CASE WHEN NEW.ref_post_id IS NOT NULL THEN '/feedback/?reports=1'
                     ELSE v_from || CASE WHEN position('?' IN v_from) > 0 THEN '&' ELSE '?' END || 'reports=1' END;
BEGIN
  IF NEW.status = 'new' THEN
    RETURN NEW;
  END IF;
  IF NEW.status IS NOT DISTINCT FROM OLD.status AND NEW.sender_reply IS NOT DISTINCT FROM OLD.sender_reply THEN
    RETURN NEW;
  END IF;
  v_said := CASE NEW.status
              WHEN 'triaged' THEN 'WorkHive has read it'
              WHEN 'in_progress' THEN 'WorkHive is working on it'
              WHEN 'resolved' THEN 'WorkHive resolved it'
              WHEN 'wontfix' THEN 'WorkHive decided not to act on it'
              WHEN 'duplicate' THEN 'WorkHive is handling it with an earlier report'
              ELSE 'WorkHive updated it' END;
  IF NEW.auth_uid IS NOT NULL THEN
    PERFORM public.enqueue_user_push(
      ARRAY[NEW.auth_uid],
      'WorkHive answered your report',
      '"' || left(coalesce(NEW.subject, 'Your report'), 70) || '": ' || v_said || coalesce('. ' || left(NEW.sender_reply, 160), '.'),
      v_url);
  END IF;

  IF NEW.ref_post_id IS NOT NULL THEN
    SELECT array_agg(DISTINCT (a.meta->>'actor_auth_uid')::uuid) INTO v_reporters
      FROM public.hive_audit_log a
     WHERE a.action = 'report_post' AND a.target_id = NEW.ref_post_id::text
       AND a.meta ? 'actor_auth_uid'
       AND (a.meta->>'actor_auth_uid') <> coalesce(NEW.auth_uid::text, '');
    IF v_reporters IS NOT NULL THEN
      PERFORM public.enqueue_user_push(
        v_reporters,
        'WorkHive reviewed the post you reported',
        v_said || coalesce('. ' || left(NEW.sender_reply, 160), '.'),
        '/feedback/?reports=1');
    END IF;
  END IF;
  RETURN NEW;
END;
$function$;

-- 3b. "Your reports": the caller's own reports, and WorkHive's answer on a post they reported
CREATE OR REPLACE FUNCTION public.my_feedback_outcomes()
 RETURNS TABLE (id uuid, created_at timestamptz, kind text, subject text, status text, sender_reply text,
                triaged_at timestamptz, resolved_at timestamptz, updated_at timestamptz)
 LANGUAGE sql
 STABLE
 SECURITY DEFINER
 SET search_path TO 'public', 'pg_temp'
AS $function$
  SELECT * FROM (
    SELECT f.id, f.created_at, f.kind, f.subject, f.status, f.sender_reply, f.triaged_at, f.resolved_at, f.updated_at
      FROM public.platform_feedback f
     WHERE auth.uid() IS NOT NULL AND f.auth_uid = auth.uid()
       AND f.created_at >= now() - interval '90 days'
    UNION ALL
    -- an escalation of a post this person reported: they read WorkHive's answer, not the supervisor's message
    SELECT f.id, f.created_at, f.kind,
           'A post you reported: ' || substr(f.subject, length('Reported post: ') + 1),
           f.status, f.sender_reply, f.triaged_at, f.resolved_at, f.updated_at
      FROM public.platform_feedback f
     WHERE auth.uid() IS NOT NULL AND f.ref_post_id IS NOT NULL
       AND f.auth_uid IS DISTINCT FROM auth.uid()
       AND f.created_at >= now() - interval '90 days'
       AND EXISTS (SELECT 1 FROM public.hive_audit_log a
                    WHERE a.action = 'report_post' AND a.target_id = f.ref_post_id::text
                      AND a.meta->>'actor_auth_uid' = auth.uid()::text)
  ) x
  ORDER BY coalesce(x.updated_at, x.created_at) DESC, x.id
  LIMIT 20;
$function$;

-- 3c. community's moderation news: a report sent on to WorkHive says so, and then says what WorkHive decided
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
         -- a report still waiting, and sent on to WorkHive, is told by the escalation line below instead
         AND NOT (p.moderation_outcome IS NULL
                  AND EXISTS (SELECT 1 FROM public.platform_feedback f WHERE f.ref_post_id = p.id))
       ORDER BY p.id, a.created_at DESC
    ) r
    UNION ALL
    -- moderated_by: the supervisor who sent it on; outcome: WorkHive's status; moderated_at: when that status was set
    SELECT * FROM (
      SELECT DISTINCT ON (f.ref_post_id) 'escalation'::text, f.ref_post_id,
             left(regexp_replace(coalesce(p.content, ''), '\s+', ' ', 'g'), 60),
             f.status, f.worker_name, f.status_at, f.sender_reply, f.created_at
        FROM public.platform_feedback f
        JOIN public.community_posts p ON p.id = f.ref_post_id
       WHERE auth.uid() IS NOT NULL AND f.ref_post_id IS NOT NULL
         AND f.status_at > now() - interval '30 days'
         AND EXISTS (SELECT 1 FROM public.hive_audit_log a
                      WHERE a.action = 'report_post' AND a.target_id = f.ref_post_id::text
                        AND a.meta->>'actor_auth_uid' = auth.uid()::text)
       ORDER BY f.ref_post_id, f.created_at DESC
    ) e
  ) x
  ORDER BY coalesce(x.moderated_at, x.reported_at) DESC
  LIMIT 20;
$function$;

REVOKE ALL ON FUNCTION public.tg_platform_feedback_tell_sender() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.my_feedback_outcomes() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.my_feedback_outcomes() TO authenticated, service_role;
REVOKE ALL ON FUNCTION public.my_moderation_news() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.my_moderation_news() TO authenticated;

COMMIT;
