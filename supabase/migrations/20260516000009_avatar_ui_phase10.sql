-- Phase 10: Visual Companion UI & Floating Avatar

create table if not exists avatar_state (
  id bigserial primary key,
  session_id text unique,
  current_state text default 'idle',  -- idle, listening, thinking, speaking, success, error
  emotion text,  -- neutral, concerned, excited, warm
  last_gesture text,
  updated_at timestamptz default now()
);

create index if not exists idx_avatar_session on avatar_state(session_id);

-- Animation configuration
create table if not exists avatar_animations (
  id bigserial primary key,
  state_name text unique,
  animation_key text,
  duration_ms int,
  config jsonb
);
