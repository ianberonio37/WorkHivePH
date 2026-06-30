-- Arc G G2 — restore tenant isolation on hive_members (auth-migration enforcement, step 2 / highest-harm).
--
-- THE FINDING: hive_members (the membership ROOT) carried legacy pre-auth permissive `USING (true)` policies:
--   allow_anon_all (ALL), anon_select_members + hive_members_read (SELECT), anon_delete_members (DELETE),
--   anon_upsert_members (UPDATE) — all granted to anon. DEFINER-RLS aside, these mean ANY anonymous client
--   could read every hive's full membership (worker names, auth_uids), DELETE any member (kick anyone out of
--   any hive), and UPDATE any member (self-promote to supervisor in any hive). The worst of the G2 class.
--
-- THE CHALLENGE (why this needs a helper, not an inline subquery): a SELECT policy ON hive_members that
-- subqueries hive_members RECURSES (Postgres throws "infinite recursion detected in policy"), and 64 OTHER
-- tables' policies already subquery hive_members (`hive_id IN (SELECT hive_id FROM hive_members WHERE
-- auth_uid=auth.uid())`). So we add a SECURITY DEFINER helper `user_hive_ids()` that reads the CALLER's own
-- hives (WHERE auth_uid=auth.uid()) bypassing RLS — self-scoped (no cross-tenant leak), read-only (not a
-- mutator, so validate_definer_tenant_gate does not flag it), search_path-locked.
--
-- THE FIX: a scoped SELECT policy (read your own membership row via the simple auth_uid=auth.uid() clause —
-- which also bootstraps + keeps the 64 dependent subqueries working — OR co-members of your hives via the
-- DEFINER helper) + drop the 5 always-true policies. The scoped UPDATE/DELETE policies (hive_members_update,
-- hive_members_delete = auth_uid=auth.uid()) already exist and remain. INSERT is intentionally left for now
-- (anon_insert_members is signup/join-coupled — lower harm; a separate careful pass).
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): member reads own-hive members (5) + cross-hive 0 + a dependent
-- table (inventory_items) still returns the member's 27 rows (NO recursion, 64 dependent policies intact) +
-- anon sees 0. No errors.

create or replace function public.user_hive_ids()
returns setof uuid
language sql
security definer
set search_path = 'public'
stable
as $function$
  select hive_id from hive_members where auth_uid = auth.uid() and status = 'active'
$function$;

grant execute on function public.user_hive_ids() to authenticated, anon, service_role;

create policy hive_members_read_scoped on public.hive_members for select
  using (auth_uid = auth.uid() or hive_id in (select public.user_hive_ids()));

drop policy if exists allow_anon_all       on public.hive_members;  -- ALL true
drop policy if exists anon_select_members  on public.hive_members;  -- SELECT true
drop policy if exists hive_members_read    on public.hive_members;  -- SELECT true
drop policy if exists anon_delete_members  on public.hive_members;  -- DELETE true (kick anyone)
drop policy if exists anon_upsert_members  on public.hive_members;  -- UPDATE true (self-promote)
