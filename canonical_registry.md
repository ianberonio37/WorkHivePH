# Canonical Source Registry

Authoritative inventory of every table, RPC, view, edge fn, and HTML surface on the platform.
Re-built on every Mega Gate run by `tools/mine_canonical_registry.py`.

## Summary

- Tables:        **154**
- Views:         **51**
- RPCs:          **183**
- HTML surfaces: **51**
- Edge fns:      **98**
- Phantom tables (referenced in code, not in migrations): **0**
- Duplicate signals: **71**

## Tables (sorted by usage)

| Table | Cols | RLS | Realtime | Read by surfaces | Written by surfaces | Edge-fn writers |
|---|---:|---|---|---|---|---|
| `hive_audit_log` | 9 | no | yes | alert-hub.html, asset-hub.html, audit-log.html, community.html ... | alert-hub.html, asset-hub.html, community.html ... | export-hive-data, supervisor-reset-password |
| `automation_log` | 6 | yes | no | alert-hub.html | — | batch-risk-scoring, benchmark-compute, cmms-push-completion ... |
| `logbook` | 32 | yes | no | dayplanner.html, hive.html, integrations.html, logbook.html ... | dayplanner.html, hive.html, integrations.html ... | cmms-sync, cmms-webhook-receiver |
| `asset_nodes` | 26 | yes | yes | asset-hub.html, hive.html, integrations.html, inventory.html ... | asset-hub.html, integrations.html, inventory.html ... | — |
| `ai_rate_limits` | 5 | yes | no | — | — | _shared/rate-limit.ts, agentic-rag-loop, fmea-populator ... |
| `pm_completions` | 9 | yes | no | asset-hub.html, hive.html, logbook.html, pm-scheduler.html ... | logbook.html, pm-scheduler.html | — |
| `project_links` | 8 | no | no | inventory.html, logbook.html, pm-scheduler.html, project-manager.html ... | inventory.html, logbook.html, pm-scheduler.html ... | — |
| `marketplace_listings` | 22 | yes | yes | founder-console.html, marketplace-admin.html, marketplace-seller.html, marketplace.html ... | founder-console.html, marketplace-admin.html, marketplace-seller.html ... | — |
| `pm_assets` | 12 | yes | no | asset-hub.html, integrations.html, logbook.html, pm-scheduler.html | asset-hub.html, integrations.html, logbook.html ... | — |
| `fault_knowledge` | 14 | yes | no | integrations.html, logbook.html | integrations.html | cmms-sync, visual-defect-capture |
| `hive_members` | 7 | yes | no | asset-hub.html, hive.html, inventory.html, logbook.html ... | hive.html | — |
| `marketplace_sellers` | 19 | yes | no | founder-console.html, marketplace-admin.html, marketplace-seller.html, platform-actions.html | founder-console.html, marketplace-admin.html, marketplace-seller.html ... | — |
| `external_sync` | 11 | no | no | integrations.html | integrations.html | cmms-push-completion, cmms-sync, cmms-webhook-receiver |
| `inventory_items` | 21 | yes | no | integrations.html, inventory.html, logbook.html | integrations.html, inventory.html | cmms-webhook-receiver |
| `integration_configs` | 17 | no | no | integrations.html, plant-connections.html | integrations.html | cmms-sync |
| `marketplace_disputes` | 16 | yes | no | founder-console.html, marketplace-admin.html, platform-actions.html | founder-console.html, marketplace-admin.html, platform-actions.html | — |
| `pm_scope_items` | 8 | yes | no | asset-hub.html, integrations.html, pm-scheduler.html | asset-hub.html, integrations.html, pm-scheduler.html | — |
| `worker_profiles` | 8 | yes | no | resume.html, voice-journal.html | voice-journal.html | — |
| `parts_staging_recommendations` | 14 | no | yes | alert-hub.html, asset-hub.html | asset-hub.html | parts-staging-recommender |
| `voice_journal_entries` | 10 | yes | no | assistant.html, voice-journal.html | — | _shared/journal-recall.ts |
| `projects` | 19 | no | yes | inventory.html, logbook.html, pm-scheduler.html, project-manager.html | project-manager.html | — |
| `network_benchmarks` | 9 | no | no | hive.html | — | benchmark-compute |
| `ai_cost_log` | 17 | yes | no | ai-quality.html, founder-console.html, llm-observability.html | — | _shared/cost-log.ts |
| `marketplace_inquiries` | 11 | yes | no | marketplace-seller.html, marketplace.html | marketplace-seller.html, marketplace.html | — |
| `hive_benchmarks` | 9 | no | no | hive.html, ph-intelligence.html | — | benchmark-compute |
| `ph_intelligence_reports` | 9 | no | no | ph-intelligence.html | — | intelligence-report |
| `api_keys` | 9 | yes | no | integrations.html | integrations.html | intelligence-api |
| `cmms_audit_log` | 12 | no | no | integrations.html | integrations.html | cmms-sync |
| `shift_plans` | 13 | yes | yes | shift-brain.html | shift-brain.html | shift-planner-orchestrator |
| `rcm_fmea_modes` | 20 | yes | yes | asset-hub.html | asset-hub.html | fmea-populator |
| `amc_briefings` | 14 | yes | yes | alert-hub.html | alert-hub.html | amc-orchestrator |
| `canonical_period_summaries` | 12 | yes | no | — | — | hierarchical-summarizer |
| `schedule_items` | 14 | yes | no | assistant.html, dayplanner.html | dayplanner.html | — |
| `skill_profiles` | 6 | yes | no | resume.html, skillmatrix.html | skillmatrix.html | — |
| `project_roles` | 8 | no | yes | project-manager.html | project-manager.html | — |
| `project_change_orders` | 16 | no | yes | project-manager.html | project-manager.html | — |
| `parts_staged_reservations` | 11 | no | yes | asset-hub.html, inventory.html | asset-hub.html | — |
| `gateway_audit_log` | 13 | yes | no | plant-connections.html | — | platform-gateway |
| `agentic_rag_traces` | 16 | yes | no | agentic-rag-observability.html | — | agentic-rag-loop |
| `wh_traces` | 9 | yes | no | — | — | _shared/error-tracker.ts |
| `ai_reply_feedback` | 12 | yes | no | ai-quality.html, assistant.html | assistant.html | — |
| `analytics_snapshots` | 7 | yes | no | analytics.html | — | analytics-orchestrator |
| `ai_reports` | 7 | yes | no | — | — | scheduled-agents |
| `community_posts` | 14 | yes | no | community.html | community.html | — |
| `community_reactions` | 6 | yes | no | community.html | community.html | — |
| `community_replies` | 8 | yes | no | community.html | community.html | — |
| `community_xp` | 5 | yes | no | community.html, hive.html | — | — |
| `engineering_calcs` | 13 | yes | no | project-manager.html | — | — |
| `equipment_reading_templates` | 8 | no | no | asset-hub.html, logbook.html | — | — |
| `hives` | 10 | yes | no | hive.html | hive.html | — |
| `inventory_transactions` | 11 | yes | no | inventory.html | inventory.html | — |
| `marketplace_orders` | 17 | yes | no | marketplace-admin.html | marketplace-admin.html | — |
| `marketplace_platform_admins` | 3 | yes | no | marketplace-admin.html, marketplace.html | — | — |
| `marketplace_reviews` | 7 | yes | no | marketplace-seller-profile.html, marketplace.html | — | — |
| `marketplace_saved_searches` | 12 | yes | no | marketplace.html | marketplace.html | — |
| `marketplace_watchlist` | 4 | yes | no | marketplace.html | marketplace.html | — |
| `report_contacts` | 6 | yes | no | report-sender.html | report-sender.html | — |
| `project_items` | 19 | no | yes | project-manager.html | project-manager.html | — |
| `project_progress_logs` | 12 | no | yes | project-manager.html | project-manager.html | — |
| `failure_signature_alerts` | 15 | no | no | — | — | failure-signature-scan |
| `asset_risk_scores` | 12 | no | no | — | — | batch-risk-scoring |
| `rcm_strategies` | 16 | yes | yes | asset-hub.html | asset-hub.html | — |
| `weibull_fits` | 13 | yes | yes | — | — | weibull-fitter |
| `pf_intervals` | 11 | yes | no | — | — | pf-calculator |
| `agent_memory` | 21 | yes | no | — | — | _shared/memory.ts |
| `ai_quality_log` | 11 | yes | no | — | — | ai-eval-runner |
| `pdf_jobs` | 14 | yes | no | — | — | pdf-ingest |
| `hive_route_calls` | 5 | yes | no | — | — | _shared/rate-limit.ts |
| `sensor_readings` | 13 | yes | yes | — | — | sensor-readings-ingest |
| `anomaly_signals` | 22 | yes | yes | alert-hub.html | alert-hub.html | — |
| `knowledge_graph_facts` | 18 | yes | yes | — | — | semantic-fact-extractor |
| `platform_feedback` | 21 | yes | yes | founder-console.html | founder-console.html | — |
| `agent_episodic_memory` | 14 | yes | no | — | — | _shared/episodic-memory.ts |
| `unified_events` | 12 | yes | no | — | — | data-fabric-normalizer |
| `ai_cache` | 8 | yes | no | — | — | _shared/cache.ts |
| `ai_user_rate_limits` | 6 | yes | no | — | — | _shared/rate-limit.ts |
| `agent_followups` | 13 | yes | no | — | — | _shared/followups.ts |
| `resume_documents` | 9 | yes | no | resume.html | resume.html | — |
| `resume_versions` | 6 | yes | no | resume.html | resume.html | — |
| `embedding_cache` | 6 | no | no | — | — | _shared/embedding-chain.ts |
| `alert_dismissals` | 7 | yes | no | alert-hub.html | alert-hub.html | — |
| `skill_badges` | 8 | yes | no | resume.html | — | — |
| `skill_exam_attempts` | 9 | yes | no | skillmatrix.html | — | — |
| `achievement_xp_log` | 7 | yes | no | achievements.html | — | — |
| `canonical_sources` | 10 | yes | no | — | — | — |
| `hive_route_quotas` | 7 | yes | no | — | — | — |
| `sensor_topic_map` | 10 | yes | no | plant-connections.html | — | — |
| `canonical_agent_contracts` | 6 | yes | no | — | — | — |
| `analytics_events` | 10 | yes | no | founder-console.html | — | — |
| `hive_retention_config` | 6 | yes | no | plant-connections.html | — | — |
| `sso_configs` | 13 | yes | no | plant-connections.html | — | — |
| `assets` | 15 | yes | no | — | — | — |
| `bom_knowledge` | 9 | no | no | — | — | — |
| `calc_knowledge` | 9 | no | no | — | — | — |
| `early_access_emails` | 4 | yes | no | — | — | — |
| `hive_analytics_cache` | 4 | no | no | — | — | — |
| `parts_records` | 10 | yes | no | — | — | — |
| `pm_knowledge` | 13 | yes | no | — | — | — |
| `skill_knowledge` | 10 | yes | no | — | — | — |
| `project_knowledge` | 11 | no | no | — | — | — |
| `achievement_definitions` | 7 | yes | no | — | — | — |
| `worker_achievements` | 7 | yes | yes | — | — | — |
| `asset_edges` | 8 | yes | yes | — | — | — |
| `asset_embeddings` | 5 | yes | no | — | — | — |
| `hive_quotas` | 11 | yes | no | — | — | — |
| `canonical_standards` | 9 | yes | no | — | — | — |
| `canonical_formulas` | 10 | yes | no | — | — | — |
| `canonical_capture_contracts` | 11 | yes | no | — | — | — |
| `canonical_capabilities` | 10 | yes | no | — | — | — |
| `hive_readiness` | 14 | yes | yes | — | — | — |
| `hive_readiness_audit` | 9 | yes | no | — | — | — |
| `hive_adoption_score` | 16 | yes | yes | — | — | — |
| `auth_session_events` | 9 | yes | no | — | — | — |
| `mfa_enrollments` | 11 | yes | no | — | — | — |
| `drone_inspections` | 16 | yes | yes | — | — | — |
| `industry_standards` | 13 | yes | no | — | — | — |
| `consulting_engagements` | 15 | yes | no | — | — | — |
| `dialog_state` | 12 | yes | no | — | — | — |
| `anomaly_alerts` | 16 | yes | no | — | — | — |
| `kb_documents` | 11 | yes | no | — | — | — |
| `kb_chunks` | 7 | yes | no | — | — | — |
| `offline_snapshot_cache` | 7 | no | no | — | — | — |
| `voice_response_queue` | 8 | no | no | — | — | — |
| `fallback_model_faq` | 5 | yes | no | — | — | — |
| `tts_cache` | 9 | no | no | — | — | — |
| `tts_quality_log` | 7 | no | no | — | — | — |
| `conversation_analytics` | 12 | no | no | — | — | — |
| `cross_hive_alerts` | 7 | no | no | — | — | — |
| `best_practices` | 7 | no | no | — | — | — |
| `avatar_state` | 6 | no | no | — | — | — |
| `avatar_animations` | 5 | no | no | — | — | — |
| `multilingual_terms` | 7 | no | no | — | — | — |
| `language_preferences` | 4 | no | no | — | — | — |
| `terminology_gaps` | 6 | no | no | — | — | — |
| `industry_standards_chunks` | 8 | yes | no | — | — | — |
| `platform_knowledge_graph_facts` | 17 | yes | no | — | — | — |
| `platform_feedback_votes` | 3 | yes | no | — | — | — |
| `canonical_lineage_edges` | 7 | yes | no | — | — | — |
| `IF` | 7 | no | no | — | — | — |
| `ai_audit_log` | 7 | yes | no | — | — | — |
| `ai_knowledge_gap` | 7 | yes | no | — | — | — |
| `ai_quality_escalation` | 8 | yes | no | — | — | — |
| `asset_watchlist` | 4 | yes | no | — | — | — |
| `companion_handoff` | 8 | yes | no | — | — | — |
| `mentor_relay_queue` | 10 | yes | no | — | — | — |
| `shared_voice_notes` | 7 | yes | no | — | — | — |
| `wh_feature_flags` | 5 | yes | no | — | — | — |
| `wh_voice_presence` | 3 | yes | no | — | — | — |
| `wh_health_status` | 5 | yes | no | — | — | — |
| `persona_knowledge` | 13 | no | no | — | — | — |
| `login_attempts` | 6 | yes | no | — | — | — |
| `ai_global_budget` | 11 | no | no | — | — | — |
| `skill_exam_keys` | 3 | yes | no | — | — | — |
| `ops_artifact_metrics` | 6 | yes | no | — | — | — |

