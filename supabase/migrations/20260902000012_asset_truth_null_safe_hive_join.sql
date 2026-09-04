-- VEHICLE SEED VM5 (2026-09-02): v_asset_truth counted a SOLO asset's history as ZERO.
--
-- Found live on the 360: the timeline listed 5 logbook entries + 1 PM completion while the
-- stat tiles read "0 / 0" on the same screen. Every aggregate in the view joins on
-- `l.hive_id = n.hive_id` — and for a solo asset both sides are NULL, where SQL equality is
-- UNKNOWN, so every count collapses to 0. The classic NULL-join: the check and the action
-- read different rows. `IS NOT DISTINCT FROM` is the null-safe equality: identical semantics
-- for hive assets, and NULL pairs with NULL for solo.
--
-- CREATE OR REPLACE strips reloptions (the exact hole 20260902000006 opened on the scope
-- view), so security_invoker is re-asserted in the SAME migration.

CREATE OR REPLACE VIEW public.v_asset_truth AS
SELECT id AS asset_id,
    hive_id,
    auth_uid,
    parent_id,
    level,
    tag,
    name,
    iso_class,
    criticality,
    location,
    manufacturer,
    model,
    serial_no,
    install_date,
    external_ids,
    legacy_asset_id,
    pm_asset_id,
    status,
    submitted_by,
    approved_by,
    approved_at,
    created_at,
    updated_at,
    ( SELECT count(*) AS count
           FROM logbook l
          WHERE NOT (l.hive_id IS DISTINCT FROM n.hive_id) AND l.asset_node_id = n.id) AS lifetime_logbook_entries,
    ( SELECT max(l.created_at) AS max
           FROM logbook l
          WHERE NOT (l.hive_id IS DISTINCT FROM n.hive_id) AND l.asset_node_id = n.id AND l.maintenance_type = 'Breakdown / Corrective'::text) AS last_failure_at,
    ( SELECT count(*) AS count
           FROM pm_completions pc
          WHERE NOT (pc.hive_id IS DISTINCT FROM n.hive_id) AND pc.asset_id = n.pm_asset_id AND pc.status = 'done'::text) AS pm_completed_count,
    ( SELECT count(*) AS count
           FROM asset_edges e
          WHERE NOT (e.hive_id IS DISTINCT FROM n.hive_id) AND (e.from_node_id = n.id OR e.to_node_id = n.id)) AS edge_count,
    ( SELECT count(*) AS count
           FROM pm_completions pc
          WHERE NOT (pc.hive_id IS DISTINCT FROM n.hive_id) AND pc.asset_id = n.pm_asset_id AND pc.status = 'skipped'::text) AS pm_skipped_count
   FROM asset_nodes n
  WHERE status = 'approved'::text;

ALTER VIEW public.v_asset_truth SET (security_invoker = true);
