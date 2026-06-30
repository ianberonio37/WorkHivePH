-- Arc G G2 — make worker_profiles PERSONAL (it holds PII: email/username/display_name) — was open-read.
--
-- worker_profiles had `profiles open read USING(true)` so any user could read every worker's EMAIL and
-- username/display_name. Every app read is own-scoped (.eq('auth_uid', self)) EXCEPT the signup
-- username-uniqueness check, which reads across all users by username (anonymously, before a session
-- exists). Personal-scoping the table directly would break that check (it would always say "available").
--
-- THE FIX: a SECURITY DEFINER `check_username_available(text)` that returns ONLY a boolean (no PII) for the
-- anon signup path, + a personal (auth_uid = auth.uid()) read policy on the table itself. index.html's two
-- direct username reads are switched to the RPC in the same change. Insert/update-own policies are kept.
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): RPC anon -> taken=false / free=true; anon direct table read = 0;
-- a member reads own profile (1) and 0 others. All 15 rows are backfilled (0 null auth_uid).

create or replace function public.check_username_available(p_username text)
returns boolean
language sql
security definer
set search_path = pg_catalog, public
stable
as $function$
  select not exists (select 1 from worker_profiles where lower(username) = lower(p_username))
$function$;

grant execute on function public.check_username_available(text) to anon, authenticated;

drop policy if exists "profiles open read" on public.worker_profiles;
drop policy if exists profiles_read_own on public.worker_profiles;
create policy profiles_read_own on public.worker_profiles for select
  using (auth.uid() is not null and auth_uid = auth.uid());
