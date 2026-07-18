-- 20260707000008_fix_agent_memory_read_leak.sql
--
-- FIX (privacy / tenant-isolation, dim-3): the `agent_memory_read` RLS policy leaked EVERY worker's
-- private AI-companion conversation to every other member of their hive. agent_memory holds the raw
-- turns of a worker's chat with the companion (user_input / assistant_response / turn_text). The policy
-- USING clause was `auth.uid() = auth_uid OR (hive member of the row's hive)` — so any active hive
-- member could SELECT any other member's companion turns. Proven live 2026-07-07: signed in as Leandro
-- (Baguio Textile Mills) I read 13 of Bryan Garcia's private companion rows, incl. his question
-- "When did this asset last fail and why?".
--
-- This directly contradicts the table's OWN design header (migration 20260511000001): "Rows scoped by
-- (hive_id, worker_name, agent_id) so a worker's question to asset-brain doesn't LEAK into their
-- analytics conversation." The insert/update/delete policies are already own-rows-only; only the READ
-- over-shared. No feature needs cross-worker client reads: the only client readers (voice-handler
-- _fetchRecentMemory by session_id, companion_battery by own auth_uid) are self-scoped, and the
-- gateway's server-side recall (loadMemory / persistEpisodic) uses the service-role adminClient, which
-- bypasses RLS entirely. So scoping the read to the owner breaks nothing and closes the leak.
--
-- Fix: re-create agent_memory_read as OWN-ROWS-ONLY (by auth_uid OR worker_id — both are used: saveTurn
-- rows carry auth_uid, store_memory_turn rows carry worker_id). A future "shared org memory" feature, if
-- ever built, must expose only explicitly-shared rows via a NARROW policy, never blanket hive-read on
-- personal conversation turns.

DROP POLICY IF EXISTS agent_memory_read ON public.agent_memory;

CREATE POLICY agent_memory_read ON public.agent_memory
  FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND (auth.uid() = auth_uid OR auth.uid() = worker_id)
  );
