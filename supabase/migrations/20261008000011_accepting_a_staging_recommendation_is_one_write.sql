-- ★ACCEPTING A PARTS-STAGING RECOMMENDATION WAS TWO WRITES THAT DID NOT KNOW ABOUT EACH OTHER (2026-10-08,
-- found authoring the UI-write recipes). asset-hub.html _onStagingAccept fired, in parallel:
--   1. an UPSERT of parts_staged_reservations (one row per ticked part), and
--   2. an UPDATE of parts_staging_recommendations to status 'accepted'.
-- Either could land without the other. A reservation with the recommendation still 'pending' leaves the card
-- offering the same parts again; a recommendation marked 'accepted' with no reservation hides the card while
-- nothing is held for the predicted failure. And whichever half failed, the toast said "The parts were not
-- staged. Nothing changed" - which was false whenever the other half had gone through. A network rejection of
-- either promise (Promise.allSettled 'rejected') was not even read, so it reported success.
--
-- One function, one transaction: both writes commit together or neither does, and the function says exactly
-- which case happened. SECURITY INVOKER on purpose - it grants no authority the caller did not already have.
-- parts_staging_recommendations_hive_rw and parts_staged_reservations_hive_rw (active hive membership) still
-- decide, so a recommendation in a hive the caller does not belong to is simply not found.
--
-- The QUANTITY comes from the recommendation, never from the caller: the client used to send qty_reserved,
-- which made the reservation size a client claim. The caller names only WHICH of the recommended parts.

CREATE OR REPLACE FUNCTION public.accept_parts_staging(p_recommendation_id uuid, p_item_ids text[])
RETURNS jsonb
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_rec     public.parts_staging_recommendations%ROWTYPE;
  v_actor   text;
  v_wanted  integer;
  v_staged  integer := 0;
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Sign in to stage parts.' USING ERRCODE = '42501';
  END IF;
  IF p_item_ids IS NULL OR cardinality(p_item_ids) = 0 THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'no_parts');
  END IF;

  -- Row lock: a second device accepting the same card waits here, then sees acted_at set.
  SELECT * INTO v_rec
    FROM public.parts_staging_recommendations
   WHERE id = p_recommendation_id
   FOR UPDATE;
  IF NOT FOUND THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'not_found');
  END IF;
  IF v_rec.acted_at IS NOT NULL THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'already_acted', 'status', v_rec.status);
  END IF;
  IF v_rec.expires_at IS NOT NULL AND v_rec.expires_at < now() THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'expired');
  END IF;

  SELECT hm.worker_name INTO v_actor
    FROM public.hive_members hm
   WHERE hm.hive_id = v_rec.hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
   LIMIT 1;

  -- Only parts the recommendation actually names. Anything else in p_item_ids is ignored, not trusted.
  WITH picked AS (
    SELECT DISTINCT ON (p->>'item_id')
           p->>'item_id' AS item_id,
           CASE WHEN jsonb_typeof(p->'qty_avg') = 'number' AND (p->>'qty_avg')::numeric > 0
                THEN (p->>'qty_avg')::numeric ELSE 1 END AS qty
      FROM jsonb_array_elements(COALESCE(v_rec.parts, '[]'::jsonb)) p
     WHERE p->>'item_id' = ANY (p_item_ids)
  ),
  ins AS (
    INSERT INTO public.parts_staged_reservations
      (hive_id, asset_name, item_id, qty_reserved, reserved_by, recommendation_id, notes)
    SELECT v_rec.hive_id, v_rec.asset_name, picked.item_id, picked.qty,
           COALESCE(v_actor, 'unknown'), v_rec.id,
           'auto-staged from risk ' || to_char(COALESCE(v_rec.risk_score, 0), 'FM0.00')
      FROM picked
    -- Idempotent against a retry: the UNIQUE (recommendation_id, item_id) index makes a repeat a no-op.
    ON CONFLICT (recommendation_id, item_id) DO NOTHING
    RETURNING 1
  )
  SELECT (SELECT count(*) FROM picked), (SELECT count(*) FROM ins) INTO v_wanted, v_staged;

  IF v_wanted = 0 THEN
    RETURN jsonb_build_object('ok', false, 'reason', 'no_parts');
  END IF;

  UPDATE public.parts_staging_recommendations
     SET status = 'accepted', acted_at = now(), acted_by = COALESCE(v_actor, 'unknown')
   WHERE id = v_rec.id;

  RETURN jsonb_build_object('ok', true, 'staged', v_staged, 'already_held', v_wanted - v_staged);
END;
$function$;

COMMENT ON FUNCTION public.accept_parts_staging(uuid, text[]) IS
  'Accept a parts-staging recommendation: reserve the chosen recommended parts AND mark the recommendation '
  'accepted in ONE transaction (asset-hub.html). SECURITY INVOKER - hive RLS still decides. Returns '
  '{ok, staged, already_held} or {ok:false, reason: not_found|already_acted|expired|no_parts}.';

REVOKE ALL ON FUNCTION public.accept_parts_staging(uuid, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.accept_parts_staging(uuid, text[]) TO authenticated, service_role;
