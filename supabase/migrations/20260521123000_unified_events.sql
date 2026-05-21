-- Unified Events (Phase 5 of AGENTIC_RAG_ROADMAP.md)
--
-- Canonical event schema that normalizes every external + internal data
-- source into one shape so the agentic-rag-loop Retriever can query
-- across SAP work orders + Maximo work orders + OPC-UA sensor readings +
-- MQTT messages + voice journal entries + photo OCR + manual logs in a
-- single hive-scoped query.
--
-- Hash column makes ingest idempotent (sha256 of source+source_id+occurred_at).
-- Payload_text is the embeddable representation (nullable for binary types).
-- Embedding is nullable until the enrichment pass runs.

-- canonical-allow: unified event-stream ingest table (SAP/Maximo/OPC-UA/MQTT/voice/etc) — sources are themselves canonical, this is the aggregator
CREATE TABLE IF NOT EXISTS public.unified_events (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  asset_tag     text,
  source        text NOT NULL CHECK (source IN ('sap_pm','maximo','opc_ua','mqtt','cmms_webhook','voice','photo_ocr','manual_log','sensor','email_ingest')),
  source_id     text NOT NULL,                                    -- foreign system's primary key
  event_type    text NOT NULL,                                    -- 'work_order' | 'sensor_reading' | 'alarm' | 'note' | 'image' | ...
  occurred_at   timestamptz NOT NULL,
  payload       jsonb NOT NULL,
  payload_text  text,                                             -- flattened text for embedding (nullable for binary)
  embedding     vector(384),                                      -- nullable until enrichment pass
  hash          text NOT NULL,                                    -- sha256 of source+source_id+occurred_at for dedup
  ingested_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source, source_id, hash)
);

CREATE INDEX IF NOT EXISTS idx_unified_events_hive_asset_time ON public.unified_events (hive_id, asset_tag, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_unified_events_hive_source      ON public.unified_events (hive_id, source, occurred_at DESC);
CREATE INDEX IF NOT EXISTS idx_unified_events_event_type       ON public.unified_events (event_type, occurred_at DESC);
-- ivfflat index deferred until embeddings populated.

GRANT SELECT, INSERT ON public.unified_events TO anon, authenticated;

ALTER TABLE public.unified_events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS ue_read   ON public.unified_events;
DROP POLICY IF EXISTS ue_insert ON public.unified_events;

CREATE POLICY ue_read ON public.unified_events
  FOR SELECT USING (
    auth.uid() IS NOT NULL
    AND hive_id IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = unified_events.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.status = 'active'
    )
  );

-- Inserts via service role only (the data-fabric-normalizer edge fn).
CREATE POLICY ue_insert ON public.unified_events
  FOR INSERT WITH CHECK (false);
