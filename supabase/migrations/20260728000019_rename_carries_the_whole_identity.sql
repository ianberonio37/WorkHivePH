-- ─────────────────────────────────────────────────────────────────────────────
-- Renaming an asset moved 2 rows and orphaned 116. Carry the whole identity.
--
-- FOUND BY THE AH11 WALK (2026-07-28, ASSET_HUB_DEEPWALK_EXPANSION_ROADMAP):
-- sync_pm_asset_identity (PM3, added earlier in this same arc) correctly propagates a rename into
-- pm_assets — and pm_assets is not the only place an asset's identity is stored as free text.
-- Four other tables key off the asset TAG, and none of them moved.
--
-- MEASURED LIVE, renaming GEN-002 -> GEN-002X through the signed-in client:
--     asset_nodes           1 row updated
--     pm_assets             2 rows synced   <- all the propagation there was
--     logbook.machine     103 rows still pointing at a tag that no longer exists
--     fault_knowledge      12 rows  "
--     asset_risk_scores     1 row   "
-- (Reverted immediately; 0 rows anywhere carry the test tag.)
--
-- Platform-wide the exposed surface, and note every one of these columns holds the TAG even where
-- it is NAMED asset_name — a display-name change is harmless, a TAG change is what breaks them:
--     logbook.machine                        3,739 of 3,811 rows hold a live tag
--     fault_knowledge.machine                  534 of 534    — 100%
--     asset_risk_scores.asset_name             255 of 259
--     parts_staging_recommendations.asset_name   3 of 4
--
-- WHY EACH ONE MATTERS, because they are not equally bad:
--
--   asset_risk_scores  is the worst, because the page does not merely lose the score — it ASSERTS
--                      something false. asset-hub's risk card falls back to "No risk score yet for
--                      this asset. Scores are computed daily at 13:00 PHT... Once enough fault
--                      history accumulates, a score will appear here." A score DOES exist; it is
--                      filed under a name nothing looks up any more. The empty state is honest
--                      about a cold start and a lie about a renamed asset.
--
--   fault_knowledge    has NO uuid column at all — machine is the only link. A rename severs the
--                      AI's learned fault corpus for that machine permanently, and nothing
--                      anywhere would report it.
--
--   logbook            is the least severe and the most visible: 3,739 of 3,811 rows also carry
--                      asset_node_id, so the asset's timeline survives a rename by uuid. What goes
--                      stale is the displayed machine string, plus the 72 text-only rows that have
--                      no uuid to fall back on and do genuinely sever.
--
-- SHAPE OF THE FIX. Same reasoning as PM3's: propagation is a SYSTEM action, not a user edit, so
-- the database performs it under SECURITY DEFINER after checking hive membership itself, rather
-- than asking every client to hold write access to five tables. sync_pm_asset_identity stays —
-- it is in canonical_registry and logbook.html calls it — but becomes a thin wrapper, so the
-- narrow behaviour cannot be reached by accident from some future caller.
--
-- A MERGE GUARD, which the old RPC did not need and this one does: rewriting five tables' worth of
-- history onto a tag that ALREADY belongs to another asset would silently fuse two machines'
-- logbooks, fault knowledge and risk scores together, and nothing downstream could tell them apart
-- again. That is refused outright rather than half-applied.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.sync_asset_identity(
  p_old_tag  text,
  p_new_tag  text DEFAULT NULL,
  p_new_name text DEFAULT NULL,
  -- The node being renamed, so the merge guard below does not mistake the asset for a clash with
  -- ITSELF. This is not optional in practice: every caller updates asset_nodes.tag FIRST and then
  -- asks for propagation, so by the time we run, the new tag is already legitimately in use — by
  -- the very row we are renaming. Caught exactly that way on the first live run, where the guard
  -- refused a rename that had nothing to clash with. Left nullable so the pre-update call order
  -- still works, and so the older 3-argument wrapper below keeps its signature.
  p_node_id  uuid DEFAULT NULL
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_pm      integer := 0;
  v_logbook integer := 0;
  v_fault   integer := 0;
  v_risk    integer := 0;
  v_parts   integer := 0;
  v_clash   integer := 0;
  v_hive    uuid;
BEGIN
  IF p_old_tag IS NULL OR (p_new_tag IS NULL AND p_new_name IS NULL) THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'nothing to do');
  END IF;

  -- Which hive is being renamed IN. Scoping the clash check to that ONE hive is essential, not
  -- tidiness: tags are unique per hive, not per platform, and the fixture gives every hive its own
  -- GEN-002 / P-001 / AC-004. A guard that asked "does any hive I belong to hold this tag?" refused
  -- a perfectly legal rename the moment the operator was a member of two hives — which is the
  -- normal case, not an edge one. Caught live on the revert leg of the AH11 walk, after the
  -- forward leg had already moved 119 rows: the rename back was blocked by ANOTHER TENANT's asset.
  SELECT n.hive_id INTO v_hive
    FROM public.asset_nodes n
   WHERE (p_node_id IS NOT NULL AND n.id = p_node_id)
      OR (p_node_id IS NULL AND lower(n.tag) = lower(p_old_tag))
   ORDER BY (p_node_id IS NOT NULL AND n.id = p_node_id) DESC
   LIMIT 1;

  -- A tag change onto a tag another asset already holds would FUSE two machines' histories.
  -- Refuse; a partial rename here is unrecoverable because the text is the only link.
  IF p_new_tag IS NOT NULL AND lower(p_new_tag) IS DISTINCT FROM lower(p_old_tag) THEN
    SELECT count(*) INTO v_clash
      FROM public.asset_nodes n
     WHERE lower(n.tag) = lower(p_new_tag)
       AND (p_node_id IS NULL OR n.id <> p_node_id)
       AND (v_hive IS NULL OR n.hive_id = v_hive)
       AND (
             auth.uid() IS NULL
             OR EXISTS (SELECT 1 FROM public.hive_members hm
                         WHERE hm.hive_id = n.hive_id AND hm.auth_uid = auth.uid()
                           AND hm.status = 'active')
           );
    IF v_clash > 0 THEN
      RETURN jsonb_build_object(
        'ok', false,
        'reason', 'tag already in use',
        'detail', format('%s is already the tag of another asset in this hive; renaming onto it '
                         'would merge the two machines'' logbook, fault knowledge and risk history.',
                         p_new_tag));
    END IF;
  END IF;

  -- Nothing to rename against if we cannot place the asset in a hive.
  IF v_hive IS NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'asset not found',
      'detail', format('No asset in a hive you belong to carries the tag %s.', p_old_tag));
  END IF;

  -- TWO predicates on every UPDATE, and both are load-bearing:
  --   hive_id = v_hive   confines the rewrite to the ONE hive the asset lives in. Without it, a
  --                      rename in one tenant rewrote another tenant's rows — measured, not
  --                      theorised: renaming Lucena's GEN-002 also rewrote Manila Electronics
  --                      Assembly's 60 logbook rows, 6 fault_knowledge rows, its risk score, a
  --                      parts recommendation and a pm_asset, because the fixture gives every hive
  --                      its own GEN-002 and the first draft scoped by "any hive I belong to".
  --   IN (mine)          keeps the caller's own membership required, so SECURITY DEFINER cannot be
  --                      used to reach a hive they are not in. v_hive alone would trust the tag.
  WITH mine AS (
    SELECT hm.hive_id FROM public.hive_members hm
     WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
  ),
  -- 1. PM programs: both the display name and the tag (the original PM3 behaviour).
  u_pm AS (
    UPDATE public.pm_assets pa
       SET asset_name = COALESCE(p_new_name, pa.asset_name),
           tag_id     = COALESCE(p_new_tag,  pa.tag_id)
     WHERE lower(pa.tag_id) = lower(p_old_tag)
       AND pa.hive_id = v_hive
       AND (auth.uid() IS NULL OR pa.hive_id IN (SELECT hive_id FROM mine))
    RETURNING 1
  ),
  -- 2..5 follow the TAG only. These columns store the tag even where they are named asset_name,
  --      so a display-name change must NOT touch them.
  u_log AS (
    UPDATE public.logbook l SET machine = p_new_tag
     WHERE p_new_tag IS NOT NULL
       AND lower(l.machine) = lower(p_old_tag)
       AND l.hive_id = v_hive
       AND (auth.uid() IS NULL OR l.hive_id IN (SELECT hive_id FROM mine))
    RETURNING 1
  ),
  u_fault AS (
    UPDATE public.fault_knowledge f SET machine = p_new_tag
     WHERE p_new_tag IS NOT NULL
       AND lower(f.machine) = lower(p_old_tag)
       AND f.hive_id = v_hive
       AND (auth.uid() IS NULL OR f.hive_id IN (SELECT hive_id FROM mine))
    RETURNING 1
  ),
  u_risk AS (
    UPDATE public.asset_risk_scores r SET asset_name = p_new_tag
     WHERE p_new_tag IS NOT NULL
       AND lower(r.asset_name) = lower(p_old_tag)
       AND r.hive_id = v_hive
       AND (auth.uid() IS NULL OR r.hive_id IN (SELECT hive_id FROM mine))
    RETURNING 1
  ),
  u_parts AS (
    UPDATE public.parts_staging_recommendations s SET asset_name = p_new_tag
     WHERE p_new_tag IS NOT NULL
       AND lower(s.asset_name) = lower(p_old_tag)
       AND s.hive_id = v_hive
       AND (auth.uid() IS NULL OR s.hive_id IN (SELECT hive_id FROM mine))
    RETURNING 1
  )
  SELECT (SELECT count(*) FROM u_pm),    (SELECT count(*) FROM u_log),
         (SELECT count(*) FROM u_fault), (SELECT count(*) FROM u_risk),
         (SELECT count(*) FROM u_parts)
    INTO v_pm, v_logbook, v_fault, v_risk, v_parts;

  RETURN jsonb_build_object(
    'ok', true,
    'pm_assets',                     v_pm,
    'logbook',                       v_logbook,
    'fault_knowledge',               v_fault,
    'asset_risk_scores',             v_risk,
    'parts_staging_recommendations', v_parts,
    'total', v_pm + v_logbook + v_fault + v_risk + v_parts
  );
