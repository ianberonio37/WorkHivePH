-- Phase 9: Cross-Hive Coordination & Team Context

create table if not exists cross_hive_alerts (
  id bigserial primary key,
  source_hive_id uuid not null,
  related_hive_ids uuid[] not null,
  shared_asset_id uuid,
  alert_reason text,
  severity text,  -- critical, high, medium
  detected_at timestamptz default now()
);

create index if not exists idx_cross_hive_source on cross_hive_alerts(source_hive_id, severity);

-- Best practice sharing (solutions from one hive that worked for another)
create table if not exists best_practices (
  id bigserial primary key,
  source_hive_id uuid not null,
  problem_category text,  -- equipment availability, safety, compliance, etc.
  solution_title text not null,
  solution_description text,
  effectiveness_score real,  -- 0-1, user-rated
  created_at timestamptz default now()
);

create index if not exists idx_practices_category on best_practices(problem_category, effectiveness_score desc);
