-- ============================================================================
-- SECURITY FIX (I-axis, Community PDDA 7th): close the community_xp write hole
-- ----------------------------------------------------------------------------
-- BUG (proven live 2026-07-11): the sole policy on community_xp was
--   community_xp_write  FOR ALL  TO public  USING (auth.uid() IS NOT NULL)  WITH CHECK NULL
-- i.e. ANY authenticated user could INSERT/UPDATE/DELETE ANY row. Exploit
-- confirmed: a regular member set another member's xp_total to 999999. This lets
-- anyone mint arbitrary Community XP (top the leaderboard, self-promote) and — the
-- moment the Community->Marketplace reputation bridge ships — trivially mint a
-- "Community-trusted" seller badge. It also violates the community skill's core
-- rule: "All XP is awarded by DB triggers, never from client JS."
--
-- FIX: XP is written ONLY by SECURITY DEFINER code (increment_community_xp, which
-- the trg_community_post/reply/reaction_xp triggers call — confirmed prosecdef=true,
-- so it bypasses RLS). No client role needs INSERT/UPDATE/DELETE. All three client
-- references to community_xp in the codebase are .select() (reads: leaderboard,
-- profile card, hive board) — verified — so removing client writes has ZERO read
-- regression. We keep an authenticated SELECT policy for those reads.
-- ============================================================================

DROP POLICY IF EXISTS community_xp_write ON public.community_xp;

-- Reads: authenticated members may read XP (leaderboard, profile card, within-hive
-- reputation view). Cross-hive/anon reputation is served by the SECURITY DEFINER
-- get_community_reputation() RPC, so anon does not need direct table read here.
DROP POLICY IF EXISTS community_xp_read ON public.community_xp;
CREATE POLICY community_xp_read ON public.community_xp
  FOR SELECT TO authenticated
  USING (auth.uid() IS NOT NULL);

-- Writes: intentionally NO policy for client roles. Only SECURITY DEFINER functions
-- (increment_community_xp + the XP triggers) and service_role write community_xp.
-- With RLS enabled and no permissive write policy, client INSERT/UPDATE/DELETE is denied.
