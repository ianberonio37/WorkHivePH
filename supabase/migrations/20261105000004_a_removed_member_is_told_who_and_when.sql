-- ★A REMOVED MEMBER IS TOLD WHO REMOVED THEM AND WHEN (2026-11-05, GJ M8 - J14 / G-LEAVE hand-off 1).
--
-- A supervisor's Remove sets hive_members.status = 'kicked'. The removed person's next open of the Hive Board said
-- "You were removed from <hive> by a supervisor" - undated, and in a hive with several supervisors not saying which.
-- The hive's audit log knows (kick_member, actor, created_at), but its read policy is supervisors-only, and the
-- person has just stopped being a member. The one row a removed person can always read is their OWN membership row
-- (its read policy begins auth_uid = auth.uid()), so the removal is stamped there: who decided it, and when.
--
-- The stamp is set by a BEFORE UPDATE trigger, never by the page, so no client can write a different name or time:
--   status -> 'kicked'            removed_at = now(), removed_by = the acting member's display name
--   status 'kicked' -> anything   the stamp is cleared (re-approved: the person is a member again)
-- A removal made with no signed-in actor (a service-role repair) is stamped with the time and no name.

ALTER TABLE public.hive_members
  ADD COLUMN IF NOT EXISTS removed_at timestamptz,
  ADD COLUMN IF NOT EXISTS removed_by text;

COMMENT ON COLUMN public.hive_members.removed_at IS 'When a supervisor removed this member (status -> kicked). Set by trg_hive_members_stamp_removal; cleared when the member is re-approved.';
COMMENT ON COLUMN public.hive_members.removed_by IS 'The display name of the member who removed this one. Set by trg_hive_members_stamp_removal from auth.uid(), never by a client.';

CREATE OR REPLACE FUNCTION public.hive_members_stamp_removal()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    -- a membership is born unstamped: a join request cannot arrive carrying someone's name as its remover
    NEW.removed_at := NULL;
    NEW.removed_by := NULL;
    RETURN NEW;
  END IF;
  IF NEW.status = 'kicked' AND OLD.status IS DISTINCT FROM 'kicked' THEN
    NEW.removed_at := now();
    NEW.removed_by := (SELECT wp.display_name FROM public.worker_profiles wp WHERE wp.auth_uid = auth.uid() LIMIT 1);
  ELSIF OLD.status = 'kicked' AND NEW.status IS DISTINCT FROM 'kicked' THEN
    NEW.removed_at := NULL;
    NEW.removed_by := NULL;
  ELSE
    -- a stamp is the trigger's alone: an update that does not change the status keeps it as it was
    NEW.removed_at := OLD.removed_at;
    NEW.removed_by := OLD.removed_by;
  END IF;
  RETURN NEW;
END $$;

-- a trigger's function: nobody calls it (EXECUTE is checked when a trigger is created, never when it fires).
-- Supabase grants anon EXECUTE explicitly on every new function, so PUBLIC alone never reaches it (definer-doors Y2).
REVOKE ALL ON FUNCTION public.hive_members_stamp_removal() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_hive_members_stamp_removal ON public.hive_members;
CREATE TRIGGER trg_hive_members_stamp_removal
  BEFORE INSERT OR UPDATE ON public.hive_members
  FOR EACH ROW EXECUTE FUNCTION public.hive_members_stamp_removal();

-- ★AND TOLD AGAIN ON THE NEXT VISIT, NOT ONLY THE FIRST (GJ M8 J14 hand-off 1, read on 3G). The page told a removal once -
-- a toast stashed across one reload - and then forgot the hive, so a person who missed the toast opened the Hive Board
-- again to a plain "join or create" screen that never said why their hive was gone. After a removal the person can no
-- longer read the hive's row (its read policy is members-only), so its NAME comes from here: their own most recent
-- removal within 30 days - the hive, who removed them, when. Nothing about anyone else, nothing older.
CREATE OR REPLACE FUNCTION public.my_recent_removal()
RETURNS TABLE(hive_name text, removed_by text, removed_at timestamptz)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO 'public', 'pg_temp'
AS $$
  SELECT h.name, m.removed_by, m.removed_at
    FROM public.hive_members m
    JOIN public.hives h ON h.id = m.hive_id
   WHERE m.auth_uid = auth.uid() AND m.status = 'kicked' AND m.removed_at >= now() - interval '30 days'
   ORDER BY m.removed_at DESC
   LIMIT 1
$$;

REVOKE ALL ON FUNCTION public.my_recent_removal() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.my_recent_removal() TO authenticated;
