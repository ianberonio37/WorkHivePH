---
name: fk-graph
type: fk
source: db:pg_constraint:foreign-keys
source_sha: 78dff460cffad90f
last_verified: 2026-07-13
supersedes: null
---
## fk · relational-integrity graph (145 foreign keys)

**UNINDEXED FK columns (22)** — slow joins + table-locking cascade deletes; add an index on the child column:
- `agent_episodic_memory`.`auth_uid` -> `auth.users`
- `agent_episodic_memory`.`source_trace_id` -> `agentic_rag_traces`
- `anomaly_signals`.`asset_node_id` -> `asset_nodes`
- `asset_edges`.`auth_uid` -> `auth.users`
- `auth_session_events`.`auth_uid` -> `auth.users`
- `auth_session_events`.`hive_id` -> `hives`
- `drone_inspections`.`asset_node_id` -> `asset_nodes`
- `knowledge_graph_facts`.`superseded_by` -> `knowledge_graph_facts`
- `logbook`.`pm_completion_id` -> `pm_completions`
- `marketplace_disputes`.`listing_id` -> `marketplace_listings`
- `marketplace_inquiries`.`hive_id` -> `hives`
- `marketplace_orders`.`hive_id` -> `hives`
- `marketplace_sellers`.`hive_id` -> `hives`
- `parts_staged_reservations`.`recommendation_id` -> `parts_staging_recommendations`
- `pf_intervals`.`fmea_mode_id` -> `rcm_fmea_modes`
- `platform_feedback`.`auth_uid` -> `auth.users`
- `platform_knowledge_graph_facts`.`superseded_by` -> `platform_knowledge_graph_facts`
- `pm_knowledge`.`asset_id` -> `asset_nodes`
- `rcm_strategies`.`written_to_pm_scope_item_id` -> `pm_scope_items`
- `resume_documents`.`hive_id` -> `hives`
- `voice_journal_entries`.`hive_id` -> `hives`
- `weibull_fits`.`fmea_mode_id` -> `rcm_fmea_modes`

**ON DELETE CASCADE FKs (95)** — deleting the parent row deletes children; confirm the blast radius is intended (esp. FKs into hives/hive_members):
- `agent_episodic_memory`.`hive_id` -> `hives`
- `agent_followups`.`hive_id` -> `hives`
- `agent_memory`.`hive_id` -> `hives`
- `agentic_rag_traces`.`hive_id` -> `hives`
- `ai_audit_log`.`hive_id` -> `hives`
- `ai_knowledge_gap`.`hive_id` -> `hives`
- `ai_quality_escalation`.`hive_id` -> `hives`
- `ai_rate_limits`.`hive_id` -> `hives`
- `ai_reports`.`hive_id` -> `hives`
- `amc_briefings`.`hive_id` -> `hives`
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
- `cmms_audit_log`.`hive_id` -> `hives`
- `community_posts`.`hive_id` -> `hives`
- `community_reactions`.`post_id` -> `community_posts`
- `community_replies`.`post_id` -> `community_posts`
- `community_xp`.`hive_id` -> `hives`
- `companion_handoff`.`hive_id` -> `hives`
- `consulting_engagements`.`hive_id` -> `hives`
- `drone_inspections`.`hive_id` -> `hives`
- `failure_signature_alerts`.`hive_id` -> `hives`
- `fault_knowledge`.`hive_id` -> `hives`
- `hive_adoption_score`.`hive_id` -> `hives`
- `hive_analytics_cache`.`hive_id` -> `hives`
- `hive_audit_log`.`hive_id` -> `hives`
- `hive_benchmarks`.`hive_id` -> `hives`
- `hive_members`.`hive_id` -> `hives`
- `hive_quotas`.`hive_id` -> `hives`
- `hive_readiness`.`hive_id` -> `hives`

Links: [[reference_pm_knowledge_fk_100pct_broken]] [[reference_logbook_asset_linkage_undercount]]
