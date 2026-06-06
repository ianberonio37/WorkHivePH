# Canonical Source Registry

Authoritative inventory of every table, RPC, view, edge fn, and HTML surface on the platform.
Re-built on every Mega Gate run by `tools/mine_canonical_registry.py`.

## Summary

- Tables:        **145**
- Views:         **49**
- RPCs:          **77**
- HTML surfaces: **46**
- Edge fns:      **86**
- Phantom tables (referenced in code, not in migrations): **0**
- Duplicate signals: **64**

## Tables (sorted by usage)

| Table | Cols | RLS | Realtime | Read by surfaces | Written by surfaces | Edge-fn writers |
|---|---:|---|---|---|---|---|
| `hive_audit_log` | 9 | no | yes | alert-hub.html, asset-hub.html, audit-log.html, community.html ... | alert-hub.html, asset-hub.html, community.html ... | export-hive-data |
| `automation_log` | 6 | yes | no | alert-hub.html | — | batch-risk-scoring, benchmark-compute, cmms-push-completion ... |
| `ai_rate_limits` | 3 | yes | no | — | — | _shared/rate-limit.ts, agentic-rag-loop, asset-brain-query ... |
| `logbook` | 30 | yes | no | dayplanner.html, hive.html, integrations.html, logbook.html ... | dayplanner.html, hive.html, integrations.html ... | cmms-sync, cmms-webhook-receiver |
| `asset_nodes` | 26 | yes | yes | asset-hub.html, hive.html, integrations.html, inventory.html ... | asset-hub.html, integrations.html, inventory.html ... | — |
| `marketplace_orders` | 17 | no | no | marketplace-admin.html, marketplace.html | marketplace-admin.html, marketplace.html | marketplace-checkout, marketplace-release, marketplace-webhook |
| `fault_knowledge` | 14 | yes | no | integrations.html, logbook.html | integrations.html | cmms-sync, visual-defect-capture |
| `project_links` | 8 | no | no | logbook.html, pm-scheduler.html, project-manager.html, project-report.html | logbook.html, pm-scheduler.html, project-manager.html | — |
| `marketplace_sellers` | 19 | no | no | marketplace-admin.html, marketplace-seller.html | marketplace-admin.html, marketplace-seller.html | marketplace-connect-onboard, marketplace-connect-status |
| `pm_assets` | 11 | yes | no | asset-hub.html, integrations.html, logbook.html, pm-scheduler.html | asset-hub.html, integrations.html, logbook.html ... | — |
| `external_sync` | 10 | no | no | integrations.html | integrations.html | cmms-push-completion, cmms-sync, cmms-webhook-receiver |
| `hive_members` | 7 | yes | no | asset-hub.html, hive.html, inventory.html, logbook.html ... | hive.html | — |
| `marketplace_disputes` | 14 | no | no | founder-console.html, marketplace-admin.html, marketplace-seller.html, marketplace.html | marketplace-admin.html, marketplace-seller.html, marketplace.html | — |
| `pm_completions` | 9 | yes | no | asset-hub.html, hive.html, logbook.html, pm-scheduler.html ... | logbook.html, pm-scheduler.html | — |
| `integration_configs` | 16 | no | no | integrations.html, plant-connections.html | integrations.html | cmms-sync |
| `inventory_items` | 21 | yes | no | integrations.html, inventory.html, logbook.html | integrations.html, inventory.html, logbook.html | — |
| `marketplace_listings` | 20 | no | no | marketplace-admin.html, marketplace-seller.html, marketplace.html | marketplace-admin.html, marketplace-seller.html, marketplace.html | — |
| `pm_scope_items` | 8 | yes | no | asset-hub.html, integrations.html, pm-scheduler.html | asset-hub.html, integrations.html, pm-scheduler.html | — |
| `parts_staging_recommendations` | 14 | no | yes | alert-hub.html, asset-hub.html | asset-hub.html | parts-staging-recommender |
| `voice_journal_entries` | 10 | yes | no | assistant.html, voice-journal.html | — | _shared/journal-recall.ts |
| `network_benchmarks` | 9 | no | no | hive.html | — | benchmark-compute |
| `ai_cost_log` | 17 | yes | no | ai-quality.html, founder-console.html, llm-observability.html | — | _shared/cost-log.ts |
| `engineering_calcs` | 13 | yes | no | engineering-design.html, project-manager.html | engineering-design.html | — |
| `inventory_transactions` | 11 | yes | no | inventory.html, logbook.html | inventory.html, logbook.html | — |
| `marketplace_inquiries` | 11 | no | no | marketplace-seller.html, marketplace.html | marketplace-seller.html, marketplace.html | — |
| `projects` | 19 | no | yes | logbook.html, pm-scheduler.html, project-manager.html | project-manager.html | — |
| `hive_benchmarks` | 9 | no | no | hive.html, ph-intelligence.html | — | benchmark-compute |
| `ph_intelligence_reports` | 9 | no | no | ph-intelligence.html | — | intelligence-report |
| `api_keys` | 9 | no | no | integrations.html | integrations.html | intelligence-api |
| `cmms_audit_log` | 12 | no | no | integrations.html | integrations.html | cmms-sync |
| `shift_plans` | 13 | yes | yes | shift-brain.html | shift-brain.html | shift-planner-orchestrator |
| `rcm_fmea_modes` | 20 | yes | yes | asset-hub.html | asset-hub.html | fmea-populator |
| `amc_briefings` | 14 | yes | yes | alert-hub.html | alert-hub.html | amc-orchestrator |
| `canonical_period_summaries` | 12 | yes | no | — | — | hierarchical-summarizer |
| `marketplace_platform_admins` | 3 | no | no | marketplace-admin.html, marketplace.html, platform-health.html | — | — |
| `marketplace_reviews` | 7 | no | no | marketplace-seller-profile.html, marketplace.html | marketplace.html | — |
| `schedule_items` | 12 | yes | no | assistant.html, dayplanner.html | dayplanner.html | — |
| `skill_badges` | 8 | yes | no | resume.html, skillmatrix.html | skillmatrix.html | — |
| `skill_profiles` | 6 | yes | no | resume.html, skillmatrix.html | skillmatrix.html | — |
| `project_roles` | 8 | no | yes | project-manager.html | project-manager.html | — |
| `project_change_orders` | 16 | no | yes | project-manager.html | project-manager.html | — |
| `failure_signature_alerts` | 15 | no | no | alert-hub.html | — | failure-signature-scan |
| `asset_edges` | 8 | yes | yes | asset-hub.html | asset-hub.html | — |
| `parts_staged_reservations` | 11 | no | yes | asset-hub.html, inventory.html | asset-hub.html | — |
| `gateway_audit_log` | 13 | yes | no | plant-connections.html | — | platform-gateway |
| `agentic_rag_traces` | 16 | yes | no | agentic-rag-observability.html | — | agentic-rag-loop |
| `ai_reports` | 7 | yes | no | — | — | scheduled-agents |
| `community_posts` | 13 | yes | no | community.html | community.html | — |
| `community_reactions` | 6 | yes | no | community.html | community.html | — |
| `community_replies` | 6 | yes | no | community.html | community.html | — |
| `community_xp` | 4 | yes | no | community.html, hive.html | — | — |
| `equipment_reading_templates` | 8 | no | no | asset-hub.html, logbook.html | — | — |
| `hives` | 10 | yes | no | hive.html | hive.html | — |
| `marketplace_saved_searches` | 12 | no | no | marketplace.html | marketplace.html | — |
| `marketplace_watchlist` | 4 | no | no | marketplace.html | marketplace.html | — |
| `report_contacts` | 6 | yes | no | report-sender.html | report-sender.html | — |
| `skill_exam_attempts` | 9 | yes | no | skillmatrix.html | skillmatrix.html | — |
| `worker_profiles` | 7 | yes | no | voice-journal.html | voice-journal.html | — |
| `project_items` | 19 | no | yes | project-manager.html | project-manager.html | — |
| `project_progress_logs` | 12 | no | yes | project-manager.html | project-manager.html | — |
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
| `platform_feedback` | 20 | yes | yes | founder-console.html | founder-console.html | — |
| `agent_episodic_memory` | 12 | yes | no | — | — | _shared/episodic-memory.ts |
| `unified_events` | 12 | yes | no | — | — | data-fabric-normalizer |
| `ai_cache` | 8 | yes | no | — | — | _shared/cache.ts |
| `ai_user_rate_limits` | 4 | yes | no | — | — | _shared/rate-limit.ts |
| `wh_traces` | 9 | yes | no | — | — | _shared/error-tracker.ts |
| `agent_followups` | 13 | yes | no | — | — | _shared/followups.ts |
| `resume_documents` | 9 | yes | no | resume.html | resume.html | — |
| `resume_versions` | 6 | yes | no | resume.html | resume.html | — |
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
| `asset_embeddings` | 5 | yes | no | — | — | — |
| `hive_quotas` | 10 | yes | no | — | — | — |
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

