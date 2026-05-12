-- Canonical Anchor Batch Registration (2026-05-12)
--
-- Closes 4 of the 5 near-term cleanups surfaced by the Canonical Anchor Gate
-- (validate_canonical_anchor.py, gate #69):
--
--   1. Register the 5 analytics RPCs as engine canonicals
--      (get_mtbf_by_machine / get_mttr_by_machine / get_failure_frequency /
--       get_downtime_pareto / get_repeat_failures)
--   2. Register the 4 missing engine views
--      (v_sensor_recent, v_worker_achievements, v_achievement_xp_log,
--       asset_brain_overview as deprecated wrapper)
--   3. Bulk-register the foundational fuel tables (logbook, pm_completions,
--      inventory_items, worker_profiles, asset_nodes, ...) in canonical_sources
--   4. Ship Tier A views (v_worker_truth + v_worker_assignment_truth) +
--      register them
--
-- Tier A note: v_worker_skill_truth already exists (20260512000001) and is
-- registered. This migration adds the other two Tier A canonicals so the
-- L3 anchor gate goes from 1-registered to 3-registered.
--
-- Skills consulted: architect (registry-first pattern), data-engineer
-- (canonical view = LEFT JOIN preserves zero-data rows), maintenance-expert
-- (ISO 14224 worker-skill contract), platform-guardian (forward-only
-- ratchet via baseline lockfile).

BEGIN;

-- -----------------------------------------------------------------------------
-- PART 1. Engine canonicals (5 RPCs + 4 views)
-- -----------------------------------------------------------------------------

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES

-- 5 analytics RPCs (Postgres functions over v_logbook_truth). Same window
-- contract used by Analytics, Asset Hub, Predictive, Shift Brain.
('mtbf_by_machine', 'rpc', 'get_mtbf_by_machine',
 'maintenance-expert', 'realtime',
 'Per-machine Mean Time Between Failures (ISO 14224:2016 sec 9.3). Args: p_hive_id, p_period_days. Returns machine, failure_count, mtbf_days.',
 jsonb_build_object('args', jsonb_build_array('p_hive_id', 'p_period_days'),
                    'returns', jsonb_build_array('machine', 'failure_count', 'mtbf_days'),
                    'standard', 'ISO 14224:2016 sec 9.3'),
 'Phase 1.1 of the engine consolidation. Replaced Python recompute on every Analytics refresh. Reads v_logbook_truth.'),

('mttr_by_machine', 'rpc', 'get_mttr_by_machine',
 'maintenance-expert', 'realtime',
 'Per-machine Mean Time To Repair (ISO 14224:2016 sec 9.4). Args: p_hive_id, p_period_days. Returns machine, repair_count, total_downtime_hours, mttr_hours.',
 jsonb_build_object('args', jsonb_build_array('p_hive_id', 'p_period_days'),
                    'returns', jsonb_build_array('machine', 'repair_count', 'total_downtime_hours', 'mttr_hours'),
                    'standard', 'ISO 14224:2016 sec 9.4'),
 'Phase 1.1. Joined to v_logbook_truth.maintenance_type = ''Breakdown / Corrective'' with closed_at not null.'),

('failure_frequency', 'rpc', 'get_failure_frequency',
 'maintenance-expert', 'realtime',
 'Per-machine failure count in window (SMRP metric 5.1). Args: p_hive_id, p_period_days. Returns machine, failure_count.',
 jsonb_build_object('args', jsonb_build_array('p_hive_id', 'p_period_days'),
                    'returns', jsonb_build_array('machine', 'failure_count'),
                    'standard', 'SMRP Best Practices 5.1'),
 'Phase 1.1. Underpins Failure Frequency tile + Pareto sort.'),

('downtime_pareto', 'rpc', 'get_downtime_pareto',
 'maintenance-expert', 'realtime',
 'Pareto distribution of downtime hours by asset (80/20 analysis). Args: p_hive_id, p_period_days. Returns machine, downtime_hours, pct_of_total, cumulative_pct.',
 jsonb_build_object('args', jsonb_build_array('p_hive_id', 'p_period_days'),
                    'returns', jsonb_build_array('machine', 'downtime_hours', 'pct_of_total', 'cumulative_pct'),
                    'standard', 'ISO 14224:2016 sec 9.5 + Pareto principle'),
 'Phase 1.1. Drives the Downtime Pareto tile in Analytics Phase 1.'),

('repeat_failures', 'rpc', 'get_repeat_failures',
 'maintenance-expert', 'realtime',
 'Assets with >=2 failures of the same root_cause in window. Args: p_hive_id, p_period_days. Returns machine, root_cause, occurrence_count, last_occurrence.',
 jsonb_build_object('args', jsonb_build_array('p_hive_id', 'p_period_days'),
                    'returns', jsonb_build_array('machine', 'root_cause', 'occurrence_count', 'last_occurrence'),
                    'standard', 'ISO 14224:2016 sec 9.6'),
 'Phase 1.1. Signal of ineffective repair, prioritised in Prescriptive Action Plan.'),

-- 4 engine views

('sensor_recent', 'view', 'v_sensor_recent',
 'data-engineer', 'realtime',
 'Most recent sensor reading per (hive_id, asset_node_id, metric) with anomaly flag. Replaces raw sensor_readings reads from asset-hub + analytics anomaly tiles.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'asset_node_id', 'metric'),
                    'hive_scoped', true,
                    'quality_flags', jsonb_build_array('OK', 'STALE', 'ANOMALY')),
 'Phase 2.2 sensor truth. Anomaly flag computed from baseline std-dev band; used by asset-hub sensor-anomaly-banner.'),

