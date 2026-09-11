-- v_hives_truth: expose `updated_at` so hive.html's name and intent edits can guard themselves.
--
-- ★AN OPTIMISTIC-CONCURRENCY GUARD ON A VIEW-BACKED FORM NEEDS THE STAMP ON THE VIEW. The page never
-- touches `hives` directly for reads - it reads `v_hives_truth` - so adding the column and the trigger
-- (20260908000001) gave the database a server-authoritative stamp the PAGE still could not see. A guard
-- re-sends the value it read when the form opened; if the read cannot return it, there is nothing to
-- re-send and the guard is decorative.
--
-- ★★CREATE OR REPLACE VIEW STRIPS security_invoker. This view is `security_invoker=true` today, and that
-- is load-bearing: it makes every read run as the CALLER, so RLS on `hives` decides what comes back. A
-- replace that does not re-assert the option silently turns the view into a definer-rights read of the
-- whole table - which is how a previous change here opened anon access to 437 rows. The option is set
-- again in this same migration, immediately, and the grants below are re-stated rather than assumed.
--
-- Additive: one column added to the projection, no predicate changed, no column removed or renamed.

CREATE OR REPLACE VIEW public.v_hives_truth AS
  SELECT id,
    name,
    invite_code,
    created_by,
    created_at,
    intent,
    preferred_persona,
    ( SELECT count(*)::integer AS count
           FROM hive_members hm
          WHERE hm.hive_id = h.id AND hm.status = 'active'::text) AS member_count,
    ( SELECT count(*)::integer AS count
           FROM asset_nodes an
          WHERE an.hive_id = h.id AND an.status = 'approved'::text) AS asset_count,
    ( SELECT min(hm.joined_at) AS min
           FROM hive_members hm
          WHERE hm.hive_id = h.id AND hm.status = 'active'::text) AS first_member_joined_at,
    intent = '{}'::jsonb AS intent_not_captured,
    -- APPENDED, not inserted: CREATE OR REPLACE VIEW may only add columns at the END of the
    -- projection. Putting `updated_at` after `created_at`, where it reads naturally, fails with
    -- "cannot change name of view column" because every column after it shifts position.
    updated_at
   FROM hives h;

-- re-assert IMMEDIATELY: between the replace above and this line the view reads with definer rights
ALTER VIEW public.v_hives_truth SET (security_invoker = true);

-- and re-state the grants rather than trusting that a replace preserved them
GRANT SELECT ON public.v_hives_truth TO authenticated;

COMMENT ON VIEW public.v_hives_truth IS
  'Canonical hive read, security_invoker so RLS on hives decides every row. Carries updated_at so a '
  'view-backed edit form can re-send the stamp it opened with and be refused rather than silently '
  'overwrite a concurrent save.';