## RPCs / Functions

| Function | Args | Definer | Called by surfaces | Called by edge fns |
|---|---|---|---|---|
| `acknowledge_alert` | p_alert_id bigint | yes | — | — |
| `ai_cache_bump` | p_key TEXT | yes | — | _shared/cache.ts |
| `ai_cache_sweep_expired` |  | yes | — | — |
| `amc_expire_stale` |  | yes | — | — |
| `award_achievement_xp` | p_worker    text,   p_ach_id    text,   p_xp        int,   p | yes | — | — |
| `check_hive_quota_ai_reports` |  | yes | — | — |
| `check_hive_quota_community` |  | yes | — | — |
| `check_hive_quota_inv_tx` |  | yes | — | — |
| `check_hive_quota_logbook` |  | yes | — | — |
| `check_hive_quota_pm_completions` |  | yes | — | — |
| `check_listing_rate` |  | no | — | — |
| `check_platform_feedback_rate_limit` |  | yes | — | — |
| `community_post_rate_limit` |  | no | — | — |
| `community_reply_rate_limit` |  | no | — | — |
| `compute_adoption_risk` | p_hive_id uuid | yes | hive.html | — |
| `compute_anomaly_signals` | p_hive_id uuid | yes | alert-hub.html | — |
| `compute_hive_readiness` | p_hive_id uuid | yes | hive.html | — |
| `delete_worker_data` | p_worker_name text | yes | — | — |
| `export_hive_data` | p_hive_id uuid | yes | — | export-hive-data |
| `fetch_active_alerts` | p_hive_id uuid | yes | — | — |
| `fetch_dialog_state` | p_session_id text | yes | — | — |
| `fetch_session_memory` | p_session_id text,   p_limit int default 10 | yes | — | — |
| `generate_change_order_number` | p_project_id uuid | no | project-manager.html | — |
| `generate_project_code` | p_hive_id uuid, p_type text, p_year integer | no | project-manager.html | — |
| `get_adoption_risk_current` | p_hive_id uuid | yes | hive.html | — |
| `get_downtime_pareto` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator |
| `get_failure_frequency` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator |
| `get_hive_dashboard` | p_hive_id   uuid,   p_day_start timestamptz DEFAULT date_tru | yes | — | — |
| `get_hive_readiness_current` | p_hive_id uuid | yes | hive.html | — |
| `get_mtbf_by_machine` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator, batch-risk-scoring |
| `get_mttr_by_machine` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator |
| `get_oee_by_machine` | p_hive_id     uuid,   p_period_days int DEFAULT 90 | yes | — | analytics-orchestrator |
| `get_repeat_failures` | "p_hive_id" "uuid" DEFAULT NULL::"uuid", "p_worker" "text" D | no | — | analytics-orchestrator |
| `handle_community_post_xp` |  | yes | — | — |
| `handle_community_reaction_xp` |  | yes | — | — |
| `handle_community_reply_xp` |  | yes | — | — |
| `hard_delete_expired_soft_deletes` |  | yes | — | — |
| `increment_community_xp` | "p_worker_name" "text", "p_hive_id" "uuid", "p_amount" integ | yes | — | — |
| `increment_listing_view` | "p_listing_id" "uuid" | yes | marketplace.html | — |
| `match_procedural_memories` | p_query_embedding  vector,   p_hive_id          uuid,   p_wo | yes | — | _shared/skill-library.ts |
| `platform_feedback_stamp_resolved` |  | yes | — | — |
| `populate_asset_node_bridges` |  | yes | — | — |
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
| `semantic_search_industry_standards` | p_query_embedding       vector,   p_similarity_threshold  re | no | — | — |
| `semantic_search_kb` | p_hive_id uuid,   p_query_embedding vector,   p_similarity_t | yes | — | — |
| `semantic_search_kg_facts` | p_hive_id               uuid,   p_query_embedding       vect | no | — | — |
| `semantic_search_platform_kg_facts` | p_query_embedding       vector,   p_similarity_threshold  re | no | — | — |
| `sensor_readings_set_external_key` |  | no | — | — |
| `set_projects_updated_at` |  | no | — | — |
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
| `trg_logbook_achievement_xp` |  | yes | — | — |
| `trg_pm_achievement_xp` |  | yes | — | — |
| `trg_skill_badge_achievement_xp` |  | yes | — | — |
| `unified_event_source_rank` | p_source text | no | — | — |
| `update_dialog_state` | p_hive_id uuid,   p_session_id text,   p_turn_num int,   p_i | no | — | — |
| `update_seller_rating` |  | no | — | — |
| `update_seller_tier` |  | no | — | — |

