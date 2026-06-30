-- Arc G G4 — make the v_*_truth views security_invoker so they RESPECT base-table RLS (the read-path fix).
--
-- ★ THE BIGGEST FINDING of the Arc G sweep: 37 of 38 `v_*_truth` views ran as their OWNER (no
-- security_invoker) and were granted SELECT to anon + authenticated. A Postgres view that is not
-- `security_invoker` executes with the VIEW OWNER's privileges and BYPASSES RLS on its base tables. Since
-- the frontend (and any PostgREST client) reads through these truth views — the canonical read API — the
-- base-table RLS hardened across this arc was BYPASSED for every read: proven live — a hive-A member got
-- `inventory_items` cross-hive = 0 via the TABLE (RLS works) but = 27 via `v_inventory_items_truth` (the
-- view leaked). Read-path tenant isolation was effectively off platform-wide, regardless of base RLS.
--
-- THE FIX: `ALTER VIEW … SET (security_invoker = true)` so each view runs as the CALLER and its base-table
-- RLS applies. VERIFIED LIVE (ROLLBACK'd, 2026-06-20): flipping all 37 → 27 hive-scoped truth views now
-- isolate (member reads own-hive>0, cross-hive 0, anon 0), **0 views broke** (no join hides a member's own
-- rows), and the only still-cross-hive views (v_community_posts_truth, v_marketplace_listings_truth,
-- v_insurance_bridge_truth) correctly inherit their base table's BY-DESIGN cross-hive policy. Idempotent.

do $mig$
declare v record;
begin
  for v in
    select c.relname
    from pg_class c join pg_namespace n on n.oid = c.relnamespace
    where n.nspname = 'public' and c.relkind = 'v' and c.relname like 'v\_%truth'
      and (c.reloptions is null or not c.reloptions::text ~* 'security_invoker=(on|true)')
  loop
    execute format('alter view public.%I set (security_invoker = true)', v.relname);
  end loop;
end $mig$;
