-- 2026-05-21 Flywheel turn #18: explicit ON DELETE on the 2 legacy FKs
-- =====================================================================
-- Two FKs from the original schema baseline omitted ON DELETE behavior:
--
--   1) parts_records.asset_ref_id -> assets(id)
--   2) worker_achievements.achievement_id -> achievement_definitions(id)
--
-- Without an explicit clause, Postgres defaults to NO ACTION — same as
-- RESTRICT but the failure surfaces at COMMIT rather than at the
-- failing row, which is debug-hostile. Both relationships SHOULD be
-- RESTRICT (the parent must stay alive while children reference it),
-- so the behavior change is zero but the declaration becomes explicit
-- and the validate_fk_on_delete.py L0 ratchet drops to 0.
--
-- ALTER FK requires DROP + ADD. The ADD repeats the original column
-- list with ON DELETE RESTRICT.

BEGIN;

-- parts_records.asset_ref_id
ALTER TABLE public.parts_records
  DROP CONSTRAINT IF EXISTS parts_records_asset_ref_id_fkey;
ALTER TABLE public.parts_records
  ADD  CONSTRAINT parts_records_asset_ref_id_fkey
  FOREIGN KEY (asset_ref_id) REFERENCES public.assets(id) ON DELETE RESTRICT;

-- worker_achievements.achievement_id
ALTER TABLE public.worker_achievements
  DROP CONSTRAINT IF EXISTS worker_achievements_achievement_id_fkey;
ALTER TABLE public.worker_achievements
  ADD  CONSTRAINT worker_achievements_achievement_id_fkey
  FOREIGN KEY (achievement_id) REFERENCES public.achievement_definitions(id) ON DELETE RESTRICT;

COMMIT;
