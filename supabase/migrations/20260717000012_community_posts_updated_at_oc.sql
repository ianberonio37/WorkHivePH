-- P6 concurrent-edit (bug-hunt roadmap, 2026-07-18, found live in community.html editPost).
-- community.html openEditor->submit blind-writes {content, category, public, mentions, edited_at}
-- with NO optimistic-concurrency guard. Two real failures:
--   (1) the same author editing in two sessions (phone + desktop) -> silent lost-update: whoever
--       saves last wins, the other edit's text vanishes with no warning;
--   (2) the edit re-writes `public`, which is ALSO a MODERATION-controlled field (togglePublic,
--       flagged/hide flows). A supervisor hides a post (public=false); the author then re-saves an
--       unrelated typo fix -> their stale isPublic=true overwrites the hide = moderation BYPASS.
-- Fix: add updated_at + the shared touch trigger so the client can guard .eq('updated_at', snapshot)
-- and treat a 0-row update as a conflict (reload authoritative state). Every write (edits AND the
-- moderation toggles pin/flag/public/soft-delete) bumps updated_at, so a stale author edit that would
-- clobber a concurrent moderation action now conflict-fails instead. community_replies has no edit
-- path (verified: no reply-body UPDATE in community.html) so it needs no column.
ALTER TABLE public.community_posts ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();
DROP TRIGGER IF EXISTS tg_touch_community_posts ON public.community_posts;
CREATE TRIGGER tg_touch_community_posts BEFORE UPDATE ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();
