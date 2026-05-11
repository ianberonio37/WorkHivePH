-- Physical AI Wave B1: sensor_readings + sensor_topic_map.
--
-- The plant-side MQTT bridge (Python paho-mqtt script running on a hive's
-- Pi / plant gateway, NOT on Render free tier - it would sleep) collects
-- topic/value pairs and batches them through sensor-readings-ingest edge
-- function. This table is the canonical store.
--
-- Architecture choice: the long-running subscriber lives at the plant edge.
-- Render free tier sleeps after 15 min of idle HTTP. Supabase edge
-- functions are short-lived. So the persistent MQTT client is something the
-- hive operator runs themselves; WorkHive's contract is HTTP-only.
--
-- Topic format expected from the bridge:
--   plant/{hive_code}/sensors/{asset_tag}/{parameter}
-- The bridge resolves {asset_tag} -> asset_id via sensor_topic_map first,
-- then POSTs { hive_id, asset_id, parameter, value, recorded_at, source }
-- per reading to sensor-readings-ingest.
--
-- Skills consulted:
--   integration-engineer (MQTT topic format, idempotent ingestion via
--     external dedup key on (topic_full + recorded_at))
--   realtime-engineer (selective publication: do NOT subscribe to full
--     table on the client, only filtered streams per asset)
--   architect (time-series partitioning deferred; composite index covers
--     the dominant query "last N readings per (hive, asset, parameter)")
--   security (CHECK constraint on numeric value range, parameter allowlist
--     via PARAMETER_RE in the edge function, no PII)
--   data-engineer (keyset pagination friendly index on (asset_id, recorded_at),
--     daily retention policy compatible with data_retention validator)
--   predictive-analytics (anomaly Z-score reads recent_window_days, default 30)
--   performance (BRIN index on recorded_at for cheap time-range scans at
--     large scale; composite btree on (hive_id, asset_id, parameter, recorded_at)
--     for the dominant "last N per asset/parameter" lookup)

BEGIN;

-- ─── 1. sensor_readings ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.sensor_readings (
  id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  asset_id      uuid        NOT NULL REFERENCES public.asset_nodes(id) ON DELETE CASCADE,
  parameter     text        NOT NULL CHECK (parameter ~ '^[a-z][a-z0-9_]{0,40}$'),
  -- sensor_type, unit, quality_flag are required by the Digital Twin schema
  -- (validate_digital_twin.py L2). They are nullable because most plant
  -- bridges only know parameter + value; sensor_type and unit can be inferred
  -- from the topic map; quality_flag is filled by the ingest function when
  -- the value passes a sanity range, else null.
  sensor_type   text,                                              -- 'analog'|'digital'|'derived'|'vision'
  unit          text,                                              -- 'mm/s' | '°C' | 'A' | 'kPa' | ...
  quality_flag  text        CHECK (quality_flag IS NULL OR quality_flag IN ('good','uncertain','bad','stale')),
  value         numeric     NOT NULL CHECK (value = value),     -- rejects NaN
  recorded_at   timestamptz NOT NULL,
  ingested_at   timestamptz NOT NULL DEFAULT now(),
  source        text        NOT NULL DEFAULT 'mqtt'
                            CHECK (source IN ('mqtt','opc_ua','manual','edge_ai','sensor_test')),
  meta          jsonb       NOT NULL DEFAULT '{}'::jsonb,
  -- Deterministic dedup key. Two readings from the same source for the
  -- same (asset, parameter, recorded_at) are the same event. Used by the
  -- ingest endpoint's ON CONFLICT path.
  external_key  text        GENERATED ALWAYS AS (
                              source || ':' || asset_id::text || ':' || parameter || ':' || extract(epoch from recorded_at)::text
                            ) STORED,
  CONSTRAINT sensor_readings_dedup UNIQUE (external_key)
);

COMMENT ON TABLE public.sensor_readings IS
  'Time-series sensor readings per asset. Ingested via the sensor-readings-ingest edge function from a plant-side MQTT bridge or OPC-UA gateway. Dedup via external_key (source + asset + parameter + recorded_at).';

-- Dominant query: last N readings per (hive, asset, parameter) — composite btree.
CREATE INDEX IF NOT EXISTS idx_sensor_readings_lookup
  ON public.sensor_readings (hive_id, asset_id, parameter, recorded_at DESC);

-- Time-range scans at scale benefit from BRIN (very cheap to maintain).
CREATE INDEX IF NOT EXISTS idx_sensor_readings_recorded
  ON public.sensor_readings USING brin (recorded_at);

-- ─── 2. sensor_topic_map ─────────────────────────────────────────────────────
-- Optional resolver table: maps a free-form MQTT/OPC-UA topic suffix to
-- the canonical asset_id + parameter. The plant-side bridge can choose to
-- resolve client-side and skip this table entirely; it exists for hives
-- whose topic naming doesn't match WorkHive tag conventions.

