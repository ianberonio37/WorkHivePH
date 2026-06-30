-- Arc G G2 — scope worker_achievements to own + same-hive members (was globally anon-readable).
--
-- worker_achievements carries auth_uid (personal gamification: achievement_id, current_level, xp_total,
-- last_action_at, worker_name) but RLS was DISABLED and an inert legacy `ach_worker_read USING(true)`
-- policy + an anon SELECT grant left every worker's XP/levels/activity readable by ANY anonymous client
-- across ALL hives (proven live: anon SELECT count(*) = 55). migs 000010/000011 hardened the sibling
-- personal tables (skill_profiles/skill_badges/worker_profiles) but MISSED this one — the rls_coverage
-- gate only counts hive_id tables, and this is auth_uid-keyed (a per-OBJECT gap the sub-layer aggregate hid).
--
-- The correct model is own + same-hive (NOT personal-only). Evidence from achievements.html:
--   • own read   — v_worker_achievements_truth .eq('worker_name', WORKER_NAME)         (line 980)
--   • standings  — v_worker_achievements_truth .in('worker_name', <hive-member names>) (line 852)
-- There is NO global/cross-hive read, so a personal-only policy (like skill_matrix) would BREAK the in-hive
-- standings leaderboard. Mirrors the platform's user_hive_ids() helper (recursion-safe SECURITY DEFINER).
--
-- Writes go through award_achievement_xp (SECURITY DEFINER → bypasses RLS) so writes are unaffected, and the
-- own-row realtime subscription (filter worker_name=eq.WORKER_NAME) still delivers under the read policy.
--
-- VERIFIED LIVE (ROLLBACK'd, two-tenant, 2026-06-20):
--   Pablo (hive A): own 5 · same-hive peer David 5 · cross-hive Bryan 0 · total visible 21 (hive A only)
--   Leandro (hive B): own 3 · cross-hive Pablo 0 · total visible 12 (hive B only)
--   anon (empty claims): 0   (was 55 before the fix)

-- worker_names visible to the current user = members of every hive the caller actively belongs to.
-- SECURITY DEFINER so it bypasses hive_members RLS (no recursion, no visibility gap); search_path locked.
create or replace function public.user_hive_worker_names()
returns setof text
language sql
stable
security definer
set search_path to 'public'
as $fn$
  select distinct worker_name
  from public.hive_members
  where hive_id in (select public.user_hive_ids())
    and status = 'active'
$fn$;

revoke all on function public.user_hive_worker_names() from public;
grant execute on function public.user_hive_worker_names() to anon, authenticated;

-- drop the inert legacy-open policies, enable RLS, replace with own + same-hive read.
-- (drop the new policy name too so this migration is re-runnable / idempotent.)
drop policy if exists ach_worker_read           on public.worker_achievements;
drop policy if exists allow_anon_all            on public.worker_achievements;
drop policy if exists worker_achievements_read  on public.worker_achievements;

alter table public.worker_achievements enable row level security;

create policy worker_achievements_read on public.worker_achievements for select
  using (
    auth.uid() is not null and (
      auth_uid = auth.uid()
      or worker_name in (select public.user_hive_worker_names())
    )
  );