## RPCs / Functions

| Function | Args | Definer | Called by surfaces | Called by edge fns |
|---|---|---|---|---|
| `acknowledge_alert` | p_alert_id bigint | yes | — | — |
| `ai_cache_bump` | p_key TEXT | yes | — | _shared/cache.ts |
| `ai_cache_sweep_expired` |  | yes | — | — |
| `amc_expire_stale` |  | yes | — | — |
| `anomaly_signals_forward_only_status` |  | no | — | — |
| `auth_worker_names` |  | yes | — | — |
| `award_achievement_xp` | p_worker    text,   p_ach_id    text,   p_xp        int,   p | yes | — | — |
| `bind_acknowledged_by_from_hive` |  | no | — | — |
| `bind_alert_dismissal_actor` |  | no | — | — |
| `bind_analytics_events_submitter` |  | yes | — | — |
| `bind_anomaly_signal_attribution` |  | no | — | — |
| `bind_approved_by_from_hive` |  | no | — | — |
| `bind_asset_nodes_submitter` |  | yes | — | — |
| `bind_assigned_by_from_hive` |  | no | — | — |
| `bind_community_post_submitter` |  | yes | — | — |
| `bind_community_reaction_submitter` |  | yes | — | — |
| `bind_community_reply_submitter` |  | yes | — | — |
| `bind_engineering_calc_submitter` |  | yes | — | — |
| `bind_inventory_item_submitter` |  | yes | — | — |
| `bind_logbook_submitter` |  | yes | — | — |
| `bind_parts_record_submitter` |  | yes | — | — |
| `bind_platform_feedback_submitter` |  | yes | — | — |
| `bind_pm_asset_submitter` |  | yes | — | — |
| `bind_pm_completion_submitter` |  | yes | — | — |
| `bind_projects_submitter` |  | yes | — | — |
| `bind_reviewed_by_from_hive` |  | no | — | — |
| `bind_skill_profile_worker_name` |  | no | — | — |
| `bind_voice_journal_submitter` |  | yes | — | — |
| `bind_worker_name_from_hive` |  | no | — | — |
| `cap_alert_dismissals_text` |  | no | — | — |
| `cap_asset_nodes_text` |  | no | — | — |
| `cap_community_reactions_text` |  | no | — | — |
| `cap_early_access_emails_text` |  | no | — | — |
| `cap_engineering_calcs_text` |  | no | — | — |
| `cap_hive_members_text` |  | yes | — | — |
| `cap_hives_text` |  | no | — | — |
| `cap_inventory_items_text` |  | no | — | — |
| `cap_inventory_transactions_text` |  | no | — | — |
| `cap_logbook_text_fields` |  | no | — | — |
| `cap_marketplace_inquiries_text` |  | no | — | — |
| `cap_marketplace_listings_text` |  | no | — | — |
| `cap_marketplace_saved_searches_text` |  | no | — | — |
| `cap_marketplace_sellers_text` |  | no | — | — |
| `cap_parts_staged_reservations_text` |  | no | — | — |
| `cap_pdf_job_size` |  | no | — | — |
| `cap_pm_assets_text` |  | no | — | — |
| `cap_pm_completions_text` |  | no | — | — |
| `cap_pm_scope_items_text` |  | no | — | — |
| `cap_project_change_orders_text` |  | no | — | — |
| `cap_project_items_text` |  | no | — | — |
| `cap_project_links_text` |  | no | — | — |
| `cap_project_progress_logs_text` |  | no | — | — |
| `cap_project_roles_text` |  | no | — | — |
| `cap_projects_text` |  | no | — | — |
| `cap_rcm_fmea_modes_text` |  | no | — | — |
| `cap_rcm_strategies_text` |  | no | — | — |
| `cap_report_contacts_text` |  | no | — | — |
| `cap_resume_documents_text` |  | no | — | — |
| `cap_resume_versions_text` |  | no | — | — |
| `cap_schedule_items_text` |  | no | — | — |
| `cap_skill_profiles_text` |  | no | — | — |
| `cap_worker_profiles_text` |  | no | — | — |
| `check_daily_row_cap` |  | yes | — | — |
| `check_hive_quota_ai_reports` |  | yes | — | — |
| `check_hive_quota_community` |  | yes | — | — |
| `check_hive_quota_inv_tx` |  | yes | — | — |
| `check_hive_quota_logbook` |  | yes | — | — |
| `check_hive_quota_pm_completions` |  | yes | — | — |
| `check_inline_image_size` |  | yes | — | — |
| `check_listing_rate` |  | no | — | — |
| `check_logbook_rate_limit` |  | yes | — | — |
| `check_login_lockout` | p_identifier text, p_ip text default '' | yes | — | login |
| `check_platform_feedback_rate_limit` |  | yes | — | — |
| `check_username_available` | p_username text | yes | — | — |
| `clear_login_attempts` | p_identifier text, p_ip text default '' | yes | — | login |
| `community_post_rate_limit` |  | no | — | — |
| `community_reply_rate_limit` |  | no | — | — |
| `compute_adoption_risk` | p_hive_id uuid | yes | hive.html | — |
| `compute_anomaly_signals` | p_hive_id uuid | yes | alert-hub.html | — |
| `compute_hive_readiness` | p_hive_id uuid | yes | hive.html | — |
| `consume_ai_global_budget` | p_rpm int,   p_rpd int,   p_is_background boolean | yes | — | _shared/rate-limit.ts |
| `deactivate_my_account` |  | yes | — | — |
| `delete_worker_data` | p_worker_name text | yes | — | — |
| `enforce_ai_reply_feedback_daily_limit` |  | yes | — | — |
| `export_hive_data` | p_hive_id uuid | yes | — | export-hive-data |
| `fetch_active_alerts` | p_hive_id uuid | yes | — | — |
| `fetch_dialog_state` | p_session_id text | yes | — | — |
| `fetch_session_memory` | p_session_id text,   p_limit int default 10 | yes | — | — |
| `find_hive_by_code` | p_code text | yes | hive.html | — |
| `generate_change_order_number` | p_project_id uuid | no | project-manager.html | — |
| `generate_project_code` | p_hive_id uuid, p_type text, p_year integer | no | project-manager.html | — |
| `get_adoption_risk_current` | p_hive_id uuid | yes | hive.html | — |
| `get_community_reputation` | p_worker_name text,   p_hive_id     uuid | yes | community.html, marketplace.html | — |
| `get_community_reputation_by_auth` | p_auth_uid uuid | yes | — | — |
| `get_downtime_pareto` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator |
| `get_failure_frequency` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator, scheduled-agents |
| `get_hive_board_dashboard` | p_hive_id uuid | yes | hive.html | — |
| `get_hive_dashboard` | p_hive_id   uuid,   p_day_start timestamptz DEFAULT date_tru | yes | — | — |
| `get_hive_readiness_current` | p_hive_id uuid | yes | hive.html | — |
| `get_hive_trade_peers` | p_hive_id uuid | yes | community.html | — |
| `get_marketplace_parts_for_my_assets` | p_hive_id uuid | yes | marketplace.html | — |
| `get_marketplace_price_comps` | p_category    text,   p_condition   text DEFAULT NULL,   p_p | yes | marketplace.html | — |
| `get_marketplace_trust_badges` | p_seller_names text[] | yes | marketplace.html | — |
| `get_mtbf_by_machine` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator, batch-risk-scoring, scheduled-agents |
| `get_mttr_by_machine` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator, scheduled-agents |
| `get_oee_by_machine` | p_hive_id     uuid,   p_period_days int DEFAULT 90 | yes | — | analytics-orchestrator |
| `get_pm_compliance_smrp` | p_hive_id     uuid,   p_period_days int DEFAULT 90 | yes | pm-scheduler.html | analytics-orchestrator |
| `get_repeat_failures` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator, scheduled-agents |
| `get_saved_search_matches` |  | yes | marketplace.html | — |
| `get_seller_community_reputation` | p_worker_name text, p_hive_id uuid | yes | marketplace-seller-profile.html | — |
| `grade_skill_exam` | p_discipline text, p_level int, p_answers int[] | yes | skillmatrix.html | — |
| `guard_community_announcement` |  | yes | — | — |
| `guard_marketplace_seller_trust_columns` |  | yes | — | — |
| `handle_community_post_xp` |  | yes | — | — |
| `handle_community_reaction_xp` |  | yes | — | — |
| `handle_community_reply_xp` |  | yes | — | — |
| `hard_delete_expired_soft_deletes` |  | yes | — | — |
| `hive_has_other_members` | p_hive_id uuid | yes | — | — |
| `increment_community_xp` | "p_worker_name" "text", "p_hive_id" "uuid", "p_amount" integ | yes | — | — |
| `increment_listing_view` | "p_listing_id" "uuid" | yes | marketplace.html | — |
| `inventory_deduct` | p_item_id text,   p_qty     numeric,   p_note    text DEFAUL | yes | inventory.html, logbook.html | — |
| `inventory_restock` | p_item_id text, p_qty numeric, p_note text DEFAULT NULL, p_t | yes | inventory.html | — |
| `inventory_sync_balance_from_ledger` |  | yes | — | — |
| `is_marketplace_admin` |  | yes | — | — |
| `is_platform_admin` |  | yes | — | — |
| `join_hive_by_code` | p_code text, p_worker_name text | yes | hive.html | — |
| `match_persona_knowledge` | query_embedding vector(384),   scopes          text[],   mat | no | — | _shared/persona-knowledge.ts |
| `match_procedural_memories` | p_query_embedding  vector,   p_hive_id          uuid,   p_wo | yes | — | _shared/episodic-memory.ts, _shared/skill-library.ts |
| `photo_attach_stats` |  | yes | — | — |
| `platform_feedback_stamp_resolved` |  | yes | — | — |
| `populate_asset_node_bridges` |  | yes | — | — |
| `prune_embedding_cache` | p_max_age_days int DEFAULT 45 | yes | — | — |
| `record_ai_chain_depth` | p_depth int | yes | — | ai-gateway |
| `record_login_failure` | p_identifier text, p_ip text default '',                     | yes | — | login |
| `refresh_v_kpi_truth` |  | yes | — | — |
| `rerank_kb_chunks` | p_chunk_ids bigint[],   p_query text | yes | — | — |
| `resolve_inventory_linked_asset_node_ids` |  | yes | — | — |
| `resolve_logbook_asset_node_id` |  | yes | — | — |
| `resume_documents_touch_updated_at` |  | no | — | — |
| `search_all_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | — |
| `search_bom_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | — |
| `search_calc_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | — |
| `search_fault_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | semantic-search |
| `search_pm_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | semantic-search |
| `search_skill_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | yes | — | semantic-search |
| `search_voice_journal_entries` | query_embedding vector(384),   match_auth_uid  uuid,   match | no | — | _shared/journal-recall.ts, voice-semantic-rag |
| `seed_hive_quota_defaults` |  | yes | — | — |
| `semantic_search_industry_standards` | p_query_embedding       vector,   p_similarity_threshold  re | no | — | — |
| `semantic_search_kb` | p_hive_id uuid,   p_query_embedding vector,   p_similarity_t | yes | — | — |
| `semantic_search_kg_facts` | p_hive_id               uuid,   p_query_embedding       vect | yes | — | — |
| `semantic_search_platform_kg_facts` | p_query_embedding       vector,   p_similarity_threshold  re | no | — | — |
| `sensor_readings_set_external_key` |  | no | — | — |
| `set_community_best_answer` | p_reply_id uuid, p_accepted boolean | yes | community.html | — |
| `set_projects_updated_at` |  | no | — | — |
| `shift_plans_forward_only_status` |  | no | — | — |
| `slo_error_budget` | p_route             text default null,   p_window_min        | no | — | — |
| `store_memory_turn` | p_hive_id uuid,   p_session_id text,   p_turn_num int,   p_u | yes | — | — |
| `suppress_alert` | p_alert_id bigint, p_hours int default 24 | yes | — | — |
| `sync_auth_uid_on_signup` |  | yes | — | — |
| `tg_asset_nodes_touch_updated` |  | no | — | — |
| `tg_rcm_touch_updated` |  | no | — | — |
| `tg_shift_plans_touch_updated` |  | no | — | — |
| `toggle_feedback_upvote` | p_feedback_id uuid,   p_voter_token text | yes | — | — |
| `touch_logbook_updated_at` |  | yes | — | — |
| `touch_updated_at` |  | yes | — | — |
| `trg_community_achievement_xp` |  | yes | — | — |
| `trg_engcalc_achievement_xp` |  | yes | — | — |
| `trg_hivemember_achievement_xp` |  | yes | — | — |
| `trg_iron_worker_check` |  | yes | — | — |
| `trg_logbook_achievement_xp` |  | yes | — | — |
| `trg_pm_achievement_xp` |  | yes | — | — |
| `trg_shiftplan_achievement_xp` |  | yes | — | — |
| `trg_skill_badge_achievement_xp` |  | yes | — | — |
| `unified_event_source_rank` | p_source text | no | — | — |
| `update_dialog_state` | p_hive_id uuid,   p_session_id text,   p_turn_num int,   p_i | no | — | — |
| `update_seller_rating` |  | yes | — | — |
| `update_seller_tier` |  | yes | — | — |
| `user_can_access_hive` | p_hive_id uuid | yes | — | — |
| `user_hive_ids` |  | yes | — | — |
| `user_hive_worker_names` |  | yes | — | — |
| `user_supervisor_hive_ids` |  | yes | — | — |
| `wh_bind_audit_actor` |  | yes | — | — |
| `wh_guard_supervisor_approval` |  | yes | — | — |