('worker_achievements', 'view', 'v_worker_achievements',
 'community', 'realtime',
 'Per (hive_id, worker_name): unlocked achievements (key, name, tier, xp_awarded, unlocked_at). Replaces hive.html + dayplanner ad-hoc joins of worker_achievements + achievement_definitions.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'worker_name', 'achievement_key'),
                    'hive_scoped', true,
                    'tier_values', jsonb_build_array('bronze', 'silver', 'gold')),
 'Phase A.2 precursor of Tier A worker truth — broader Tier A v_worker_truth wraps this for general identity reads.'),

('achievement_xp_log', 'view', 'v_achievement_xp_log',
 'community', 'realtime',
 'Per (hive_id, worker_name, achievement_key, awarded_at): full XP attribution trail. Drives community feed XP tiles + worker mini-profile drawer.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'worker_name', 'achievement_key', 'awarded_at'),
                    'hive_scoped', true,
                    'append_only', true),
 'Phase A.2. Append-only audit trail; the canonical XP timeline.'),

-- (asset_brain_overview was retired in 20260512000007 — it had no live
-- consumers and was blocking the logbook.asset_ref_id column drop.
-- v_asset_truth is its canonical replacement.)
('asset_brain_overview_retired', 'view', 'v_asset_truth',
 'architect', 'realtime',
 'Retirement marker: asset_brain_overview was dropped in Phase 5b.1 (migration 20260512000007). v_asset_truth is the canonical replacement.',
 jsonb_build_object('retired', true,
                    'replaced_by', 'v_asset_truth',
                    'retired_in', '20260512000007'),
 'Tombstone entry — kept so AI agents tracing the old name find the canonical target.')

ON CONFLICT (domain) DO UPDATE
  SET source_kind   = EXCLUDED.source_kind,
      source_name   = EXCLUDED.source_name,
      owner_skill   = EXCLUDED.owner_skill,
      freshness     = EXCLUDED.freshness,
      description   = EXCLUDED.description,
      contract      = EXCLUDED.contract,
      notes         = EXCLUDED.notes,
      registered_at = now();


-- -----------------------------------------------------------------------------
-- PART 2. Foundational fuel tables (bulk registration)
-- -----------------------------------------------------------------------------
-- These are the raw data tables that other surfaces read DIRECTLY (no
-- canonical view wraps them yet). Registering them in canonical_sources is
-- the explicit declaration: "this is the fuel, read it as-is."
--
-- Each row's domain is a stable identifier; the source_name maps to the
-- actual table name. Description captures purpose; contract captures the
-- shape that downstream code can rely on.

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES

-- Work execution fuels
('logbook_raw', 'table', 'logbook',
 'data-engineer', 'realtime',
 'Raw logbook entries (work executed). Primary fuel for v_logbook_truth + analytics RPCs. Hive-scoped via hive_id (nullable for solo mode).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'solo_mode_supported', true,
                    'canonical_view', 'v_logbook_truth'),
 'Most-read table on the platform. New code should prefer v_logbook_truth.'),

('pm_completions_raw', 'table', 'pm_completions',
 'data-engineer', 'realtime',
 'Raw PM (preventive maintenance) task completions. Joined with pm_scope_items via pm_assets to produce v_pm_compliance_truth.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'canonical_view', 'v_pm_compliance_truth'),
 'New code should prefer v_pm_compliance_truth for hive-mode reads.'),

('pm_scope_items_raw', 'table', 'pm_scope_items',
 'maintenance-expert', 'realtime',
 'PM scope definition per asset (category, interval_days, last_done_at). Drives the v_pm_scope_items_truth view + pm-scheduler.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'canonical_view', 'v_pm_scope_items_truth'),
 'pm-scheduler reads this directly; canonical view wraps the cross-asset rollup.'),

