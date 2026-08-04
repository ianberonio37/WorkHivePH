-- ANY SIGNED-IN USER COULD READ THE WHOLE PLATFORM-ADMIN ROSTER.
--
-- Found 2026-08-04 by the live-MCP walk, signed in as a real non-admin (David Velasco) to test the
-- BE identity rows. The UI held: the Admin link on marketplace.html stayed display:none, and typing
-- the admin URL directly hit the "Platform Admins Only" gate with main-content hidden. The server
-- held too: a forged-identity insert came back 403 42501 (RLS), and three cross-tenant writes matched
-- 0 rows with the target row's updated_at unmoved.
--
-- What did NOT hold was the roster itself. `select worker_name from marketplace_platform_admins`
-- returned BOTH admins to David:
--
--     mkt_admins_read | SELECT | using (auth.uid() IS NOT NULL)
--
-- That predicate asks whether SOMEONE is signed in. It never asks WHO -- the same shape as the
-- `using (id = 1)` treasury policy this platform already fixed once. The consequence is not a write
-- or a tenant leak, it is TARGETING: it hands every signed-in user the exact list of accounts worth
-- phishing, and on a marketplace where those two accounts approve listings, verify sellers and mint
-- credits, "who holds the keys" is not public information.
--
-- SELF-ROW ONLY. Every consumer already filters to the caller's own name(s) -- marketplace.html's
-- updateAdminLink does .eq('worker_name', WORKER_NAME), marketplace-admin.html's
-- verifyPlatformAdmin does the same, and utils.js resolves the caller's names from v_worker_truth by
-- auth_uid and then .in()s them -- so nothing on the platform needs to LIST admins, and a self-only
-- read keeps every one of those checks working: an admin still sees their own row (gate opens), a
-- non-admin sees zero rows (gate fires, fail-closed).
--
-- The two authority functions are unaffected because both are SECURITY DEFINER and bypass RLS here:
-- is_platform_admin() joins worker_profiles.display_name to this table on auth.uid(), and
-- is_marketplace_admin() matches auth_worker_names(). The write policy keeps using the latter.
--
-- The subquery is safe under RLS: worker_profiles carries `profiles_read_own`
-- (auth.uid() IS NOT NULL AND auth_uid = auth.uid()), so a caller resolves exactly their own
-- display_name and nobody else's.

drop policy if exists mkt_admins_read on public.marketplace_platform_admins;

create policy mkt_admins_read_self
  on public.marketplace_platform_admins
  for select
  to public
  using (
    worker_name in (
      select wp.display_name
      from public.worker_profiles wp
      where wp.auth_uid = auth.uid()
    )
  );

comment on policy mkt_admins_read_self on public.marketplace_platform_admins is
  'Self-row only. A caller may confirm THEIR OWN admin grant (which is all any client check needs) '
  'and may not enumerate the roster. Replaced mkt_admins_read, whose using(auth.uid() IS NOT NULL) '
  'checked that someone was signed in without ever checking who.';
