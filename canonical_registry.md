# Canonical Source Registry

Authoritative inventory of every table, RPC, view, edge fn, and HTML surface on the platform.
Re-built on every Mega Gate run by `tools/mine_canonical_registry.py`.

## Summary

- Tables:        **124**
- Views:         **33**
- RPCs:          **71**
- HTML surfaces: **36**
- Edge fns:      **50**
- Phantom tables (referenced in code, not in migrations): **0**
- Duplicate signals: **56**

## Tables (sorted by usage)

| Table | Cols | RLS | Realtime | Read by surfaces | Written by surfaces | Edge-fn writers |
|---|---:|---|---|---|---|---|
| `hive_audit_log` | 9 | no | yes | alert-hub.html, asset-hub.html, audit-log.html, community.html ... | alert-hub.html, asset-hub.html, community.html ... | export-hive-data |
| `automation_log` | 6 | yes | no | alert-hub.html | — | batch-risk-scoring, benchmark-compute, cmms-push-completion ... |
| `logbook` | 30 | yes | no | dayplanner.html, hive.html, integrations.html, logbook.html ... | dayplanner.html, hive.html, integrations.html ... | cmms-sync |
| `asset_nodes` | 25 | yes | yes | asset-hub.html, hive.html, integrations.html, inventory.html ... | asset-hub.html, integrations.html, inventory.html ... | — |
| `pm_completions` | 9 | yes | no | asset-hub.html, hive.html, index.html, logbook.html ... | logbook.html, pm-scheduler.html | — |
| `pm_assets` | 11 | yes | no | asset-hub.html, index.html, integrations.html, logbook.html ... | asset-hub.html, integrations.html, logbook.html ... | — |
| `hive_members` | 7 | yes | no | asset-hub.html, community.html, hive.html, inventory.html ... | hive.html | — |
| `marketplace_orders` | 17 | no | no | founder-console.html, marketplace-admin.html, marketplace-seller.html, marketplace.html | marketplace-admin.html, marketplace.html | marketplace-checkout, marketplace-release, marketplace-webhook |
| `hives` | 8 | yes | no | analytics-report.html, hive.html | hive.html | — |
| `external_sync` | 10 | no | no | asset-hub.html, integrations.html, logbook.html, plant-connections.html | integrations.html | cmms-push-completion, cmms-sync, cmms-webhook-receiver |
| `marketplace_listings` | 20 | no | no | asset-hub.html, marketplace-admin.html, marketplace-seller-profile.html, marketplace-seller.html ... | marketplace-admin.html, marketplace-seller.html, marketplace.html | — |
| `fault_knowledge` | 14 | yes | no | integrations.html, logbook.html | integrations.html | cmms-sync, visual-defect-capture |
| `worker_profiles` | 7 | yes | no | index.html, voice-journal.html | index.html, voice-journal.html | platform-gateway |
| `project_links` | 8 | no | no | logbook.html, pm-scheduler.html, project-manager.html, project-report.html | logbook.html, pm-scheduler.html, project-manager.html | — |
| `marketplace_sellers` | 19 | no | no | marketplace-admin.html, marketplace-seller.html | marketplace-admin.html, marketplace-seller.html | marketplace-connect-onboard, marketplace-connect-status |
| `projects` | 19 | no | yes | logbook.html, pm-scheduler.html, project-manager.html, project-report.html | project-manager.html | — |
| `ai_rate_limits` | 3 | yes | no | — | — | asset-brain-query, fmea-populator, visual-defect-capture ... |
| `inventory_transactions` | 11 | yes | no | inventory.html, logbook.html | inventory.html, logbook.html | — |
| `marketplace_disputes` | 14 | no | no | founder-console.html, marketplace-admin.html, marketplace-seller.html, marketplace.html | marketplace-admin.html, marketplace-seller.html, marketplace.html | — |
| `integration_configs` | 13 | no | no | integrations.html, plant-connections.html | integrations.html | cmms-sync |
| `inventory_items` | 21 | yes | no | integrations.html, inventory.html, logbook.html | integrations.html, inventory.html, logbook.html | — |
| `pm_scope_items` | 8 | yes | no | asset-hub.html, integrations.html, pm-scheduler.html | asset-hub.html, integrations.html, pm-scheduler.html | — |
| `project_progress_logs` | 12 | no | yes | project-manager.html, project-report.html | project-manager.html | — |
| `parts_staging_recommendations` | 14 | no | yes | alert-hub.html, asset-hub.html | asset-hub.html | parts-staging-recommender |
| `marketplace_inquiries` | 11 | no | no | marketplace-seller-profile.html, marketplace-seller.html, marketplace.html | marketplace-seller.html, marketplace.html | — |
| `project_items` | 19 | no | yes | project-manager.html, project-report.html | project-manager.html | — |
| `failure_signature_alerts` | 15 | no | no | alert-hub.html, hive.html, index.html | — | failure-signature-scan |
| `network_benchmarks` | 9 | no | no | hive.html | — | benchmark-compute |
| `amc_briefings` | 14 | yes | yes | alert-hub.html, index.html | alert-hub.html | amc-orchestrator |
| `ai_reports` | 7 | yes | no | hive.html, report-sender.html | — | scheduled-agents |
| `engineering_calcs` | 13 | yes | no | engineering-design.html, project-manager.html | engineering-design.html | — |
| `skill_badges` | 8 | yes | no | assistant.html, hive.html, skillmatrix.html | skillmatrix.html | — |
| `hive_benchmarks` | 9 | no | no | hive.html, ph-intelligence.html | — | benchmark-compute |
| `ph_intelligence_reports` | 9 | no | no | ph-intelligence.html | — | intelligence-report |
| `api_keys` | 9 | no | no | integrations.html | integrations.html | intelligence-api |
| `cmms_audit_log` | 12 | no | no | integrations.html | integrations.html | cmms-sync |
| `shift_plans` | 13 | yes | yes | shift-brain.html | shift-brain.html | shift-planner-orchestrator |
| `rcm_fmea_modes` | 20 | yes | yes | asset-hub.html | asset-hub.html | fmea-populator |
| `sensor_readings` | 13 | yes | yes | asset-hub.html, index.html | — | sensor-readings-ingest |
| `community_posts` | 13 | yes | no | community.html, public-feed.html | community.html | — |
| `marketplace_platform_admins` | 3 | no | no | marketplace-admin.html, marketplace.html, platform-health.html | — | — |
| `marketplace_reviews` | 7 | no | no | marketplace-seller-profile.html, marketplace.html | marketplace.html | — |
| `schedule_items` | 12 | yes | no | assistant.html, dayplanner.html | dayplanner.html | — |
| `project_roles` | 8 | no | yes | project-manager.html | project-manager.html | — |
| `project_change_orders` | 16 | no | yes | project-manager.html | project-manager.html | — |
| `asset_edges` | 8 | yes | yes | asset-hub.html | asset-hub.html | — |
| `parts_staged_reservations` | 11 | no | yes | asset-hub.html, inventory.html | asset-hub.html | — |
| `gateway_audit_log` | 13 | yes | no | plant-connections.html | — | platform-gateway |
| `voice_journal_entries` | 10 | yes | no | assistant.html, voice-journal.html | — | — |
| `community_reactions` | 6 | yes | no | community.html | community.html | — |
| `community_replies` | 6 | yes | no | community.html | community.html | — |
| `community_xp` | 4 | yes | no | community.html, hive.html | — | — |
| `early_access_emails` | 4 | yes | no | index.html | index.html | — |
| `equipment_reading_templates` | 8 | no | no | asset-hub.html, logbook.html | — | — |
| `marketplace_saved_searches` | 12 | no | no | marketplace.html | marketplace.html | — |
| `marketplace_watchlist` | 4 | no | no | marketplace.html | marketplace.html | — |
| `report_contacts` | 6 | yes | no | report-sender.html | report-sender.html | — |
| `skill_exam_attempts` | 9 | yes | no | skillmatrix.html | skillmatrix.html | — |
| `skill_profiles` | 6 | yes | no | skillmatrix.html | skillmatrix.html | — |
| `asset_risk_scores` | 12 | no | no | — | — | batch-risk-scoring |
| `rcm_strategies` | 16 | yes | yes | asset-hub.html | asset-hub.html | — |
| `weibull_fits` | 13 | yes | yes | — | — | weibull-fitter |
| `pf_intervals` | 11 | yes | no | — | — | pf-calculator |
| `ai_cost_log` | 13 | yes | no | ai-quality.html, founder-console.html | — | — |
| `ai_quality_log` | 11 | yes | no | — | — | ai-eval-runner |
| `pdf_jobs` | 14 | yes | no | — | — | pdf-ingest |
| `anomaly_signals` | 22 | yes | yes | alert-hub.html | alert-hub.html | — |
| `platform_feedback` | 20 | yes | yes | founder-console.html | founder-console.html | — |
| `worker_achievements` | 7 | yes | yes | achievements.html | — | — |
| `achievement_xp_log` | 7 | yes | no | achievements.html | — | — |
| `sensor_topic_map` | 10 | yes | no | plant-connections.html | — | — |
| `analytics_events` | 10 | yes | no | founder-console.html | — | — |
| `hive_retention_config` | 6 | yes | no | plant-connections.html | — | — |
| `sso_configs` | 13 | yes | no | plant-connections.html | — | — |
| `assets` | 15 | yes | no | — | — | — |
| `bom_knowledge` | 9 | no | no | — | — | — |
| `calc_knowledge` | 9 | no | no | — | — | — |
| `hive_analytics_cache` | 4 | no | no | — | — | — |
| `parts_records` | 10 | yes | no | — | — | — |
| `pm_knowledge` | 13 | yes | no | — | — | — |
| `skill_knowledge` | 10 | yes | no | — | — | — |
| `project_knowledge` | 11 | no | no | — | — | — |
| `achievement_definitions` | 7 | yes | no | — | — | — |
| `asset_embeddings` | 5 | yes | no | — | — | — |
| `canonical_sources` | 10 | yes | no | — | — | — |
| `agent_memory` | 21 | yes | no | — | — | — |
| `hive_quotas` | 10 | yes | no | — | — | — |
| `hive_route_quotas` | 7 | yes | no | — | — | — |
| `hive_route_calls` | 5 | yes | no | — | — | — |
| `canonical_standards` | 9 | yes | no | — | — | — |
| `canonical_formulas` | 10 | yes | no | — | — | — |
| `canonical_agent_contracts` | 6 | yes | no | — | — | — |
| `canonical_capture_contracts` | 11 | yes | no | — | — | — |
| `canonical_capabilities` | 10 | yes | no | — | — | — |
| `hive_readiness` | 14 | yes | yes | — | — | — |
| `hive_readiness_audit` | 9 | yes | no | — | — | — |
| `hive_adoption_score` | 16 | yes | yes | — | — | — |
| `auth_session_events` | 9 | yes | no | — | — | — |
| `mfa_enrollments` | 11 | yes | no | — | — | — |
| `knowledge_graph_facts` | 18 | yes | yes | — | — | — |
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