('pm_assets_raw', 'table', 'pm_assets',
 'maintenance-expert', 'realtime',
 'PM-specific asset registry (legacy bridge to asset_nodes via pm_asset_id). PK is uuid.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'bridges_to', 'asset_nodes.pm_asset_id'),
 'Being progressively unified into asset_nodes. v_asset_truth carries the bridge.'),

('inventory_items_raw', 'table', 'inventory_items',
 'data-engineer', 'realtime',
 'Raw inventory items (parts on shelf). Fuels v_inventory_items_truth + parts-tracker.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'canonical_view', 'v_inventory_items_truth'),
 'Approval-workflow tracked in approval_status column.'),

('inventory_transactions_raw', 'table', 'inventory_transactions',
 'data-engineer', 'realtime',
 'Raw inventory transactions (use, restock). Append-only audit trail; drives parts consumption + stockout analytics.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'append_only', true),
 'Used by Analytics parts_consumption + parts_stockout. Future: get_parts_consumption RPC will wrap this.'),

-- Workforce fuels
('worker_profiles_raw', 'table', 'worker_profiles',
 'multitenant-engineer', 'realtime',
 'Worker identity: auth_uid <-> display_name <-> username. The bridge from Supabase Auth to worker_name everywhere else.',
 jsonb_build_object('key', jsonb_build_array('auth_uid', 'username'),
                    'hive_scoped', false,
                    'canonical_view', 'v_worker_truth'),
 'Tier A canonical wraps this with hive_members for identity + role + hive in one shot.'),

('skill_badges_raw', 'table', 'skill_badges',
 'maintenance-expert', 'realtime',
 'Per-discipline skill badges per worker (level 1-5). Underlies v_worker_skill_truth.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'level_range', jsonb_build_array(1, 5),
                    'canonical_view', 'v_worker_skill_truth'),
 'skill_badges is the fuel; v_worker_skill_truth is the canonical aggregate.'),

('skill_profiles_raw', 'table', 'skill_profiles',
 'maintenance-expert', 'realtime',
 'Per-worker primary skill declaration. Joined to v_worker_skill_truth via worker_name.',
 jsonb_build_object('key', jsonb_build_array('worker_name'),
                    'hive_scoped', false),
 'Used by Skill Matrix + AMC Crew-Builder.'),

('skill_exam_attempts_raw', 'table', 'skill_exam_attempts',
 'maintenance-expert', 'realtime',
 'Skill matrix exam attempts (pass/fail per discipline+level).',
 jsonb_build_object('key', jsonb_build_array('id')),
 'Drives cooldown logic in skillmatrix.html.'),

('hive_members_raw', 'table', 'hive_members',
 'multitenant-engineer', 'realtime',
 'Hive membership: (hive_id, worker_name) -> (role, status, joined_at, auth_uid). The boundary between solo and team mode.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'worker_name'),
                    'role_values', jsonb_build_array('worker', 'supervisor'),
                    'status_values', jsonb_build_array('active', 'pending', 'left')),
 'Foundation of hive isolation. Every hive-scoped query reads this.'),

('hives_raw', 'table', 'hives',
 'multitenant-engineer', 'realtime',
 'Hive registry (tenant). Each hive has a unique invite_code + plan.',
 jsonb_build_object('key', jsonb_build_array('id')),
 'Top of the multitenant hierarchy.'),

-- Asset fuels
('asset_nodes_raw', 'table', 'asset_nodes',
 'architect', 'realtime',
 'Canonical asset registry (uuid PK). Replaced legacy assets table in Phase 5c. Underlies v_asset_truth.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'canonical_view', 'v_asset_truth',
                    'iso_class_taxonomy', 'ISO 14224:2016'),
 'Solo-mode supported via hive_id IS NULL (post-Phase-5c).'),

('asset_embeddings_raw', 'table', 'asset_embeddings',
 'ai-engineer', 'realtime',
 'pgvector embeddings per asset for semantic similarity search.',
 jsonb_build_object('key', jsonb_build_array('asset_node_id'),
                    'dim', 1536),
 'Drives "find similar asset" + RAG retrieval for AMC.'),

('asset_risk_scores_raw', 'table', 'asset_risk_scores',
 'predictive-analytics', 'daily_recompute',
 'Daily snapshot of risk score per asset. Nightly batch from batch-risk-scoring edge fn.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'asset_name', 'computed_at'),
                    'hive_scoped', true,
                    'canonical_view', 'v_risk_truth'),
 'v_risk_truth shows the LATEST row per asset; this table is the daily history.'),

-- Predictive / reliability fuels
('weibull_fits_raw', 'table', 'weibull_fits',
 'predictive-analytics', 'weekly_recompute',
 'Weibull distribution fits per asset (beta, eta, characteristic_life). Computed by reliability workbench.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'canonical_view', 'v_weibull_truth'),
 'Reliability Workbench Phase 1.'),

