-- Thirty registrations everyone believed existed, and none of them did.
--
-- canonical_sources' PRIMARY KEY is (domain) ALONE. Migrations have been filing several objects under one
-- shared domain -- a natural reading of the column name -- and only the first of each group ever survived.
-- With ON CONFLICT DO NOTHING the rest vanished without an error; without it the statement would have
-- failed loudly and been fixed years ago.
--
-- MEASURED, not inferred: 243 registrations are declared across the migration history and 30 of them are
-- absent from the table. The canonical-anchor gate reported every one as ANCHORED, because it reads the
-- migration TEXT and a declaration looked like a registration. Found while registering the credit economy,
-- when a four-row INSERT reported `INSERT 0 1` and the gate still passed.
--
-- Each row is re-filed under its own OBJECT NAME as the domain, which is unique by construction and is the
-- convention the surviving rows already follow (domain 'service_catalog' holds source_name
-- 'service_catalog'). Descriptions are deliberately thin: this repair restores the ANCHOR, and the object's
-- own migration remains the place its contract is documented. Better a registered object with a plain
-- description than an object the registry has never heard of.
--
-- The gate now also fails on a same-migration domain collision, so this class cannot come back silently.

insert into public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
values
  ('ai_cache', 'table', 'ai_cache', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260526000001_p1_roadmap_substrate.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('ai_user_rate_limits', 'table', 'ai_user_rate_limits', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260526000001_p1_roadmap_substrate.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('avatar_animations', 'table', 'avatar_animations', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('best_practices', 'table', 'best_practices', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('fallback_model_faq', 'table', 'fallback_model_faq', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('get_community_reputation', 'rpc', 'get_community_reputation', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260712000007_register_community_marketplace_canonical_sources.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('get_community_reputation_by_auth', 'rpc', 'get_community_reputation_by_auth', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260712000007_register_community_marketplace_canonical_sources.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('get_hive_trade_peers', 'rpc', 'get_hive_trade_peers', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260712000007_register_community_marketplace_canonical_sources.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('get_marketplace_parts_for_my_assets', 'rpc', 'get_marketplace_parts_for_my_assets', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260712000007_register_community_marketplace_canonical_sources.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('get_marketplace_price_comps', 'rpc', 'get_marketplace_price_comps', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260712000007_register_community_marketplace_canonical_sources.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('get_marketplace_trust_badges', 'rpc', 'get_marketplace_trust_badges', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260712000007_register_community_marketplace_canonical_sources.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('get_saved_search_matches', 'rpc', 'get_saved_search_matches', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260712000007_register_community_marketplace_canonical_sources.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('guard_service_review', 'rpc', 'guard_service_review', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260728000046_service_reviews_bidirectional.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('kb_chunks', 'table', 'kb_chunks', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('language_preferences', 'table', 'language_preferences', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('ops_db_size_history', 'table', 'ops_db_size_history', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260718000005_db_size_history.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('push_subscriptions', 'table', 'push_subscriptions', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260728000044_push_subscriptions.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('rpc', 'table', 'rpc', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260509000001_canonical_sources_foundation.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('terminology_gaps', 'table', 'terminology_gaps', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('tts_quality_log', 'table', 'tts_quality_log', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('v_active_anomaly_alerts', 'view', 'v_active_anomaly_alerts', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('v_community_reputation_truth', 'view', 'v_community_reputation_truth', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260712000007_register_community_marketplace_canonical_sources.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('v_conversation_health', 'view', 'v_conversation_health', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('v_dialog_state_current', 'view', 'v_dialog_state_current', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('v_industry_standards_coverage', 'view', 'v_industry_standards_coverage', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('v_kb_freshness_truth', 'view', 'v_kb_freshness_truth', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('v_storage_health', 'view', 'v_storage_health', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260718000005_db_size_history.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('voice_response_queue', 'table', 'voice_response_queue', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260518000002_canonical_anchor_phase_2_11.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('wh_health_status', 'table', 'wh_health_status', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260526000001_p1_roadmap_substrate.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.'),
  ('wh_traces', 'table', 'wh_traces', 'platform', 'on_demand', '{}'::jsonb,
   'Repaired 2026-08-03. Declared in migrations\20260526000001_p1_roadmap_substrate.sql but never present: its INSERT collided on canonical_sources'' (domain) primary key and the row was dropped in silence.')
on conflict (domain) do nothing;
