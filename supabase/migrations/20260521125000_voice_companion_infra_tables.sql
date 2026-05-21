-- Voice Companion infrastructure tables (2026-05-21 Mega Gate paydown)
--
-- voice-handler.js references these 9 tables from helpers T95 / T113 /
-- T114 / T137 / T144 / T146 / T147 / T149 + the quality feedback path.
-- All writes are wrapped in try/catch (best-effort, console.warn on fail),
-- so the code does NOT crash without these tables — but every insert
-- silently no-ops. Adding the tables unlocks the actual functionality
-- (audit log, knowledge gaps, mentor relay, presence, handoff, watchlist,
-- shared notes, feature flags, quality escalation).
--
-- All tables: hive_scoped, RLS on (hive_id IN user's hive_members), no
-- soft delete, append-only-ish (per-table notes below).
--
-- Idempotency: DROP POLICY IF EXISTS before each CREATE POLICY so re-running
-- the migration on an already-migrated DB doesn't fail. GRANT statements
-- after RLS enable so anon/authenticated roles can actually read (RLS without
-- GRANT returns 401 silently — caught by validate_idempotency.py L0).

-- T95: ai_audit_log — per-action audit trail of confirmed companion writes.
CREATE TABLE IF NOT EXISTS public.ai_audit_log (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name  text,
  event        text NOT NULL,                    -- 'logbook.create' / 'pm.schedule' / 'erasure_request' / ...
  payload      jsonb NOT NULL DEFAULT '{}'::jsonb,
  source       text DEFAULT 'voice-handler',
  created_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_audit_log_hive_created ON public.ai_audit_log (hive_id, created_at DESC);
ALTER TABLE public.ai_audit_log ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.ai_audit_log TO anon, authenticated;
DROP POLICY IF EXISTS ai_audit_log_hive_select ON public.ai_audit_log;
CREATE POLICY ai_audit_log_hive_select ON public.ai_audit_log FOR SELECT TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));
DROP POLICY IF EXISTS ai_audit_log_hive_insert ON public.ai_audit_log;
CREATE POLICY ai_audit_log_hive_insert ON public.ai_audit_log FOR INSERT TO authenticated
  WITH CHECK (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- T113: ai_knowledge_gap — logged when the LLM hits a question it can't answer.
CREATE TABLE IF NOT EXISTS public.ai_knowledge_gap (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name  text,
  question     text NOT NULL,
  reason       text,                              -- 'no_data' / 'rag_miss' / 'low_confidence' / 'forbidden_topic'
  topic        text,
  created_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ai_knowledge_gap_hive_created ON public.ai_knowledge_gap (hive_id, created_at DESC);
ALTER TABLE public.ai_knowledge_gap ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.ai_knowledge_gap TO anon, authenticated;
DROP POLICY IF EXISTS ai_knowledge_gap_hive_all ON public.ai_knowledge_gap;
CREATE POLICY ai_knowledge_gap_hive_all ON public.ai_knowledge_gap FOR ALL TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()))
  WITH CHECK (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- Quality escalation queue (3+ thumbs-down in 7d -> supervisor review).
CREATE TABLE IF NOT EXISTS public.ai_quality_escalation (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name     text,
  thumbs_down_7d  integer DEFAULT 0,
  last_negative_at timestamptz,
  reviewed_at     timestamptz,
  reviewed_by     text,
  created_at      timestamptz DEFAULT now()
);
ALTER TABLE public.ai_quality_escalation ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.ai_quality_escalation TO anon, authenticated;
DROP POLICY IF EXISTS ai_quality_escalation_hive_all ON public.ai_quality_escalation;
CREATE POLICY ai_quality_escalation_hive_all ON public.ai_quality_escalation FOR ALL TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()))
  WITH CHECK (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- T149: asset_watchlist — worker subscribes to an asset; alerted on next session.
CREATE TABLE IF NOT EXISTS public.asset_watchlist (
  hive_id       uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name   text NOT NULL,
  asset_tag     text NOT NULL,
  subscribed_at timestamptz DEFAULT now(),
  PRIMARY KEY (hive_id, worker_name, asset_tag)
);
ALTER TABLE public.asset_watchlist ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.asset_watchlist TO anon, authenticated;
DROP POLICY IF EXISTS asset_watchlist_hive_all ON public.asset_watchlist;
CREATE POLICY asset_watchlist_hive_all ON public.asset_watchlist FOR ALL TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()))
  WITH CHECK (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- T146 + T150 + T154: companion_handoff — cross-worker message relay + broadcast + mention.
CREATE TABLE IF NOT EXISTS public.companion_handoff (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  from_worker  text,                              -- '__broadcast__' for supervisor broadcasts
  to_worker    text,
  message      text,
  status       text DEFAULT 'pending' CHECK (status IN ('pending','delivered','read','mention')),
  source       text DEFAULT 'voice-handler',
  created_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_companion_handoff_hive_to_pending ON public.companion_handoff (hive_id, to_worker, status, created_at DESC);
ALTER TABLE public.companion_handoff ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.companion_handoff TO anon, authenticated;
DROP POLICY IF EXISTS companion_handoff_hive_all ON public.companion_handoff;
CREATE POLICY companion_handoff_hive_all ON public.companion_handoff FOR ALL TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()))
  WITH CHECK (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- T114: mentor_relay_queue — worker defers question to senior; senior reads on next session.
CREATE TABLE IF NOT EXISTS public.mentor_relay_queue (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  from_worker  text,
  question     text NOT NULL,
  status       text DEFAULT 'pending' CHECK (status IN ('pending','answered','dismissed')),
  answer       text,
  answered_by  text,
  answered_at  timestamptz,
  source       text DEFAULT 'voice-handler',
  created_at   timestamptz DEFAULT now()
);
ALTER TABLE public.mentor_relay_queue ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.mentor_relay_queue TO anon, authenticated;
DROP POLICY IF EXISTS mentor_relay_queue_hive_all ON public.mentor_relay_queue;
CREATE POLICY mentor_relay_queue_hive_all ON public.mentor_relay_queue FOR ALL TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()))
  WITH CHECK (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- T147: shared_voice_notes — per-thread team note (asset thread, shift thread, etc).
CREATE TABLE IF NOT EXISTS public.shared_voice_notes (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  thread_key   text NOT NULL DEFAULT 'general',   -- 'asset:P-203' / 'shift:morning' / 'general'
  worker_name  text,
  content      text NOT NULL,
  source       text DEFAULT 'voice-handler',
  created_at   timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_shared_voice_notes_hive_thread ON public.shared_voice_notes (hive_id, thread_key, created_at DESC);
ALTER TABLE public.shared_voice_notes ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.shared_voice_notes TO anon, authenticated;
DROP POLICY IF EXISTS shared_voice_notes_hive_all ON public.shared_voice_notes;
CREATE POLICY shared_voice_notes_hive_all ON public.shared_voice_notes FOR ALL TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()))
  WITH CHECK (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- T137: wh_feature_flags — per-hive feature flag overrides loaded with 5-min cache.
CREATE TABLE IF NOT EXISTS public.wh_feature_flags (
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  name         text NOT NULL,
  enabled      boolean NOT NULL DEFAULT false,
  config       jsonb DEFAULT '{}'::jsonb,
  updated_at   timestamptz DEFAULT now(),
  PRIMARY KEY (hive_id, name)
);
ALTER TABLE public.wh_feature_flags ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.wh_feature_flags TO anon, authenticated;
DROP POLICY IF EXISTS wh_feature_flags_hive_select ON public.wh_feature_flags;
CREATE POLICY wh_feature_flags_hive_select ON public.wh_feature_flags FOR SELECT TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- T144: wh_voice_presence — 60s heartbeat of active voice workers per hive.
CREATE TABLE IF NOT EXISTS public.wh_voice_presence (
  hive_id      uuid REFERENCES public.hives(id) ON DELETE CASCADE,
  worker_name  text NOT NULL,
  last_seen    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (hive_id, worker_name)
);
CREATE INDEX IF NOT EXISTS idx_wh_voice_presence_hive_last_seen ON public.wh_voice_presence (hive_id, last_seen DESC);
ALTER TABLE public.wh_voice_presence ENABLE ROW LEVEL SECURITY;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.wh_voice_presence TO anon, authenticated;
DROP POLICY IF EXISTS wh_voice_presence_hive_all ON public.wh_voice_presence;
CREATE POLICY wh_voice_presence_hive_all ON public.wh_voice_presence FOR ALL TO authenticated
  USING (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()))
  WITH CHECK (hive_id IN (SELECT hive_id FROM public.hive_members WHERE auth_uid = auth.uid()));