('pf_intervals_raw', 'table', 'pf_intervals',
 'predictive-analytics', 'on_demand_recompute',
 'P-F interval calculations (potential-failure to functional-failure interval). RCM Phase II workbench output.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'canonical_view', 'v_pf_truth'),
 'Reliability Workbench Phase 2.'),

('rcm_fmea_modes_raw', 'table', 'rcm_fmea_modes',
 'maintenance-expert', 'realtime',
 'RCM FMEA failure modes per asset (failure_mode, severity, occurrence, detection, RPN).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'canonical_view', 'v_fmea_truth',
                    'standard', 'SAE JA 1011'),
 'Reliability Workbench foundation.'),

('rcm_strategies_raw', 'table', 'rcm_strategies',
 'maintenance-expert', 'realtime',
 'RCM-3 strategy decisions per failure mode (predictive / preventive / detective / run-to-failure / redesign).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'canonical_view', 'v_rcm_truth',
                    'standard', 'SAE JA 1011 sec 6'),
 'Drives PM strategy recommendations.'),

('failure_signature_alerts_raw', 'table', 'failure_signature_alerts',
 'predictive-analytics', 'realtime',
 'Alerts when an in-progress logbook entry matches a known failure-signature embedding.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'rag', true),
 'pgvector-backed early warning system.'),

-- AI infra fuels
('agent_memory_raw', 'table', 'agent_memory',
 'ai-engineer', 'realtime',
 'Cross-session AI memory store. Append-only; latest entries form the context window for ai-gateway calls.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'append_only', true),
 'Single AI memory layer (closes PRODUCTION_FIXES #44).'),

('ai_cost_log_raw', 'table', 'ai_cost_log',
 'ai-engineer', 'realtime',
 'Per-call AI cost log (provider, model, prompt_tokens, completion_tokens, latency_ms, cost_usd).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'append_only', true),
 'Drives ai-cost-observability gate + quota enforcement.'),

('ai_quality_log_raw', 'table', 'ai_quality_log',
 'ai-engineer', 'realtime',
 'AI evaluation outcomes (pass/fail) per fixture + ai-eval-coverage gate.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'append_only', true),
 'Fixture-based regression detection for prompt changes.'),

('gateway_audit_log_raw', 'table', 'gateway_audit_log',
 'security', 'realtime',
 'Every call routed through platform-gateway (route, hive_id, status, latency). Audit trail.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'append_only', true,
                    'hive_scoped', true),
 'Powers the gateway-coverage validator + per-route quota enforcement.'),

('hive_route_quotas_raw', 'table', 'hive_route_quotas',
 'security', 'realtime',
 'Per-(hive_id, route) call quota configuration (max_calls_per_hour, hard_cap).',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'route'),
                    'hive_scoped', true),
 'Gateway middleware enforces these.'),

('hive_route_calls_raw', 'table', 'hive_route_calls',
 'security', 'realtime',
 'Rolling counter of calls per (hive_id, route, window_start) for quota enforcement.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'route', 'window_start'),
                    'hive_scoped', true),
 'Companion to hive_route_quotas. TTL-pruned hourly.'),

('hive_quotas_raw', 'table', 'hive_quotas',
 'multitenant-engineer', 'realtime',
 'Per-hive global quotas (max_workers, max_pms_per_day, max_ai_calls_per_day). Plan tier enforcement.',
 jsonb_build_object('key', jsonb_build_array('hive_id'),
                    'hive_scoped', true),
 'Plan tier ratchet (free/pro/enterprise).'),

-- Project + knowledge fuels
('projects_raw', 'table', 'projects',
 'architect', 'realtime',
 'Capex / shutdown / contractor / workorder projects per hive.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'type_values', jsonb_build_array('workorder', 'shutdown', 'capex', 'contractor'),
                    'status_values', jsonb_build_array('planning', 'active', 'on_hold', 'complete', 'cancelled', 'archived')),
 'Tier B canonical (v_project_truth) will wrap this when shipped.'),

('project_items_raw', 'table', 'project_items',
 'architect', 'realtime',
 'Line items in a project (BOM, SOW tasks, deliverables).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true),
 'Used by project-manager.html + analytics-orchestrator project rollup.'),

('project_progress_logs_raw', 'table', 'project_progress_logs',
 'architect', 'realtime',
 'Progress entries against project items (% complete, blocker notes, cost-to-date).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'append_only', true),
 'Drives the project progress chart + budget burn-down.'),

