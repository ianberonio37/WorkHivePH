-- COMMUNITY XP WAS A TOTAL WITH NO LEDGER, SO IT COULD NOT REVERSE — AND WAS FARMABLE.
--
-- Found 2026-08-05 by walking PB-community-057 (xp_once_and_reverses) on the live database.
-- Three cycles of (insert a category='safety' post -> soft-delete it) took one worker's
-- community_xp.xp_total from 185 to 260, with ZERO posts left visible to any feed. Each safety
-- INSERT pays +25 through handle_community_post_xp, and nothing anywhere reverses it.
--
-- THE PATH MATTERS AND THE OBVIOUS FIX IS THE WRONG ONE. community.html:1821 does NOT delete a
-- post; it soft-deletes with .update({deleted_at}), and :1840 offers a RESTORE with
-- .update({deleted_at: null}). Every feed read filters `.is('deleted_at', null)`. So an ON DELETE
-- trigger — the first thing you would reach for — would never fire on the path a person actually
-- takes, and the farm would survive a fix that looked complete. The reversal therefore hangs on the
-- deleted_at TRANSITION, and ON DELETE is kept only for the hard-delete paths (moderation, reset).
--
-- WHY A LEDGER RATHER THAN A COUNTER-DECREMENT. community_xp is (worker_name, hive_id, xp_total,
-- updated_at, auth_uid): a running total with no record of WHICH row earned WHAT. You cannot reverse
-- what you cannot attribute, and you cannot audit it either — the one-sided-write class. The platform
-- already solved exactly this for reactions: migration 20260804000049 added
-- community_reaction_xp_awards, one row per paid post, the PRIMARY KEY doing the once-only
-- enforcement, claimed race-safely with INSERT .. ON CONFLICT DO NOTHING + GET DIAGNOSTICS ROW_COUNT.
-- Posts were simply left out of that pattern. This extends it rather than inventing a second one.
--
-- The ledger is APPEND-ONLY IN PRACTICE: a reversal stamps reversed_at instead of deleting the row,
-- because deleting it would re-open the post to being paid again — the precise warning
-- 20260806000058 records about the reaction ledger. Restore clears reversed_at and re-pays, so
-- delete/restore/delete cannot drift the total.
--
-- The reaction ledger shares the reversal gap (soft-delete a post whose reactions paid 20 and the 20
-- stands), so the reversal covers BOTH ledgers. One mechanism, both award kinds.

BEGIN;

-- ── the ledger ────────────────────────────────────────────────────────────────────────────────────
-- Key is (post_id, reason), NOT post_id alone: a first post that is also a safety post legitimately
-- earns BOTH the 50 and the 25, and a post_id-only key would silently swallow the second award under
-- ON CONFLICT DO NOTHING.
CREATE TABLE IF NOT EXISTS public.community_post_xp_awards (
  post_id     uuid        NOT NULL REFERENCES public.community_posts(id) ON DELETE CASCADE,
  reason      text        NOT NULL CHECK (reason IN ('first_post', 'safety_post')),
  author_name text        NOT NULL,
  hive_id     uuid        NOT NULL,
  xp_awarded  integer     NOT NULL CHECK (xp_awarded > 0),
  awarded_at  timestamptz NOT NULL DEFAULT now(),
  reversed_at timestamptz,
  PRIMARY KEY (post_id, reason)
);

-- Reversal walks by post, so index the lookup the trigger actually makes.
CREATE INDEX IF NOT EXISTS community_post_xp_awards_live_idx
  ON public.community_post_xp_awards (post_id) WHERE reversed_at IS NULL;

-- Mirror the reaction ledger's posture exactly: no client role may read or write it. The ledger is
-- the ONLY record of what has been paid, so a client that can edit it can mint or erase reputation.
ALTER TABLE public.community_post_xp_awards ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.community_post_xp_awards FROM anon, authenticated;

-- ── awarding: claim first, pay only if the claim was ours ─────────────────────────────────────────
-- The ledger insert IS the guard. Two concurrent inserts of the same (post_id, reason) leave exactly
-- one with ROW_COUNT=1, so exactly one pays — the idiom proven by handle_community_reaction_xp.
CREATE OR REPLACE FUNCTION public.handle_community_post_xp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  post_count integer;
  claimed    integer;
