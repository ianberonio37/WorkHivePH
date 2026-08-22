-- tile_equals_view: the dashboard RPC's numbers equal the truth views they summarise — recomputed
-- live for open jobs, critical/high risks, low stock, and PM overdue (distinct assets). The RPC is
-- called under an active member's claims (it derives the hive from the caller).
-- expect: open_jobs_agree \| t
-- expect: risks_agree \| t
-- expect: low_stock_agree \| t
-- expect: pm_overdue_agree \| t
CREATE TEMP TABLE _tv AS
SELECT hm.hive_id, hm.auth_uid FROM hive_members hm
WHERE hm.status='active' AND hm.auth_uid IS NOT NULL LIMIT 1;
BEGIN;
SELECT set_config('request.jwt.claims',
  json_build_object('sub', (SELECT auth_uid FROM _tv)::text, 'role', 'authenticated')::text, true);
CREATE TEMP TABLE _dash AS SELECT get_hive_dashboard((SELECT hive_id FROM _tv)) AS j;
SELECT 'open_jobs_agree | ' || (
  ((SELECT j->>'open_jobs_count' FROM _dash)::int)
  = (SELECT count(*) FROM v_logbook_truth WHERE hive_id = (SELECT hive_id FROM _tv) AND status = 'Open'));
SELECT 'risks_agree | ' || (
  ((SELECT j->>'risks_count' FROM _dash)::int)   -- the fn's key is risks_count
  = (SELECT count(*) FROM v_risk_truth WHERE hive_id = (SELECT hive_id FROM _tv)
      AND risk_level IN ('critical','high')));
SELECT 'low_stock_agree | ' || (
  ((SELECT j->>'low_stock_count' FROM _dash)::int)
  = (SELECT count(*) FROM v_inventory_items_truth WHERE hive_id = (SELECT hive_id FROM _tv)
      AND is_low_stock));
SELECT 'pm_overdue_agree | ' || (
  ((SELECT j->>'pm_overdue_count' FROM _dash)::int)
  = (SELECT count(DISTINCT pm_asset_id) FROM v_pm_scope_items_truth
      WHERE hive_id = (SELECT hive_id FROM _tv) AND is_overdue));
ROLLBACK;
DROP TABLE _tv;
