-- Phase 8: Conversation Analytics & Learning Loop

create table if not exists conversation_analytics (
  id bigserial primary key,
  session_id text,
  turn_num int,
  question_category text,  -- mtbf, mttr, risk, pm, inventory, etc.
  answer_quality_rating int,  -- -1 (thumbs down), 0 (neutral), 1 (thumbs up)
  user_feedback text,
  model_confidence real,
  response_time_ms int,
  created_at timestamptz default now()
);

create index if not exists idx_analytics_session on conversation_analytics(session_id, turn_num);
create index if not exists idx_analytics_category on conversation_analytics(question_category, answer_quality_rating);

-- View: conversation health metrics
create or replace view v_conversation_health as
select
  question_category,
  count(*) as total_questions,
  avg(answer_quality_rating) as avg_quality,
  avg(response_time_ms) as avg_latency_ms,
  count(case when answer_quality_rating = 1 then 1 end)::real / count(*) as quality_ratio
from conversation_analytics
where created_at > now() - interval '7 days'
group by question_category;