## HTML Surfaces

| Page | Primary tables (read) | Tables written | RPCs called | Edge fns invoked |
|---|---|---|---|---|
| `achievements.html` | achievement_xp_log, v_worker_achievements_truth, v_worker_truth | — | — | — |
| `agentic-rag-observability.html` | agentic_rag_traces | — | — | — |
| `ai-quality.html` | ai_cost_log, ai_reply_feedback | — | — | — |
| `alert-hub.html` | alert_dismissals, amc_briefings, anomaly_signals, automation_log ... | alert_dismissals, amc_briefings, anomaly_signals ... | compute_anomaly_signals | analytics-orchestrator |
| `analytics-report.html` | v_hives_truth | — | — | — |
| `analytics.html` | analytics_snapshots | — | — | batch-risk-scoring |
| `architecture.html` | — | — | — | — |
| `asset-hub.html` | asset_nodes, equipment_reading_templates, hive_audit_log, hive_members ... | asset_nodes, hive_audit_log, parts_staged_reservations ... | — | ai-gateway, asset-brain-query, fmea-populator |
| `assistant.html` | ai_reply_feedback, schedule_items, v_inventory_items_truth, v_logbook_truth ... | ai_reply_feedback | — | ai-gateway |
| `audit-log.html` | hive_audit_log | — | — | — |
| `community.html` | community_posts, community_reactions, community_replies, community_xp ... | community_posts, community_reactions, community_replies ... | get_community_reputation, get_hive_trade_peers, set_community_best_answer | — |
| `dayplanner.html` | logbook, schedule_items, v_logbook_truth, v_pm_scope_items_truth | logbook, schedule_items | — | — |
| `design-system.html` | — | — | — | — |
| `engineering-design.html` | — | — | — | — |
| `findings.html` | — | — | — | — |
| `founder-console.html` | ai_cost_log, analytics_events, hive_audit_log, marketplace_disputes ... | marketplace_disputes, marketplace_listings, marketplace_sellers ... | — | — |
| `hive.html` | asset_nodes, community_xp, hive_audit_log, hive_benchmarks ... | hive_audit_log, hive_members, hives ... | compute_adoption_risk, compute_hive_readiness, find_hive_by_code | ai-gateway, ai-orchestrator, benchmark-compute |
| `index.html` | — | — | — | — |
| `integrations.html` | api_keys, asset_nodes, cmms_audit_log, external_sync ... | api_keys, asset_nodes, cmms_audit_log ... | — | cmms-sync |
| `inventory.html` | asset_nodes, hive_audit_log, hive_members, inventory_items ... | asset_nodes, hive_audit_log, inventory_items ... | inventory_deduct, inventory_restock | — |
| `lineage.html` | — | — | — | — |
| `llm-observability.html` | ai_cost_log | — | — | — |
| `logbook.html` | asset_nodes, equipment_reading_templates, fault_knowledge, hive_audit_log ... | asset_nodes, hive_audit_log, logbook ... | inventory_deduct | cmms-push-completion, equipment-label-ocr, visual-defect-capture |
| `marketplace-admin.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_orders ... | hive_audit_log, marketplace_disputes, marketplace_listings ... | — | — |
| `marketplace-seller-profile.html` | marketplace_reviews, v_marketplace_inquiries_truth, v_marketplace_listings_truth, v_marketplace_sellers_truth | — | get_seller_community_reputation | — |
| `marketplace-seller.html` | hive_audit_log, marketplace_inquiries, marketplace_listings, marketplace_sellers ... | hive_audit_log, marketplace_inquiries, marketplace_listings ... | — | — |
| `marketplace.html` | hive_audit_log, marketplace_inquiries, marketplace_listings, marketplace_platform_admins ... | hive_audit_log, marketplace_inquiries, marketplace_listings ... | get_community_reputation, get_marketplace_parts_for_my_assets, get_marketplace_price_comps | marketplace-listing-assist |
| `offline-fallback.html` | — | — | — | — |
| `ph-intelligence.html` | hive_benchmarks, ph_intelligence_reports | — | — | intelligence-report |
| `plant-connections.html` | gateway_audit_log, hive_retention_config, integration_configs, sensor_topic_map ... | — | — | — |
| `platform-actions.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_sellers ... | hive_audit_log, marketplace_disputes, marketplace_listings ... | — | — |
| `pm-scheduler.html` | asset_nodes, hive_audit_log, hive_members, logbook ... | hive_audit_log, logbook, pm_assets ... | get_pm_compliance_smrp | — |
| `project-manager.html` | asset_nodes, engineering_calcs, hive_members, pm_completions ... | project_change_orders, project_items, project_links ... | generate_change_order_number, generate_project_code | embed-entry, project-orchestrator, project-progress |
| `project-report.html` | project_links, v_project_items_truth, v_project_progress_truth, v_project_truth | — | — | project-orchestrator |
| `promo-poster.html` | — | — | — | — |
| `props.html` | — | — | — | — |
| `public-feed.html` | v_community_posts_truth | — | — | — |
| `report-sender.html` | report_contacts, v_ai_reports_truth | report_contacts | — | — |
| `resume.html` | resume_documents, resume_versions, skill_badges, skill_profiles ... | resume_documents, resume_versions | — | — |
| `shift-brain.html` | shift_plans, v_worker_truth | shift_plans | — | analytics-orchestrator, shift-planner-orchestrator |
| `skillmatrix.html` | skill_exam_attempts, skill_profiles, v_skill_badges_truth | skill_profiles | grade_skill_exam | — |
| `snapshot.html` | — | — | — | — |
| `status.html` | — | — | — | — |
| `symbol-gallery.html` | — | — | — | — |
| `token_stats.html` | — | — | — | — |
| `tslib.es6.html` | — | — | — | — |
| `tslib.html` | — | — | — | — |
| `uiMode.html` | — | — | — | — |
| `validator-catalog.html` | — | — | — | — |
| `voice-journal.html` | v_worker_truth, voice_journal_entries, worker_profiles | worker_profiles | — | ai-gateway |
| `workhive_index.html` | — | — | — | — |

