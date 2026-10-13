-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- marketplace_sellers had TWO SELECT policies and NO SELECT grant, so both were dead
-- ════════════════════════════════════════════════════════════════════════════════════════════════
-- Found by live verification of the BRP class-A sweep (2026-10-04): marketplace-seller.html answered 403
-- on v_marketplace_sellers_truth for a signed-in seller, on every load, under both the stored and a
-- drifted display name - so it was not the display-name class at all.
--
-- MEASURED GRANTS on public.marketplace_sellers before this migration:
--     anon           DELETE, INSERT, REFERENCES, TRIGGER, UPDATE
--     authenticated  DELETE, INSERT, REFERENCES, TRIGGER, UPDATE
-- No SELECT for either. And the table carries TWO SELECT policies written for exactly those roles:
--     mkt_sellers_read       {public}  USING (auth.uid() IS NOT NULL)
--     mkt_sellers_read_anon  {anon}    USING (seller_has_published_listing(worker_name))
--
-- ★A POLICY CANNOT RESURRECT A PRIVILEGE. GRANTs are checked BEFORE row-level security, so a role without
-- SELECT is refused outright and its policies never run. Both of those policies have been dead code: they
-- describe, in detail, a read the grant forbids. The marketplace's own public seller directory and every
-- consumer of the security_invoker view v_marketplace_sellers_truth (which requires the CALLER to hold
-- SELECT on this base table) have been answering 403. A seller opening their own page saw no tier, no
-- badges and no listing counts, and the page's catch recorded it as a failed read rather than a refusal.
--
-- The inverse is the part worth saying out loud: these roles could INSERT, UPDATE and DELETE rows they
-- could not READ. The write policies (`auth_uid = auth.uid() OR is_marketplace_admin()`) still bound who
-- may write, so this was never an open door - but a grant set that permits writing and forbids reading is
-- backwards, and it is how the dead SELECT policies escaped notice for so long.
--
-- THIS MIGRATION GRANTS ONLY SELECT, AND CHANGES NO POLICY. The two policies already state the intended
-- scope; the grant is what was missing. Row visibility after this is exactly what they always said it
-- should be: a signed-in reader sees sellers, anon sees only sellers with a published listing. Nothing is
-- widened beyond what was already written down and reviewed.

BEGIN;

DO $$
BEGIN
  -- Refuse to run if the premise has changed: if a SELECT grant already exists this migration is not the
  -- fix for anything, and if the policies are gone it would be granting a read nobody scoped.
  IF EXISTS (SELECT 1 FROM information_schema.role_table_grants
              WHERE table_schema='public' AND table_name='marketplace_sellers'
                AND grantee IN ('anon','authenticated') AND privilege_type='SELECT') THEN
    RAISE EXCEPTION 'a SELECT grant already exists - re-check the premise before applying this';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies
                  WHERE schemaname='public' AND tablename='marketplace_sellers'
                    AND policyname='mkt_sellers_read' AND cmd='SELECT') THEN
    RAISE EXCEPTION 'mkt_sellers_read is missing - this grant would be unscoped; stop';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies
                  WHERE schemaname='public' AND tablename='marketplace_sellers'
                    AND policyname='mkt_sellers_read_anon' AND cmd='SELECT') THEN
    RAISE EXCEPTION 'mkt_sellers_read_anon is missing - anon would be unscoped; stop';
  END IF;
  IF NOT (SELECT relrowsecurity FROM pg_class
           WHERE oid = 'public.marketplace_sellers'::regclass) THEN
    RAISE EXCEPTION 'RLS is DISABLED on marketplace_sellers - granting SELECT would expose every row';
  END IF;
END $$;

GRANT SELECT ON public.marketplace_sellers TO anon, authenticated;

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM information_schema.role_table_grants
   WHERE table_schema='public' AND table_name='marketplace_sellers'
     AND grantee IN ('anon','authenticated') AND privilege_type='SELECT';
  IF n <> 2 THEN RAISE EXCEPTION 'expected 2 SELECT grants, found %', n; END IF;
  -- RLS must still be the thing deciding WHICH rows; a grant without it is a table scan for everyone.
  IF NOT (SELECT relrowsecurity FROM pg_class WHERE oid='public.marketplace_sellers'::regclass) THEN
    RAISE EXCEPTION 'RLS is no longer enabled - refusing to commit a bare SELECT grant';
  END IF;
  RAISE NOTICE 'marketplace_sellers: SELECT granted to anon + authenticated; the two SELECT policies that '
               'were written for them can now actually run, and RLS still decides which rows';
END $$;

COMMIT;
