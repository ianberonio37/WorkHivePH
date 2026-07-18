-- 20260712000015_skill_profiles_bola_fix.sql
-- Dayplanner/Growth PDDA arc (2026-07-12) — I-axis (integrity) keystone K6.
--
-- BOLA (schema-confirmed): the sole write policy on skill_profiles was
--   skill_profiles_write  FOR ALL  TO public
--     USING      ((auth.uid() IS NOT NULL) AND ((auth_uid = auth.uid()) OR (auth_uid IS NULL)))
--     WITH CHECK ((auth.uid() IS NOT NULL))
-- Two holes:
--   (1) WITH CHECK does NOT pin auth_uid=auth.uid() → any authenticated worker can INSERT or
--       UPDATE a skill_profiles row carrying ANOTHER worker's worker_name/auth_uid, i.e. fabricate
--       or overwrite a colleague's competency targets/primary_skill (a personal-competency record).
--   (2) USING's `OR auth_uid IS NULL` branch let any authed user grab/edit unattributed legacy rows.
-- This is the same client-authorized-write class as the already-shipped community_xp lockdown
-- (20260711000000) and the pm/inventory WITH-CHECK-pins-auth_uid rule.
--
-- FIX: skill_profiles legitimately STAYS client-writable (a worker sets their OWN targets — a
-- personal preference, not a credential, mirroring schedule_items), but the write is pinned to the
-- owner: USING and WITH CHECK both require auth_uid = auth.uid(). The null-branch is dropped.
-- Safe: a live count confirmed 0 rows with auth_uid IS NULL (skill_profiles/skill_badges/
-- skill_exam_attempts all 0), so tightening breaks no existing row. Reads are unchanged
-- (skill_profiles_read already = own-row only). Idempotent: DROP POLICY IF EXISTS before CREATE.
-- Verified live by the skill-write-isolation gate (rolled-back cross-worker probe).

DROP POLICY IF EXISTS skill_profiles_write ON public.skill_profiles;

CREATE POLICY skill_profiles_write ON public.skill_profiles
  FOR ALL
  USING (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND auth_uid = auth.uid()
  );