BEGIN
  -- Count only LIVE posts. Counting soft-deleted ones would let a person delete their history and
  -- never see the first-post milestone again, and would also make the count non-reproducible.
  SELECT COUNT(*) INTO post_count
  FROM public.community_posts
  WHERE author_name = NEW.author_name AND hive_id = NEW.hive_id AND deleted_at IS NULL;

  IF post_count = 1 THEN
    INSERT INTO public.community_post_xp_awards (post_id, reason, author_name, hive_id, xp_awarded)
    VALUES (NEW.id, 'first_post', NEW.author_name, NEW.hive_id, 50)
    ON CONFLICT (post_id, reason) DO NOTHING;
    GET DIAGNOSTICS claimed = ROW_COUNT;
    IF claimed = 1 THEN
      PERFORM public.increment_community_xp(NEW.author_name, NEW.hive_id, 50);
    END IF;
  END IF;

  IF NEW.category = 'safety' THEN
    INSERT INTO public.community_post_xp_awards (post_id, reason, author_name, hive_id, xp_awarded)
    VALUES (NEW.id, 'safety_post', NEW.author_name, NEW.hive_id, 25)
    ON CONFLICT (post_id, reason) DO NOTHING;
    GET DIAGNOSTICS claimed = ROW_COUNT;
    IF claimed = 1 THEN
      PERFORM public.increment_community_xp(NEW.author_name, NEW.hive_id, 25);
    END IF;
  END IF;

  IF post_count = 10 THEN
    INSERT INTO public.skill_badges (worker_name, discipline, level, badge_key, earned_at, auth_uid)
    VALUES (NEW.author_name, 'Community', 1, 'voice_of_the_hive', now(), NEW.auth_uid)
    ON CONFLICT (worker_name, badge_key) DO NOTHING;
  END IF;

  RETURN NEW;
END;
$function$;

