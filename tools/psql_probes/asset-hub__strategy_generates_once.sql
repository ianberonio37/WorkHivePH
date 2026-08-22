-- strategy_generates_once: an approved RCM strategy materialises its PM row ONCE — every
-- written_to_pm_scope_item_id points at a real scope item, and no scope item is claimed by MORE
-- than one strategy (double-generation would double the PM workload silently).
-- expect: linked_strategies \| [1-9][0-9]*
-- expect: dangling_links \| 0
-- expect: multiclaimed_items \| 0
SELECT 'linked_strategies | ' || count(*) FROM rcm_strategies WHERE written_to_pm_scope_item_id IS NOT NULL;
SELECT 'dangling_links | ' || count(*) FROM rcm_strategies r
WHERE r.written_to_pm_scope_item_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM pm_scope_items s WHERE s.id = r.written_to_pm_scope_item_id);
SELECT 'multiclaimed_items | ' || count(*) FROM (
  SELECT written_to_pm_scope_item_id FROM rcm_strategies
  WHERE written_to_pm_scope_item_id IS NOT NULL
  GROUP BY written_to_pm_scope_item_id HAVING count(*) > 1) d;
