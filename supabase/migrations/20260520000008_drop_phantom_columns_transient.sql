-- Drop 10 TRANSIENT phantom columns confirmed dead via grep.
--
-- Vetted 2026-05-20: each column has ZERO references in any application
-- file (HTML / JS / TS / Python API). They were intended as write-only
-- telemetry / cache fields but no insert path nor read path ever
-- materialised. Dropping them recovers storage + clarifies the schema.
--
-- DEFERRED (kept in registry, future drop pass):
--   - turn_text, approved_notes, relevance_score, reserved_at,
--     actual_start, actual_end, weibull_fit_id, offset_value:
--     each has 1-2 references — verify those aren't write-only paths
--     before dropping.
--   - hour_bucket, hourly_cap, voter_token, sensor_type: 4-7 references —
--     likely active; not phantoms.
--   - canonical_lineage_edges.target_kind, canonical_sources.last_validated:
--     allowlisted in audit (lineage edge created this session;
--     last_validated written by validate_schema_phantom.py).
--   - hive_adoption_score risk cols (3) + industry_standards version
--     cols (3): planned-feature columns; user-vetted decision.

BEGIN;

-- AI eval log timestamp — column was never INSERTed by any edge fn.
ALTER TABLE IF EXISTS public.ai_quality_log         DROP COLUMN IF EXISTS run_at;

-- Anomaly alerts notification timestamp — never set.
ALTER TABLE IF EXISTS public.anomaly_alerts         DROP COLUMN IF EXISTS last_notified_at;

-- Fallback model FAQ embedding + accuracy — vector + score never populated.
ALTER TABLE IF EXISTS public.fallback_model_faq     DROP COLUMN IF EXISTS question_embedding;
ALTER TABLE IF EXISTS public.fallback_model_faq     DROP COLUMN IF EXISTS accuracy_score;

-- KB document file-size telemetry — never written by ingest.
ALTER TABLE IF EXISTS public.kb_documents           DROP COLUMN IF EXISTS file_size_bytes;

-- Offline snapshot cache timestamp — write path never landed.
ALTER TABLE IF EXISTS public.offline_snapshot_cache DROP COLUMN IF EXISTS cached_at;

-- Platform feedback vote timestamp — only voter_token is used.
ALTER TABLE IF EXISTS public.platform_feedback_votes DROP COLUMN IF EXISTS voted_at;

-- Sensor ingest timestamp — overrides the universal created_at; never set.
ALTER TABLE IF EXISTS public.sensor_readings        DROP COLUMN IF EXISTS ingested_at;

-- TTS cache payload + format — cache reads use different fields.
ALTER TABLE IF EXISTS public.tts_cache              DROP COLUMN IF EXISTS audio_data;
ALTER TABLE IF EXISTS public.tts_cache              DROP COLUMN IF EXISTS audio_format;

COMMIT;