-- ── reversal: one function, both ledgers, driven by whether the post is still live ────────────────
CREATE OR REPLACE FUNCTION public.reverse_community_post_xp(p_post_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT post_id, reason, author_name, hive_id, xp_awarded
      FROM public.community_post_xp_awards
     WHERE post_id = p_post_id AND reversed_at IS NULL
     FOR UPDATE
  LOOP
    PERFORM public.increment_community_xp(r.author_name, r.hive_id, -r.xp_awarded);
    UPDATE public.community_post_xp_awards SET reversed_at = now()
     WHERE post_id = r.post_id AND reason = r.reason;
  END LOOP;

  -- The reaction ledger has no reversed_at column and one row per post, so its reversal is recorded
  -- by zeroing the amount rather than by deleting the row: the row must SURVIVE, or the post becomes
  -- payable a second time (20260806000058's own warning).
  FOR r IN
    SELECT post_id, author_name, hive_id, xp_awarded
      FROM public.community_reaction_xp_awards
     WHERE post_id = p_post_id AND xp_awarded > 0
     FOR UPDATE
  LOOP
    PERFORM public.increment_community_xp(r.author_name, r.hive_id, -r.xp_awarded);
    UPDATE public.community_reaction_xp_awards SET xp_awarded = 0 WHERE post_id = r.post_id;
  END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION public.restore_community_post_xp(p_post_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT post_id, reason, author_name, hive_id, xp_awarded
      FROM public.community_post_xp_awards
     WHERE post_id = p_post_id AND reversed_at IS NOT NULL
     FOR UPDATE
  LOOP
    PERFORM public.increment_community_xp(r.author_name, r.hive_id, r.xp_awarded);
    UPDATE public.community_post_xp_awards SET reversed_at = NULL
     WHERE post_id = r.post_id AND reason = r.reason;
  END LOOP;
END;
$function$;

-- The transition trigger — the one that actually fires on the product's delete button.
CREATE OR REPLACE FUNCTION public.handle_community_post_visibility_xp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
BEGIN
  IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
    PERFORM public.reverse_community_post_xp(NEW.id);
  ELSIF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NULL THEN
    PERFORM public.restore_community_post_xp(NEW.id);
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_community_post_visibility_xp ON public.community_posts;
CREATE TRIGGER trg_community_post_visibility_xp
  AFTER UPDATE OF deleted_at ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.handle_community_post_visibility_xp();

-- The hard-delete path (moderation, reset). BEFORE DELETE, because the ledger row is
-- ON DELETE CASCADE and would already be gone in an AFTER trigger.
CREATE OR REPLACE FUNCTION public.handle_community_post_delete_xp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
BEGIN
  IF OLD.deleted_at IS NULL THEN      -- an already-soft-deleted post was reversed at that moment
    PERFORM public.reverse_community_post_xp(OLD.id);
  END IF;
  RETURN OLD;
END;
$function$;

DROP TRIGGER IF EXISTS trg_community_post_delete_xp ON public.community_posts;
CREATE TRIGGER trg_community_post_delete_xp
  BEFORE DELETE ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.handle_community_post_delete_xp();

-- increment_community_xp now takes negative amounts, so it must not be able to drive a total below
-- zero — a negative reputation would be a new defect.
--
-- AND A REVERSAL MUST NEVER *CREATE* A ROW. The first cut of this migration used one upsert for both
-- directions, which meant reversing an award for a worker who has no community_xp row INSERTED one at
-- GREATEST(0, -25) = 0. That is not hypothetical: reset.py clears community_xp (its line 106) BEFORE
-- community_posts (line 109), so the very next DELETE fired this trigger and resurrected a
-- zero-valued row into a table that had just been emptied — measured, 0 rows -> 1 row at value 0.
-- A reset would have ended with junk XP rows for every author of a safety post, and the defect would
-- have been blamed on the seeder. Semantically the guard is the obvious one: if there is no row,
-- there is no award to take back, so a reversal is a no-op rather than a creation.
CREATE OR REPLACE FUNCTION public.increment_community_xp(p_worker_name text, p_hive_id uuid, p_amount integer)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  v_auth_uid uuid;
BEGIN
  IF p_amount < 0 THEN
    UPDATE public.community_xp
       SET xp_total   = GREATEST(0, public.community_xp.xp_total + p_amount),
           updated_at = now()
     WHERE worker_name = p_worker_name AND hive_id = p_hive_id;
    RETURN;                       -- no row to debit means nothing was ever credited here
  END IF;

  SELECT hm.auth_uid INTO v_auth_uid
  FROM public.hive_members hm
  WHERE hm.worker_name = p_worker_name AND hm.hive_id = p_hive_id AND hm.status = 'active'
  LIMIT 1;

  INSERT INTO public.community_xp (worker_name, hive_id, xp_total, updated_at, auth_uid)
  VALUES (p_worker_name, p_hive_id, p_amount, now(), v_auth_uid)
  ON CONFLICT (worker_name, hive_id) DO UPDATE
  SET xp_total   = GREATEST(0, public.community_xp.xp_total + p_amount),
      updated_at = now(),
      auth_uid   = COALESCE(public.community_xp.auth_uid, EXCLUDED.auth_uid);
END;
$function$;

-- ── register it, or the anchor gate is right to complain ──────────────────────────────────────────
-- The parenthesised VALUES tuple is the house idiom the canonical-anchor gate reads from migration
-- text; a SELECT-list form registers at runtime and is invisible to that reader.
INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description)
VALUES
  ('community_post_xp', 'table', 'community_post_xp_awards', 'community', 'on_demand',
   jsonb_build_object(
     'key',        jsonb_build_array('post_id', 'reason'),
     'writes',     'handle_community_post_xp() awards; reverse_community_post_xp()/restore_community_post_xp() flip reversed_at. All SECURITY DEFINER.',
     'reads',      'none - RLS is enabled with NO policy and anon/authenticated are revoked, so no client role can select from it',
     'authority',  'the primary key IS the invariant: one row per (post, reason) means each award is paid at most once, race-safe under concurrent inserts',
     'award_rule', '50 for the author first LIVE post in a hive, 25 for a category=safety post; reversed when the post stops being visible and re-applied if it is restored',
     'reversal',   'reversed_at is stamped, never deleted - deleting the row would re-open the post to being paid again'),
   'One row per XP award paid for a community post, keyed by (post_id, reason). Append-only in '
   'practice: a reversal stamps reversed_at so delete/restore/delete cannot drift the total. Written '
   'only by SECURITY DEFINER triggers; readable by no client role.')
ON CONFLICT (domain) DO NOTHING;

DO $$
DECLARE v_pk text;
BEGIN
  SELECT string_agg(a.attname, ',' ORDER BY a.attname)
    INTO v_pk
    FROM pg_index i
    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY (i.indkey)
   WHERE i.indrelid = 'public.community_post_xp_awards'::regclass AND i.indisprimary;
  IF v_pk IS DISTINCT FROM 'post_id,reason' THEN
    RAISE EXCEPTION 'the registry says the key is (post_id, reason); the table says %', coalesce(v_pk, '(none)');
  END IF;
  RAISE NOTICE 'community_post_xp_awards anchored; key agrees with the contract';
END $$;

-- ── backfill: existing paid awards have no ledger rows, so they are unreversible until they do ────
-- Only LIVE posts are backfilled, and deliberately WITHOUT re-paying: the XP is already in the
-- total. This writes the attribution that was missing, so a future delete can reverse it.
INSERT INTO public.community_post_xp_awards (post_id, reason, author_name, hive_id, xp_awarded, awarded_at)
SELECT p.id, 'safety_post', p.author_name, p.hive_id, 25, p.created_at
  FROM public.community_posts p
 WHERE p.category = 'safety' AND p.deleted_at IS NULL
   AND EXISTS (SELECT 1 FROM public.community_xp x
                WHERE x.worker_name = p.author_name AND x.hive_id = p.hive_id)
ON CONFLICT (post_id, reason) DO NOTHING;

COMMIT;
