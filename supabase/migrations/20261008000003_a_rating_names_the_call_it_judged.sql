-- ★A "WRONG" COULD NOT BE MATCHED TO THE CALL IT JUDGED (LM-E walk, 2026-10-08). public.ai_reply_feedback is where a
-- person's "was this right?" lands (the companion launcher, the voice bubble, the Assistant chat and the shared
-- whAiTrustRow under Asset Brain / the voice journal / the shift briefing / the analytics narrative / the resume
-- polish). It stored the question and the answer TEXT and nothing that identified the call that produced the answer,
-- so the harvest (tools/companion_harvest.py) could only pair a thumbs-down with its trace by matching words - which
-- fails on a repeated question, on a hydrated name, and on an answer the gateway rewrote at egress. The answering
-- endpoint already hands the page an id for the call: ai-gateway's envelope carries `trace_id` (the wh_traces key it
-- records under, 16 lowercase hex), and agentic-rag-loop returns `trace_id` = its agentic_rag_traces.id (a uuid, the
-- same id agent_episodic_memory.source_trace_id already stores). The writer now keeps that id beside the reply it
-- rendered and sends it with the rating.
--
-- NULL is a real value, never a gap to fill: a reply that came from no traced call (a client-side cache replay, a
-- canned local line, a stored shift-plan briefing, a direct call to a function that returns no id) has no trace, and
-- a writer must never mint one. The CHECK admits exactly the two id shapes the platform returns, so a client-writable
-- column cannot become free-text storage; the writers pass only an id that matches, else NULL, so the CHECK can never
-- cost a person their rating.
--
-- Nothing else changes. RLS: ai_reply_feedback_insert binds auth_uid + hive membership and is indifferent to one more
-- column; there is no UPDATE/DELETE policy, so the id cannot be rewritten after the fact. Grants: authenticated,
-- service_role and grafana_reader hold TABLE-level privileges and there are no column ACLs on this table, so the new
-- column is covered with no GRANT (and no REVOKE would bite under a table grant anyway). No view or function reads
-- this table except the daily-limit trigger, which counts rows by auth_uid. Forward-only and idempotent.

alter table public.ai_reply_feedback
  add column if not exists trace_id text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.ai_reply_feedback'::regclass and conname = 'ai_reply_feedback_trace_id_shape'
  ) then
    alter table public.ai_reply_feedback
      add constraint ai_reply_feedback_trace_id_shape check (
        trace_id is null
        or trace_id ~ '^[0-9a-f]{8,32}$'
        or trace_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
      );
  end if;
end $$;

-- The harvest's join path: a thumbs-down -> the wh_traces / agentic_rag_traces row of the call it judged.
create index if not exists idx_ai_reply_feedback_trace
  on public.ai_reply_feedback (trace_id)
  where trace_id is not null;

comment on column public.ai_reply_feedback.trace_id is
  'Id of the call whose answer this rating judged, as the answering endpoint returned it: ai-gateway envelope trace_id '
  '(= wh_traces.trace_id, 16 hex) or agentic-rag-loop trace_id (= agentic_rag_traces.id, uuid). NULL when the rated '
  'reply came from no traced call; never minted by the client (LM-E, 2026-10-08).';
