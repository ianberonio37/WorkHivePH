-- Phase 5: Proactive Alerts & Anomaly Intelligence
-- Detects KPI spikes, risk escalation, maintenance overdue

create table if not exists anomaly_alerts (
  id bigserial primary key,
  hive_id uuid not null,
  asset_id uuid,
  alert_type text not null,  -- 'kpi_spike', 'risk_escalation', 'maintenance_overdue', 'failure_prediction'
  severity text not null,     -- 'critical', 'high', 'medium', 'info'
  metric_name text,           -- 'mttr', 'mtbf', 'oee', 'availability', etc.
  metric_value real,
  metric_threshold real,
  deviation_percent real,     -- e.g., 140% = 40% over baseline
  description text,
  action_suggested text,      -- "Your PM is scheduled in X days, schedule earlier?"
  detected_at timestamptz default now(),
  last_notified_at timestamptz,
  acknowledged_at timestamptz,
  suppressed_until timestamptz  -- worker can mute for 24h
);

create index if not exists idx_anomaly_alerts_hive on anomaly_alerts(hive_id, detected_at desc);
create index if not exists idx_anomaly_alerts_severity on anomaly_alerts(severity, hive_id);
create index if not exists idx_anomaly_alerts_asset on anomaly_alerts(asset_id);

alter table anomaly_alerts enable row level security;

drop policy if exists "anomaly_alerts_hive_access" on anomaly_alerts;
-- 2026-05-20 fix: blueprint referenced a non-existent `worker_hives` table;
-- the platform uses `hive_members` with auth_uid + hive_id columns.
create policy "anomaly_alerts_hive_access" on anomaly_alerts
  for select
  using (
    exists (
      select 1 from public.hive_members hm
      where hm.hive_id = anomaly_alerts.hive_id
        and hm.auth_uid = auth.uid()
        and hm.status = 'active'
    )
  );

-- View: active, non-suppressed alerts
create or replace view v_active_anomaly_alerts as
select
  id, hive_id, asset_id, alert_type, severity, metric_name,
  metric_value, metric_threshold, deviation_percent,
  description, action_suggested, detected_at
from anomaly_alerts
where (suppressed_until is null or suppressed_until < now())
  and acknowledged_at is null
order by
  case when severity = 'critical' then 1
       when severity = 'high' then 2
       when severity = 'medium' then 3
       else 4 end,
  detected_at desc;

-- RPC: fetch active alerts for a hive
-- 2026-05-20 self-heal: DROP first so an existing function with a different
-- return type doesn't block CREATE OR REPLACE (Postgres disallows return-type
-- changes via OR REPLACE).
drop function if exists fetch_active_alerts(uuid);
create or replace function fetch_active_alerts(p_hive_id uuid)
returns table (
  alert_id bigint,
  alert_type text,
  severity text,
  description text,
  action_suggested text,
  deviation_percent real,
  detected_at timestamptz
) as $$
begin
  return query
  select
    aa.id, aa.alert_type, aa.severity, aa.description,
    aa.action_suggested, aa.deviation_percent, aa.detected_at
  from anomaly_alerts aa
  where aa.hive_id = p_hive_id
    and (aa.suppressed_until is null or aa.suppressed_until < now())
    and aa.acknowledged_at is null
  order by
    case when aa.severity = 'critical' then 1
         when aa.severity = 'high' then 2
         when aa.severity = 'medium' then 3
         else 4 end,
    aa.detected_at desc
  limit 10;
end;
$$ language plpgsql security definer set search_path = public;

-- RPC: acknowledge an alert (worker closed it)
create or replace function acknowledge_alert(p_alert_id bigint)
returns json as $$
begin
  update anomaly_alerts
  set acknowledged_at = now()
  where id = p_alert_id;

  return json_build_object('ok', true, 'alert_id', p_alert_id);
end;
$$ language plpgsql security definer set search_path = public;

-- RPC: suppress alert for 24h (user mutes low-severity)
create or replace function suppress_alert(p_alert_id bigint, p_hours int default 24)
returns json as $$
begin
  update anomaly_alerts
  set suppressed_until = now() + (p_hours || ' hours')::interval
  where id = p_alert_id;

  return json_build_object('ok', true, 'alert_id', p_alert_id, 'suppressed_hours', p_hours);
end;
$$ language plpgsql security definer set search_path = public;

-- Edge function will call: detect_kpi_spikes(), detect_risk_escalation(), detect_maintenance_overdue()
-- and insert into anomaly_alerts table via trigger
