-- ci_domain_truth inventory CI2: "lead time is stated wherever a reorder is suggested."
-- The datum existed NOWHERE — no lead-time column on inventory_items, so the reorder banner could not
-- state one and a person deciding when to order had no way to know how long delivery takes. This adds
-- the capture point, not an invented value: a nullable per-part lead_time_days, editable on the part
-- card. The banner states it when known and says "not recorded" when null — a reorder must never show
-- a lead time nobody entered.
--
-- Re-runnable: ADD COLUMN IF NOT EXISTS; CREATE OR REPLACE VIEW appends the new column at the END of
-- the select list (Postgres forbids reordering existing view columns in-place).

ALTER TABLE public.inventory_items
  ADD COLUMN IF NOT EXISTS lead_time_days integer
  CONSTRAINT inventory_items_lead_time_days_sane
    CHECK (lead_time_days IS NULL OR (lead_time_days >= 0 AND lead_time_days <= 365));

-- The truth view enumerates its columns, so the new column must be carried through explicitly or no
-- reader of v_inventory_items_truth ever sees it. security_invoker restated because CREATE OR REPLACE
-- must not silently drop the posture the view already has (verified live before this migration:
-- reloptions = {security_invoker=true}).
CREATE OR REPLACE VIEW public.v_inventory_items_truth
WITH (security_invoker = true) AS
 SELECT id,
    hive_id,
    worker_name,
    part_number,
    part_name,
    category,
    unit,
    qty_on_hand,
    min_qty,
    min_qty AS reorder_point,
    bin_location,
    linked_asset_node_ids,
    notes,
    photo,
    status,
    submitted_by,
    approved_by,
    approved_at,
    created_at,
    updated_at,
    qty_on_hand <= 0::numeric AS is_out_of_stock,
    min_qty > 0::numeric AND qty_on_hand <= min_qty AS is_low_stock,
    min_qty > 0::numeric AND qty_on_hand <= (min_qty / 2.0) AS is_critical_low,
    lead_time_days
   FROM inventory_items i;
