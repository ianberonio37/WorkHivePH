-- REPORTING A POST DID NOTHING, AND TOLD THE REPORTER IT WORKED.
--
-- Found 2026-08-20 immediately after 20260820000063, while checking the other half of the same
-- invariant ("a report creates exactly one moderation record"). The self-clear hole was real; this
-- is worse, and it was hiding directly beneath it.
--
-- submitReport() flags the post from the CLIENT:
--     db.from('community_posts').update({ flagged: true }).eq('id', ...)
-- but community_posts_update authorises only `auth_uid = auth.uid() OR supervisor`. A member
-- reporting SOMEONE ELSE'S post satisfies neither, so RLS matches zero rows. PostgREST returns no
-- error for a zero-row update - there is nothing wrong with updating nothing - so `if (error)` is
-- false and the success path runs:
--
--     post.flagged = true;                 <- in local memory only
--     _removePostCard(_reportingPostId);   <- vanishes from the reporter's feed
--     showToast('Report sent to your supervisor', 'success');
--
-- MEASURED: seeded an unflagged post by one member, had another member run exactly that update, and
-- flagged stayed FALSE. So the post the reporter believes they escalated is still unflagged, still
-- visible to every other member, and never enters the supervisor's queue, which reads `flagged`. The
-- reporter is shown the most convincing possible evidence that it worked: the post disappears.
--
-- TWO CHANGES.
--
-- 1. report_community_post(): moderation-class writes on this page already go through a DEFINER RPC
--    (set_community_best_answer), so reporting joins that pattern rather than widening the RLS
--    policy, which would hand every member blanket UPDATE on their hive-mates' posts to fix one
--    column. It verifies active membership of the post's OWN hive, so the tenant boundary is
--    enforced by the function rather than inherited from a policy it bypasses, and RETURNS boolean
--    so a caller can no longer mistake "nothing happened" for success.
--
-- 2. The 63 trigger is refined from a flat preserve to a DIRECTIONAL rule. Flat preservation was
--    correct against self-clearing and would have blocked this fix: a member must be able to raise
--    flagged false -> true to report, and must not be able to lower it true -> false. `pinned` stays
--    fully preserved, since there is no member-initiated pinning to allow.

CREATE OR REPLACE FUNCTION public.tg_community_posts_moderation_fields()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF auth.uid() IS NULL THEN
    RETURN NEW;
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.hive_members hm
     WHERE hm.hive_id = NEW.hive_id AND hm.auth_uid = auth.uid()
       AND hm.role = 'supervisor' AND hm.status = 'active'
  ) THEN
    RETURN NEW;
  END IF;

  -- Raising a flag is reporting and is allowed; lowering one is clearing and is not.
  IF OLD.flagged AND NOT NEW.flagged THEN
    NEW.flagged := OLD.flagged;
  END IF;

  NEW.pinned := OLD.pinned;
  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.report_community_post(p_post_id uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_hive_id uuid;
  v_already boolean;
BEGIN
  SELECT hive_id, flagged INTO v_hive_id, v_already
  FROM public.community_posts WHERE id = p_post_id;

  IF v_hive_id IS NULL THEN
    RAISE EXCEPTION 'post not found';
  END IF;

  -- Membership of the POST's hive, not of any hive: without this the DEFINER context would let a
  -- member of one hive flag a post in another.
  IF NOT EXISTS (
    SELECT 1 FROM public.hive_members hm
     WHERE hm.hive_id = v_hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
  ) THEN
    RAISE EXCEPTION 'only a member of this hive can report a post';
  END IF;

  UPDATE public.community_posts SET flagged = true WHERE id = p_post_id;

  -- true = this call is what flagged it. Already-flagged is still a successful report (the audit row
  -- the caller writes records the second reporter), so the caller is told the outcome, not an error.
  RETURN NOT coalesce(v_already, false);
END;
$$;

REVOKE ALL ON FUNCTION public.report_community_post(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.report_community_post(uuid) TO authenticated;