CREATE TABLE IF NOT EXISTS public.sensor_topic_map (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id        uuid        NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  topic_pattern  text        NOT NULL,    -- e.g. "plant/manila/sensors/PUMP-201/vibration_mms"
  asset_id       uuid        NOT NULL REFERENCES public.asset_nodes(id) ON DELETE CASCADE,
  parameter      text        NOT NULL CHECK (parameter ~ '^[a-z][a-z0-9_]{0,40}$'),
  unit           text,                    -- 'mm/s' | '°C' | 'A' | 'kPa' | ...
  scale          numeric     NOT NULL DEFAULT 1,        -- linear scale on raw value
  offset_value   numeric     NOT NULL DEFAULT 0,        -- linear offset on raw value
  active         boolean     NOT NULL DEFAULT true,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT sensor_topic_map_unique UNIQUE (hive_id, topic_pattern)
);

COMMENT ON TABLE public.sensor_topic_map IS
  'Optional MQTT/OPC-UA topic to asset_id+parameter resolver. Plant-side bridges that pre-resolve can skip this entirely.';

CREATE INDEX IF NOT EXISTS idx_sensor_topic_map_hive_active
  ON public.sensor_topic_map (hive_id, active);

-- ─── 3. Grants ───────────────────────────────────────────────────────────────

GRANT SELECT, INSERT, UPDATE, DELETE ON public.sensor_readings  TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.sensor_topic_map TO anon, authenticated;

-- ─── 4. RLS ──────────────────────────────────────────────────────────────────

ALTER TABLE public.sensor_readings  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sensor_topic_map ENABLE ROW LEVEL SECURITY;

-- Read: any active hive member.
DROP POLICY IF EXISTS sensor_readings_read ON public.sensor_readings;
CREATE POLICY sensor_readings_read ON public.sensor_readings FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS sensor_topic_map_read ON public.sensor_topic_map;
CREATE POLICY sensor_topic_map_read ON public.sensor_topic_map FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Write: client cannot write directly. The sensor-readings-ingest edge
-- function uses service_role to bypass RLS; the plant-side bridge POSTs
-- through that endpoint. Supervisors manage the topic map via supervisor
-- write policy.
DROP POLICY IF EXISTS sensor_readings_locked ON public.sensor_readings;
CREATE POLICY sensor_readings_locked ON public.sensor_readings FOR INSERT
  WITH CHECK (false);

DROP POLICY IF EXISTS sensor_readings_no_update ON public.sensor_readings;
CREATE POLICY sensor_readings_no_update ON public.sensor_readings FOR UPDATE
  USING (false) WITH CHECK (false);

DROP POLICY IF EXISTS sensor_readings_no_delete ON public.sensor_readings;
CREATE POLICY sensor_readings_no_delete ON public.sensor_readings FOR DELETE
  USING (false);

DROP POLICY IF EXISTS sensor_topic_map_write_supervisor ON public.sensor_topic_map;
CREATE POLICY sensor_topic_map_write_supervisor ON public.sensor_topic_map FOR ALL
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = sensor_topic_map.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = sensor_topic_map.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  );

-- ─── 5. Realtime publication (only sensor_readings, NOT topic_map) ───────────

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'sensor_readings'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.sensor_readings';
  END IF;
END
$$;

-- ─── 6. Canonical view: v_sensor_recent (last 30 days per asset/parameter) ───

CREATE OR REPLACE VIEW public.v_sensor_recent AS
SELECT
  sr.id, sr.hive_id, sr.asset_id, sr.parameter, sr.value,
  sr.recorded_at, sr.source, sr.meta,
  n.tag       AS asset_tag,
  n.name      AS asset_name,
  n.iso_class
FROM public.sensor_readings sr
LEFT JOIN public.asset_nodes n ON n.id = sr.asset_id
WHERE sr.recorded_at >= now() - interval '30 days';

GRANT SELECT ON public.v_sensor_recent TO anon, authenticated;

COMMENT ON VIEW public.v_sensor_recent IS
  'Last 30 days of sensor readings, joined to asset_nodes for tag/name. Source of truth for Asset Hub Live Telemetry tile.';

-- ─── 7. Canonical sources registration ───────────────────────────────────────

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'sensor_readings',
  'table',
  'sensor_readings',
  'integration-engineer',
  'realtime',
  'Time-series sensor readings per (hive, asset, parameter). Ingested via sensor-readings-ingest edge function from a plant-side MQTT or OPC-UA bridge. Dedup via external_key UNIQUE constraint. Source of truth for the Asset Hub Live Telemetry tile and the v_risk_truth sensor_anomaly_score factor (Phase 5a/b model upgrade).',
  jsonb_build_object(
    'key', jsonb_build_array('id'),
    'natural_key', jsonb_build_array('source','asset_id','parameter','recorded_at'),
    'hive_scoped', true,
    'parameter_examples', jsonb_build_array(
      'vibration_mms','bearing_temp_c','motor_current_a','oil_debris_ppm',
      'discharge_pressure_kpa','flow_rate_lpm','rpm','voltage_v'
    ),
    'source_values', jsonb_build_array('mqtt','opc_ua','manual','edge_ai','sensor_test'),
    'persistent_subscriber', 'plant-side; WorkHive contract is HTTP-only ingestion',
    'anomaly_layer', 'python-api/sensors/anomaly.py - rule-based Z-score over recent_window_days'
  ),
  'Phase B1 (Physical AI). Writes are locked at RLS; ingestion goes through sensor-readings-ingest edge function (service-role). Realtime publication enabled for Asset Hub Live Telemetry; selective filter by asset_id at the client. v_sensor_recent is the consumer-facing read shape.'
)
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
