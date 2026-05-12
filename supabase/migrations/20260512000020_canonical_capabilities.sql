-- Tier G / Layer 9 — canonical_capabilities registry (2026-05-12).
--
-- The 9th canonical layer. Where canonical_sources answers "what data
-- lives where," canonical_capabilities answers "what user-facing
-- FUNCTION lives where." Closes the AI/voice/alert/display sprawl gap:
-- 5+ AI entry points, 4 voice surfaces, 3 alert mechanisms, N
-- cross-page KPI displays — each canonical capability pins ONE primary
-- surface plus documented secondaries.
--
-- Forward enforcement: validate_capability_dedup.py (3-layer gate)
-- prevents new surfaces from claiming a capability that already has
-- a primary, OR introducing parallel primaries for the same job.
--
-- Backward enforcement (this session): consolidation pass retired
-- parts-tracker.html (legacy) and merged its function into inventory.
-- Other pages stay distinct (their jobs ARE different — analytics-report
-- is print-ready, voice-journal is dedicated audio capture, etc.).
--
-- Skills consulted: architect (registry + primary/secondary pattern),
-- ai-engineer (which AI surfaces are primary vs router vs UI),
-- frontend (shared UI primitives — renderKpiTile, renderSourceChip),
-- designer (IA clarification — one canonical answer per user job),
-- performance (consolidation reduces bundle + cold-start surface).

BEGIN;

