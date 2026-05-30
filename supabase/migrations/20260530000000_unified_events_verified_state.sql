-- Unified Events VERIFIED STATE (memory-stack flywheel Turn 2, layer 07 "Shared
-- Memory": one truth, every agent aligned).
--
-- unified_events already has ACCESS CONTROL (RLS, hive-scoped) and CONSISTENCY
-- (idempotent dedup via UNIQUE(source, source_id, hash)). What it lacked was
-- CONFLICT RESOLUTION + VERIFIED STATE: when two sources report the same asset
-- differently (SAP says P-203 work order CLOSED at 14:00; a voice note says
-- P-203 still DOWN at 15:00), both rows coexisted and every agent was free to
-- read a different "truth". This migration adds the missing resolver so all
-- agents read ONE verified state per (hive, asset, event_type).
--
-- Resolution rule = SOURCE TRUST PRECEDENCE, then RECENCY:
--   1 system-of-record CMMS  (sap_pm, maximo)        -- authoritative work orders
--   2 cmms_webhook                                   -- real-time CMMS push
--   3 machine telemetry      (sensor, opc_ua, mqtt)  -- objective, point-in-time
--   4 photo_ocr                                      -- OCR, error-prone
--   5 human note             (manual_log, voice, email_ingest)
-- Within a rank, the most-recent occurred_at wins. conflict_count exposes how
-- many competing events existed so a consumer can flag disagreement.
--
-- Skills consulted: integration-engineer (owns unified_events / the data
-- fabric; source-precedence reflects real CMMS-vs-telemetry-vs-human trust),
-- architect (canonical _truth view + DISTINCT ON + canonical_sources registry
-- pattern), data-engineer (window-count over the resolution partition),
-- multitenant-engineer (security_invoker so base-table hive RLS is enforced
-- for the querying user), security (no widening of the insert/read surface).

BEGIN;

-- Immutable trust rank for a source. Lower = more trusted. Unknown -> 9.
CREATE OR REPLACE FUNCTION public.unified_event_source_rank(p_source text)
RETURNS int
LANGUAGE sql IMMUTABLE PARALLEL SAFE
AS $$
  SELECT CASE p_source
    WHEN 'sap_pm'       THEN 1
    WHEN 'maximo'       THEN 1
    WHEN 'cmms_webhook' THEN 2
    WHEN 'sensor'       THEN 3
    WHEN 'opc_ua'       THEN 3
    WHEN 'mqtt'         THEN 3
    WHEN 'photo_ocr'    THEN 4
    WHEN 'manual_log'   THEN 5
    WHEN 'voice'        THEN 5
    WHEN 'email_ingest' THEN 5
    ELSE 9
  END
$$;

COMMENT ON FUNCTION public.unified_event_source_rank(text) IS
  'Source trust precedence for unified_events conflict resolution. Lower = more trusted (system-of-record CMMS=1 .. human note=5). Used by v_asset_state_truth.';

-- Verified-state view: the single winning event per (hive, asset, event_type),
-- resolved by trust rank then recency. security_invoker=true so the base table
-- RLS (active hive membership) gates the querying user exactly as a direct
-- read of unified_events would.
CREATE OR REPLACE VIEW public.v_asset_state_truth
WITH (security_invoker = true)
AS
SELECT DISTINCT ON (e.hive_id, e.asset_tag, e.event_type)
  e.hive_id,
  e.asset_tag,
  e.event_type,
  e.source                                        AS verified_source,
  public.unified_event_source_rank(e.source)      AS verified_source_rank,
  e.source_id,
  e.occurred_at                                   AS verified_at,
  e.payload                                        AS verified_payload,
  e.payload_text                                   AS verified_text,
  count(*)    OVER (PARTITION BY e.hive_id, e.asset_tag, e.event_type) AS conflict_count,
  count(*)    OVER (PARTITION BY e.hive_id, e.asset_tag, e.event_type) - 1 AS superseded_count,
  e.ingested_at
FROM public.unified_events e
WHERE e.asset_tag IS NOT NULL
ORDER BY
  e.hive_id,
  e.asset_tag,
  e.event_type,
  public.unified_event_source_rank(e.source) ASC,   -- most trusted source first
  e.occurred_at DESC;                                -- then most recent within tier

COMMENT ON VIEW public.v_asset_state_truth IS
  'Verified current state per (hive_id, asset_tag, event_type) over unified_events. Conflict resolved by source trust precedence (unified_event_source_rank) then recency. conflict_count/superseded_count expose disagreement. Registered in canonical_sources as domain=asset_state_truth. The shared-memory "one truth" surface every agent reads.';

GRANT SELECT ON public.v_asset_state_truth TO anon, authenticated;

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES (
  'asset_state_truth',
  'view',
  'v_asset_state_truth',
  'integration-engineer',
  'realtime',
  'Verified current asset state from the unified event stream. One winning event per (hive, asset, event_type), resolved by source trust precedence then recency. The shared-memory layer-07 surface: every agent reads the same truth instead of picking an arbitrary competing event.',
  jsonb_build_object(
    'key', jsonb_build_array('hive_id', 'asset_tag', 'event_type'),
    'hive_scoped', true,
    'resolution', 'source_rank ASC, occurred_at DESC',
    'source_rank', jsonb_build_object(
      'sap_pm', 1, 'maximo', 1, 'cmms_webhook', 2,
      'sensor', 3, 'opc_ua', 3, 'mqtt', 3,
      'photo_ocr', 4, 'manual_log', 5, 'voice', 5, 'email_ingest', 5
    ),
    'conflict_count', 'total competing events for the key; superseded_count = conflict_count - 1'
  ),
  'Turn 2 of the AI Agent Memory Stack flywheel. Resolves the verified-state/conflict-resolution gap in layer 07. Read via _shared/verified-state.ts (resolveAssetState).'
)
ON CONFLICT (domain) DO UPDATE
  SET source_kind  = EXCLUDED.source_kind,
      source_name  = EXCLUDED.source_name,
      owner_skill  = EXCLUDED.owner_skill,
      freshness    = EXCLUDED.freshness,
      description  = EXCLUDED.description,
      contract     = EXCLUDED.contract,
      notes        = EXCLUDED.notes,
      registered_at = now();

COMMIT;
