---
name: ops-cron-realtime
type: ops
source: db:cron.job+pg_publication_tables
source_sha: 702e7fb4387e6a76
last_verified: 2026-07-13
supersedes: null
---
## ops · cron jobs + realtime publication

**pg_cron jobs (17)** — a failing cron is SILENT; audit `cron.job_run_details` for failures:
- `achievement-xp-log-purge` @ `0 3 * * 0` → DELETE FROM achievement_xp_log WHERE earned_at < now() - interval '90 days'
- `agent-memory-retention` @ `15 4 * * *` →        DELETE FROM public.agent_memory        WHERE kind = 'turn'          AND c
- `ai-eval-daily` @ `30 3 * * *` →        SELECT net.http_post(         url     := current_setting('app.supabase_fu
- `amc-brief-0600pht` @ `0 22 * * *` → SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/a
- `amc-expire-stale-0555pht` @ `55 21 * * *` → SELECT public.amc_expire_stale();
- `batch-risk-scoring-daily` @ `0 5 * * *` → SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/b
- `embedding-cache-retention` @ `25 4 * * *` →        -- LRU age eviction: drop cache entries not used in 45 days. Recomputed o
- `failure-digest-weekly` @ `0 7 * * 1` → SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/s
- `failure-signature-scan-daily` @ `0 21 * * *` → SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/f
- `gateway-audit-retention` @ `30 4 * * *` →        DELETE FROM public.gateway_audit_log        WHERE created_at < now() - IN
- `hard-delete-soft-expired` @ `0 4 * * *` →  SELECT public.hard_delete_expired_soft_deletes(); 
- `hive-route-calls-retention` @ `45 4 * * *` →        DELETE FROM public.hive_route_calls        WHERE hour_bucket < now() - IN
- `ml-retrain-weekly` @ `0 18 * * 6` → SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/t
- `ops-db-size-snapshot-daily` @ `10 0 * * *` → select public.snapshot_db_size()
- `pm-overdue-daily` @ `0 6 * * *` → SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/s
- `predictive-weekly` @ `0 20 * * 0` → SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/s
- `project-risk-weekly` @ `0 6 * * 3` → SELECT net.http_post(url := current_setting('app.supabase_functions_url') || '/s

**Realtime publication `supabase_realtime` (33 tables)** — a table NOT here has DEAD postgres_changes subscriptions (no error, just no events):
`amc_briefings`, `anomaly_signals`, `asset_edges`, `asset_nodes`, `asset_risk_scores`, `automation_log`, `community_posts`, `community_reactions`, `community_replies`, `drone_inspections`, `hive_adoption_score`, `hive_audit_log`, `hive_readiness`, `inventory_items`, `knowledge_graph_facts`, `logbook`, `marketplace_listings`, `parts_staged_reservations`, `parts_staging_recommendations`, `platform_feedback`, `pm_completions`, `project_change_orders`, `project_items`, `project_progress_logs`, `project_roles`, `projects`, `rcm_fmea_modes`, `rcm_strategies`, `schedule_items`, `sensor_readings`, `shift_plans`, `weibull_fits`, `worker_achievements`

Links: [[reference_cron_silent_failure_retention]] [[reference_realtime_publication_and_singleton]]