## Duplicate signals -- review

### Surface-pair overlap (Jaccard >= 0.5, >= 2 shared tables)

| Surface A | Surface B | Shared tables | Jaccard |
|---|---|---|---:|
| `marketplace-admin.html` | `platform-actions.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_sellers, v_marketplace_listings_truth, v_marketplace_sellers_truth | 0.75 |
| `marketplace-seller.html` | `platform-actions.html` | hive_audit_log, marketplace_listings, marketplace_sellers, v_marketplace_listings_truth, v_marketplace_sellers_truth | 0.62 |
| `founder-console.html` | `platform-actions.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_sellers, v_marketplace_listings_truth, v_marketplace_sellers_truth | 0.55 |
| `logbook.html` | `pm-scheduler.html` | asset_nodes, hive_audit_log, hive_members, logbook, pm_assets, pm_completions, project_links, projects, v_pm_scope_items_truth | 0.5 |
| `marketplace-admin.html` | `marketplace-seller.html` | hive_audit_log, marketplace_listings, marketplace_sellers, v_marketplace_listings_truth, v_marketplace_sellers_truth | 0.5 |

### Near-duplicate column names within a table

- `marketplace_sellers`: `kyb_verified` vs `kyb_verified_at`
- `marketplace_sellers`: `cert_verified` vs `cert_verified_at`
- `unified_events`: `source` vs `source_id`

