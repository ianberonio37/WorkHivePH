-- Arc G G2 — restore tenant isolation on 5 core hive-private tables (auth-migration enforcement, step 1).
--
-- THE FINDING (Arc G G2 live two-tenant sweep, 2026-06-20): these tables have a CORRECT hive-scoped RLS
-- policy AND a legacy pre-auth permissive `USING (true)` policy (`allow_anon_all`, `open`, `anon read…`,
-- `anon insert…`). Postgres OR's permissive policies, so the always-true one DEFEATS the scoped one — RLS
-- was effectively OFF and any anon/cross-hive client could read+write every hive's inventory, PM assets,
-- PM completions, PM scope, and engineering calcs. This is the pre-auth open-RLS state (project_rls_decision);
-- the Supabase-Auth migration added the proper auth.uid() policies but never removed the legacy-open ones.
--
-- WHY THIS IS SAFE NOW (verified, not assumed):
--   1. Each table already has a proper scoped SELECT + write policy (inventory_items_read/_write, etc.) that
--      fully covers authenticated access — dropping the legacy-open one orphans nothing.
--   2. Live ROLLBACK'd proof (per table): after the drop, a logged-in member still reads their own hive
--      (27/30/576/10/143 rows) AND cross-hive reads = 0 AND anon sees 0. Isolation restored, no breakage.
--   3. Guest access was removed by the auth migration (submitGuest -> signup), so every query to these
--      hive-private tables carries an auth session — no anon-key path remains.
-- Ratcheted by validate_rls_no_permissive_bypass.py (9 -> 4 exposed). The remaining 4 (hive_members,
-- parts_records, ai_user_rate_limits, wh_traces) need a NEW scoped policy written first — a later step.

drop policy if exists allow_anon_all on public.inventory_items;
drop policy if exists "open"          on public.inventory_items;

drop policy if exists allow_anon_all on public.pm_assets;
drop policy if exists allow_anon_all on public.pm_completions;
drop policy if exists allow_anon_all on public.engineering_calcs;

drop policy if exists allow_anon_all              on public.pm_scope_items;
drop policy if exists "anon read pm_scope_items"  on public.pm_scope_items;
drop policy if exists "anon insert pm_scope_items" on public.pm_scope_items;