## RPCs / Functions

| Function | Args | Definer | Called by surfaces | Called by edge fns |
|---|---|---|---|---|
| `acknowledge_alert` | p_alert_id bigint | yes | — | — |
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
| `platform_feedback_stamp_resolved` |  | yes | — | — |
| `populate_asset_node_bridges` |  | yes | — | — |
| `refresh_v_kpi_truth` |  | yes | — | — |
| `rerank_kb_chunks` | p_chunk_ids bigint[],   p_query text | yes | — | — |
| `resolve_inventory_linked_asset_node_ids` |  | yes | — | — |
| `resolve_logbook_asset_node_id` |  | yes | — | — |
| `search_all_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | — |
| `search_bom_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | — |
| `search_calc_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | — |
| `search_fault_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | semantic-search |
| `search_pm_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | no | — | semantic-search |
| `search_skill_knowledge` | "query_embedding" "public"."vector", "match_hive_id" "uuid", | yes | — | semantic-search |
| `search_voice_journal_entries` | query_embedding vector(384 | no | — | voice-semantic-rag |
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
| `update_dialog_state` | p_hive_id uuid,   p_session_id text,   p_turn_num int,   p_i | no | — | — |
| `update_seller_rating` |  | no | — | — |
| `update_seller_tier` |  | no | — | — |

## HTML Surfaces

| Page | Primary tables (read) | Tables written | RPCs called | Edge fns invoked |
|---|---|---|---|---|
| `achievements.html` | achievement_xp_log, v_worker_truth, worker_achievements | — | — | — |
| `ai-quality.html` | ai_cost_log | — | — | — |
| `alert-hub.html` | amc_briefings, anomaly_signals, automation_log, failure_signature_alerts ... | amc_briefings, anomaly_signals, hive_audit_log | compute_anomaly_signals | — |
| `analytics-report.html` | hives | — | — | — |
| `analytics.html` | — | — | — | — |
| `architecture.html` | — | — | — | — |
| `asset-hub.html` | asset_edges, asset_nodes, equipment_reading_templates, external_sync ... | asset_edges, asset_nodes, hive_audit_log ... | — | asset-brain-query, fmea-populator, pf-calculator |
| `assistant.html` | schedule_items, skill_badges, v_inventory_items_truth, v_logbook_truth ... | — | — | — |
| `audit-log.html` | hive_audit_log | — | — | — |
| `community.html` | community_posts, community_reactions, community_replies, community_xp ... | community_posts, community_reactions, community_replies ... | — | — |
| `dayplanner.html` | logbook, schedule_items, v_logbook_truth | logbook, schedule_items | — | — |
| `engineering-design.html` | engineering_calcs | engineering_calcs | — | engineering-bom-sow, engineering-calc-agent |
| `founder-console.html` | ai_cost_log, analytics_events, hive_audit_log, marketplace_disputes ... | platform_feedback | — | — |
| `hive.html` | ai_reports, asset_nodes, community_xp, failure_signature_alerts ... | hive_audit_log, hive_members, hives ... | compute_adoption_risk, compute_hive_readiness, get_adoption_risk_current | ai-orchestrator, benchmark-compute |
| `index.html` | amc_briefings, early_access_emails, failure_signature_alerts, pm_assets ... | early_access_emails, worker_profiles | — | — |
| `integrations.html` | api_keys, asset_nodes, cmms_audit_log, external_sync ... | api_keys, asset_nodes, cmms_audit_log ... | — | cmms-sync |
| `inventory.html` | asset_nodes, hive_audit_log, hive_members, inventory_items ... | asset_nodes, hive_audit_log, inventory_items ... | — | — |
| `logbook.html` | asset_nodes, equipment_reading_templates, external_sync, fault_knowledge ... | asset_nodes, hive_audit_log, inventory_items ... | — | cmms-push-completion, equipment-label-ocr, visual-defect-capture |
| `marketplace-admin.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_orders ... | hive_audit_log, marketplace_disputes, marketplace_listings ... | — | — |
| `marketplace-seller-profile.html` | marketplace_inquiries, marketplace_listings, marketplace_reviews, v_marketplace_sellers_truth | — | — | — |
| `marketplace-seller.html` | hive_audit_log, marketplace_disputes, marketplace_inquiries, marketplace_listings ... | hive_audit_log, marketplace_disputes, marketplace_inquiries ... | — | — |
| `marketplace.html` | hive_audit_log, marketplace_disputes, marketplace_inquiries, marketplace_listings ... | hive_audit_log, marketplace_disputes, marketplace_inquiries ... | increment_listing_view | — |
| `parts-tracker.html` | — | — | — | — |
| `ph-intelligence.html` | hive_benchmarks, ph_intelligence_reports | — | — | intelligence-report |
| `plant-connections.html` | external_sync, gateway_audit_log, hive_retention_config, integration_configs ... | — | — | — |
| `platform-health.html` | marketplace_platform_admins | — | — | — |
| `pm-scheduler.html` | asset_nodes, hive_audit_log, hive_members, logbook ... | hive_audit_log, logbook, pm_assets ... | — | — |
| `predictive.html` | v_risk_truth | — | — | analytics-orchestrator |
| `project-manager.html` | asset_nodes, engineering_calcs, hive_members, marketplace_listings ... | project_change_orders, project_items, project_links ... | generate_change_order_number, generate_project_code | embed-entry, project-orchestrator, project-progress |
| `project-report.html` | project_items, project_links, project_progress_logs, projects | — | — | project-orchestrator |
| `public-feed.html` | community_posts | — | — | — |
| `report-sender.html` | ai_reports, report_contacts | report_contacts | — | — |
| `shift-brain.html` | shift_plans, v_worker_truth | shift_plans | — | shift-planner-orchestrator |
| `skillmatrix.html` | skill_badges, skill_exam_attempts, skill_profiles | skill_badges, skill_exam_attempts, skill_profiles | — | — |
| `symbol-gallery.html` | — | — | — | — |
| `voice-journal.html` | voice_journal_entries, worker_profiles | worker_profiles | — | ai-gateway |

