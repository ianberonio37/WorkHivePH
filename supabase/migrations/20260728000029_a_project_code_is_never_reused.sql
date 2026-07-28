-- ─────────────────────────────────────────────────────────────────────────────
-- A project code must never be handed out twice, even after a soft delete.
--
-- FOUND BY THE PJ2 WALK (2026-07-28, PROJECT_MANAGER_DEEPWALK_EXPANSION_ROADMAP).
--
-- generate_project_code() computes MAX(sequence) + 1 over projects `WHERE deleted_at IS NULL`, so a
-- soft-deleted project's code is immediately available again. The unique index is partial for the
-- same reason — `projects_code_per_hive ... WHERE (deleted_at IS NULL)` — so the reuse is permitted
-- rather than caught.
--
-- PROVEN LIVE, in a rolled-back transaction:
--   1. soft-delete SHD-2026-001  ->  live count for that code goes 1 -> 0
--   2. generate_project_code()   ->  returns SHD-2026-001 again
--   3. create a project with it  ->  accepted
--   4. RESTORE the original      ->  ERROR: duplicate key value violates unique constraint
--                                    "projects_code_per_hive"
--
-- WHY THIS MATTERS MORE NOW: 20260728000026 made restore a first-class, supervisor-gated, AUDITED
-- operation. So the arc has just made prominent a path that can fail with a raw Postgres
-- duplicate-key error and no explanation — a supervisor clicks restore and gets 23505.
--
-- THE FIX IS TO STOP REUSING, NOT TO PATCH RESTORE, and the reason is the same one the change-order
-- work settled on: the code is an IDENTITY that leaves the system. It is printed on the Reliability
-- and Project Reports, quoted in change orders, and referenced in sign-off documents. Two different
-- projects sharing SHD-2026-001 in the historical record is a worse outcome than a restore failing —
-- one is a confusing error, the other is two documents that cannot be told apart.
--
-- Dropping `AND deleted_at IS NULL` from the scan means the sequence only ever moves forward. The
-- partial UNIQUE INDEX is deliberately left alone: it still permits a deleted row and a live row to
-- coexist, which is what makes soft-delete work at all — this change simply stops the generator
-- from walking into that overlap.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.generate_project_code(
  p_hive_id uuid,
  p_type    text,
  p_year    text
)
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  prefix   text;
  next_seq integer;
  result   text;
BEGIN
  prefix := CASE p_type
    WHEN 'workorder'  THEN 'WO'
    WHEN 'shutdown'   THEN 'SHD'
    WHEN 'capex'      THEN 'CAP'
    WHEN 'contractor' THEN 'CON'
    ELSE 'PRJ'
  END;

  -- NOTE the absence of `AND deleted_at IS NULL`. That clause is what allowed a deleted project's
  -- code to be reissued, which then made RESTORING it impossible. The sequence now only moves
  -- forward, so a code identifies exactly one project for the life of the hive — including the
  -- ones that were deleted, whose codes are still sitting on printed reports.
  SELECT COALESCE(MAX(
    CAST(SUBSTRING(project_code FROM '\d+$') AS integer)
  ), 0) + 1
  INTO next_seq
  FROM public.projects
  WHERE hive_id = p_hive_id
    AND project_code LIKE prefix || '-' || p_year || '-%';

  result := prefix || '-' || p_year || '-' || LPAD(next_seq::text, 3, '0');
  RETURN result;
END;
$function$;

COMMENT ON FUNCTION public.generate_project_code(uuid, text, text) IS
  'Next project code for a hive/type/year. Scans ALL projects including soft-deleted ones, so a code '
  'is never reissued: reusing one made restoring the original fail with a raw 23505 against '
  'projects_code_per_hive, and left two projects sharing a code in reports that had already been '
  'printed. PJ2, 2026-07-28.';
