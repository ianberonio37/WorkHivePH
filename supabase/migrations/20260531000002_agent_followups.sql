-- ─────────────────────────────────────────────────────────────────────────
-- Memory-stack Turn 6 (Prospective / layer 06): per-user deferred follow-up
-- queue. The agent's PROSPECTIVE memory - "remember to check back on X later."
--
-- Gap closed: the stack had Working/Episodic/Semantic/Procedural/Hierarchical/
-- Shared wired, but NOTHING let an agent defer an intention to a future time.
-- 'prospective' was not even a memory_type; notifications is an immediate alert
-- center; scheduled-agents is platform pg_cron. This table is the missing
-- per-(hive,worker) tickler: a specialist enqueues "recheck pump P-204
-- vibration in 7 days", and ai-gateway surfaces it back into the agent's
-- context once it is due.
--
-- RLS mirrors agent_episodic_memory: membership-gated SELECT (NOT a USING(true)
-- open policy - that would bump the RLS-open board baseline), writes locked to
-- the service role (the gateway). Consumers cannot poison the queue.
-- ─────────────────────────────────────────────────────────────────────────

BEGIN;

CREATE TABLE IF NOT EXISTS public.agent_followups (
  id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid        REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name     text,
  topic           text        NOT NULL,                 -- short subject of the follow-up
  detail          text,                                 -- what to check / why
  due_at          timestamptz NOT NULL,                 -- when it should surface
  status          text        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','surfaced','resolved','dismissed')),
  importance      real        NOT NULL DEFAULT 0.5 CHECK (importance BETWEEN 0 AND 1),
  source_trace_id text,
  created_by      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  surfaced_at     timestamptz,
  resolved_at     timestamptz
);

COMMENT ON TABLE public.agent_followups IS
  'Turn 6 (Prospective layer) - per-(hive,worker) deferred follow-up queue. A specialist enqueues a future-dated intention via its envelope (followups[]); ai-gateway surfaces due ones back into the agent context (recallDueFollowups) and marks them surfaced. Writes are service-role only.';

-- Hot path: "pending follow-ups for this worker that are due now" + the
-- per-worker pending-cap count. Partial index keeps the due-scan tiny.
CREATE INDEX IF NOT EXISTS idx_followups_scope_status_due
  ON public.agent_followups (hive_id, worker_name, status, due_at);
CREATE INDEX IF NOT EXISTS idx_followups_due_pending
  ON public.agent_followups (due_at)
  WHERE status = 'pending';

GRANT SELECT, INSERT, UPDATE ON public.agent_followups TO anon, authenticated;

ALTER TABLE public.agent_followups ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS followups_read   ON public.agent_followups;
DROP POLICY IF EXISTS followups_insert ON public.agent_followups;
DROP POLICY IF EXISTS followups_update ON public.agent_followups;

-- Read: members of the row's hive (membership-gated, NOT open). The gateway
-- itself reads via service role; this policy is for any future client surface.
CREATE POLICY followups_read ON public.agent_followups
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND hive_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = agent_followups.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Enqueue + status transitions only via the service role (ai-gateway). Block
-- direct anon/auth writes so a client cannot inject or resolve follow-ups.
CREATE POLICY followups_insert ON public.agent_followups
  FOR INSERT WITH CHECK (false);
CREATE POLICY followups_update ON public.agent_followups
  FOR UPDATE USING (false);

COMMIT;
