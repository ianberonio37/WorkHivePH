-- Arc G G2 — restore PERSONAL (auth_uid) isolation on 2 tables with a legacy always-true policy.
--
-- The same legacy `allow_anon_all USING(true)` pattern that defeated hive isolation also defeats PERSONAL
-- isolation on auth_uid-owned tables: schedule_items (your day-planner) and skill_exam_attempts (your exam
-- attempts) each already have a proper auth_uid-scoped read + write policy, but the always-true policy
-- OR-defeated them — so any user could read/write anyone's schedule and exam attempts. Drop the redundant
-- always-true policy; the proper auth-scoped policies remain.
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): after the drop, a user reads only their OWN rows
-- (schedule_items 6 / skill_exam_attempts 20), 0 of other users' rows, anon 0.
--
-- NOT touched here (need a design call — their READ may be team-visible by design): worker_profiles
-- (display-name PII, joined widely for name display), skill_profiles + skill_badges (skill matrix is
-- typically visible to supervisors/teammates). Those keep their open read pending a per-table decision.

drop policy if exists allow_anon_all on public.schedule_items;
drop policy if exists allow_anon_all on public.skill_exam_attempts;
