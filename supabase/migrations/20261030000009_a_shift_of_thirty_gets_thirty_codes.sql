-- HS W2 (2026-10-30, the hive at thirty - measured by tools/prove_hive_scale_burst.mjs): when the shift pressed Create
-- at the same moment, 4 of 29 new projects saved and 1 of 29 change orders. project-manager.html asks for the next code
-- first (generate_project_code / generate_change_order_number), then inserts with it - and both answered MAX(issued) + 1,
-- read from the rows already saved. Twenty-nine people asking before any of them saved were all told the SAME next code;
-- the unique keys (projects_code_per_hive, project_change_orders_co_number) then refused all but the first, and each
-- person was told their project was not created. Saved one after another, all 29 landed - the defect is a shift's.
--
-- The next number now comes from a counter row taken under its own lock (INSERT ... ON CONFLICT DO UPDATE ... RETURNING):
-- each caller gets the next one whether or not anyone has saved yet. The counter never falls behind what is already
-- issued (GREATEST with the highest code on the table, deleted projects included - 029's rule: a code is never reissued),
-- so codes a seeder or an import wrote are respected. A number asked for and never saved is a gap, never a reuse.
--
-- generate_change_order_number becomes SECURITY DEFINER to write its counter, so it now proves membership itself (the
-- project's hive), as generate_project_code does, and is no longer callable by anon or PUBLIC.

-- canonical-allow: an internal counter the two code generators keep under a row lock; no page or role reads it (revoked below), so it is no canonical source of anything a person sees
CREATE TABLE IF NOT EXISTS public.code_counters (
  scope    text PRIMARY KEY,
  last_seq integer NOT NULL
);
COMMENT ON TABLE public.code_counters IS
  'The last number issued per code scope (project:<hive>:<prefix>:<year>, change_order:<project>). Written only by the '
  'SECURITY DEFINER code generators, under the row lock, so callers at the same moment get distinct numbers.';
ALTER TABLE public.code_counters ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.code_counters FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION public.generate_project_code(p_hive_id uuid, p_type text, p_year integer)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  prefix   text;
  v_used   integer;
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

  -- the highest code already issued - deleted projects included (029: a code identifies one project for the life of
  -- the hive, so a deleted project's code is never reissued)
  SELECT COALESCE(MAX(CAST(SUBSTRING(project_code FROM '\d+$') AS integer)), 0)
    INTO v_used
    FROM public.projects
   WHERE hive_id = p_hive_id
     AND project_code LIKE prefix || '-' || p_year::text || '-%';

  -- the next number, under the counter row's lock: a second caller waits for the first and reads ITS number
  INSERT INTO public.code_counters AS c (scope, last_seq)
  VALUES ('project:' || p_hive_id::text || ':' || prefix || ':' || p_year::text, v_used + 1)
  ON CONFLICT (scope) DO UPDATE SET last_seq = GREATEST(c.last_seq, v_used) + 1
  RETURNING last_seq INTO next_seq;

  -- ★LPAD TRUNCATES AS WELL AS PADS (found 2026-10-31 by the burst walk, prove_hive_scale_burst): LPAD('1000', 3, '0') is
  -- '100', so past the 999th code of a type in a year every number from 1000 to 1009 became the same code and every create
  -- after it failed on projects_code_per_hive (3 of 29 landed). Pad to at least three digits, never cut one off.
  RETURN prefix || '-' || p_year::text || '-' || LPAD(next_seq::text, GREATEST(3, length(next_seq::text)), '0');
END;
$function$;
REVOKE ALL ON FUNCTION public.generate_project_code(uuid, text, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.generate_project_code(uuid, text, integer) TO authenticated, service_role;

CREATE OR REPLACE FUNCTION public.generate_change_order_number(p_project_id uuid)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_used   integer;
  next_seq integer;
BEGIN
  -- a definer function with a project id in its arguments: only a member of the project's hive may draw its numbers
  IF auth.uid() IS NOT NULL AND NOT EXISTS (
    SELECT 1 FROM public.projects p
      JOIN public.hive_members hm ON hm.hive_id = p.hive_id
     WHERE p.id = p_project_id AND hm.auth_uid = auth.uid() AND hm.status = 'active'
  ) THEN
    RAISE EXCEPTION 'Not a member of this project''s hive.'
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  SELECT COALESCE(MAX(CAST(SUBSTRING(co_number FROM '\d+$') AS integer)), 0)
    INTO v_used
    FROM public.project_change_orders
   WHERE project_id = p_project_id;

  INSERT INTO public.code_counters AS c (scope, last_seq)
  VALUES ('change_order:' || p_project_id::text, v_used + 1)
  ON CONFLICT (scope) DO UPDATE SET last_seq = GREATEST(c.last_seq, v_used) + 1
  RETURNING last_seq INTO next_seq;

  RETURN 'CO-' || LPAD(next_seq::text, GREATEST(3, length(next_seq::text)), '0');   -- never truncates (see the project code above)
END;
$function$;
REVOKE ALL ON FUNCTION public.generate_change_order_number(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.generate_change_order_number(uuid) TO authenticated, service_role;