## Duplicate signals -- review

### Surface-pair overlap (Jaccard >= 0.5, >= 2 shared tables)

| Surface A | Surface B | Shared tables | Jaccard |
|---|---|---|---:|
| `marketplace-admin.html` | `marketplace-seller.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_orders, marketplace_sellers, v_marketplace_sellers_truth | 0.75 |
| `marketplace-admin.html` | `marketplace.html` | hive_audit_log, marketplace_disputes, marketplace_listings, marketplace_orders, marketplace_platform_admins, v_marketplace_sellers_truth | 0.55 |
| `marketplace-seller.html` | `marketplace.html` | hive_audit_log, marketplace_disputes, marketplace_inquiries, marketplace_listings, marketplace_orders, v_marketplace_sellers_truth | 0.55 |
| `logbook.html` | `pm-scheduler.html` | asset_nodes, hive_audit_log, hive_members, logbook, pm_assets, pm_completions, project_links, projects | 0.5 |

### Near-duplicate column names within a table

- `marketplace_sellers`: `kyb_verified` vs `kyb_verified_at`
- `marketplace_sellers`: `cert_verified` vs `cert_verified_at`

### Dead tables (no readers, no writers)

- `assets` (defined but unreferenced)
- `bom_knowledge` (defined but unreferenced)
- `calc_knowledge` (defined but unreferenced)
- `hive_analytics_cache` (defined but unreferenced)
- `parts_records` (defined but unreferenced)
- `pm_knowledge` (defined but unreferenced)
- `skill_knowledge` (defined but unreferenced)
- `project_knowledge` (defined but unreferenced)
- `achievement_definitions` (defined but unreferenced)
- `asset_embeddings` (defined but unreferenced)
- `canonical_sources` (defined but unreferenced)
- `agent_memory` (defined but unreferenced)
- `hive_quotas` (defined but unreferenced)
- `hive_route_quotas` (defined but unreferenced)
- `hive_route_calls` (defined but unreferenced)
- `canonical_standards` (defined but unreferenced)
- `canonical_formulas` (defined but unreferenced)
- `canonical_agent_contracts` (defined but unreferenced)
- `canonical_capture_contracts` (defined but unreferenced)
- `canonical_capabilities` (defined but unreferenced)
- `hive_readiness` (defined but unreferenced)
- `hive_readiness_audit` (defined but unreferenced)
- `hive_adoption_score` (defined but unreferenced)
- `auth_session_events` (defined but unreferenced)
- `mfa_enrollments` (defined but unreferenced)
- `knowledge_graph_facts` (defined but unreferenced)
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
