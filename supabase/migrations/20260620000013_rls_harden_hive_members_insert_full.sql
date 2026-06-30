-- Arc G G2 — close the hive_members INSERT residuals (auth_uid-NULL + role escalation).
--
-- After 20260620000005 dropped the anon always-true insert, hive_members_insert still had CHECK
-- `auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR auth_uid IS NULL)`. Two residuals remained:
--   (1) the `auth_uid IS NULL` clause let an authenticated user insert an unlinked row into ANY hive;
--   (2) nothing constrained `role`, so a user could self-insert their OWN row (auth_uid = self) as
--       'supervisor' into an EXISTING hive — and because that row IS theirs, it is a real privilege
--       escalation (they become a supervisor of a hive they never belonged to).
--
-- THE FIX: WITH CHECK `auth_uid = auth.uid()` (no NULL path — every membership row is the caller's own)
-- AND a role guard: 'supervisor' is only allowed when the hive has no OTHER members yet — i.e. the caller
-- is CREATING the hive (the legitimate supervisor-insert at hive.html:1354). Joining inserts role='worker'
-- and is unconstrained. The "other members?" test must bypass RLS + can't subquery hive_members inline
-- from a hive_members policy (recursion), so it lives in SECURITY DEFINER `hive_has_other_members()`.
-- App co-change (hive.html): the 3 insert sites drop the dead `_authUid || null` fallback (the page
-- already redirects to sign-in when !_authUid at line 1232, so _authUid is always set here).
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): create own supervisor into a NEW empty hive PASS · join as
-- worker PASS · insert with auth_uid NULL BLOCKED · insert another user's row BLOCKED · self-insert
-- 'supervisor' into a POPULATED hive (escalation) BLOCKED.

create or replace function public.hive_has_other_members(p_hive_id uuid)
returns boolean
language sql
security definer
set search_path = pg_catalog, public
stable
as $function$
  select exists (
    select 1 from hive_members where hive_id = p_hive_id and auth_uid is distinct from auth.uid()
  )
$function$;

grant execute on function public.hive_has_other_members(uuid) to anon, authenticated;

drop policy if exists hive_members_insert on public.hive_members;
create policy hive_members_insert on public.hive_members for insert
  with check (
    auth.uid() is not null
    and auth_uid = auth.uid()
    and (role <> 'supervisor' or not public.hive_has_other_members(hive_id))
  );
