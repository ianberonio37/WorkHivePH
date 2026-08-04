-- The community leaderboard could be farmed by one person clicking one button.
--
-- MEASURED 2026-08-04 (rolled-back psql probe, live local DB):
--   baseline after the post itself ............ 50 XP
--   after THREE emojis from ONE person ........ 70 XP   (+20 "3 reactions" paid)
--   after ONE remove + re-add ................. 90 XP   (+20 again)
--   after 5 more toggles ..................... 190 XP   (+120 more, unbounded)
--
-- Two separate defects in handle_community_reaction_xp(), both in one line:
--     SELECT COUNT(*) ... WHERE post_id = NEW.post_id;  IF reaction_count = 3 THEN pay 20
--
--   1. COUNT(*) counts ROWS, not PEOPLE. The unique key is
--      (post_id, worker_name, emoji), so ONE person may leave four reactions on the
--      same post -- one per allowed emoji. Three clicks by a single reactor satisfied
--      "gets 3 reactions". The community.html copy promises "+20 when one of your posts
--      gets 3 reactions: the team found it useful", and one person is not the team.
--
--   2. The award had no memory. The trigger is INSERT-only and re-evaluates the count
--      on every insert, while un-reacting HARD-DELETES the row (community.html:1477 --
--      the ordinary toggle, `.delete().eq('post_id'...)`, not a soft delete). So the
--      count falls to 2 and climbs back to 3 on every toggle, and every crossing paid
--      again. React / un-react / react is a button any signed-in user already has.
--
-- REACHABILITY: community_reactions_write requires only auth.uid() IS NOT NULL plus
-- either hive membership OR posts.public = true. On a PUBLIC post that is every signed-in
-- user on the platform, not just the hive. There is no self-reaction guard either, so an
-- author could farm their own total unaided.
--
-- WHY IT MATTERS BEYOND A LEADERBOARD: community XP feeds the community-trust signal shown
-- against a seller's marketplace listings. A forgeable trust counter is the same class as
-- the fake-sales defect fixed in the trust-forge work -- a number a buyer is asked to rely
-- on that its own producer does not police. The page even claims "XP rewards real help,
-- never logins, streaks, or giving reactions", which is precisely what was happening.
--
-- THE FIX, three parts:
--   a. count DISTINCT worker_name, so three reactions means three PEOPLE;
--   b. exclude the post's own author, so self-reactions never count toward "the team
--      found it useful";
--   c. give the award a memory -- a one-row-per-post ledger written with
--      ON CONFLICT DO NOTHING, paying only when the insert actually took. That makes the
--      award idempotent and race-safe: two concurrent third-reactors cannot both win,
--      because only one INSERT can succeed on the primary key.
-- Threshold becomes >= 3 rather than = 3; with a ledger, "at least three people" is the
-- honest reading and it no longer matters which insert observes the crossing.

CREATE TABLE IF NOT EXISTS public.community_reaction_xp_awards (
  post_id    uuid PRIMARY KEY REFERENCES public.community_posts(id) ON DELETE CASCADE,
  author_name text        NOT NULL,
  hive_id     uuid,
  xp_awarded  integer     NOT NULL,
  awarded_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.community_reaction_xp_awards IS
  'One row per post that has been paid the 3-distinct-reactor XP award. Written only by '
  'handle_community_reaction_xp() with ON CONFLICT DO NOTHING; the primary key is what '
  'makes the award once-per-post and race-safe.';

ALTER TABLE public.community_reaction_xp_awards ENABLE ROW LEVEL SECURITY;
-- No policy on purpose: nothing outside the SECURITY DEFINER trigger has any business
-- reading or writing this ledger, and RLS-with-no-policy denies every client role.
REVOKE ALL ON public.community_reaction_xp_awards FROM anon, authenticated;

CREATE OR REPLACE FUNCTION public.handle_community_reaction_xp()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  distinct_reactors integer;
  v_author          text;
  v_hive_id         uuid;
  v_paid            boolean := false;
BEGIN
  SELECT author_name, hive_id INTO v_author, v_hive_id
  FROM public.community_posts WHERE id = NEW.post_id;

  IF v_author IS NULL THEN
    RETURN NEW;
  END IF;

  -- People, not rows -- and never the author's own reactions.
  SELECT COUNT(DISTINCT worker_name) INTO distinct_reactors
  FROM public.community_reactions
  WHERE post_id = NEW.post_id
    AND worker_name IS DISTINCT FROM v_author;

  IF distinct_reactors >= 3 THEN
    -- The ledger IS the guard: pay only if this insert is the one that claimed the post.
    INSERT INTO public.community_reaction_xp_awards (post_id, author_name, hive_id, xp_awarded)
    VALUES (NEW.post_id, v_author, v_hive_id, 20)
    ON CONFLICT (post_id) DO NOTHING;

    GET DIAGNOSTICS distinct_reactors = ROW_COUNT;
    v_paid := (distinct_reactors = 1);

    IF v_paid THEN
      PERFORM public.increment_community_xp(v_author, v_hive_id, 20);
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;

-- Backfill the ledger for posts that already crossed three distinct non-author reactors,
-- so the fix does not hand out a second award on the next reaction to an old post.
INSERT INTO public.community_reaction_xp_awards (post_id, author_name, hive_id, xp_awarded, awarded_at)
SELECT cp.id, cp.author_name, cp.hive_id, 20, now()
FROM public.community_posts cp
WHERE (
  SELECT COUNT(DISTINCT cr.worker_name) FROM public.community_reactions cr
  WHERE cr.post_id = cp.id AND cr.worker_name IS DISTINCT FROM cp.author_name
) >= 3
ON CONFLICT (post_id) DO NOTHING;
