-- Phase 4: Multi-Turn Dialog Flow & Intent Refinement
-- Tracks dialog state, intent evolution, and clarification requests

create table if not exists dialog_state (
  id bigserial primary key,
  hive_id uuid not null,
  worker_id uuid not null,
  session_id text not null,  -- shared with agent_memory
  current_intent text,        -- 'mtbf', 'mttr', 'risk_assessment', 'pm_scheduling', etc.
  intent_confidence real,     -- 0.0-1.0, updated per turn
  context_slots jsonb,        -- {"equipment": "pump_c", "time_window": "7d", ...}
  clarification_pending boolean default false,
  clarification_prompt text,  -- "Are you asking about downtime in Equipment A or whole hive?"
  last_turn_num int,          -- most recent turn processed
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_dialog_state_session on dialog_state(session_id);
create index if not exists idx_dialog_state_worker_hive on dialog_state(worker_id, hive_id);

alter table dialog_state enable row level security;

drop policy if exists "dialog_state_worker_access" on dialog_state;
create policy "dialog_state_worker_access" on dialog_state
  for select
  using (auth.uid() = worker_id);

drop policy if exists "dialog_state_insert_own" on dialog_state;
create policy "dialog_state_insert_own" on dialog_state
  for insert
  with check (auth.uid() = worker_id);

drop policy if exists "dialog_state_update_own" on dialog_state;
create policy "dialog_state_update_own" on dialog_state
  for update
  using (auth.uid() = worker_id);

-- View: current dialog state for a session
create or replace view v_dialog_state_current as
select
  session_id,
  current_intent,
  intent_confidence,
  context_slots,
  clarification_pending,
  clarification_prompt,
  last_turn_num
from dialog_state
where updated_at > now() - interval '1 hour';

-- RPC: fetch dialog state for a session
create or replace function fetch_dialog_state(
  p_session_id text
)
returns table (
  current_intent text,
  intent_confidence real,
  context_slots jsonb,
  clarification_pending boolean,
  clarification_prompt text
) as $$
begin
  return query
  select
    ds.current_intent,
    ds.intent_confidence,
    ds.context_slots,
    ds.clarification_pending,
    ds.clarification_prompt
  from dialog_state ds
  where ds.session_id = p_session_id
    and ds.worker_id = auth.uid()
  order by ds.updated_at desc
  limit 1;
end;
$$ language plpgsql security definer set search_path = public;

-- RPC: update dialog state with new intent + slots
create or replace function update_dialog_state(
  p_hive_id uuid,
  p_session_id text,
  p_turn_num int,
  p_intent text,
  p_confidence real,
  p_context_slots jsonb,
  p_clarification_pending boolean default false,
  p_clarification_prompt text default null
)
returns json as $$
declare
  v_exists boolean;
begin
  select exists(
    select 1 from dialog_state
    where session_id = p_session_id and worker_id = auth.uid()
  ) into v_exists;

  if v_exists then
    update dialog_state
    set
      current_intent = p_intent,
      intent_confidence = p_confidence,
      context_slots = coalesce(p_context_slots, context_slots),
      clarification_pending = p_clarification_pending,
      clarification_prompt = p_clarification_prompt,
      last_turn_num = p_turn_num,
      updated_at = now()
    where session_id = p_session_id and worker_id = auth.uid();
  else
    insert into dialog_state (
      hive_id, worker_id, session_id, current_intent, intent_confidence,
      context_slots, clarification_pending, clarification_prompt, last_turn_num
    )
    values (
      p_hive_id, auth.uid(), p_session_id, p_intent, p_confidence,
      p_context_slots, p_clarification_pending, p_clarification_prompt, p_turn_num
    );
  end if;

  return json_build_object(
    'ok', true,
    'session_id', p_session_id,
    'intent', p_intent,
    'confidence', p_confidence
  );
end;
$$ language plpgsql security definer set search_path = public;

-- Intent definitions (enumeration for clarity)
create type intent_kind as enum (
  'mtbf', 'mttr', 'oee', 'availability', 'reliability',
  'downtime', 'risk_assessment', 'equipment_status', 'pm_scheduling',
  'inventory_check', 'asset_details', 'predictive_alert', 'troubleshooting',
  'training_request', 'compliance_audit', 'unknown'
);