END;
$function$;

COMMENT ON FUNCTION public.sync_asset_identity(text, text, text, uuid) IS
  'Carries an asset TAG rename across every table that stores the identity as free text: pm_assets, '
  'logbook.machine, fault_knowledge.machine, asset_risk_scores.asset_name and '
  'parts_staging_recommendations.asset_name. Hive-scoped, SECURITY DEFINER because propagation is a '
  'system action rather than a user edit, and it can only ever rewrite identity columns. Refuses a '
  'rename onto a tag another asset already holds, which would fuse two machines'' histories. '
  'Returns per-table counts so a caller can report what actually moved. AH11, 2026-07-28.';

-- Backward compatibility: sync_pm_asset_identity is in canonical_registry and is what logbook.html
-- called. It keeps its signature and its integer return, and now delegates — so the narrow
-- PM-only propagation is no longer reachable from anywhere, including future callers.
CREATE OR REPLACE FUNCTION public.sync_pm_asset_identity(
  p_old_tag  text,
  p_new_tag  text DEFAULT NULL,
  p_new_name text DEFAULT NULL
)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v jsonb;
BEGIN
  v := public.sync_asset_identity(p_old_tag, p_new_tag, p_new_name, NULL);
  IF COALESCE((v->>'ok')::boolean, false) THEN
    RETURN COALESCE((v->>'pm_assets')::integer, 0);
  END IF;
  RETURN 0;
END;
$function$;

DROP FUNCTION IF EXISTS public.sync_asset_identity(text, text, text);
REVOKE ALL ON FUNCTION public.sync_asset_identity(text, text, text, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.sync_asset_identity(text, text, text, uuid) TO authenticated, service_role;
