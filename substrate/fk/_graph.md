---
name: fk-graph
type: fk
source: db:pg_constraint:foreign-keys
source_sha: 672a6bef3f7cb88f
last_verified: 2026-07-13
supersedes: null
---
## fk · relational-integrity graph (211 foreign keys)

**UNINDEXED FK columns (35)** — slow joins + table-locking cascade deletes; add an index on the child column:
- `agent_episodic_memory`.`source_trace_id` -> `agentic_rag_traces`
- `ai_cost_log`.`auth_uid` -> `auth.users`
- `anomaly_signals`.`asset_node_id` -> `asset_nodes`
- `asset_edges`.`auth_uid` -> `auth.users`
- `auth_session_events`.`auth_uid` -> `auth.users`
- `auth_session_events`.`hive_id` -> `hives`
- `community_post_xp_awards`.`hive_id` -> `hives`
- `community_reaction_xp_awards`.`hive_id` -> `hives`
- `community_reactions`.`hive_id` -> `hives`
- `conversation_analytics`.`hive_id` -> `hives`
- `credit_reservations`.`hive_id` -> `hives`
- `dialog_state`.`hive_id` -> `hives`
- `drone_inspections`.`asset_node_id` -> `asset_nodes`
- `embedding_outbox`.`hive_id` -> `hives`
- `gcash_inbound_receipts`.`matched_topup` -> `service_credit_topups`
- `knowledge_graph_facts`.`superseded_by` -> `knowledge_graph_facts`
- `logbook`.`pm_completion_id` -> `pm_completions`
- `marketplace_disputes`.`listing_id` -> `marketplace_listings`
- `marketplace_inquiries`.`hive_id` -> `hives`
- `marketplace_listings`.`sold_to_inquiry_id` -> `marketplace_inquiries`
- `marketplace_orders`.`hive_id` -> `hives`
- `offline_snapshot_cache`.`hive_id` -> `hives`
- `pf_intervals`.`fmea_mode_id` -> `rcm_fmea_modes`
- `platform_feedback`.`auth_uid` -> `auth.users`
- `platform_knowledge_graph_facts`.`superseded_by` -> `platform_knowledge_graph_facts`
- `pm_knowledge`.`asset_id` -> `asset_nodes`
- `project_change_orders`.`hive_id` -> `hives`
- `rcm_strategies`.`written_to_pm_scope_item_id` -> `pm_scope_items`
- `resume_documents`.`hive_id` -> `hives`
- `service_credit_topups`.`payer_auth_uid` -> `auth.users`
- `service_providers`.`auth_uid` -> `auth.users`
- `service_requests`.`catalog_item_id` -> `service_catalog`
- `service_voucher_redemptions`.`consumer_auth_uid` -> `auth.users`
- `service_voucher_redemptions`.`request_id` -> `service_requests`
- `weibull_fits`.`fmea_mode_id` -> `rcm_fmea_modes`

**ON DELETE CASCADE FKs (138)** — deleting the parent row deletes children; confirm the blast radius is intended (esp. FKs into hives/hive_members):
- `agent_episodic_memory`.`hive_id` -> `hives`
- `agent_followups`.`hive_id` -> `hives`
- `agent_memory`.`hive_id` -> `hives`
- `agentic_rag_traces`.`hive_id` -> `hives`
- `ai_audit_log`.`hive_id` -> `hives`
- `ai_knowledge_gap`.`hive_id` -> `hives`
- `ai_quality_escalation`.`hive_id` -> `hives`
- `ai_rate_limits`.`hive_id` -> `hives`
- `ai_reports`.`hive_id` -> `hives`
- `ai_user_rate_limits`.`hive_id` -> `hives`
- `alert_dismissals`.`hive_id` -> `hives`
- `amc_briefings`.`hive_id` -> `hives`
- `analytics_snapshots`.`hive_id` -> `hives`
- `anomaly_alerts`.`hive_id` -> `hives`
- `anomaly_signals`.`hive_id` -> `hives`
- `api_keys`.`hive_id` -> `hives`
- `asset_edges`.`from_node_id` -> `asset_nodes`
- `asset_edges`.`hive_id` -> `hives`
- `asset_edges`.`to_node_id` -> `asset_nodes`
- `asset_embeddings`.`hive_id` -> `hives`
- `asset_embeddings`.`node_id` -> `asset_nodes`
- `asset_nodes`.`hive_id` -> `hives`
- `asset_risk_scores`.`hive_id` -> `hives`
- `asset_watchlist`.`hive_id` -> `hives`
- `bom_knowledge`.`hive_id` -> `hives`
- `calc_knowledge`.`hive_id` -> `hives`
- `canonical_period_summaries`.`hive_id` -> `hives`
- `client_errors`.`hive_id` -> `hives`
- `cmms_audit_log`.`hive_id` -> `hives`
- `community_post_xp_awards`.`hive_id` -> `hives`
- `community_post_xp_awards`.`post_id` -> `community_posts`
- `community_posts`.`hive_id` -> `hives`
- `community_reaction_xp_awards`.`hive_id` -> `hives`
- `community_reaction_xp_awards`.`post_id` -> `community_posts`
- `community_reactions`.`hive_id` -> `hives`
- `community_reactions`.`post_id` -> `community_posts`
- `community_replies`.`hive_id` -> `hives`
- `community_replies`.`post_id` -> `community_posts`
- `community_xp`.`hive_id` -> `hives`
- `companion_handoff`.`hive_id` -> `hives`

Links: [[reference_pm_knowledge_fk_100pct_broken]] [[reference_logbook_asset_linkage_undercount]]
