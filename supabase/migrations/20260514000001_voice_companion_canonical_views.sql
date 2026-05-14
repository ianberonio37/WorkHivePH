-- Voice Companion Phase 1: Canonical Views for Platform Scraper
-- Creates the v_*_truth views needed by voice-handler.js platform scraper agent
-- Date: 2026-05-14

-- v_pm_truth: PM tasks with status and due dates
CREATE OR REPLACE VIEW public.v_pm_truth AS
SELECT
  pm.id,
  pm.hive_id,
  pm.asset_id,
  pm.template_id,
  pm.name,
  pm.status,
  pm.next_due_date,
  pm.last_completed_at,
  pm.created_at,
  pm.updated_at
FROM public.preventive_maintenance pm
WHERE pm.deleted_at IS NULL;

-- v_inventory_truth: Inventory items with stock status
CREATE OR REPLACE VIEW public.v_inventory_truth AS
SELECT
  inv.id,
  inv.hive_id,
  inv.name,
  inv.category,
  inv.qty_current,
  inv.qty_min,
  inv.qty_max,
  inv.reorder_qty,
  inv.supplier_id,
  inv.last_restock_at,
  inv.created_at,
  inv.updated_at,
  CASE
    WHEN inv.qty_current = 0 THEN 'out'
    WHEN inv.qty_current <= inv.qty_min THEN 'low'
    ELSE 'ok'
  END AS stock_level
FROM public.inventory_items inv
WHERE inv.deleted_at IS NULL;

-- v_risk_truth: Asset risk scores with MTBF
CREATE OR REPLACE VIEW public.v_risk_truth AS
SELECT
  ast.id AS asset_id,
  ast.name AS asset_name,
  ast.hive_id,
  COALESCE(ast.risk_score, 0) AS risk_score,
  COALESCE(ast.risk_level, 'unknown') AS risk_level,
  COALESCE(
    EXTRACT(DAY FROM (NOW() - INTERVAL '30 days' * (
      SELECT COUNT(*) FILTER (WHERE status = 'completed')
      FROM public.preventive_maintenance
      WHERE asset_id = ast.id AND deleted_at IS NULL
    )))::INT,
    0
  ) AS mtbf_days,
  ast.created_at,
  ast.updated_at
FROM public.assets ast
WHERE ast.deleted_at IS NULL AND ast.hive_id IS NOT NULL;

-- v_asset_truth: Equipment status summary
CREATE OR REPLACE VIEW public.v_asset_truth AS
SELECT
  ast.id,
  ast.name,
  ast.hive_id,
  ast.equipment_type,
  COALESCE(ast.status, 'unknown') AS status,
  ast.location,
  ast.risk_score,
  ast.created_at,
  ast.updated_at
FROM public.assets ast
WHERE ast.deleted_at IS NULL AND ast.hive_id IS NOT NULL;

-- v_adoption_truth: Adoption metrics (workers, hive intent)
CREATE OR REPLACE VIEW public.v_adoption_truth AS
SELECT
  h.id AS hive_id,
  h.name AS hive_name,
  COUNT(DISTINCT wh.worker_id) AS active_workers_this_week,
  COALESCE(h.intent, 'general') AS hive_intent,
  COUNT(DISTINCT vj.id) FILTER (WHERE vj.created_at > NOW() - INTERVAL '7 days') AS voice_entries_week,
  h.created_at,
  h.updated_at
FROM public.hives h
LEFT JOIN public.worker_hives wh ON h.id = wh.hive_id AND wh.deleted_at IS NULL
LEFT JOIN public.voice_journal_entries vj ON h.id = vj.hive_id
WHERE h.deleted_at IS NULL
GROUP BY h.id, h.name, h.intent, h.created_at, h.updated_at;
