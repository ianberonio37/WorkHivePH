-- Platform admin role for the marketplace
-- Replaces the previous gate that allowed any hive supervisor to access
-- marketplace-admin.html. With the platform now spanning multiple hives
-- (cross-hive listings, public marketplace), admin authority needs to be
-- platform-wide and explicitly granted, not derived from per-hive supervisor.

-- String-identity compatible (worker_name as PK) since Supabase Auth is still
-- deferred. When Auth migrates, we add an auth_uid column and gate by that.

CREATE TABLE IF NOT EXISTS public.marketplace_platform_admins (
  worker_name text         PRIMARY KEY,
  granted_at  timestamptz  NOT NULL DEFAULT now(),
  granted_by  text         NOT NULL  -- 'bootstrap' for the first admin, later: another admin's worker_name
);

CREATE INDEX IF NOT EXISTS idx_mkt_platform_admins_worker
  ON public.marketplace_platform_admins (worker_name);

GRANT SELECT, INSERT, DELETE ON public.marketplace_platform_admins TO anon, authenticated;

-- ============================================================
-- BOOTSTRAP: After applying this migration, run ONCE in the
-- Supabase Dashboard → SQL Editor (replace 'Ian Phone' with
-- your exact wh_last_worker localStorage value):
--
-- INSERT INTO public.marketplace_platform_admins (worker_name, granted_by)
-- VALUES ('Ian Phone', 'bootstrap');
--
-- To grant a co-admin later:
-- INSERT INTO public.marketplace_platform_admins (worker_name, granted_by)
-- VALUES ('CoAdmin Name', 'Ian Phone');
--
-- To revoke:
-- DELETE FROM public.marketplace_platform_admins
-- WHERE worker_name = 'Some Name';
-- ============================================================