## HTML Surfaces

| Page | Primary tables (read) | Tables written | RPCs called | Edge fns invoked |
|---|---|---|---|---|
| `achievements.html` | achievement_xp_log, v_worker_achievements_truth, v_worker_truth | — | — | — |
| `agentic-rag-observability.html` | agentic_rag_traces | — | — | — |
| `ai-quality.html` | ai_cost_log | — | — | — |
| `alert-hub.html` | amc_briefings, anomaly_signals, automation_log, failure_signature_alerts ... | amc_briefings, anomaly_signals, hive_audit_log | compute_anomaly_signals | — |
| `analytics-report.html` | v_hives_truth | — | — | — |
| `analytics.html` | — | — | — | — |
| `architecture.html` | — | — | — | — |
| `asset-hub.html` | asset_edges, asset_nodes, equipment_reading_templates, hive_audit_log ... | asset_edges, asset_nodes, hive_audit_log ... | — | asset-brain-query, fmea-populator, pf-calculator |
| `assistant.html` | schedule_items, v_inventory_items_truth, v_logbook_truth, v_pm_compliance_truth ... | — | — | — |
| `audit-log.html` | hive_audit_log | — | — | — |
| `community.html` | community_posts, community_reactions, community_replies, community_xp ... | community_posts, community_reactions, community_replies ... | — | — |
| `dayplanner.html` | logbook, schedule_items, v_logbook_truth | logbook, schedule_items | — | — |
| `engineering-design.html` | engineering_calcs | engineering_calcs | — | engineering-bom-sow, engineering-calc-agent |
| `findings.html` | — | — | — | — |
| `founder-console.html` | ai_cost_log, analytics_events, hive_audit_log, marketplace_disputes ... | platform_feedback | — | — |
| `hive.html` | asset_nodes, community_xp, hive_audit_log, hive_benchmarks ... | hive_audit_log, hive_members, hives ... | compute_adoption_risk, compute_hive_readiness, get_adoption_risk_current | ai-orchestrator, benchmark-compute |
| `index.html` | — | — | — | — |
| `integrations.html` | api_keys, asset_nodes, cmms_audit_log, external_sync ... | api_keys, asset_nodes, cmms_audit_log ... | — | cmms-sync |
| `inventory.html` | asset_nodes, hive_audit_log, hive_members, inventory_items ... | asset_nodes, hive_audit_log, inventory_items ... | — | — |
| `lineage.html` | — | — | — | — |
| `llm-observability.html` | ai_cost_log | — | — | — |
| `logbook.html` | asset_nodes, equipment_reading_templates, fault_knowledge, hive_audit_log ... | asset_nodes, hive_audit_log, inventory_items ... | — | cmms-push-completion, equipment-label-ocr, visual-defect-capture |
| `marketplace-admin.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_orders ... | hive_audit_log, marketplace_disputes, marketplace_listings ... | — | — |
| `marketplace-seller-profile.html` | marketplace_reviews, v_marketplace_inquiries_truth, v_marketplace_listings_truth, v_marketplace_sellers_truth | — | — | — |
| `marketplace-seller.html` | hive_audit_log, marketplace_disputes, marketplace_inquiries, marketplace_listings ... | hive_audit_log, marketplace_disputes, marketplace_inquiries ... | — | — |
| `marketplace.html` | hive_audit_log, marketplace_disputes, marketplace_inquiries, marketplace_listings ... | hive_audit_log, marketplace_disputes, marketplace_inquiries ... | increment_listing_view | — |
| `parts-tracker.html` | — | — | — | — |
| `ph-intelligence.html` | hive_benchmarks, ph_intelligence_reports | — | — | intelligence-report |
| `plant-connections.html` | gateway_audit_log, hive_retention_config, integration_configs, sensor_topic_map ... | — | — | — |
| `platform-health.html` | marketplace_platform_admins | — | — | — |
| `pm-scheduler.html` | asset_nodes, hive_audit_log, hive_members, logbook ... | hive_audit_log, logbook, pm_assets ... | — | — |
| `predictive.html` | v_risk_truth | — | — | analytics-orchestrator |
| `project-manager.html` | asset_nodes, engineering_calcs, hive_members, pm_completions ... | project_change_orders, project_items, project_links ... | generate_change_order_number, generate_project_code | embed-entry, project-orchestrator, project-progress |
| `project-report.html` | project_links, v_project_items_truth, v_project_progress_truth, v_project_truth | — | — | project-orchestrator |
| `public-feed.html` | v_community_posts_truth | — | — | — |
| `report-sender.html` | report_contacts, v_ai_reports_truth | report_contacts | — | — |
| `resume.html` | resume_documents, resume_versions, skill_badges, skill_profiles ... | resume_documents, resume_versions | — | — |
| `shift-brain.html` | shift_plans, v_worker_truth | shift_plans | — | shift-planner-orchestrator |
| `skillmatrix.html` | skill_badges, skill_exam_attempts, skill_profiles, v_skill_badges_truth | skill_badges, skill_exam_attempts, skill_profiles | — | — |
| `snapshot.html` | — | — | — | — |
| `symbol-gallery.html` | — | — | — | — |
| `token_stats.html` | — | — | — | — |
| `uiMode.html` | — | — | — | — |
| `validator-catalog.html` | — | — | — | — |
| `voice-journal.html` | v_worker_truth, voice_journal_entries, worker_profiles | worker_profiles | — | ai-gateway |
| `workhive_index.html` | — | — | — | — |

## Duplicate signals -- review

### Surface-pair overlap (Jaccard >= 0.5, >= 2 shared tables)

| Surface A | Surface B | Shared tables | Jaccard |
|---|---|---|---:|
| `marketplace-admin.html` | `marketplace-seller.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_sellers, v_marketplace_listings_truth, v_marketplace_sellers_truth | 0.55 |
| `marketplace-admin.html` | `marketplace.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_orders, marketplace_platform_admins, v_marketplace_listings_truth, v_marketplace_sellers_truth | 0.54 |
| `logbook.html` | `pm-scheduler.html` | asset_nodes, hive_audit_log, hive_members, logbook, pm_assets, pm_completions, project_links, projects, v_pm_scope_items_truth | 0.53 |
| `marketplace-seller.html` | `marketplace.html` | hive_audit_log, marketplace_disputes, marketplace_inquiries, marketplace_listings, v_marketplace_listings_truth, v_marketplace_orders_truth, v_marketplace_sellers_truth | 0.5 |

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