('project_knowledge_raw', 'table', 'project_knowledge',
 'ai-engineer', 'realtime',
 'pgvector embeddings of project notes for semantic retrieval (RAG).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'dim', 1536),
 'Tier B knowledge canonical (v_knowledge_truth) will unify across all *_knowledge tables.'),

('fault_knowledge_raw', 'table', 'fault_knowledge',
 'ai-engineer', 'realtime',
 'pgvector embeddings of historical fault descriptions for "have we seen this before" lookups.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'dim', 1536),
 'Tier B knowledge canonical will unify.'),

('skill_knowledge_raw', 'table', 'skill_knowledge',
 'ai-engineer', 'realtime',
 'pgvector embeddings of skill-matrix exam questions + reference answers.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'dim', 1536),
 'Tier B knowledge canonical will unify.'),

('pm_knowledge_raw', 'table', 'pm_knowledge',
 'ai-engineer', 'realtime',
 'pgvector embeddings of PM task descriptions + standard procedures.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'dim', 1536),
 'Tier B knowledge canonical will unify.'),

('bom_knowledge_raw', 'table', 'bom_knowledge',
 'ai-engineer', 'realtime',
 'pgvector embeddings of historical BOMs for engineering-calc retrieval.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'dim', 1536),
 'Drives BOM/SOW retrieval in Engineering Calc.'),

('calc_knowledge_raw', 'table', 'calc_knowledge',
 'ai-engineer', 'realtime',
 'pgvector embeddings of historical engineering calculations for similarity lookup.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'dim', 1536),
 'Drives "find similar calc" in Engineering Calc.'),

-- Marketplace fuels
('marketplace_listings_raw', 'table', 'marketplace_listings',
 'data-engineer', 'realtime',
 'Marketplace seller listings (parts, services, equipment).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', false,
                    'status_values', jsonb_build_array('draft', 'active', 'paused', 'sold')),
 'Cross-hive marketplace (intentionally NOT hive-scoped).'),

('marketplace_orders_raw', 'table', 'marketplace_orders',
 'data-engineer', 'realtime',
 'Marketplace orders (escrow flow: pending -> escrow_hold -> buyer_confirmed -> released).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'status_values', jsonb_build_array('pending', 'escrow_hold', 'buyer_confirmed', 'released', 'disputed', 'refunded'),
                    'standard', 'PCI DSS - payment data not stored here'),
 'Money-movement table. Idempotency-Key REQUIRED on Stripe POSTs.'),

('marketplace_inquiries_raw', 'table', 'marketplace_inquiries',
 'community', 'realtime',
 'Buyer inquiries on listings (pre-order conversation thread).',
 jsonb_build_object('key', jsonb_build_array('id')),
 'Cross-hive communication path.'),

('marketplace_reviews_raw', 'table', 'marketplace_reviews',
 'community', 'realtime',
 'Buyer reviews of completed marketplace orders (1-5 stars + text).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'rating_range', jsonb_build_array(1, 5)),
 'Feeds v_marketplace_sellers_truth.avg_rating.'),

-- Community fuels
('community_replies_raw', 'table', 'community_replies',
 'community', 'realtime',
 'Replies to community_posts (community_thread fuel).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true),
 'Mention support + soft-delete + edit trail.'),

('community_reactions_raw', 'table', 'community_reactions',
 'community', 'realtime',
 'Emoji reactions to community_posts + community_replies.',
 jsonb_build_object('key', jsonb_build_array('post_id', 'worker_name', 'emoji'),
                    'hive_scoped', true),
 'One reaction per (post, worker, emoji).'),

('community_xp_raw', 'table', 'community_xp',
 'community', 'realtime',
 'Per (hive_id, worker_name): running community XP total. Computed by handle_community_post_xp trigger.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'worker_name'),
                    'hive_scoped', true),
 'Drives community leaderboard tile.'),

('worker_achievements_raw', 'table', 'worker_achievements',
 'community', 'realtime',
 'Unlocked achievements per worker. Underlies v_worker_achievements.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'worker_name', 'achievement_key'),
                    'hive_scoped', true,
                    'canonical_view', 'v_worker_achievements'),
 'Append-only unlock log.'),

('achievement_xp_log_raw', 'table', 'achievement_xp_log',
 'community', 'realtime',
 'Append-only XP attribution log. Underlies v_achievement_xp_log.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'append_only', true,
                    'canonical_view', 'v_achievement_xp_log'),
 'Full XP audit trail.'),

-- Voice journal + sensor ingest
('voice_journal_entries_raw', 'table', 'voice_journal_entries',
 'ai-engineer', 'realtime',
 'Voice-recorded journal entries with transcription + AI summary.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true),
 'Companion to journal-recall semantic search.'),

