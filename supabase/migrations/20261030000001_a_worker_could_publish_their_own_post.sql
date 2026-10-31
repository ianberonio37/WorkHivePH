-- A WORKER COULD PUBLISH THEIR OWN POST TO EVERY HIVE - AND UN-PUBLISH ONE THEIR SUPERVISOR HAD SHARED.
--
-- Found 2026-10-30 walking Wave HS (the hive at thirty), lens L2 "each role sees the actions it may take", on
-- community.html. The page makes sharing a supervisor's decision: the "Share with all WorkHive teams" box is shown only
-- to supervisors, the post menu offers "Make post public" only to supervisors, and the editor computes
-- `isPublic = HIVE_ROLE === 'supervisor' && ...`. The server did not hold the same line.
--
-- MEASURED, as Joel Cruz (worker, Batangas Refinery Maintenance), each in a rolled-back transaction:
--   UPDATE his own private post SET public = true            -> public = TRUE    <-- published to the Global feed
--   INSERT a post with public = true                          -> public = TRUE    <-- same, at creation
--   UPDATE his own post SET pinned = true (control)           -> pinned unchanged (the 2026-08-20 guard holds)
--
-- AND THE QUIETER HALF. The editor's save sends `public: isPublic`, which is always false for a worker. So a worker who
-- fixes a typo in a post their supervisor had shared took it off the Global feed - the supervisor's decision undone by
-- an edit of the wording, and nobody told.
--
-- WHY THE GUARD CHANGES FROM DEFINER TO INVOKER. `public` has one legitimate non-supervisor writer:
-- publish_service_showcase(), a SECURITY DEFINER function that publishes a client's consented completion story. A
-- SECURITY DEFINER trigger cannot tell that function from a browser, because inside it current_user is always the
-- trigger's owner. As SECURITY INVOKER, current_user is `authenticated` for a request through the API and the
-- function's owner when a definer function writes on the platform's behalf (the showcase, report_community_post,
-- wh_trash) - so the guard applies to exactly the writes a person makes directly. Who is a supervisor is read through
-- user_supervisor_hive_ids(), the definer helper guard_community_announcement already uses, so the two guards on this
-- table answer the question the same way.
--
-- Non-supervisors keep their edit rights and lose only the moderation fields, silently preserved as before (raising
-- would break an ordinary edit of a post that is pinned, flagged or shared).
--
-- AND A POST'S WORDS ARE ITS AUTHOR'S - A SUPERVISOR INCLUDED. The same walk read the supervisor's side: the update policy
-- lets a supervisor write any column of any post in the hive (it exists for moderation), so through the API a supervisor
-- could rewrite a worker's post and it would still read as the worker's, under the worker's name. The page never offers
-- it (the editor opens only your own posts), so nothing legitimate breaks: moderation is pin, share, flag and delete, and
-- the wording, category and mentions stay as the author left them. Measured as Ernesto Villareal (supervisor):
--   UPDATE Gina Lacson's post SET content = ...   -> content CHANGED   <-- a supervisor's words under a worker's name

CREATE OR REPLACE FUNCTION public.tg_community_posts_moderation_fields()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
BEGIN
  IF auth.uid() IS NULL OR current_user <> 'authenticated' THEN
    RETURN NEW;                       -- server-side context, or a definer function acting for the platform
  END IF;

  IF TG_OP = 'INSERT' THEN
    IF NOT (NEW.hive_id IN (SELECT public.user_supervisor_hive_ids())) THEN
      NEW.pinned := false;            -- a member's new post starts unpinned and inside the hive
      NEW.public := false;
    END IF;
    RETURN NEW;
  END IF;

  IF OLD.auth_uid IS DISTINCT FROM auth.uid() THEN
    NEW.content   := OLD.content;     -- nobody else's words go out under this author's name
    NEW.category  := OLD.category;
    NEW.mentions  := OLD.mentions;
    NEW.edited_at := OLD.edited_at;
  END IF;

  IF NEW.hive_id IN (SELECT public.user_supervisor_hive_ids()) THEN
    RETURN NEW;                       -- a supervisor of THIS hive may moderate and share
  END IF;

  -- Raising a flag is reporting and is allowed; lowering one is clearing and is not.
  IF OLD.flagged AND NOT NEW.flagged THEN
    NEW.flagged := OLD.flagged;
  END IF;
  NEW.pinned := OLD.pinned;
  NEW.public := OLD.public;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS tg_community_posts_moderation_fields ON public.community_posts;
CREATE TRIGGER tg_community_posts_moderation_fields
  BEFORE INSERT OR UPDATE ON public.community_posts
  FOR EACH ROW
  EXECUTE FUNCTION public.tg_community_posts_moderation_fields();
