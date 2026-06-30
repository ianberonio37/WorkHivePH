-- Arc G G2 — scope the skill matrix to the owning worker (was cross-hive readable via USING(true)).
--
-- skill_profiles and skill_badges carry auth_uid but their SELECT was an always-true policy (plus a legacy
-- allow_anon_all on skill_profiles), so any user could read every worker's skills/badges across all hives.
-- Evidence: EVERY app read filters by `worker_name = WORKER_NAME` (own) — skillmatrix.html:625, resume.html
-- 847/849; no supervisor/team view reads other workers' skill rows directly. So the correct, simplest model
-- is PERSONAL (auth_uid-scoped), matching schedule_items / skill_exam_attempts. All rows are backfilled
-- (0 null auth_uid), so a pure auth_uid policy orphans nothing; the existing auth-scoped write policy stays.
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): owner reads own rows (skill_profiles 1 / skill_badges 19),
-- 0 of other workers' rows, anon 0.

drop policy if exists allow_anon_all     on public.skill_profiles;
drop policy if exists skill_profiles_read on public.skill_profiles;
create policy skill_profiles_read on public.skill_profiles for select
  using (auth.uid() is not null and auth_uid = auth.uid());

drop policy if exists allow_anon_all   on public.skill_badges;
drop policy if exists skill_badges_read on public.skill_badges;
create policy skill_badges_read on public.skill_badges for select
  using (auth.uid() is not null and auth_uid = auth.uid());
