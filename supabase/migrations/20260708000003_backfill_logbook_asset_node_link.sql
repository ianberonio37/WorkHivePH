-- 20260708000000_backfill_logbook_asset_node_link.sql
-- ============================================================================
-- Deep-walk CL1 finding (2026-07-08): logbook entries whose `machine` EXACTLY
-- matches a registered asset's `tag` were left asset_node_id = NULL when the
-- asset wasn't resolved via the asset-picker (free-text machine, or the voice
-- pre-fill path which set the machine STRING but discarded the router-resolved
-- asset_id). Result: v_asset_truth.lifetime_logbook_entries counts ONLY FK-linked
-- rows (WHERE l.asset_node_id = n.id), so asset-brain, analytics, and the asset
-- timeline UNDERCOUNT an asset's history. Measured live on Baguio Textile Mills:
-- PB-001 showed 18 lifetime entries via the canonical view but 37 rows carry
-- machine = 'PB-001'; platform-wide 415 / 902 entries (46%) name a real tag yet
-- are unlinked.
--
-- This backfill deterministically links an unlinked entry to the asset whose tag
-- it EXACTLY names within the SAME hive. Safe + idempotent by construction:
--   * only touches rows where asset_node_id IS NULL (never re-points a linked row);
--   * exact tag match, hive-scoped;
--   * (hive_id, tag) is unique in asset_nodes (verified: 0 duplicate-tag groups),
--     so the join is 1:1 and can never mis-link.
-- Re-running affects 0 rows. On a fresh DB (migrations run before seed) this is a
-- no-op; the seeder + the client write-path resolution are the forward guards.
-- ============================================================================

UPDATE public.logbook l
SET    asset_node_id = a.id
FROM   public.asset_nodes a
WHERE  l.asset_node_id IS NULL
  AND  l.hive_id = a.hive_id
  AND  l.machine = a.tag;