('sensor_topic_map_raw', 'table', 'sensor_topic_map',
 'data-engineer', 'realtime',
 'Maps MQTT/sensor topics to (hive_id, asset_node_id, metric). Drives sensor-readings-ingest.',
 jsonb_build_object('key', jsonb_build_array('topic'),
                    'hive_scoped', true),
 'Sensor ingestion configuration table.'),

-- Benchmarking + PH intelligence
('hive_benchmarks_raw', 'table', 'hive_benchmarks',
 'analytics-engineer', 'daily_recompute',
 'Per (hive_id, metric): snapshot of own performance metrics for trend comparison.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'metric', 'computed_at'),
                    'hive_scoped', true,
                    'append_only', true),
 'Drives "how am I trending" charts on ph-intelligence.html.'),

('network_benchmarks_raw', 'table', 'network_benchmarks',
 'analytics-engineer', 'daily_recompute',
 'Anonymised cross-hive benchmark percentiles (p25/p50/p75/p90 of each metric across all hives).',
 jsonb_build_object('key', jsonb_build_array('metric', 'computed_at'),
                    'hive_scoped', false,
                    'anonymisation', 'no hive_id in projection'),
 'Drives Network View comparisons.'),

('ph_intelligence_reports_raw', 'table', 'ph_intelligence_reports',
 'analytics-engineer', 'realtime',
 'Generated Philippine industrial-intelligence reports per hive.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true),
 'Renders the ph-intelligence page.'),

-- Parts staging (predictive parts pre-positioning)
('parts_staging_recommendations_raw', 'table', 'parts_staging_recommendations',
 'predictive-analytics', 'daily_recompute',
 'Recommended parts to stage near assets predicted to fail soon.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true),
 'Phase 3 predictive analytics output.'),

('parts_staged_reservations_raw', 'table', 'parts_staged_reservations',
 'data-engineer', 'realtime',
 'Active parts reservations (parts pulled from inventory + staged).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true),
 'Joined with inventory_transactions on release.'),

-- Misc infra
('pdf_jobs_raw', 'table', 'pdf_jobs',
 'devops', 'realtime',
 'Async PDF generation queue (queue/processing/done/failed).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'status_values', jsonb_build_array('queued', 'processing', 'done', 'failed')),
 'Drives report-sender + analytics-report PDF generation.'),

('api_keys_raw', 'table', 'api_keys',
 'security', 'realtime',
 'Programmatic API keys per hive for external integrations.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true),
 'Hashed at rest. Service-role-only writes.'),

('early_access_emails_raw', 'table', 'early_access_emails',
 'community', 'realtime',
 'Pre-launch waitlist email captures from the landing page.',
 jsonb_build_object('key', jsonb_build_array('email'),
                    'hive_scoped', false),
 'Marketing fuel.'),

-- Marketplace fuels I missed first pass
('marketplace_sellers_raw', 'table', 'marketplace_sellers',
 'data-engineer', 'realtime',
 'Seller profiles (DTI-registered businesses) on the marketplace. Underlies v_marketplace_sellers_truth.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'canonical_view', 'v_marketplace_sellers_truth'),
 'Cross-hive: sellers are platform entities, not hive-scoped.'),

('marketplace_disputes_raw', 'table', 'marketplace_disputes',
 'data-engineer', 'realtime',
 'Marketplace dispute cases (raised against orders).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'status_values', jsonb_build_array('open', 'investigating', 'resolved_buyer', 'resolved_seller', 'closed')),
 'Escrow funds held until resolution.'),

('marketplace_watchlist_raw', 'table', 'marketplace_watchlist',
 'community', 'realtime',
 'Per-buyer watchlist of listings.',
 jsonb_build_object('key', jsonb_build_array('worker_name', 'listing_id')),
 'Drives "back in stock" notifications.'),

('marketplace_saved_searches_raw', 'table', 'marketplace_saved_searches',
 'community', 'realtime',
 'Saved buyer search queries for periodic match alerts.',
 jsonb_build_object('key', jsonb_build_array('worker_name', 'query_hash')),
 'Future: weekly digest of new matches.'),

('marketplace_platform_admins_raw', 'table', 'marketplace_platform_admins',
 'security', 'realtime',
 'Platform-level marketplace admin list (dispute arbitration, fraud review).',
 jsonb_build_object('key', jsonb_build_array('auth_uid')),
 'Service-role write only.'),

-- Project sub-tables I missed
('project_links_raw', 'table', 'project_links',
 'architect', 'realtime',
 'Linked references between projects + assets / logbook entries / PM completions / inventory items.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'link_type_values', jsonb_build_array('asset', 'logbook', 'pm_completion', 'inventory_item')),
 'Bridge table for project<->everything-else.'),

