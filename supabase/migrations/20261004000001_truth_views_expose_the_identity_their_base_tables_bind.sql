-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- The truth views expose the IDENTITY their base tables already bind (BRP class B)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Ian, 2026-10-04: "in my logbook, in the select an asset, there is nothing there, but I can see it in
-- my asset hub". Root cause on that surface: ownership was asked by `worker_name` (a localStorage
-- display string) while asset-hub asked by `auth_uid` — and `bind_asset_nodes_submitter()` freezes
-- worker_name for personal rows (its lookup joins on `hive_id = NEW.hive_id`, never true against NULL)
-- while always binding auth_uid. Fixed and gated on the picker.
--
-- The sweep that followed found 80 sites of the same shape, and 21 of them could not be fixed at all:
-- the truth VIEWS expose `worker_name` and NOT the `auth_uid` their base tables carry, so no consumer
-- can ask the ownership question correctly. hive, dayplanner, assistant, resume, inventory and
-- marketplace-seller all read "my rows" through these views. Fixing the view unlocks every reader at
-- once, which is why this lands before the per-site unions.
--
-- ★NO NEW EXPOSURE, MEASURED NOT ASSUMED. Both views are `security_invoker`, so RLS is evaluated as the
-- CALLER and a person still sees only rows they could already see. And the column itself is already
-- reachable: `anon` and `authenticated` each hold SELECT on `logbook.auth_uid` and
-- `inventory_items.auth_uid` on the BASE tables today (information_schema.column_privileges), so adding
-- it to the view hands nobody anything they could not already select.
--
-- ★security_invoker IS RESTATED ON PURPOSE. a CREATE-OR-REPLACE of a VIEW discards its reloptions (the phrase is broken up on purpose: the
-- canonical-anchor miner reads the word that FOLLOWS the literal "CREATE OR REPLACE VIEW" as a view
-- name, so writing it intact in prose registered a phantom view), and losing
-- `security_invoker` turns a per-caller view into one that reads as its OWNER — the exact mistake that
-- once opened `anon` to 437 rows on this platform. v_logbook_truth carries `security_invoker=on` and
-- v_inventory_items_truth `security_invoker=true` today; both are re-declared below, and the
-- verification block at the end FAILS the migration if either comes back without it.
--
-- Column order is preserved and `auth_uid` is APPENDED last, which is what CREATE OR REPLACE VIEW
-- permits: existing columns keep their name, type and position, so every existing reader is unaffected.
-- Grants survive because the object is replaced, never dropped (also asserted below).

BEGIN;

-- ── v_logbook_truth · 34 cols -> 35 ──────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_logbook_truth
WITH (security_invoker = on) AS
 SELECT l.id,
    l.hive_id,
    l.worker_name,
    l.created_at,
    l.closed_at,
    l.date,
    l.status,
    l.maintenance_type,
    l.category,
    l.machine,
    l.problem,
    l.action,
    l.root_cause,
    l.failure_consequence,
    l.downtime_hours,
    l.production_output,
    l.parts_used,
    l.readings_json,
    l.knowledge,
    l.tasklist_acknowledged,
    l.tasklist_note,
    l.photo,
    l.pm_completion_id,
    l.wo_state,
    l.wo_assigned_to,
    l.asset_node_id,
    n.tag AS asset_tag,
    n.name AS asset_node_name,
    n.iso_class AS asset_iso_class,
    n.criticality AS asset_criticality,
    n.location AS asset_location,
    l.maintenance_type ~* '(corrective|breakdown)'::text AS is_corrective,
    l.loto_applied,
    l.permit_reference,
    l.auth_uid                      -- APPENDED (BRP-B, 2026-10-04): the identity the row was bound to
   FROM logbook l
     LEFT JOIN asset_nodes n ON n.id = l.asset_node_id;

-- ── v_inventory_items_truth · 25 cols -> 26 ──────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_inventory_items_truth
WITH (security_invoker = on) AS
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
    qty_on_hand <= 0::numeric OR min_qty > 0::numeric AND qty_on_hand <= min_qty AS is_low_stock,
    min_qty > 0::numeric AND qty_on_hand <= (min_qty / 2.0) AS is_critical_low,
    lead_time_days,
    rejection_reason,
    auth_uid                        -- APPENDED (BRP-B, 2026-10-04): the identity the row was bound to
   FROM inventory_items i;

-- ── VERIFY IN THE SAME TRANSACTION, so a half-applied change rolls back ──────────────────────────
DO $$
DECLARE
  v text;
  opts text[];
  n_cols int;
  n_grants int;
BEGIN
  FOREACH v IN ARRAY ARRAY['v_logbook_truth', 'v_inventory_items_truth'] LOOP
    -- 1 · the identity column is actually there
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = v AND column_name = 'auth_uid') THEN
      RAISE EXCEPTION '% did not gain auth_uid', v;
    END IF;

    -- 2 · security_invoker SURVIVED the replace. Without this the view would read as its owner and
    --     bypass RLS for every caller - strictly worse than the bug being fixed.
    SELECT c.reloptions INTO opts
      FROM pg_class c JOIN pg_namespace ns ON ns.oid = c.relnamespace
     WHERE ns.nspname = 'public' AND c.relname = v;
    IF opts IS NULL OR NOT (
         'security_invoker=on' = ANY(opts) OR 'security_invoker=true' = ANY(opts)) THEN
      RAISE EXCEPTION '% lost security_invoker (reloptions=%) - a CREATE-OR-REPLACE of a VIEW discards '
                      'reloptions, and an owner-rights view here would bypass RLS', v, opts;
    END IF;

    -- 3 · the reader grants survived (replace must not drop privileges)
    SELECT count(*) INTO n_grants FROM information_schema.role_table_grants
     WHERE table_schema = 'public' AND table_name = v
       AND grantee IN ('anon', 'authenticated') AND privilege_type = 'SELECT';
    IF n_grants < 2 THEN
      RAISE EXCEPTION '% lost a reader SELECT grant (found % of 2)', v, n_grants;
    END IF;
  END LOOP;

  -- 4 · the column counts moved by exactly one each: nothing was dropped or reordered away
  SELECT count(*) INTO n_cols FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'v_logbook_truth';
  IF n_cols <> 35 THEN RAISE EXCEPTION 'v_logbook_truth has % columns, expected 35', n_cols; END IF;
  SELECT count(*) INTO n_cols FROM information_schema.columns
   WHERE table_schema = 'public' AND table_name = 'v_inventory_items_truth';
  IF n_cols <> 26 THEN RAISE EXCEPTION 'v_inventory_items_truth has % columns, expected 26', n_cols; END IF;

  RAISE NOTICE 'BRP-B: both truth views expose auth_uid, security_invoker intact, grants intact';
END $$;

COMMIT;
