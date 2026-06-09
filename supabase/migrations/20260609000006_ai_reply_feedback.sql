-- AI Reply Feedback -- the live thumbs (up/down) capture for the 8.5 harvest.
--
-- WHY a new table (decided 2026-06-09): the harvest (companion_harvest.py)
-- turns thumbs-DOWN replies into golden-candidate eval units, and a candidate
-- is "the failing QUESTION + the agent". None of the existing sinks carry the
-- question text on a client-writable path:
--   * ai_cost_log.quality_rating  -- has the rating slot but NO question/answer
--                                    columns, and no client UPDATE policy (its
--                                    only policies are read + insert-WITH-CHECK-
--                                    false). voice-handler's RPC/UPDATE rating
--                                    path was a no-op end to end.
--   * agentic_rag_traces.user_rating -- has question + final_answer + rating,
--                                    but is service-role-insert-only and the
--                                    voice-journal route never creates a trace.
--   * ai_quality_log              -- offline LLM-judge fixtures, service role.
-- This table is the ONE working, client-writable home for live reply ratings
-- across every companion surface (floating launcher / chat / voice), and it
-- stores the question + answer so the harvester can recover what was asked.
--
-- canonical-allow: infrastructure feedback log (per-reply rating) -- not a
-- user-facing domain entity, no v_*_truth canonical view exists for it.
CREATE TABLE IF NOT EXISTS public.ai_reply_feedback (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES public.hives(id) ON DELETE SET NULL,  -- NULL = solo mode
  auth_uid     uuid DEFAULT auth.uid(),   -- stamped by the DB; bound to the caller in RLS
  worker_name  text,                       -- display_name, human-readable for harvest reports
  agent        text NOT NULL,              -- ai-gateway agent route (e.g. 'voice-journal')
  source       text NOT NULL,              -- 'floating' | 'chat' | 'voice'
  page         text,                       -- page id for context (logbook, analytics, ...)
  persona      text,                       -- hezekiah | zaniah at rating time
  question     text NOT NULL,              -- what the worker asked (the harvest signal)
  answer       text,                       -- what the companion replied
  rating       smallint NOT NULL CHECK (rating IN (-1, 1)),  -- -1 thumbs-down, +1 thumbs-up
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- Harvest read paths: thumbs-down first, then by agent, then by hive.
CREATE INDEX IF NOT EXISTS idx_ai_reply_feedback_rating ON public.ai_reply_feedback (rating, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_reply_feedback_agent  ON public.ai_reply_feedback (agent, rating, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_reply_feedback_hive   ON public.ai_reply_feedback (hive_id, created_at DESC);

-- SQL migrations do NOT auto-grant (only the Supabase GUI does). Without this,
-- every authenticated query returns 401 regardless of the RLS policies below.
GRANT SELECT, INSERT ON public.ai_reply_feedback TO authenticated;

ALTER TABLE public.ai_reply_feedback ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ai_reply_feedback_insert ON public.ai_reply_feedback;
DROP POLICY IF EXISTS ai_reply_feedback_read   ON public.ai_reply_feedback;

-- INSERT: the row's auth_uid must be the caller (the DEFAULT stamps it, so the
-- client never sends it and a forged auth_uid is rejected). If a hive is named,
-- the caller must be an ACTIVE member of THAT hive (membership join, not a raw
-- hive_id equality). Solo rows (hive_id IS NULL) are allowed for any signed-in
-- worker rating their own private companion reply.
CREATE POLICY ai_reply_feedback_insert ON public.ai_reply_feedback
  FOR INSERT TO authenticated
  WITH CHECK (
    auth_uid = auth.uid()
    AND (
      hive_id IS NULL
      OR EXISTS (
        SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = ai_reply_feedback.hive_id
          AND hm.auth_uid = auth.uid()
          AND hm.status = 'active'
      )
    )
  );

-- READ: own rows always; hive members can read their hive's feedback (for a
-- future AI-quality dashboard). The harvester runs with the service role and
-- bypasses RLS, so it sees every hive's question text.
CREATE POLICY ai_reply_feedback_read ON public.ai_reply_feedback
  FOR SELECT TO authenticated
  USING (
    auth_uid = auth.uid()
    OR (
      hive_id IS NOT NULL
      AND EXISTS (
        SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = ai_reply_feedback.hive_id
          AND hm.auth_uid = auth.uid()
          AND hm.status = 'active'
      )
    )
  );

-- Anti-poisoning flood guard. A client-writable feedback table is a harvest-
-- poisoning vector: a script could inject thousands of fake thumbs-down to
-- bias the golden-candidate set. A real worker never rates hundreds of replies
-- a day, so cap inserts per identity per day at the DB level (unbypassable from
-- the client). The harvester ALSO human-disposes every candidate (never auto-
-- promotes to the locked test split), so this is defense-in-depth, not the only
-- guard. Best-effort: NULL auth_uid (shouldn't happen post-auth-migration) skips.
CREATE OR REPLACE FUNCTION public.enforce_ai_reply_feedback_daily_limit()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
  day_count integer;
  daily_cap constant integer := 200;
BEGIN
  IF NEW.auth_uid IS NULL THEN
    RETURN NEW;
  END IF;
  SELECT count(*) INTO day_count
  FROM public.ai_reply_feedback
  WHERE auth_uid = NEW.auth_uid
    AND created_at >= now() - interval '1 day';
  IF day_count >= daily_cap THEN
    RAISE EXCEPTION 'Daily AI reply feedback limit reached'
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_ai_reply_feedback_daily_limit ON public.ai_reply_feedback;
CREATE TRIGGER trg_ai_reply_feedback_daily_limit
  BEFORE INSERT ON public.ai_reply_feedback
  FOR EACH ROW EXECUTE FUNCTION public.enforce_ai_reply_feedback_daily_limit();