('project_roles_raw', 'table', 'project_roles',
 'architect', 'realtime',
 'Per-project roles (owner / planner / safety_officer / cost_engineer / reviewer) per worker.',
 jsonb_build_object('key', jsonb_build_array('project_id', 'worker_name'),
                    'role_values', jsonb_build_array('owner', 'planner', 'safety_officer', 'cost_engineer', 'reviewer')),
 'Authorisation model for project edits.'),

('project_change_orders_raw', 'table', 'project_change_orders',
 'architect', 'realtime',
 'Project change orders (scope changes with cost + schedule impact).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'status_values', jsonb_build_array('proposed', 'approved', 'rejected')),
 'Audit-trail for project scope evolution.'),

-- Misc fuels missed first pass
('ai_reports_raw', 'table', 'ai_reports',
 'ai-engineer', 'realtime',
 'AI-generated report storage (scheduled-agents output + on-demand reports).',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'report_types', jsonb_build_array('weekly_digest', 'analytics_summary', 'predictive_maintenance', 'shift_briefing')),
 'Append-only. Read by hive.html + report-sender.html.'),

('parts_records_raw', 'table', 'parts_records',
 'data-engineer', 'realtime',
 'Legacy parts usage log (parallel to inventory_transactions). Read by parts-tracker.html.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', true,
                    'legacy', true,
                    'modern_alternative', 'inventory_transactions'),
 'Being progressively migrated to inventory_transactions for unified parts audit trail.'),

('schedule_items_raw', 'table', 'schedule_items',
 'data-engineer', 'realtime',
 'Worker day-plan schedule entries (DILO/WILO/MILO/YILO). Read by dayplanner.html + assistant.html.',
 jsonb_build_object('key', jsonb_build_array('id'),
                    'hive_scoped', false,
                    'category_values', jsonb_build_array('planning', 'execution', 'review', 'admin'),
                    'status_values', jsonb_build_array('pending', 'in_progress', 'done', 'blocked', 'skipped')),
 'Day Planner fuel. Worker-scoped (not hive-scoped) by design.')

ON CONFLICT (domain) DO UPDATE
  SET source_kind   = EXCLUDED.source_kind,
      source_name   = EXCLUDED.source_name,
      owner_skill   = EXCLUDED.owner_skill,
      freshness     = EXCLUDED.freshness,
      description   = EXCLUDED.description,
      contract      = EXCLUDED.contract,
      notes         = EXCLUDED.notes,
      registered_at = now();


-- -----------------------------------------------------------------------------
-- PART 3. Tier A scaffolding (v_worker_truth + v_worker_assignment_truth)
-- -----------------------------------------------------------------------------
-- v_worker_skill_truth is already shipped (20260512000001). These two
-- complete the Tier A trio.

-- v_worker_truth: identity + hive membership + role + auth_uid in one row.
-- Replaces direct worker_profiles + hive_members joins scattered across
-- ~20 pages and edge fns.

CREATE OR REPLACE VIEW public.v_worker_truth AS
SELECT
  wp.auth_uid,
  wp.username,
  wp.display_name              AS worker_name,
  wp.email,
  wp.created_at                AS registered_at,
  hm.hive_id,
  hm.role,
  hm.joined_at                 AS hive_joined_at,
  hm.status                    AS hive_status,
  -- Convenience flag: solo workers have no active hive membership
  (hm.hive_id IS NULL)         AS is_solo,
  -- Cross-hive count: how many hives is this worker a member of (active)?
  (SELECT count(*) FROM public.hive_members hm2
     WHERE hm2.worker_name = wp.display_name AND hm2.status = 'active') AS active_hive_count
FROM public.worker_profiles wp
LEFT JOIN public.hive_members hm
       ON hm.worker_name = wp.display_name
      AND hm.status      = 'active';

COMMENT ON VIEW public.v_worker_truth IS
  'Canonical worker identity. (auth_uid, username, worker_name, email) + (hive_id, role, joined_at) per active membership. Solo workers appear with hive_id=NULL. Replaces direct worker_profiles + hive_members joins.';

GRANT SELECT ON public.v_worker_truth TO anon, authenticated;


-- v_worker_assignment_truth: per (hive_id, worker_name): recent activity
-- footprint from logbook + PM completions. Used by "best tech for this job"
-- analytics (Tech Assignment + Training Gaps tiles) and Shift Brain.

