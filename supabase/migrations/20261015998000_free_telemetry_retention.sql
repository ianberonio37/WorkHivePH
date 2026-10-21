-- BRH 9 AA (2026-10-21): the telemetry tables that grow with every use get a window, so the free plan's 500 MB
-- database is never filled by what the platform records about itself.
--
-- Ian: "you know that my platform always free ... I am not upgrading to pro." Production, read-only on 2026-10-21:
-- wh_traces 5,124 rows (1.9 MB), analytics_events 3,046 (1.8 MB), client_errors 58 (104 kB) - every row ever written
-- still there, and no job removes any. Small today, but each grows with every request, page view and error, and
-- nothing bounded any of them.
--
-- Each window is longer than the longest window any reader asks for:
--   wh_traces         90 days  - the SLO views and Grafana read at most 28 days (Errors by route, 28d)
--   client_errors     90 days  - diagnostics; read as recent errors (Grafana, the error triage)
--   analytics_events 400 days  - the founder views read at most 30 days; 13 months keeps a year-on-year comparison
-- The privacy policy keeps account data "as long as your account is active" (an upper bound) and states no shorter
-- window for usage events or errors, so removing them sooner keeps what it promises.
--
-- Deliberately NOT here:
--   automation_log - it is part of the audit trail (v_audit_unified reads it), which the privacy policy keeps for
--                    10 years. It is not purged.
--   ai_cost_log    - already removed after 365 days by hard_delete_expired_soft_deletes() (job hard-delete-soft-expired,
--                    active in production); the pages say "AI cost records go after 365 days".
--
-- Gate: free-plan-budget (F1 every operational table purges on a schedule, the audit tables never inside their stated
-- window; F2 the jobs are active in the database).

-- the purge reads client_errors by age alone; its two indexes lead with hive_id or are partial
create index if not exists client_errors_created_idx on public.client_errors (created_at);

select cron.schedule('wh-traces-retention', '35 4 * * *',
  $$ delete from public.wh_traces where created_at < now() - interval '90 days' $$);

select cron.schedule('client-errors-retention', '40 4 * * *',
  $$ delete from public.client_errors where created_at < now() - interval '90 days' $$);

select cron.schedule('analytics-events-retention', '50 4 * * *',
  $$ delete from public.analytics_events where created_at < now() - interval '400 days' $$);