CREATE TABLE IF NOT EXISTS public.canonical_capabilities (
  capability_id      text PRIMARY KEY,
  category           text NOT NULL
                     CHECK (category IN ('ai','voice','audio','alert','display',
                                         'storage','input','report','realtime',
                                         'navigation','offline')),
  primary_surface    text NOT NULL,
  secondary_surfaces text[] NOT NULL DEFAULT '{}',
  retired_surfaces   text[] NOT NULL DEFAULT '{}',
  description        text NOT NULL,
  extension_pattern  text NOT NULL DEFAULT '',
  related_canonicals jsonb NOT NULL DEFAULT '{}'::jsonb,
  hive_isolation     text NOT NULL DEFAULT 'hive-scoped'
                     CHECK (hive_isolation IN ('hive-scoped','solo-supported','cross-hive','global')),
  registered_at      timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.canonical_capabilities IS
  'Tier G / Layer 9: every user-facing function on the platform pinned to one primary surface. Read this BEFORE building a new feature to find the existing canonical entry point. Validator validate_capability_dedup.py enforces no parallel primaries.';

CREATE INDEX IF NOT EXISTS idx_canonical_capabilities_category ON public.canonical_capabilities (category);
CREATE INDEX IF NOT EXISTS idx_canonical_capabilities_primary  ON public.canonical_capabilities (primary_surface);

GRANT SELECT ON public.canonical_capabilities TO anon, authenticated;
ALTER TABLE public.canonical_capabilities ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS canonical_capabilities_read ON public.canonical_capabilities;
CREATE POLICY canonical_capabilities_read ON public.canonical_capabilities FOR SELECT USING (true);
DROP POLICY IF EXISTS canonical_capabilities_locked ON public.canonical_capabilities;
CREATE POLICY canonical_capabilities_locked ON public.canonical_capabilities FOR ALL USING (false) WITH CHECK (false);


-- =============================================================================
-- SEED: post-consolidation primary surfaces
-- =============================================================================

INSERT INTO public.canonical_capabilities
  (capability_id, category, primary_surface, secondary_surfaces, retired_surfaces,
   description, extension_pattern, related_canonicals, hive_isolation)
VALUES

-- ─── AI Conversational ───────────────────────────────────────────────────
('ai_question_answer', 'ai',
 'ai-gateway',
 ARRAY['assistant.html','floating-ai.js','ai-orchestrator'],
 ARRAY[]::text[],
 'Free-form natural-language Q&A across the platform. ai-gateway is the single AI entry point — routes by intent to specialist orchestrators (ai-orchestrator dispatches 5 sub-agents). assistant.html is the full-pane chat UI; floating-ai.js is the cross-page mini-drawer; both call ai-gateway.',
 'await fetch("/functions/v1/ai-gateway", { method:"POST", body: JSON.stringify({ question, hive_id, worker_name }) })',
 jsonb_build_object(
   'agent_contracts', jsonb_build_array('analytics_action_plan_v1'),
   'memory_table',    'agent_memory',
   'cost_table',      'ai_cost_log'
 ),
 'hive-scoped'),

('ai_analytics_synthesis', 'ai',
 'analytics-orchestrator',
 ARRAY['analytics.html','analytics-report.html','assistant.html'],
 ARRAY[]::text[],
 '4-phase analytics synthesis (descriptive/diagnostic/predictive/prescriptive) with action_plan generation. Calls Python API for math + Groq for LLM synthesis.',
 'await fetch("/functions/v1/analytics-orchestrator", { method:"POST", body: JSON.stringify({ phase, hive_id, period_days }) })',
 jsonb_build_object(
   'formulas',         jsonb_build_array('mtbf_iso_14224','mttr_iso_14224','oee_iso_22400'),
   'agent_contracts',  jsonb_build_array('analytics_action_plan_v1','next_failure_forecast_v1','priority_ranking_v1')
 ),
 'hive-scoped'),

('ai_specialist_amc', 'ai',
 'amc-orchestrator',
 ARRAY['hive.html','index.html'],
 ARRAY[]::text[],
 'Asset Maintenance Companion — generates morning briefings + handover notes. Specialist; called via ai-gateway routing.',
 'await fetch("/functions/v1/amc-orchestrator", { method:"POST", body: JSON.stringify({ hive_id, shift_window }) })',
 jsonb_build_object('output_table', 'amc_briefings'),
 'hive-scoped'),

('ai_specialist_engineering', 'ai',
 'engineering-calc-agent',
 ARRAY['engineering-design.html','engineering-bom-sow'],
 ARRAY[]::text[],
 'Engineering calculator specialist — runs 58 calc handlers + generates BOM/SOW narratives.',
 'callPythonAnalytics or call engineering-calc-agent edge fn',
 jsonb_build_object('formulas_class', 'eng_calc_*'),
 'hive-scoped'),

('ai_specialist_asset_brain', 'ai',
 'asset-brain-query',
 ARRAY['asset-hub.html','assistant.html'],
 ARRAY[]::text[],
 'Asset-specific natural-language query — "tell me about PMP-001". Reads v_asset_truth + v_risk_truth + v_logbook_truth.',
 'await fetch("/functions/v1/asset-brain-query", ...)',
 jsonb_build_object('views', jsonb_build_array('v_asset_truth','v_risk_truth')),
 'hive-scoped'),

-- ─── Voice surfaces (each writes to a distinct table; kept as 4 surfaces) ──
('voice_to_logbook', 'voice',
 'voice-logbook-entry',
 ARRAY['logbook.html'],
 ARRAY[]::text[],
 'Voice recording -> Whisper transcript -> Groq extraction -> logbook row insert.',
 'POST audio_blob to /functions/v1/voice-logbook-entry',
 jsonb_build_object(
   'capture',     'logbook_add_entry_v1',
   'whisper_via', '_shared/audio-chain.ts'
 ),
 'hive-scoped'),

('voice_to_journal', 'voice',
 'voice-journal-agent',
 ARRAY['voice-journal.html'],
 ARRAY[]::text[],
 'Voice recording -> Whisper transcript -> Groq summary + multi-language reflection -> voice_journal_entries row.',
 'POST audio_blob to /functions/v1/voice-journal-agent',
 jsonb_build_object(
   'capture',     'voice_journal_capture_v1',
   'whisper_via', '_shared/audio-chain.ts',
   'tts_via',     'voice-journal.html#speak (browser SpeechSynthesis API)'
 ),
 'hive-scoped'),

('voice_to_action_router', 'voice',
 'voice-action-router',
 ARRAY['voice-report-intent','assistant.html'],
 ARRAY[]::text[],
 'Voice -> intent classification -> route to downstream action (report dispatch, asset lookup, schedule edit, etc.). The voice-report-intent edge fn is registered as a secondary that will eventually fold into voice-action-router; for now kept separate to preserve the report-sender wiring.',
 'POST audio_blob + context_page to /functions/v1/voice-action-router',
 jsonb_build_object(
   'capture',     'voice_report_intent_v1',
   'whisper_via', '_shared/audio-chain.ts'
 ),
 'hive-scoped'),

-- ─── Audio playback (TTS — minimal sprawl, single canonical location) ────
('audio_tts_browser', 'audio',
 'voice-journal.html#speak',
 ARRAY['floating-ai.js'],
 ARRAY[]::text[],
 'Browser SpeechSynthesis API wrapper. Multi-language (fil-PH falls back to en-US). Honors per-page TTS toggle in localStorage.',
 'const u = new SpeechSynthesisUtterance(text); u.lang = "fil-PH"; window.speechSynthesis.speak(u);',
 jsonb_build_object(),
 'global'),

-- ─── Alerts / Notifications (4 surfaces, kept distinct, render helpers extracted) ──
('alert_dashboard', 'alert',
 'alert-hub.html',
 ARRAY[]::text[],
 ARRAY[]::text[],
 'Dedicated alert dashboard with filters (criticality/discipline/age) + history. Single canonical destination for "show me everything that needs attention."',
 'href="alert-hub.html"',
 jsonb_build_object(
   'fuel_tables', jsonb_build_array('failure_signature_alerts','amc_briefings','parts_staging_recommendations')
 ),
 'hive-scoped'),

('alert_failure_signature', 'alert',
 'failure-signature-scan',
 ARRAY['alert-hub.html','index.html','asset-hub.html'],
 ARRAY[]::text[],
 'Cron-triggered scan of recent logbook entries against the fault_knowledge pgvector index. Writes high-similarity matches into failure_signature_alerts. UI banners on multiple pages render via shared renderFailureSignatureBanner helper (post-consolidation).',
 'await db.from("failure_signature_alerts").select("*").eq("hive_id", hiveId).is("acknowledged_at", null).order("created_at",{ascending:false})',
 jsonb_build_object('fuel_table', 'failure_signature_alerts'),
 'hive-scoped'),

('alert_amc_briefing', 'alert',
 'amc-orchestrator',
 ARRAY['hive.html','index.html','alert-hub.html'],
 ARRAY[]::text[],
 'Morning briefing alerts written into amc_briefings table by amc-orchestrator. Preview tiles on hive.html + index.html call renderAlertPreview helper.',
 'await db.from("amc_briefings").select("*").eq("hive_id", hiveId).eq("status","pending")',
 jsonb_build_object('fuel_table', 'amc_briefings'),
 'hive-scoped'),

('alert_toast_inline', 'alert',
 'utils.js#showToast',
 ARRAY[]::text[],
 ARRAY[]::text[],
 'In-page action feedback toast. Different layer from alert-hub — used for "Saved", "Error", "Synced" inline confirmations.',
 'showToast("Saved", "ok")',
 jsonb_build_object(),
 'global'),

-- ─── Display primitives (UI helpers, consolidated to shared utils.js) ────
('display_source_chip', 'display',
 'utils.js#renderSourceChip',
 ARRAY[]::text[],
 ARRAY[]::text[],
 'Canonical source-and-freshness chip rendered at the top of every page that consumes canonical_* views/RPCs. Declares source + freshness + window.',
 'document.getElementById("wh-source-chip").innerHTML = renderSourceChip({ freshness, source, window });',
 jsonb_build_object('consumers', jsonb_build_array('analytics.html','asset-hub.html','predictive.html','assistant.html')),
 'global'),

('display_kpi_tile', 'display',
 'utils.js#renderKpiTile',
 ARRAY['analytics.html','hive.html','asset-hub.html','predictive.html'],
 ARRAY[]::text[],
 'Shared KPI tile renderer: RAG-coloured value + label + sublabel + optional expandable detail. Extracted from analytics.html#kpiCard during consolidation pass.',
 'container.innerHTML += renderKpiTile({ title, standard, value, unit, sublabel, color, detail });',
 jsonb_build_object(),
 'global'),

('display_alert_preview', 'display',
 'utils.js#renderAlertPreview',
 ARRAY['hive.html','index.html','asset-hub.html'],
 ARRAY[]::text[],
 'Shared alert-row renderer for cross-page alert previews (AMC briefings, failure signature matches, sensor anomalies). Each preview tile links to alert-hub for the full view.',
 'container.innerHTML += renderAlertPreview({ kind, title, severity, asset, message, created_at, href });',
 jsonb_build_object('alert_kinds', jsonb_build_array('amc_briefing','failure_signature','sensor_anomaly','parts_staging')),
 'global'),

('display_worker_drawer', 'display',
 'worker-drawer.js',
 ARRAY['hive.html','asset-hub.html'],
 ARRAY[]::text[],
 'Worker mini-profile slide-in drawer. Reads v_worker_truth + v_worker_skill_truth.',
 'showWorkerDrawer(workerName)',
 jsonb_build_object('views', jsonb_build_array('v_worker_truth','v_worker_skill_truth')),
 'hive-scoped'),

('display_offline_banner', 'display',
 'offline-banner.js',
 ARRAY[]::text[],
 ARRAY[]::text[],
 'Global offline-detection banner. Loaded once via shared script tag, listens for navigator.onLine changes, shows toast + offline icon on every page.',
 '<script src="offline-banner.js"></script> (load once per page)',
 jsonb_build_object(),
 'global'),

('display_nav_hub', 'navigation',
 'nav-hub.js',
 ARRAY[]::text[],
 ARRAY['parts-tracker.html','platform-health.html'],
 'Two-tier navigation (quick-access row + collapsible All Tools grid). Loaded once on every page via <script src=nav-hub.js>. parts-tracker + platform-health retired from TOOLS array.',
 '<script src="nav-hub.js"></script> (load once at bottom of page)',
 jsonb_build_object(),
 'global'),

-- ─── Input / Capture surfaces (delegated to Tier F) ──────────────────────
('input_form_capture', 'input',
 'wh-capture-validate.js',
 ARRAY['logbook.html','inventory.html','pm-scheduler.html','dayplanner.html','hive.html'],
 ARRAY[]::text[],
 'Client-side capture contract validation (Tier F). Loads schema from canonical_capture_contracts and validates payload BEFORE db.from().insert/upsert.',
 'await whValidateCapture(db, "capture_id", payload); if (!result.ok) showToast(result.errors[0].message);',
 jsonb_build_object('registry', 'canonical_capture_contracts'),
 'global'),

-- ─── Storage canonicals (delegated to Tier B/E) ──────────────────────────
('storage_knowledge_unified', 'storage',
 'v_knowledge_truth',
 ARRAY['fault_knowledge','skill_knowledge','pm_knowledge','bom_knowledge','calc_knowledge','project_knowledge'],
 ARRAY[]::text[],
 'Tier B canonical: UNION ALL across all 6 *_knowledge tables for unified pgvector RAG retrieval.',
 'await db.from("v_knowledge_truth").select("source, content").eq("hive_id", hiveId)',
 jsonb_build_object('embedding_model', 'nomic-embed-text-v1_5', 'dim', 384),
 'hive-scoped'),

('storage_agent_memory', 'storage',
 'agent_memory',
 ARRAY['_shared/memory.ts'],
 ARRAY[]::text[],
 'Cross-session AI conversation memory. Append-only. Read by ai-gateway via _shared/memory.ts.',
 'await loadAgentMemory(db, { hive_id, worker_name, agent_id, max_rows });',
 jsonb_build_object(),
 'hive-scoped'),

('storage_audit_unified', 'storage',
 'v_audit_unified',
 ARRAY['hive_audit_log','cmms_audit_log','automation_log','gateway_audit_log'],
 ARRAY[]::text[],
 'Tier E canonical: UNION ALL across all 4 audit log tables. Consumed by audit-log.html.',
 'await db.from("v_audit_unified").select("*").order("created_at",{ascending:false}).limit(100)',
 jsonb_build_object(),
 'hive-scoped'),

-- ─── Report dispatch (PDF + email) ───────────────────────────────────────
('report_pdf_render', 'report',
 'pdf-ingest',
 ARRAY['analytics-report.html','project-report.html'],
 ARRAY[]::text[],
 'PDF generation queue. Pages POST a render request; pdf-ingest edge fn processes async via pdf_jobs table.',
 'await fetch("/functions/v1/pdf-ingest", { method:"POST", body: JSON.stringify({ template, params }) })',
 jsonb_build_object('fuel_table', 'pdf_jobs'),
 'hive-scoped'),

('report_email_dispatch', 'report',
 'send-report-email',
 ARRAY['report-sender.html','scheduled-agents'],
 ARRAY[]::text[],
 'Email delivery for generated reports. Uses Resend; queue via scheduled-agents for periodic dispatch.',
 'await fetch("/functions/v1/send-report-email", { method:"POST", body: JSON.stringify({ to, subject, body, attachments }) })',
 jsonb_build_object(),
 'hive-scoped')

ON CONFLICT (capability_id) DO UPDATE
  SET category           = EXCLUDED.category,
      primary_surface    = EXCLUDED.primary_surface,
      secondary_surfaces = EXCLUDED.secondary_surfaces,
      retired_surfaces   = EXCLUDED.retired_surfaces,
      description        = EXCLUDED.description,
      extension_pattern  = EXCLUDED.extension_pattern,
      related_canonicals = EXCLUDED.related_canonicals,
      hive_isolation     = EXCLUDED.hive_isolation,
      registered_at      = now();

COMMIT;
