-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- ★ A platform admin is an ACCOUNT, never a name a person can choose (S layer, 2026-10-08)
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Found by the LXC-S persona reading (tools/prove_tenant_refusal.mjs --as "Jun Salvador" --email junvanowner)
-- and confirmed at the database's own role level - `authenticated` with the person's jwt claims, inside a
-- transaction that was ROLLED BACK - acting as Jun Salvador, a solo owner with no hive and no admin rights:
--
--   1. is_platform_admin() joined worker_profiles.display_name to marketplace_platform_admins.worker_name, and
--      the policy "profiles update own" lets anyone change their own display_name. ONE update of his display name
--      to an admin's made is_platform_admin() true: analytics_events went from 0 visible rows to 238,232.
--   2. is_marketplace_admin() asked whether an admin NAME is among auth_worker_names(), which reads hive_members.
--      hives_insert lets any signed-in person found a hive and hive_members_insert lets them join it as its sole
--      supervisor UNDER ANY NAME. Two inserts named after an admin made is_marketplace_admin() true - every
--      marketplace order became readable, and 29 policies carry an `OR is_marketplace_admin()` arm.
--
-- Both are one mistake: an allowlist of NAMES checked against names the person controls. Names are deliberately
-- not unique across hives on this platform (join_hive_by_code refuses a namesake only WITHIN a hive, T185), so a
-- name can never be the key of a privilege. The allowlist now names the ACCOUNT: auth_uid, resolved once from the
-- name only when exactly one account holds it, bound on every future grant, and fail-closed otherwise.
--
-- ★AND THE SOLO OWNER'S OWN RECORD. auth_worker_names() - the bridge every name-keyed policy uses - read only
-- hive_members and marketplace_sellers, so a person with no membership and no seller row had NO name at all: Jun
-- read 0 of his own 9 achievement_xp_log rows, and achievements.html shows him an empty "Recent activity" and
-- "XP this week 0". A person who has never belonged to any hive now also answers to his own profile display_name,
-- but ONLY while no other account holds that name anywhere - so renaming yourself after somebody claims nothing.
--
-- Held by tools/validate_admin_is_an_account.py (gate `admin-is-an-account`): it re-runs both attacks as the solo
-- owner, rolled back, beside a control requiring the real admin's account to stay an admin. Measured RED on the
-- database before this migration (A1, A2 and SOLO all failed) and GREEN after.
-- ════════════════════════════════════════════════════════════════════════════════════════════════

BEGIN;

ALTER TABLE public.marketplace_platform_admins ADD COLUMN IF NOT EXISTS auth_uid uuid;
CREATE INDEX IF NOT EXISTS idx_mkt_platform_admins_auth_uid ON public.marketplace_platform_admins (auth_uid);

-- one name -> exactly one account, across every place an account holds a name; NULL when none or several
CREATE OR REPLACE FUNCTION public.resolve_admin_account(p_name text)
RETURNS uuid LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  SELECT CASE WHEN count(DISTINCT u) = 1 THEN min(u::text)::uuid END
  FROM (
    SELECT auth_uid AS u FROM public.hive_members        WHERE worker_name  = p_name AND auth_uid IS NOT NULL
    UNION ALL
    SELECT auth_uid      FROM public.worker_profiles     WHERE display_name = p_name
    UNION ALL
    SELECT auth_uid      FROM public.marketplace_sellers WHERE worker_name  = p_name AND auth_uid IS NOT NULL
  ) holders;
$fn$;
-- a by-name uid lookup must not be callable by a client: it would answer "whose account is this name?"
REVOKE ALL ON FUNCTION public.resolve_admin_account(text) FROM PUBLIC, anon, authenticated;

UPDATE public.marketplace_platform_admins
   SET auth_uid = public.resolve_admin_account(worker_name)
 WHERE auth_uid IS NULL;

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM public.marketplace_platform_admins WHERE auth_uid IS NULL;
  IF n > 0 THEN
    RAISE NOTICE 'marketplace_platform_admins: % admin name(s) resolve to no single account and are NOT admins until an account is bound (fail closed)', n;
  END IF;
END $$;

-- every future grant names the account too; a renamed grant is re-resolved, never kept on the old account
CREATE OR REPLACE FUNCTION public.bind_platform_admin_account()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.worker_name IS DISTINCT FROM OLD.worker_name
     AND NEW.auth_uid IS NOT DISTINCT FROM OLD.auth_uid THEN
    NEW.auth_uid := NULL;
  END IF;
  IF NEW.auth_uid IS NULL THEN
    NEW.auth_uid := public.resolve_admin_account(NEW.worker_name);
  END IF;
  RETURN NEW;
END $fn$;
REVOKE ALL ON FUNCTION public.bind_platform_admin_account() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_bind_platform_admin_account ON public.marketplace_platform_admins;
CREATE TRIGGER trg_bind_platform_admin_account
  BEFORE INSERT OR UPDATE OF worker_name, auth_uid ON public.marketplace_platform_admins
  FOR EACH ROW EXECUTE FUNCTION public.bind_platform_admin_account();

-- the two admin checks, on the account
CREATE OR REPLACE FUNCTION public.is_marketplace_admin()
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  SELECT auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM public.marketplace_platform_admins pa WHERE pa.auth_uid = auth.uid()
  );
$fn$;

CREATE OR REPLACE FUNCTION public.is_platform_admin()
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public', 'pg_temp' AS $fn$
  SELECT auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM public.marketplace_platform_admins pa WHERE pa.auth_uid = auth.uid()
  );
$fn$;

-- the two policies that inlined the display-name join
DROP POLICY IF EXISTS "mkt_admins_read_self" ON public.marketplace_platform_admins;
CREATE POLICY "mkt_admins_read_self" ON public.marketplace_platform_admins
  FOR SELECT USING (auth_uid IS NOT NULL AND auth_uid = auth.uid());

DROP POLICY IF EXISTS "analytics_events_select_admin" ON public.analytics_events;
CREATE POLICY "analytics_events_select_admin" ON public.analytics_events
  FOR SELECT TO authenticated USING (public.is_platform_admin());

-- the solo owner's own name (see the header): only for a person who has NEVER held a membership, and only while
-- no other account holds the name in a roster, a profile or a seller row
CREATE OR REPLACE FUNCTION public.auth_worker_names()
RETURNS SETOF text LANGUAGE sql STABLE SECURITY DEFINER SET search_path TO 'public' AS $fn$
  select worker_name from public.hive_members
    where auth_uid = auth.uid() and status = 'active'
  union
  select worker_name from public.marketplace_sellers
    where auth_uid = auth.uid()
  union
  select p.display_name from public.worker_profiles p
    where p.auth_uid = auth.uid()
      and not exists (select 1 from public.hive_members m where m.auth_uid = auth.uid())
      and not exists (select 1 from public.hive_members m
                       where m.worker_name = p.display_name and m.auth_uid is distinct from auth.uid())
      and not exists (select 1 from public.worker_profiles o
                       where o.display_name = p.display_name and o.auth_uid <> auth.uid())
      and not exists (select 1 from public.marketplace_sellers s
                       where s.worker_name = p.display_name and s.auth_uid is distinct from auth.uid());
$fn$;

COMMIT;
