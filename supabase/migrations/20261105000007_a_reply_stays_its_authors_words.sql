-- ★A REPLY COULD BE REWRITTEN BY SOMEONE ELSE, OR ACCEPTED BY ITS OWN AUTHOR (2026-11-05, found reading J7's premise).
--
-- community_posts has carried tg_community_posts_moderation_fields since the posts were hardened: "nobody else's words go
-- out under this author's name" - a supervisor may moderate a post (flag, pin, share) and may not change what it says.
-- community_replies never got the same guard. Its UPDATE policy (community_replies_modify) lets the author AND any
-- supervisor of the hive update a reply, every column, so:
--   - a supervisor could rewrite a member's answer, and it would still read as the member's;
--   - a reply's author could set is_accepted on their own reply - "best answer" is meant to be the asker's (or a
--     supervisor's) choice, made through set_community_best_answer, the one writer that keeps it single-valued.
-- The same rule as posts, the same shape: a definer function acting for the platform (set_community_best_answer runs as
-- its owner) passes; a signed-in client keeps someone else's words and the acceptance as they were.

CREATE OR REPLACE FUNCTION public.tg_community_replies_authorship_fields()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public', 'pg_temp'
AS $$
BEGIN
  IF auth.uid() IS NULL OR current_user <> 'authenticated' THEN
    RETURN NEW;                       -- server-side context, or a definer function acting for the platform
  END IF;

  IF OLD.auth_uid IS DISTINCT FROM auth.uid() THEN
    NEW.content     := OLD.content;     -- nobody else's words go out under this author's name
    NEW.author_name := OLD.author_name;
  END IF;

  -- what a reply is attached to, and who wrote it, never change from a client
  NEW.post_id  := OLD.post_id;
  NEW.hive_id  := OLD.hive_id;
  NEW.auth_uid := OLD.auth_uid;

  -- the best answer is chosen through set_community_best_answer, never by a direct write (least of all the author's)
  NEW.is_accepted := OLD.is_accepted;
  NEW.accepted_by := OLD.accepted_by;
  NEW.accepted_at := OLD.accepted_at;

  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tg_community_replies_authorship_fields ON public.community_replies;
CREATE TRIGGER tg_community_replies_authorship_fields
  BEFORE UPDATE ON public.community_replies
  FOR EACH ROW EXECUTE FUNCTION public.tg_community_replies_authorship_fields();
