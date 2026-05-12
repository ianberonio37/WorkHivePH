-- Tier G realignment (2026-05-12) — capability registry corrected to match
-- platform reality after the KPI-consolidation audit.
--
-- ORIGINAL: canonical_capabilities listed hive.html, asset-hub.html, and
-- predictive.html as `secondary_surfaces[]` for display_kpi_tile. Audit
-- showed those pages render KPI DATA but in genuinely different visual
-- primitives (compare-to-network rows, label/value trio in panel, count
-- chip grid). Forcing them onto renderKpiTile would be a visual change,
-- not a refactor.
--
-- THIS MIGRATION:
--   1. Removes the overstated secondaries from display_kpi_tile
--   2. Adds display_compact_stat (renderCompactStat) — the new shared
--      primitive for inline label/value tiles, future-facing
--   3. Adds display_count_chip (predictive .sum-card pattern) as
--      a registry entry pointing at the existing per-page styling
--
-- The audit produced one real new helper (renderCompactStat in utils.js)
-- and corrected the registry so future capability lookups don't claim
-- a refactor target that doesn't actually apply.

BEGIN;

-- 1. Correct display_kpi_tile to reflect REAL secondaries (just analytics)
UPDATE public.canonical_capabilities
SET secondary_surfaces = ARRAY['analytics.html']::text[],
    description = 'Full RAG hero card with expandable detail. Extracted from analytics.html#kpiCard to utils.js#renderKpiTile during the Tier G consolidation pass. Other pages (hive, asset-hub, predictive) render KPI DATA but in different visual primitives — see display_compact_stat and display_count_chip for those.',
    registered_at = now()
WHERE capability_id = 'display_kpi_tile';

-- 2. Add display_compact_stat — the new shared primitive
INSERT INTO public.canonical_capabilities
  (capability_id, category, primary_surface, secondary_surfaces, retired_surfaces,
   description, extension_pattern, related_canonicals, hive_isolation)
VALUES
('display_compact_stat', 'display',
 'utils.js#renderCompactStat',
 ARRAY[]::text[],
 ARRAY[]::text[],
 'Small inline label/value tile — the "MTBF: 18d" pattern. New primitive extracted during the KPI consolidation audit. Use for stat strips on pages that show multiple compact metrics inline (asset-hub risk panel future migration, hive benchmark MTBF column, top-of-shift summaries). Distinct from renderKpiTile (full RAG hero card) and from .sum-card count chips (predictive 4-tile grid).',
 'container.innerHTML += renderCompactStat({ label, value, unit, color, sublabel, icon, href });',
 jsonb_build_object('palette', jsonb_build_array('red','orange','yellow','green','blue','grey')),
 'global'),

-- 3. Document display_count_chip as registered-but-not-consolidated
('display_count_chip', 'display',
 'predictive.html',
 ARRAY[]::text[],
 ARRAY[]::text[],
 'Predictive "Critical / High / Medium / Low" 4-tile grid pattern. Distinct visual primitive — centered alignment, big number on top, colored label. Not migrated to renderCompactStat because the layout semantics differ (4-tile summary vs inline strip). Documented here so a future Tier G.b audit can decide whether to unify or keep distinct.',
 '<div class="sum-card critical"><span class="sn">N</span><span class="sl">Critical</span></div>',
 jsonb_build_object('css_classes', jsonb_build_array('summary-row','sum-card','critical','high','medium','low')),
 'global')
ON CONFLICT (capability_id) DO UPDATE
  SET secondary_surfaces = EXCLUDED.secondary_surfaces,
      description        = EXCLUDED.description,
      extension_pattern  = EXCLUDED.extension_pattern,
      related_canonicals = EXCLUDED.related_canonicals,
      registered_at      = now();

COMMIT;
