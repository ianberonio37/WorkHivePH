-- 20261014000003_a_profile_claims_only_a_hive_it_belongs_to.sql
-- ============================================================================
-- SL sub-layer S2 (2026-10-14): "The platform must refuse, with a sentence, every write this page attempts outside its
-- tenant."
--
-- FOUND by SL walk 2's write-refusal probe (tools/gen_write_authz_recipes.py --sl, the WITH CHECK half): a member,
-- on the authenticated path in a rolled-back transaction, could MOVE their own row into a hive they do not belong to -
-- `marketplace_sellers_move_into_foreign | 1` (founder-console, marketplace-admin, marketplace-seller, platform-actions)
-- and `resume_documents_move_into_foreign | 1` (resume). Both tables' INSERT and UPDATE policies check OWNERSHIP only
-- (auth_uid = auth.uid()) and never that the row's hive_id is a hive the author is an active member of. So anyone could
-- publish a seller profile - shown in the marketplace directory with its hive - or a resume under any hive's name: a
-- misrepresented affiliation in a marketplace whose buyers judge sellers partly by where they work.
--
-- FIX: the WITH CHECK keeps ownership and adds the tenant: hive_id is NULL (a solo profile) or one of the author's
-- active memberships (public.user_hive_ids(): SECURITY DEFINER, search_path pinned, by auth.uid()). A marketplace
-- admin keeps the update path they already had for sellers (moderation). Measured before applying: 0 of 17 seller rows
-- and 0 of 5 resume rows already claim a hive their author is not in, so no one is stranded by the tighter rule.
-- ============================================================================

DROP POLICY IF EXISTS mkt_sellers_insert ON public.marketplace_sellers;
CREATE POLICY mkt_sellers_insert ON public.marketplace_sellers
  FOR INSERT
  WITH CHECK (
    auth_uid = auth.uid()
    AND (hive_id IS NULL OR hive_id IN (SELECT public.user_hive_ids()))
  );

DROP POLICY IF EXISTS mkt_sellers_update ON public.marketplace_sellers;
CREATE POLICY mkt_sellers_update ON public.marketplace_sellers
  FOR UPDATE
  USING ((auth_uid = auth.uid()) OR public.is_marketplace_admin())
  WITH CHECK (
    public.is_marketplace_admin()
    OR (auth_uid = auth.uid() AND (hive_id IS NULL OR hive_id IN (SELECT public.user_hive_ids())))
  );

DROP POLICY IF EXISTS resume_documents_insert ON public.resume_documents;
CREATE POLICY resume_documents_insert ON public.resume_documents
  FOR INSERT
  WITH CHECK (
    auth.uid() IS NOT NULL AND auth.uid() = auth_uid
    AND (hive_id IS NULL OR hive_id IN (SELECT public.user_hive_ids()))
  );

DROP POLICY IF EXISTS resume_documents_update ON public.resume_documents;
CREATE POLICY resume_documents_update ON public.resume_documents
  FOR UPDATE
  USING (auth.uid() IS NOT NULL AND auth.uid() = auth_uid)
  WITH CHECK (
    auth.uid() IS NOT NULL AND auth.uid() = auth_uid
    AND (hive_id IS NULL OR hive_id IN (SELECT public.user_hive_ids()))
  );
