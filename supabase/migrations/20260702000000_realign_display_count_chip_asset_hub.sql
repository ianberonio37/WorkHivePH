-- Realign display_count_chip primary_surface after predictive.html retirement (2026-07-02).
--
-- predictive.html was deleted; its per-asset risk-360 view was absorbed into
-- asset-hub.html (Phase B.5 risk panel). Migration 20260512000021 registered
-- display_count_chip with primary_surface = 'predictive.html', which no longer
-- resolves to a file (capability-dedup L1 fails). This corrects the surface
-- WITHOUT editing that immutable migration: a new migration re-inserts the
-- canonical tuple (the capability registry loader is latest-migration-wins keyed
-- by capability_id), and ON CONFLICT DO UPDATE keeps the prod DB in sync.
BEGIN;

INSERT INTO public.canonical_capabilities
  (capability_id, category, primary_surface, secondary_surfaces, retired_surfaces,
   description, extension_pattern, related_canonicals, hive_isolation)
VALUES
('display_count_chip', 'display',
 'asset-hub.html',
 ARRAY[]::text[],
 ARRAY['predictive.html']::text[],
 'Per-asset risk-severity summary ("Critical / High / Medium / Low" band) rendered in the asset-hub.html risk panel (Phase B.5), which absorbed the predictive.html per-asset risk-360 view when that page was retired. Distinct visual primitive (centered alignment, big number on top, colored label), not migrated to renderCompactStat because the layout semantics differ (severity summary vs inline strip). Documented here so a future Tier G.b audit can decide whether to unify or keep distinct.',
 '<div class="sum-card critical"><span class="sn">N</span><span class="sl">Critical</span></div>',
 jsonb_build_object('css_classes', jsonb_build_array('summary-row','sum-card','critical','high','medium','low')),
 'global')
ON CONFLICT (capability_id) DO UPDATE
  SET primary_surface    = EXCLUDED.primary_surface,
      retired_surfaces   = EXCLUDED.retired_surfaces,
      secondary_surfaces = EXCLUDED.secondary_surfaces,
      description        = EXCLUDED.description,
      extension_pattern  = EXCLUDED.extension_pattern,
      related_canonicals = EXCLUDED.related_canonicals,
      registered_at      = now();

COMMIT;
