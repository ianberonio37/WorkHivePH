-- T108/T24 (2026-08-25): extinguish silent-work row #3 — "post reported (to supervisor)".
--
-- THE HOLE (T24's walk): a member reports a post, the reporter's toast says "sent to
-- your supervisor" — but no supervisor is told anything; they discover reports by
-- scrolling the feed. The report already flows through report_community_post
-- (SECURITY DEFINER, membership-of-the-post's-hive guarded, mig ...063/064), so the
-- notification belongs INSIDE it: fires exactly when the report lands, no client
-- wiring, no thenable trap, and only on the FIRST flagging (repeat reports of an
-- already-flagged post enqueue nothing — no supervisor spam; the audit row still
-- records the second reporter).
--
-- Recipients resolved server-side: ALL active supervisors of the post's hive with an
-- auth link. Reach: opt-in push subscribers (the feed's flagged state remains the
-- always-there surface). Re-runnable (CREATE OR REPLACE preserves the fn's contract;
-- the return semantics and guards are byte-identical to the previous version).

CREATE OR REPLACE FUNCTION public.report_community_post(p_post_id uuid)
RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE
  v_hive_id uuid;
  v_already boolean;
  v_sup_uids uuid[];
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

  -- T108: tell the hive's supervisors on the FIRST flagging only.
  IF NOT coalesce(v_already, false) THEN
    SELECT array_agg(hm.auth_uid) INTO v_sup_uids
    FROM public.hive_members hm
    WHERE hm.hive_id = v_hive_id AND hm.role = 'supervisor'
      AND hm.status = 'active' AND hm.auth_uid IS NOT NULL;
    IF v_sup_uids IS NOT NULL AND array_length(v_sup_uids, 1) > 0 THEN
      PERFORM public.enqueue_user_push(
        v_sup_uids,
        'A post was reported',
        'A member reported a post in your hive. Open Community to review it.',
        '/community.html'
      );
    END IF;
  END IF;

  -- true = this call is what flagged it. Already-flagged is still a successful report (the audit row
  -- the caller writes records the second reporter), so the caller is told the outcome, not an error.
  RETURN NOT coalesce(v_already, false);
END $$;

NOTIFY pgrst, 'reload schema';
