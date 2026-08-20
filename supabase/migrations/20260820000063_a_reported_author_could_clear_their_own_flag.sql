-- A REPORTED AUTHOR COULD CLEAR THEIR OWN FLAG.
--
-- Found 2026-08-20 walking community's CD invariant `report_one_record_no_selfclear` ("a report
-- creates exactly one moderation record and cannot be self-cleared by the reported party").
--
-- MEASURED, with a control, before any change was made:
--   seeded a flagged post authored by Bryan Garcia          -> flagged = true
--   Bryan Garcia (the REPORTED author) updates his own post -> flagged = FALSE   <-- the defect
--   an unrelated member of the same hive tries the same     -> flagged = true    <-- control holds
--
-- The control matters: it shows RLS is doing its job in general, so this is one specific hole rather
-- than an unprotected table. community_posts_update authorises `auth_uid = auth.uid() OR supervisor`
-- with no WITH CHECK and no column restriction, because that policy exists so an author can EDIT
-- their own post. `flagged` happens to live on the same row, so the edit right silently carried a
-- moderation right with it.
--
-- WHY IT IS WORSE THAN IT LOOKS. Non-supervisors already never see flagged posts
-- (community.html:1293 applies .eq('flagged', false) for them). So clearing the flag does not just
-- remove a badge: it returns the reported post to everyone's feed AND removes it from the queue the
-- supervisor reviews. The report survives in hive_audit_log, but the thing the report was about is
-- back in circulation and no longer marked.
--
-- A trigger, not a policy, is the right instrument here. RLS WITH CHECK cannot compare against the
-- OLD row, so it cannot express "you may change everything except these columns". And because the
-- USING clause legitimately PASSES for the author, the trigger is reached rather than pre-empted.
--
-- auth.uid() IS NULL means service_role, a trigger, a seeder or psql - not a browser - so the guard
-- steps aside there rather than breaking every server-side path that legitimately sets these fields.
-- `pinned` is covered by the same rule: it is the other supervisor-only control living on an
-- author-writable row, and fixing one of the two would leave the identical hole open beside it.

CREATE OR REPLACE FUNCTION public.tg_community_posts_moderation_fields()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF auth.uid() IS NULL THEN
    RETURN NEW;                       -- server-side context, not a member acting on their own post
  END IF;

  IF EXISTS (
    SELECT 1 FROM public.hive_members hm
     WHERE hm.hive_id = NEW.hive_id
       AND hm.auth_uid = auth.uid()
       AND hm.role = 'supervisor'
       AND hm.status = 'active'
  ) THEN
    RETURN NEW;                       -- a supervisor of THIS hive may moderate
  END IF;

  -- Everyone else keeps their edit rights and loses only the moderation fields. Silently preserving
  -- them is deliberate: raising here would break an ordinary edit of a flagged post, and the author
  -- is allowed to fix their wording. They are simply not allowed to un-report themselves.
  NEW.flagged := OLD.flagged;
  NEW.pinned  := OLD.pinned;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_community_posts_moderation_fields ON public.community_posts;
CREATE TRIGGER tg_community_posts_moderation_fields
  BEFORE UPDATE ON public.community_posts
  FOR EACH ROW
  EXECUTE FUNCTION public.tg_community_posts_moderation_fields();
