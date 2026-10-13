-- ★AN ANSWER LEFT NO RECORD AN OPERATOR COULD READ (LM-O walk, LM544, alert-hub, 2026-10-08). alert-hub.html's ask
-- reached analytics-orchestrator, which imported logAICost and never called it; the one trace of the model call was
-- the edge stdout line "[ai-chain] served by ...". Nineteen of the twenty-nine functions that call a model wrote no
-- row at all, and the ten that did wrote a hand-typed model name with no trace id and no user (two of them one
-- aggregate row per run, the gateway one pseudo row per turn), so even a logged call could not be tied to the answer
-- a person saw or rated.
--
-- Every served model call is now recorded once, by the shared collector (_shared/model-calls.ts, written by
-- serveObserved in _shared/observability.ts). public.ai_cost_log already holds fn, hive_id, worker_name, provider,
-- model, tokens, latency_ms and status; it lacked three things this record needs:
--   trace_id          the id the answering endpoint returned to the page (its x-wh-trace / envelope trace_id), so a
--                     record joins to the reply, to its ai_reply_feedback rating (same column, same shape) and to the
--                     other calls of the same turn (a gateway forward keeps the gateway's id in the specialist)
--   auth_uid          the VERIFIED user the call was made for (worker_name is a display name and can be renamed);
--                     ON DELETE SET NULL so a deleted account leaves no id behind in the ledger
--   tokens_estimated  true when the provider reported no usage and the tokens are a chars/4 estimate - a figure that
--                     is a guess says so beside itself
--
-- RLS is unchanged: ai_cost_log_read already lets an active member read their own hive's rows (ai-quality.html), and
-- grafana_reader reads all (the founder board); inserts stay service-role only (ai_cost_log_insert WITH CHECK false).
-- Grants are table-level with no column ACLs, so the new columns need no GRANT. The only routine that touches the
-- table, hard_delete_expired_soft_deletes, deletes by created_at and is indifferent to new columns. No view reads it.
-- Forward-only and idempotent.

alter table public.ai_cost_log
  add column if not exists trace_id         text,
  add column if not exists auth_uid         uuid,
  add column if not exists tokens_estimated boolean;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.ai_cost_log'::regclass and conname = 'ai_cost_log_trace_id_shape'
  ) then
    alter table public.ai_cost_log
      add constraint ai_cost_log_trace_id_shape check (
        trace_id is null
        or trace_id ~ '^[0-9a-f]{8,32}$'
        or trace_id ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
      );
  end if;
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.ai_cost_log'::regclass and conname = 'ai_cost_log_auth_uid_fkey'
  ) then
    alter table public.ai_cost_log
      add constraint ai_cost_log_auth_uid_fkey foreign key (auth_uid) references auth.users(id) on delete set null;
  end if;
end $$;

-- the operator's join: a reply / a rating -> every model call of that request
create index if not exists idx_ai_cost_log_trace
  on public.ai_cost_log (trace_id)
  where trace_id is not null;

comment on column public.ai_cost_log.trace_id is
  'Id the answering endpoint returned to the page for the request that made this model call (reply x-wh-trace / '
  'envelope trace_id; = ai_reply_feedback.trace_id of a rating on that reply). Written by _shared/observability.ts '
  'settleModelCalls (LM-O, 2026-10-08). NULL on rows written outside a request scope.';
comment on column public.ai_cost_log.auth_uid is
  'Verified user the model call was made for (tenant-context resolveIdentity/resolveTenancy, or the bearer verified '
  'by auth). NULL for a service-role / cron call and for an anonymous companion turn.';
comment on column public.ai_cost_log.tokens_estimated is
  'true when the provider returned no usage block and prompt_tokens/output_tokens are a chars/4 estimate.';