### Dead tables (no readers, no writers)

- `assets` (defined but unreferenced)
- `bom_knowledge` (defined but unreferenced)
- `calc_knowledge` (defined but unreferenced)
- `early_access_emails` (defined but unreferenced)
- `hive_analytics_cache` (defined but unreferenced)
- `parts_records` (defined but unreferenced)
- `pm_knowledge` (defined but unreferenced)
- `skill_knowledge` (defined but unreferenced)
- `project_knowledge` (defined but unreferenced)
- `achievement_definitions` (defined but unreferenced)
- `worker_achievements` (defined but unreferenced)
- `asset_edges` (defined but unreferenced)
- `asset_embeddings` (defined but unreferenced)
- `hive_quotas` (defined but unreferenced)
- `canonical_standards` (defined but unreferenced)
- `canonical_formulas` (defined but unreferenced)
- `canonical_capture_contracts` (defined but unreferenced)
- `canonical_capabilities` (defined but unreferenced)
- `hive_readiness` (defined but unreferenced)
- `hive_readiness_audit` (defined but unreferenced)
- `hive_adoption_score` (defined but unreferenced)
- `auth_session_events` (defined but unreferenced)
- `mfa_enrollments` (defined but unreferenced)
- `drone_inspections` (defined but unreferenced)
- `industry_standards` (defined but unreferenced)
- `consulting_engagements` (defined but unreferenced)
- `dialog_state` (defined but unreferenced)
- `anomaly_alerts` (defined but unreferenced)
- `kb_documents` (defined but unreferenced)
- `kb_chunks` (defined but unreferenced)
- `offline_snapshot_cache` (defined but unreferenced)
- `voice_response_queue` (defined but unreferenced)
- `fallback_model_faq` (defined but unreferenced)
- `tts_cache` (defined but unreferenced)
- `tts_quality_log` (defined but unreferenced)
- `conversation_analytics` (defined but unreferenced)
- `cross_hive_alerts` (defined but unreferenced)
- `best_practices` (defined but unreferenced)
- `avatar_state` (defined but unreferenced)
- `avatar_animations` (defined but unreferenced)
- `multilingual_terms` (defined but unreferenced)
- `language_preferences` (defined but unreferenced)
- `terminology_gaps` (defined but unreferenced)
- `industry_standards_chunks` (defined but unreferenced)
- `platform_knowledge_graph_facts` (defined but unreferenced)
- `platform_feedback_votes` (defined but unreferenced)
- `canonical_lineage_edges` (defined but unreferenced)
- `IF` (defined but unreferenced)
- `ai_audit_log` (defined but unreferenced)
- `ai_knowledge_gap` (defined but unreferenced)
- `ai_quality_escalation` (defined but unreferenced)
- `asset_watchlist` (defined but unreferenced)
- `companion_handoff` (defined but unreferenced)
- `mentor_relay_queue` (defined but unreferenced)
- `shared_voice_notes` (defined but unreferenced)
- `wh_feature_flags` (defined but unreferenced)
- `wh_voice_presence` (defined but unreferenced)
- `wh_health_status` (defined but unreferenced)
- `persona_knowledge` (defined but unreferenced)
- `login_attempts` (defined but unreferenced)
- `ai_global_budget` (defined but unreferenced)
- `skill_exam_keys` (defined but unreferenced)
- `ops_artifact_metrics` (defined but unreferenced)
