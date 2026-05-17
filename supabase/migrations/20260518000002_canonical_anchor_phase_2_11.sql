-- Canonical Anchor L1 Fuel + L2 Engine Registration for Phase 2-11 (2026-05-16)
--
-- Registers the 18 tables + 6 views added during the Voice Companion
-- Phase 2-11 migrations (2026-05-16) in canonical_sources, so the Canonical
-- Anchor Gate sees them as anchored. Mirrors the pattern used in
-- 20260513000003_phase1_defensive_closure.sql.

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract
) VALUES
  -- Phase 2: Session Memory
  ('session_memory', 'view', 'v_session_memory_recent',
   'ai-engineer', 'realtime',
   'Latest 50 turns per session for multi-turn context. Phase 2.',
   jsonb_build_object('key', jsonb_build_array('session_id'), 'hive_scoped', true)),

  -- Phase 4: Dialog Flow
  ('dialog_flow', 'table', 'dialog_state',
   'ai-engineer', 'realtime',
   'Per-session active dialog state (intent + slots in progress). Phase 4.',
   jsonb_build_object('key', jsonb_build_array('session_id'), 'hive_scoped', true)),
  ('dialog_flow', 'view', 'v_dialog_state_current',
   'ai-engineer', 'realtime',
   'Current dialog state per active session (last-write-wins). Phase 4.',
   jsonb_build_object('key', jsonb_build_array('session_id'), 'hive_scoped', true)),

  -- Phase 5: Anomaly Alerts
  ('anomaly_intelligence', 'table', 'anomaly_alerts',
   'predictive-analytics', 'realtime',
   'KPI spikes + risk escalations + overdue PMs surfaced proactively. Phase 5.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true)),
  ('anomaly_intelligence', 'view', 'v_active_anomaly_alerts',
   'predictive-analytics', 'realtime',
   'Currently-active anomaly alerts (not suppressed/dismissed). Phase 5.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true)),

  -- Phase 3: KB RAG
  ('knowledge_base', 'table', 'kb_documents',
   'knowledge-manager', 'on_ingest',
   'Source documents for the knowledge base (PDFs, manuals, SOPs). Phase 3.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true)),
  ('knowledge_base', 'table', 'kb_chunks',
   'knowledge-manager', 'on_ingest',
   'Embedded chunks for semantic RAG retrieval. Phase 3.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true)),
  ('knowledge_base', 'view', 'v_kb_freshness_truth',
   'knowledge-manager', 'daily',
   'Per-document freshness + embedding completeness. Phase 3.',
   jsonb_build_object('key', jsonb_build_array('doc_id'), 'hive_scoped', false)),

  -- Phase 6: Offline Resilience
  ('offline_resilience', 'table', 'offline_snapshot_cache',
   'realtime-engineer', 'on_snapshot',
   'Per-hive snapshot cache for offline-first reads. Phase 6.',
   jsonb_build_object('key', jsonb_build_array('hive_id', 'snapshot_key'), 'hive_scoped', true)),
  ('offline_resilience', 'table', 'voice_response_queue',
   'realtime-engineer', 'on_queue',
   'Voice responses queued while offline, flushed on reconnect. Phase 6.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true)),
  ('offline_resilience', 'table', 'fallback_model_faq',
   'ai-engineer', 'on_curation',
   'Curated Q/A pairs served by local fallback when all model providers fail. Phase 6.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', false)),

  -- Phase 7: Azure TTS
  ('tts', 'table', 'tts_cache',
   'ai-engineer', 'on_synth',
   'Cached TTS audio keyed by (text_hash, voice_id). Phase 7.',
   jsonb_build_object('key', jsonb_build_array('text_hash', 'voice_id'), 'hive_scoped', false)),
  ('tts', 'table', 'tts_quality_log',
   'ai-engineer', 'realtime',
   'TTS latency + quality metrics per synthesis. Phase 7.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', false)),

  -- Phase 8: Voice Analytics
  ('conversation_analytics', 'table', 'conversation_analytics',
   'analytics-engineer', 'realtime',
   'Per-turn quality metrics (intent confidence, answer rating, latency). Phase 8.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true)),
  ('conversation_analytics', 'view', 'v_conversation_health',
   'analytics-engineer', 'hourly',
   'Aggregated conversation health per hive (avg confidence, error rate). Phase 8.',
   jsonb_build_object('key', jsonb_build_array('hive_id'), 'hive_scoped', true)),

  -- Phase 9: Team Coordination
  ('team_coordination', 'table', 'cross_hive_alerts',
   'multitenant-engineer', 'realtime',
   'Cross-hive alerts (opt-in pattern sharing between hives). Phase 9.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', true)),
  ('team_coordination', 'table', 'best_practices',
   'knowledge-manager', 'on_curation',
   'Curated best-practice patterns shared across hives. Phase 9.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', false)),

  -- Phase 10: Avatar UI
  ('avatar_ui', 'table', 'avatar_state',
   'designer', 'realtime',
   'Current avatar emotion + animation state per session. Phase 10.',
   jsonb_build_object('key', jsonb_build_array('session_id'), 'hive_scoped', true)),
  ('avatar_ui', 'table', 'avatar_animations',
   'designer', 'on_publish',
   'Animation definitions (Lottie JSON or sprite refs) for avatar states. Phase 10.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', false)),

  -- Phase 11: Multilingual
  ('multilingual', 'table', 'multilingual_terms',
   'knowledge-manager', 'on_curation',
   'Term translations (English ↔ Tagalog/Cebuano/etc.). Phase 11.',
   jsonb_build_object('key', jsonb_build_array('term_en', 'language_code'), 'hive_scoped', false)),
  ('multilingual', 'table', 'language_preferences',
   'multitenant-engineer', 'realtime',
   'Per-worker language preference + locale settings. Phase 11.',
   jsonb_build_object('key', jsonb_build_array('worker_name', 'hive_id'), 'hive_scoped', true)),
  ('multilingual', 'table', 'terminology_gaps',
   'knowledge-manager', 'realtime',
   'Untranslated terms flagged for follow-up curation. Phase 11.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', false)),

  -- Industry Standards (2026-05-18 addition)
  ('industry_standards', 'table', 'industry_standards_chunks',
   'knowledge-manager', 'on_ingest',
   'Embedded chunks from industry standards (ISO, ASHRAE, NFPA, etc.) for RAG.',
   jsonb_build_object('key', jsonb_build_array('id'), 'hive_scoped', false)),
  ('industry_standards', 'view', 'v_industry_standards_coverage',
   'knowledge-manager', 'daily',
   'Per-standard coverage stats (chunks indexed, last refresh).',
   jsonb_build_object('key', jsonb_build_array('standard_id'), 'hive_scoped', false))
ON CONFLICT DO NOTHING;
