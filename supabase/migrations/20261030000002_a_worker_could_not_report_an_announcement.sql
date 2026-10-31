-- A WORKER COULD NOT REPORT AN ANNOUNCEMENT - THEY WERE TOLD "ONLY SUPERVISORS CAN POST ANNOUNCEMENTS".
--
-- Found 2026-10-30 walking Wave HS lens L2 on community.html: the post menu offers every worker "Report this post" on
-- a teammate's post, and replaying that as Joel Cruz (worker) on Gina Lacson's announcement was refused:
--   report_community_post(<announcement>)  -> ERROR  Only supervisors can post announcements
--     (report_community_post's UPDATE ... SET flagged = true fired trg_guard_community_announcement)
--
-- The guard (20260713000006) exists so only a supervisor can MAKE a post an announcement. It ran on every UPDATE of a
-- row whose category is 'announcement', so any write by a non-supervisor to an existing announcement was refused as if
-- they were posting one - the report a worker is offered, and a supervisor-turned-worker's typo fix of their own
-- announcement. The question is whether this write makes it an announcement: on INSERT, or on an UPDATE that changes
-- the category to it.

CREATE OR REPLACE FUNCTION public.guard_community_announcement()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.category = 'announcement'
     AND (TG_OP = 'INSERT' OR OLD.category IS DISTINCT FROM 'announcement')
     AND auth.uid() IS NOT NULL
     AND NOT (NEW.hive_id IN (SELECT public.user_supervisor_hive_ids())) THEN
    RAISE EXCEPTION 'Only supervisors can post announcements' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END;
$$;