-- Add quality_rating column to existing ai_cost_log (voice-handler T34 writes here).
ALTER TABLE public.ai_cost_log
  ADD COLUMN IF NOT EXISTS quality_rating smallint;  -- 1=thumbs up, -1=thumbs down, NULL=unrated

-- Register all 9 new tables in canonical_sources so the fuel anchor passes.
INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('ai_audit_log',          'table', 'ai_audit_log',          'ai-engineer',          'realtime',  'Per-action audit trail of confirmed companion writes.',                              jsonb_build_object('key',jsonb_build_array('id'),'hive_scoped',true,'soft_delete',false), 'voice-handler T95.'),
  ('ai_knowledge_gap',      'table', 'ai_knowledge_gap',      'ai-engineer',          'realtime',  'Companion questions that hit a no-data / rag-miss / low-confidence ceiling.',         jsonb_build_object('key',jsonb_build_array('id'),'hive_scoped',true,'soft_delete',false), 'voice-handler T113.'),
  ('ai_quality_escalation', 'table', 'ai_quality_escalation', 'ai-engineer',          'on-demand', 'Escalation queue: 3+ thumbs-down in 7d -> supervisor review.',                         jsonb_build_object('key',jsonb_build_array('id'),'hive_scoped',true,'soft_delete',false), 'voice-handler T46.'),
  ('asset_watchlist',       'table', 'asset_watchlist',       'realtime-engineer',    'realtime',  'Worker subscriptions to per-asset notifications.',                                     jsonb_build_object('key',jsonb_build_array('hive_id','worker_name','asset_tag'),'hive_scoped',true,'soft_delete',false), 'voice-handler T149.'),
  ('companion_handoff',     'table', 'companion_handoff',     'realtime-engineer',    'realtime',  'Cross-worker message relay + supervisor broadcast + mention notice (one table).',     jsonb_build_object('key',jsonb_build_array('id'),'hive_scoped',true,'soft_delete',false), 'voice-handler T146 + T150 + T154.'),
  ('mentor_relay_queue',    'table', 'mentor_relay_queue',    'knowledge-manager',    'on-demand', 'Worker defers question to senior; senior reads on next session.',                      jsonb_build_object('key',jsonb_build_array('id'),'hive_scoped',true,'soft_delete',false), 'voice-handler T114.'),
  ('shared_voice_notes',    'table', 'shared_voice_notes',    'knowledge-manager',    'realtime',  'Per-thread team note (asset thread / shift thread / general).',                        jsonb_build_object('key',jsonb_build_array('id'),'hive_scoped',true,'soft_delete',false), 'voice-handler T147.'),
  ('wh_feature_flags',      'table', 'wh_feature_flags',      'devops',               'on-demand', 'Per-hive feature flag overrides loaded with 5-min cache.',                             jsonb_build_object('key',jsonb_build_array('hive_id','name'),'hive_scoped',true,'soft_delete',false), 'voice-handler T137.'),
  ('wh_voice_presence',     'table', 'wh_voice_presence',     'realtime-engineer',    'realtime',  '60s heartbeat of active voice workers per hive.',                                     jsonb_build_object('key',jsonb_build_array('hive_id','worker_name'),'hive_scoped',true,'soft_delete',false), 'voice-handler T144.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind, source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill, freshness = EXCLUDED.freshness,
      description = EXCLUDED.description, contract = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
