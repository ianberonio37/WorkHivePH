-- Phase 2: Session Memory & Conversation Context
-- Tracks multi-turn conversations for recall and deduplication

create table if not exists agent_memory (
  id bigserial primary key,
  hive_id uuid not null,
  worker_id uuid not null,
  session_id text not null,  -- UUID or token-derived
  turn_num int not null,      -- 1, 2, 3... per session
  user_input text not null,
  user_input_hash text,       -- SHA256 for dedup detection
  assistant_response text not null,
  intent_classification text, -- 'mtbf', 'mttr', 'risk_assessment', etc.
  intent_confidence real,     -- 0.0-1.0
  embedding bytea,            -- Voyage embedding vector (if needed)
  response_time_ms int,       -- Latency tracking
  created_at timestamptz default now(),
  expires_at timestamptz      -- 24h inactivity cleanup
);

create index if not exists idx_agent_memory_session on agent_memory(session_id, turn_num);
create index if not exists idx_agent_memory_worker_hive on agent_memory(worker_id, hive_id, session_id);
create index if not exists idx_agent_memory_expires on agent_memory(expires_at);

-- RLS: workers can only read their own memory
alter table agent_memory enable row level security;

drop policy if exists "agent_memory_worker_access" on agent_memory;
create policy "agent_memory_worker_access" on agent_memory
  for select
  using (auth.uid() = worker_id);

drop policy if exists "agent_memory_insert_own" on agent_memory;
create policy "agent_memory_insert_own" on agent_memory
  for insert
  with check (auth.uid() = worker_id);

-- View: recent memory for a session (last 10 turns)
create or replace view v_session_memory_recent as
select
  session_id,
  turn_num,
  user_input,
  assistant_response,
  intent_classification,
  intent_confidence,
  response_time_ms,
  created_at
from agent_memory
order by turn_num desc
limit 10;

-- RPC: fetch recent memory for a session
create or replace function fetch_session_memory(
  p_session_id text,
  p_limit int default 10
)
returns table (
  turn_num int,
  user_input text,
  assistant_response text,
  intent text,
  confidence real,
  created_at timestamptz
) as $$
begin
  return query
  select
    am.turn_num,
    am.user_input,
    am.assistant_response,
    am.intent_classification,
    am.intent_confidence,
    am.created_at
  from agent_memory am
  where am.session_id = p_session_id
    and am.worker_id = auth.uid()
  order by am.turn_num asc
  limit p_limit;
end;
$$ language plpgsql security definer set search_path = public;

-- RPC: store a turn (session, user input, response, intent)
create or replace function store_memory_turn(
  p_hive_id uuid,
  p_session_id text,
  p_turn_num int,
  p_user_input text,
  p_assistant_response text,
  p_intent text,
  p_confidence real,
  p_response_time_ms int
)
returns json as $$
declare
  v_hash text;
begin
  v_hash := md5(p_user_input);

  insert into agent_memory (
    hive_id, worker_id, session_id, turn_num,
    user_input, user_input_hash, assistant_response,
    intent_classification, intent_confidence, response_time_ms,
    expires_at
  )
  values (
    p_hive_id, auth.uid(), p_session_id, p_turn_num,
    p_user_input, v_hash, p_assistant_response,
    p_intent, p_confidence, p_response_time_ms,
    now() + interval '24 hours'
  );

  return json_build_object(
    'ok', true,
    'turn_num', p_turn_num,
    'session_id', p_session_id
  );
end;
$$ language plpgsql security definer set search_path = public;

-- Cron job: cleanup expired sessions (runs daily)
-- This will be registered in edge-functions config, not here
-- select cron.schedule('cleanup_expired_memory', '0 2 * * *', $$
--   delete from agent_memory where expires_at < now();
-- $$);
