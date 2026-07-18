-- 20260707000009_fix_episodic_and_feedback_read_leak.sql
--
-- FIX (privacy / tenant-isolation, dim-3): the audit-reflex sweep off the agent_memory leak
-- (migration 20260707000008) found the SAME "hive-member READ of per-worker private data" class on
-- two sibling tables. Neither is read cross-worker by any client (server-side reads use the
-- service-role adminClient, which bypasses RLS), so tightening the client read policy breaks nothing.
--
-- 1) agent_episodic_memory.aem_read — IDENTICAL to the agent_memory leak. It holds a worker's private
--    companion episodic memory (memory_type / content / embedding extracted from their conversations),
--    yet allowed any active hive member to read it. Scope to OWNER-only (like agent_memory).
--
-- 2) ai_reply_feedback.ai_reply_feedback_read — a worker's AI thumbs up/down INCLUDING the question they
--    asked and the answer. Allowed any hive member to read a colleague's AI questions. Scope to OWNER
--    OR SUPERVISOR (mirrors auth_session_events): the supervisor branch preserves AI-quality moderation
--    / the negative-feedback escalation, while closing the any-member leak.

-- 1) agent_episodic_memory -> owner-only
DROP POLICY IF EXISTS aem_read ON public.agent_episodic_memory;
CREATE POLICY aem_read ON public.agent_episodic_memory
  FOR SELECT
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid);

-- 2) ai_reply_feedback -> owner OR supervisor-of-the-hive
DROP POLICY IF EXISTS ai_reply_feedback_read ON public.ai_reply_feedback;
CREATE POLICY ai_reply_feedback_read ON public.ai_reply_feedback
  FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND (
      auth.uid() = auth_uid
      OR (
        hive_id IS NOT NULL
        AND EXISTS (
          SELECT 1 FROM public.hive_members hm
          WHERE hm.hive_id = ai_reply_feedback.hive_id
            AND hm.auth_uid = auth.uid()
            AND hm.role = 'supervisor'
            AND hm.status = 'active'
        )
      )
    )
  );
