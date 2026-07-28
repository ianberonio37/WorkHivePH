-- ─────────────────────────────────────────────────────────────────────────────
-- My own migration 029 broke project creation outright. This repairs it.
--
-- WHAT I DID WRONG (PJ18, 2026-07-28)
-- -----------------------------------
-- 20260728000029 set out to stop project codes being reused after a soft delete, and the fix to the
-- function body was right. But I retyped the third parameter while I was in there:
--
--     original (20260505000000):  generate_project_code(p_hive_id uuid, p_type text, p_year integer)
--     mine     (20260728000029):  generate_project_code(p_hive_id uuid, p_type text, p_year text)
--
-- A different signature is a different function. CREATE OR REPLACE did not replace anything — it
-- created a SECOND overload and left the old, still-buggy one in place. So the fix was dead code
-- from the moment I wrote it.
--
-- AND IT WAS WORSE THAN DEAD. PostgREST resolves an RPC by name and cannot pick between two
-- candidates that differ only in a parameter it can coerce to either. Measured live from the page,
-- both call shapes fail:
--
--     db.rpc('generate_project_code', {..., p_year: 2026})    -> PGRST203
--     db.rpc('generate_project_code', {..., p_year: '2026'})  -> PGRST203
--     "Could not choose the best candidate function between:
--      public.generate_project_code(p_hive_id => uuid, p_type => text, p_year => integer),
--      public.generate_project_code(p_hive_id => uuid, p_type => text, p_year => text)"
--
-- Both callers on project-manager.html run this first and abort on error, so "+ New project" AND
-- "AI: from text" were both dead. This went out in the production migration push, so it is live.
--
-- WHY NEITHER I NOR THE GATES CAUGHT IT. I verified 029 by reading the function body and by calling
-- it in psql — where the ambiguity does not arise, because SQL resolves overloads by the literal's
-- type. The break only exists through PostgREST. This is the "measure the WORKED state, not the
-- generator" lesson in its most literal form: I confirmed the function was correct and never
-- confirmed the button still worked. What finally surfaced it was the SECURITY DEFINER gate
-- complaining about an ungated function — I went to look at the grants and found two rows.
--
-- THE REPAIR
--   1. Drop the (uuid, text, text) overload I added. The integer signature is the one the client
--      sends (new Date().getFullYear() is a JS number), the one canonical_registry.md documents,
--      and the one that has existed since May.
--   2. Redefine the integer signature carrying 029's actual fix — the scan no longer excludes
--      soft-deleted rows, so a code is never reissued.
--   3. Gate it on hive membership while it is open. It is SECURITY DEFINER and takes p_hive_id as
--      an argument, so without a check any authenticated user could ask for any hive's next
--      sequence number and learn how many projects that hive has. That is what the SECURITY DEFINER
--      Hive-Membership gate flagged, and it was right.
--
-- Both client callers pass their own HIVE_ID, so the membership check costs them nothing. Checked
-- before tightening, as with every other write in this arc.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Remove the accidental overload.
DROP FUNCTION IF EXISTS public.generate_project_code(uuid, text, text);

-- 2 + 3. One function, on the signature everything already expects.
CREATE OR REPLACE FUNCTION public.generate_project_code(
  p_hive_id uuid,
  p_type    text,
  p_year    integer
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  prefix   text;
  next_seq integer;
BEGIN
  -- SECURITY DEFINER + a hive id in the arguments means this must prove membership itself.
  -- auth.uid() IS NULL is service_role / seeders / migrations, as everywhere else in this arc.
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.hive_members hm
     WHERE hm.hive_id = p_hive_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
  ) THEN
    RAISE EXCEPTION 'Not a member of this hive.'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  prefix := CASE p_type
    WHEN 'workorder'  THEN 'WO'
    WHEN 'shutdown'   THEN 'SHD'
    WHEN 'capex'      THEN 'CAP'
    WHEN 'contractor' THEN 'CON'
    ELSE 'PRJ'
  END;

  -- NOTE the absence of `AND deleted_at IS NULL` — this is 029's fix, now on the signature that is
  -- actually reachable. That clause let a deleted project's code be reissued, which then made
  -- RESTORING the original fail with a raw 23505 against projects_code_per_hive, and left two
  -- projects sharing a code on reports that had already been printed. The sequence only moves
  -- forward, so a code identifies exactly one project for the life of the hive.
  SELECT COALESCE(MAX(
    CAST(SUBSTRING(project_code FROM '\d+$') AS integer)
  ), 0) + 1
  INTO next_seq
  FROM public.projects
  WHERE hive_id = p_hive_id
    AND project_code LIKE prefix || '-' || p_year::text || '-%';

  RETURN prefix || '-' || p_year::text || '-' || LPAD(next_seq::text, 3, '0');
END;
$function$;

COMMENT ON FUNCTION public.generate_project_code(uuid, text, integer) IS
  'Next project code for a hive/type/year. Scans ALL projects including soft-deleted ones so a code '
  'is never reissued (029''s fix, relanded on the reachable signature — 029 retyped p_year to text, '
  'which created a second overload instead of replacing, and PostgREST then refused both call '
  'shapes with PGRST203, killing project creation). Gated on active hive membership: it is DEFINER '
  'and takes a hive id, so without the check any user could read any hive''s next sequence number. '
  'PJ18/PJ2, 2026-07-28.';

REVOKE ALL ON FUNCTION public.generate_project_code(uuid, text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.generate_project_code(uuid, text, integer) TO authenticated, service_role;
