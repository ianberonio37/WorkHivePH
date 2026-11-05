-- ★NO PRICE EXISTED ANYWHERE, SO "WHAT DID THIS VEHICLE COST US THIS MONTH" HAD NO ANSWER (2026-11-06, GJ M9 J10 hop 4:
-- "the driver's work in the owner's cost").
--
-- A fleet owner's month is units, PMs, the driver's log and the cost. The first three are on the platform; the fourth
-- was not computable: no public table carries a cost or a price (inventory_items has part number, name, unit, qty -
-- no unit cost; inventory_transactions has qty_change and job_ref - no cost; there is no labour rate). Maintenance
-- cost per asset is a core CMMS figure, and the parts half of it needs exactly one new fact: what a part costs.
--
-- 1. inventory_items.unit_cost (PHP, nullable - "not recorded" is never 0), set on the inventory page's part form; who
--    set it and when are stamped by the server from the caller's own profile, never sent by a client (the same binding
--    as the scope item's author, 20261106000005).
-- 2. v_inventory_items_truth carries the three (appended last; security_invoker said again).
-- 3. parts_cost_by_asset(hive, days): per machine, the parts used in the period's logbook entries x each part's unit
--    cost, joined by the part's ID (never by its name - a name is not an identity, and the 848 seeded entries that hold
--    only {name, qty} are honestly UNPRICED, not guessed). It returns what it could and could not price, so the page can
--    say its basis: "parts at today's unit cost, N of M priced; labour and outside services not counted" (a figure
--    that counts one half must name the half it leaves out). Security invoker: the reader's own RLS on the logbook.

BEGIN;

ALTER TABLE public.inventory_items
  ADD COLUMN IF NOT EXISTS unit_cost numeric(12,2),
  ADD COLUMN IF NOT EXISTS unit_cost_set_by text,
  ADD COLUMN IF NOT EXISTS unit_cost_set_at timestamptz;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'inventory_items_unit_cost_sane') THEN
    ALTER TABLE public.inventory_items ADD CONSTRAINT inventory_items_unit_cost_sane
      CHECK (unit_cost IS NULL OR (unit_cost >= 0 AND unit_cost <= 10000000));
  END IF;
END $$;

CREATE OR REPLACE FUNCTION public.tg_inventory_items_bind_unit_cost()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE v_name text;
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.unit_cost IS NOT DISTINCT FROM OLD.unit_cost THEN
    NEW.unit_cost_set_by := OLD.unit_cost_set_by;   -- an edit that leaves the price alone leaves its stamp alone
    NEW.unit_cost_set_at := OLD.unit_cost_set_at;
    RETURN NEW;
  END IF;
  IF NEW.unit_cost IS NULL THEN
    NEW.unit_cost_set_by := NULL;
    NEW.unit_cost_set_at := NULL;
    RETURN NEW;
  END IF;
  IF auth.uid() IS NOT NULL THEN
    SELECT display_name INTO v_name FROM public.worker_profiles WHERE auth_uid = auth.uid() LIMIT 1;
    IF v_name IS NULL THEN
      SELECT worker_name INTO v_name FROM public.hive_members
       WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    END IF;
    NEW.unit_cost_set_by := v_name;        -- always the caller's own name; a client-sent value is overwritten
  ELSIF TG_OP = 'UPDATE' THEN
    NEW.unit_cost_set_by := coalesce(NEW.unit_cost_set_by, OLD.unit_cost_set_by);   -- a seeder or backend write
  END IF;
  NEW.unit_cost_set_at := now();
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_inventory_items_bind_unit_cost ON public.inventory_items;
CREATE TRIGGER trg_inventory_items_bind_unit_cost
  BEFORE INSERT OR UPDATE ON public.inventory_items
  FOR EACH ROW EXECUTE FUNCTION public.tg_inventory_items_bind_unit_cost();

REVOKE ALL ON FUNCTION public.tg_inventory_items_bind_unit_cost() FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE VIEW public.v_inventory_items_truth WITH (security_invoker = true) AS
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
    (qty_on_hand <= (0)::numeric) AS is_out_of_stock,
    ((qty_on_hand <= (0)::numeric) OR ((min_qty > (0)::numeric) AND (qty_on_hand <= min_qty))) AS is_low_stock,
    ((min_qty > (0)::numeric) AND (qty_on_hand <= (min_qty / 2.0))) AS is_critical_low,
    lead_time_days,
    rejection_reason,
    auth_uid,
    photo_path,
    photo_thumb_path,
    unit_cost,
    unit_cost_set_by,
    unit_cost_set_at
   FROM inventory_items i
  WHERE (deleted_at IS NULL);

-- the machine is named as its owner knows it: the asset's NAME beside the code the logbook carries (for a vehicle that
-- code is its plate, so "NBX 6851" alone never told an owner which truck it was - walked, GJ M9 J10 hand-off 4)
DROP FUNCTION IF EXISTS public.parts_cost_by_asset(uuid, integer);
CREATE FUNCTION public.parts_cost_by_asset(p_hive_id uuid, p_period_days integer DEFAULT 30)
 RETURNS TABLE(asset_node_id uuid, machine text, parts_cost numeric, priced_lines bigint, unpriced_lines bigint,
               entries bigint, last_logged_by text, last_logged_at timestamptz, asset_name text)
 LANGUAGE sql
 STABLE
 SECURITY INVOKER
 SET search_path TO 'public'
AS $function$
  WITH lines AS (
    SELECT l.id AS entry_id, l.asset_node_id, l.machine, l.worker_name, l.created_at,
           CASE WHEN (pu->>'qty') ~ '^\s*[0-9]+(\.[0-9]+)?\s*$' THEN btrim(pu->>'qty')::numeric END AS qty,
           i.unit_cost
      FROM public.logbook l
      CROSS JOIN LATERAL jsonb_array_elements(CASE WHEN jsonb_typeof(l.parts_used) = 'array' THEN l.parts_used ELSE '[]'::jsonb END) pu
      LEFT JOIN public.inventory_items i ON i.id = (pu->>'partId') AND i.hive_id = l.hive_id
     WHERE l.hive_id = p_hive_id
       AND l.deleted_at IS NULL
       AND l.created_at >= now() - make_interval(days => greatest(1, least(coalesce(p_period_days, 30), 366)))
  )
  SELECT ln.asset_node_id,
         max(ln.machine),
         round(sum(ln.qty * ln.unit_cost) FILTER (WHERE ln.unit_cost IS NOT NULL AND ln.qty IS NOT NULL), 2),
         count(*) FILTER (WHERE ln.unit_cost IS NOT NULL AND ln.qty IS NOT NULL),
         count(*) FILTER (WHERE ln.unit_cost IS NULL OR ln.qty IS NULL),
         count(DISTINCT ln.entry_id),
         (array_agg(ln.worker_name ORDER BY ln.created_at DESC))[1],
         max(ln.created_at),
         max(an.name)
    FROM lines ln
    LEFT JOIN public.asset_nodes an ON an.id = ln.asset_node_id
   GROUP BY ln.asset_node_id, CASE WHEN ln.asset_node_id IS NULL THEN ln.machine END
   ORDER BY 3 DESC NULLS LAST, 6 DESC
   LIMIT 200;
$function$;

REVOKE ALL ON FUNCTION public.parts_cost_by_asset(uuid, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.parts_cost_by_asset(uuid, integer) TO authenticated, service_role;

COMMIT;