CREATE OR REPLACE VIEW public.v_worker_assignment_truth AS
WITH recent_logbook AS (
  SELECT
    hive_id,
    worker_name,
    count(*)                                              AS jobs_30d,
    count(*) FILTER (WHERE status IN ('Open', 'In Progress')) AS open_jobs,
    max(created_at)                                       AS last_job_at,
    -- Distinct assets touched. Post Phase 5b.1 the legacy asset_ref_id
    -- column is gone; logbook.asset_node_id is the canonical reference.
    count(DISTINCT asset_node_id)  AS assets_touched_30d,
    sum(coalesce(downtime_hours, 0))                      AS total_downtime_hours_30d,
    -- Last category worked
    (array_agg(category ORDER BY created_at DESC))[1]     AS last_category
  FROM public.logbook
  WHERE created_at >= now() - interval '30 days'
  GROUP BY hive_id, worker_name
),
recent_pm AS (
  SELECT
    hive_id,
    worker_name,
    count(*)                                              AS pms_30d,
    max(completed_at)                                     AS last_pm_at
  FROM public.pm_completions
  WHERE completed_at >= now() - interval '30 days'
  GROUP BY hive_id, worker_name
)
SELECT
  wih.hive_id,
  wih.worker_name,
  wih.role,
  wih.joined_at,
  coalesce(rl.jobs_30d, 0)                AS jobs_30d,
  coalesce(rl.open_jobs, 0)               AS open_jobs,
  coalesce(rl.assets_touched_30d, 0)      AS assets_touched_30d,
  coalesce(rl.total_downtime_hours_30d, 0)::numeric AS total_downtime_hours_30d,
  rl.last_category,
  rl.last_job_at,
  coalesce(rp.pms_30d, 0)                 AS pms_30d,
  rp.last_pm_at,
  -- Capacity signal: open jobs > 5 => busy; 0 jobs in 30d => idle/new
  CASE
    WHEN coalesce(rl.open_jobs, 0) > 5             THEN 'overloaded'
    WHEN coalesce(rl.jobs_30d, 0) = 0              THEN 'idle'
    WHEN coalesce(rl.open_jobs, 0) BETWEEN 1 AND 5 THEN 'available'
    ELSE 'free'
  END                                     AS capacity_signal
FROM public.hive_members wih
LEFT JOIN recent_logbook rl
       ON rl.hive_id = wih.hive_id AND rl.worker_name = wih.worker_name
LEFT JOIN recent_pm rp
       ON rp.hive_id = wih.hive_id AND rp.worker_name = wih.worker_name
WHERE wih.status = 'active';

COMMENT ON VIEW public.v_worker_assignment_truth IS
  'Canonical worker assignment / workload snapshot. Per (hive_id, worker_name): jobs + open_jobs + assets touched in last 30d, PM completions, capacity_signal (overloaded/available/free/idle). Replaces the independent "best tech" computations in analytics-orchestrator Tech Assignment + shift-planner-orchestrator + AMC Crew-Builder.';

GRANT SELECT ON public.v_worker_assignment_truth TO anon, authenticated;


-- Register both Tier A views
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
('worker_truth', 'view', 'v_worker_truth',
 'multitenant-engineer', 'realtime',
 'Per worker: identity (auth_uid + username + worker_name + email) + hive membership (hive_id + role + joined_at). Solo workers carry hive_id=NULL.',
 jsonb_build_object('key', jsonb_build_array('auth_uid'),
                    'hive_scoped_via', 'hive_members.hive_id',
                    'solo_supported', true,
                    'role_values', jsonb_build_array('worker', 'supervisor'),
                    'replaces_direct_reads_of', jsonb_build_array('worker_profiles', 'hive_members')),
 'Tier A canonical. Solo workers appear with hive_id NULL. Use is_solo flag to branch.'),

('worker_assignment_truth', 'view', 'v_worker_assignment_truth',
 'maintenance-expert', 'realtime',
 'Per (hive_id, worker_name): 30d activity footprint (jobs, open_jobs, assets_touched, downtime_hours, last_category, PMs) + capacity_signal (overloaded/available/free/idle). Drives "best tech for this job" decisions across Analytics + Shift Brain + AMC Crew-Builder.',
 jsonb_build_object('key', jsonb_build_array('hive_id', 'worker_name'),
                    'hive_scoped', true,
                    'window', '30 days',
                    'capacity_signal_values', jsonb_build_array('overloaded', 'available', 'free', 'idle'),
                    'compose_pattern', 'For AMC Crew-Builder: filter capacity_signal IN (''available'', ''free'') and join v_worker_skill_truth on (worker_name, discipline) to pick best match.'),
 'Tier A canonical. Window is fixed at 30 days; longer windows belong in dedicated dashboards, not the assignment decision.')

ON CONFLICT (domain) DO UPDATE
  SET source_kind   = EXCLUDED.source_kind,
      source_name   = EXCLUDED.source_name,
      owner_skill   = EXCLUDED.owner_skill,
      freshness     = EXCLUDED.freshness,
      description   = EXCLUDED.description,
      contract      = EXCLUDED.contract,
      notes         = EXCLUDED.notes,
      registered_at = now();

COMMIT;
