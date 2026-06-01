-- Truth-view signal-trust contract for v_asset_state_truth
-- =========================================================
-- v_asset_state_truth (20260530000000) shipped as a new v_*_truth view WITHOUT
-- the canonical meta-columns every truth view must publish:
--   _source_count       -- how many competing rows fed this resolved state
--   _freshness_ts       -- recency of the underlying evidence
--   _canonical_version  -- formula/version tag frontends + agents assert against
-- That regressed validate_truth_view_contract (+1 over baseline). Forward-fix:
-- CREATE OR REPLACE the view appending the three columns (Postgres permits
-- appending columns to a view in-place). The original migration is immutable
-- (hash-locked), so the conforming definition lands here.
--
-- Semantics: _source_count = the competing-event count already exposed as
-- conflict_count; _freshness_ts = newest ingest in the (hive, asset, event)
-- partition; _canonical_version pins the resolution rule (source_rank ASC,
-- occurred_at DESC).

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
  e.ingested_at,
  -- Canonical truth-view signal-trust contract (appended 2026-06-01):
  count(*)           OVER (PARTITION BY e.hive_id, e.asset_tag, e.event_type) AS _source_count,
  max(e.ingested_at) OVER (PARTITION BY e.hive_id, e.asset_tag, e.event_type) AS _freshness_ts,
  'asset_state_truth:v1'                          AS _canonical_version
FROM public.unified_events e
WHERE e.asset_tag IS NOT NULL
ORDER BY
  e.hive_id,
  e.asset_tag,
  e.event_type,
  public.unified_event_source_rank(e.source) ASC,   -- most trusted source first
  e.occurred_at DESC;                                -- then most recent within tier

GRANT SELECT ON public.v_asset_state_truth TO anon, authenticated;
