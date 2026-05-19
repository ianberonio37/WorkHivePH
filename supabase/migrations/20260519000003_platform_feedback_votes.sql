-- ============================================================
-- Platform Feedback votes — public roadmap upvoting (2026-05-19)
-- ============================================================
-- Phase 2 of the universal feedback system (Phase 1 shipped in
-- 20260519000002_platform_feedback.sql). Adds the upvote tracking
-- table + atomic toggle RPC so the public /feedback/ roadmap page
-- can show vote counts that don't double-count or race.
--
-- Identity model: voter_token is auth.uid()::text when signed-in,
-- or a localStorage-generated random token when anonymous. The
-- (feedback_id, voter_token) primary key blocks double-voting from
-- the same identity bucket. Anon visitors clearing localStorage
-- can revote — acceptable for a free platform; this is a roadmap
-- signal, not a ballot.
--
-- The toggle_feedback_upvote() RPC is the only correct way to
-- vote. It checks is_public, toggles the vote row + the cached
-- upvotes count atomically. Direct UPDATEs to platform_feedback.upvotes
-- are policy-blocked at the JS layer (admin gate only).
-- ============================================================

CREATE TABLE IF NOT EXISTS public.platform_feedback_votes (
  feedback_id uuid        NOT NULL REFERENCES public.platform_feedback(id) ON DELETE CASCADE,
  voter_token text        NOT NULL,
  voted_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (feedback_id, voter_token)
);

-- Reverse index for cheap "did I vote on this?" lookups by voter
CREATE INDEX IF NOT EXISTS idx_platform_feedback_votes_voter
  ON public.platform_feedback_votes (voter_token, voted_at DESC);

ALTER TABLE public.platform_feedback_votes ENABLE ROW LEVEL SECURITY;
GRANT SELECT, INSERT, DELETE ON public.platform_feedback_votes
  TO anon, authenticated;

DROP POLICY IF EXISTS "anon vote read"   ON public.platform_feedback_votes;
DROP POLICY IF EXISTS "anon vote insert" ON public.platform_feedback_votes;
DROP POLICY IF EXISTS "anon vote delete" ON public.platform_feedback_votes;

-- All operations open at DB layer (matches platform RLS convention);
-- the toggle RPC enforces "is_public only" and (feedback_id, voter_token)
-- PK enforces no-double-vote. SELECT is open so the roadmap page can
-- query "have I voted on this set?" in one batch.
CREATE POLICY "anon vote read"
  ON public.platform_feedback_votes FOR SELECT USING (true);

CREATE POLICY "anon vote insert"
  ON public.platform_feedback_votes FOR INSERT WITH CHECK (true);

CREATE POLICY "anon vote delete"
  ON public.platform_feedback_votes FOR DELETE USING (true);


-- ── Atomic toggle RPC ──────────────────────────────────────────────
-- Returns the updated upvotes count + the user's new vote state, so
-- the client can update the UI in one round trip. Refuses to vote on
-- non-public items so a malicious crafted payload can't drive engagement
-- on items the admin hasn't promoted.

CREATE OR REPLACE FUNCTION public.toggle_feedback_upvote(
  p_feedback_id uuid,
  p_voter_token text
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_exists    boolean;
  v_is_public boolean;
  v_upvotes   integer;
  v_has_voted boolean;
BEGIN
  IF p_feedback_id IS NULL OR p_voter_token IS NULL OR length(p_voter_token) = 0 THEN
    RAISE EXCEPTION 'feedback_id and voter_token are required';
  END IF;

  -- Item must be public for voting to count
  SELECT is_public INTO v_is_public
  FROM public.platform_feedback
  WHERE id = p_feedback_id;
  IF v_is_public IS NULL THEN
    RAISE EXCEPTION 'Feedback item not found';
  END IF;
  IF NOT v_is_public THEN
    RAISE EXCEPTION 'Feedback item is not public — admin must publish before votes count';
  END IF;

  -- Toggle the vote row
  SELECT EXISTS (
    SELECT 1 FROM public.platform_feedback_votes
    WHERE feedback_id = p_feedback_id AND voter_token = p_voter_token
  ) INTO v_exists;

  IF v_exists THEN
    DELETE FROM public.platform_feedback_votes
      WHERE feedback_id = p_feedback_id AND voter_token = p_voter_token;
    UPDATE public.platform_feedback
      SET upvotes = GREATEST(upvotes - 1, 0)
      WHERE id = p_feedback_id
      RETURNING upvotes INTO v_upvotes;
    v_has_voted := false;
  ELSE
    INSERT INTO public.platform_feedback_votes (feedback_id, voter_token)
      VALUES (p_feedback_id, p_voter_token);
    UPDATE public.platform_feedback
      SET upvotes = upvotes + 1
      WHERE id = p_feedback_id
      RETURNING upvotes INTO v_upvotes;
    v_has_voted := true;
  END IF;

  RETURN json_build_object(
    'upvotes',   v_upvotes,
    'has_voted', v_has_voted
  );
END;
$$;

GRANT EXECUTE ON FUNCTION public.toggle_feedback_upvote(uuid, text)
  TO anon, authenticated;


-- ── Documentation ──────────────────────────────────────────────────
COMMENT ON TABLE public.platform_feedback_votes IS
  'Tracks who voted on which public roadmap item. PK enforces one vote
   per (feedback_id, voter_token) — voter_token is auth.uid()::text for
   signed-in or a localStorage-generated random token for anon. Cascade
   deletes when the parent feedback row is deleted.';

COMMENT ON FUNCTION public.toggle_feedback_upvote(uuid, text) IS
  'Atomic vote toggle for the public /feedback/ roadmap. Refuses to
   vote on non-public items. Returns {upvotes, has_voted} so the client
   updates UI in one round trip.';
