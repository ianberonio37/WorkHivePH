---
name: ops-cron-realtime
type: ops
source: db:cron.job+pg_publication_tables
source_sha: ff69f68916050c36
last_verified: 2026-07-13
supersedes: null
---
## ops · cron jobs + realtime publication

**pg_cron jobs (40)** — a failing cron is SILENT; audit `cron.job_run_details` for failures:
- `achievement-xp-log-purge` @ `0 3 * * 0` → DELETE FROM public.achievement_xp_log x      WHERE x.earned_at < now() - interva
- `agent-memory-retention` @ `15 4 * * *` →        DELETE FROM public.agent_memory        WHERE kind = 'turn'          AND c
- `ai-eval-daily-analytics` @ `33 3 * * *` →        SELECT private.note_scheduled_call('ai-eval-daily-analytics', 'ai-eval-ru
- `ai-eval-daily-asset-brain` @ `30 3 * * *` →        SELECT private.note_scheduled_call('ai-eval-daily-asset-brain', 'ai-eval-
- `ai-eval-daily-logbook-voice` @ `42 3 * * *` →        SELECT private.note_scheduled_call('ai-eval-daily-logbook-voice', 'ai-eva
- `ai-eval-daily-project` @ `36 3 * * *` →        SELECT private.note_scheduled_call('ai-eval-daily-project', 'ai-eval-runn
- `ai-eval-daily-report-voice` @ `45 3 * * *` →        SELECT private.note_scheduled_call('ai-eval-daily-report-voice', 'ai-eval
- `ai-eval-daily-shift` @ `39 3 * * *` →        SELECT private.note_scheduled_call('ai-eval-daily-shift', 'ai-eval-runner
- `amc-brief-0600pht` @ `0 22 * * *` → SELECT private.note_scheduled_call('amc-brief-0600pht', 'amc-orchestrator', net.
- `amc-expire-stale-0555pht` @ `55 21 * * *` → SELECT public.amc_expire_stale();
- `analytics-events-retention` @ `50 4 * * *` →  delete from public.analytics_events where created_at < now() - interval '400 da
- `batch-risk-scoring-daily` @ `0 5 * * *` → SELECT private.note_scheduled_call('batch-risk-scoring-daily', 'batch-risk-scori
- `benchmark-compute-weekly` @ `30 21 * * 0` → SELECT private.note_scheduled_call('benchmark-compute-weekly', 'benchmark-comput
- `client-errors-retention` @ `40 4 * * *` →  delete from public.client_errors where created_at < now() - interval '90 days' 
- `cron-history-retention` @ `20 4 * * *` →  delete from cron.job_run_details where end_time < now() - interval '7 days' 
- `embedding-cache-retention` @ `25 4 * * *` →        -- LRU age eviction: drop cache entries not used in 45 days. Recomputed o
- `embedding-outbox-relay` @ `* * * * *` → SELECT private.relay_embedding_outbox(20);
- `failure-digest-weekly` @ `0 7 * * 1` → SELECT private.note_scheduled_call('failure-digest-weekly', 'scheduled-agents', 
- `failure-signature-scan-daily` @ `0 21 * * *` → SELECT private.note_scheduled_call('failure-signature-scan-daily', 'failure-sign
- `gateway-audit-retention` @ `30 4 * * *` →        DELETE FROM public.gateway_audit_log        WHERE created_at < now() - IN
- `hard-delete-soft-expired` @ `0 4 * * *` →  SELECT public.hard_delete_expired_soft_deletes(); 
- `hierarchical-summaries-weekly` @ `0 21 * * 0` →    SELECT private.note_scheduled_call('hierarchical-summaries-weekly', 'hierarch
- `hive-route-calls-retention` @ `45 4 * * *` →        DELETE FROM public.hive_route_calls        WHERE hour_bucket < now() - IN
- `listing-holding-fee-monthly` @ `0 3 1 * *` → SELECT public.sweep_listing_holding_fee();
- `ml-retrain-weekly` @ `0 18 * * 6` → SELECT private.note_scheduled_call('ml-retrain-weekly', 'trigger-ml-retrain', ne
- `ops-db-size-snapshot-daily` @ `10 0 * * *` → select public.snapshot_db_size()
- `parts-recs-expire-0550pht` @ `50 21 * * *` → SELECT public.expire_stale_parts_recommendations();
- `pm-auto-hail-daily` @ `15 0 * * *` → select public.sweep_pm_auto_hail();
- `pm-overdue-daily` @ `0 6 * * *` → SELECT private.note_scheduled_call('pm-overdue-daily', 'scheduled-agents', net.h
- `predictive-weekly` @ `0 20 * * 0` → SELECT private.note_scheduled_call('predictive-weekly', 'scheduled-agents', net.
- `project-risk-weekly` @ `0 6 * * 3` → SELECT private.note_scheduled_call('project-risk-weekly', 'scheduled-agents', ne
- `scheduled-calls-settle` @ `*/5 * * * *` → SELECT private.settle_scheduled_calls();
- `service-availability-reconcile-1min` @ `* * * * *` → SELECT public.reconcile_provider_availability();
- `service-broadcast-sweep-1min` @ `* * * * *` → SELECT public.sweep_service_broadcasts();
- `service-completion-sweep-hourly` @ `7 * * * *` → SELECT public.sweep_service_completions();
- `service-outbox-drain-1min` @ `* * * * *` → SELECT public.drain_service_outbox(20);
- `service-outbox-reconcile-1min` @ `* * * * *` → SELECT public.reconcile_service_outbox();
- `v-kpi-truth-refresh-hourly` @ `0 * * * *` →  SELECT public.refresh_v_kpi_truth(); 
- `voice-journal-retention` @ `45 4 * * *` →        DELETE FROM public.voice_journal_entries        WHERE created_at < now() 
- `wh-traces-retention` @ `35 4 * * *` →  delete from public.wh_traces where created_at < now() - interval '90 days' 

**Realtime publication `supabase_realtime` (36 tables)** — a table NOT here has DEAD postgres_changes subscriptions (no error, just no events):
`amc_briefings`, `anomaly_signals`, `asset_edges`, `asset_nodes`, `asset_risk_scores`, `automation_log`, `community_posts`, `community_reactions`, `community_replies`, `drone_inspections`, `hive_adoption_score`, `hive_audit_log`, `hive_readiness`, `inventory_items`, `knowledge_graph_facts`, `logbook`, `marketplace_listings`, `parts_staged_reservations`, `parts_staging_recommendations`, `platform_feedback`, `pm_completions`, `project_change_orders`, `project_items`, `project_progress_logs`, `project_roles`, `projects`, `rcm_fmea_modes`, `rcm_strategies`, `schedule_items`, `sensor_readings`, `service_job_events`, `service_offers`, `service_requests`, `shift_plans`, `weibull_fits`, `worker_achievements`

Links: [[reference_cron_silent_failure_retention]] [[reference_realtime_publication_and_singleton]]
