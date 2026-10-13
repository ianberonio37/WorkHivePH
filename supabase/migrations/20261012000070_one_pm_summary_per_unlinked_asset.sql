-- ★ONE PM SUMMARY PER ASSET, EVEN WHEN THE ASSET HAS NO NODE (2026-10-12, UFAI edge walk W4662).
--
-- pm_knowledge is an asset-level summary: completions converge onto ONE row per asset through the unique index
-- pm_knowledge_one_per_asset (hive_id, asset_id). But a PM asset with no linked asset node resolves to asset_id NULL,
-- and a unique index treats every NULL as distinct - so each completion added a fresh summary row for the same asset.
-- Measured: 528 null-asset rows for 18 (hive, asset_name) pairs, about 29 copies each, every one competing in PM
-- retrieval. embed-entry now updates the existing null-asset row for that asset name instead of inserting; this
-- migration collapses the copies already written (the newest survives) and lets the database refuse a new one.

begin;

delete from public.pm_knowledge k
 using (
   select id,
          row_number() over (
            partition by coalesce(hive_id, '00000000-0000-0000-0000-000000000000'::uuid), asset_name
            order by updated_at desc nulls last, created_at desc nulls last, id
          ) as rn
     from public.pm_knowledge
    where asset_id is null
 ) d
 where k.id = d.id
   and d.rn > 1;

create unique index if not exists pm_knowledge_one_per_unlinked_asset
  on public.pm_knowledge (coalesce(hive_id, '00000000-0000-0000-0000-000000000000'::uuid), asset_name)
  where asset_id is null;

commit;
