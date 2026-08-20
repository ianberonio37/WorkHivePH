-- REPLY XP WAS PAID WITH NO LEDGER AND NO WAY BACK — the third award kind, left out twice.
--
-- Found 2026-08-12 while measuring the CB `partial_write` oracle ("a multi-row or multi-table write
-- either lands whole or not at all; a half-applied write is visible as an inconsistency in the
-- ledger"). Reconciling community_xp against its own award tables showed one worker 110 XP short of
-- attribution, which sent me looking at every path that increments the total. Two of the three pay
-- through a ledger. The third does not:
--
--   handle_community_post_xp     -> INSERT community_post_xp_awards, pay only if claimed
--   handle_community_reaction_xp -> INSERT community_reaction_xp_awards, pay only if claimed
--   handle_community_reply_xp    -> PERFORM increment_community_xp(author, hive, 10);  -- and nothing else
--
-- So reply XP is unattributable (no record of WHICH reply earned it) and irreversible (nothing to
-- reverse against). That is the one-sided-write class the previous two migrations exist to close.
-- 20260804000049 did reactions. 20260806000059 did posts, and said so in its own words: "Posts were
-- simply left out of that pattern. This extends it rather than inventing a second one." It then left
-- REPLIES out in exactly the same way. This is the third and last award kind.
--
-- REACHABLE, THOUGH NOT FROM THE UI. community.html only INSERTs replies (:2402) — there is no reply
-- delete button. But `community_replies_delete` grants DELETE to `auth_uid = auth.uid()` (and to
-- supervisors for their hive), so any authenticated member can delete their own reply through the
-- ordinary REST path: reply (+10) -> delete (no reversal) -> repeat. community_reply_rate_limit()
-- bounds this to 5 per 15s; it bounds the RATE and never bounded the REVERSAL, which is the same
-- distinction migration 59 recorded about the post limiter.
--
-- WHY THE GUARD HANGS ON `DELETE` HERE, WHICH IS THE OPPOSITE OF THE POST FIX. Migration 59's central
-- lesson was that an ON DELETE trigger would never fire for posts, because the product SOFT-deletes
-- and the reversal had to hang on the deleted_at TRANSITION. Copying that here would be wrong twice
-- over: community_replies HAS NO deleted_at COLUMN (id, post_id, hive_id, author_name, content,
-- created_at, auth_uid, is_accepted), and it carries no DELETE trigger at all — only four INSERT ones.
-- For replies a hard DELETE is the ONLY delete path that exists, so DELETE is precisely where the
-- reversal belongs. Same lesson, opposite conclusion, because the lesson is "hang the guard on the
-- path the product actually takes" — not "always use the transition".
--
-- AND THEREFORE NO `ON DELETE CASCADE` ON THE LEDGER, which is the one place this table must NOT copy
-- community_post_xp_awards. That table references community_posts(id) ON DELETE CASCADE, which is safe
-- only because posts are soft-deleted so the cascade never fires in practice. Replies are hard-deleted,
-- so a cascade would destroy the award row at the exact moment the reversal needs to read it — and an
-- erased award row re-opens the reply to being paid again, which is the precise warning 20260806000058
-- records about the reaction ledger. The ledger must OUTLIVE the thing it paid for. So reply_id carries
-- no foreign key, deliberately, and the reversal stamps reversed_at rather than deleting.
--
-- SAFE TO LAND NOW, AND THIS IS THE CHEAPEST MOMENT IT WILL EVER BE: community_replies is EMPTY
-- (0 rows platform-wide), so there is no backfill to get right and no existing total to disturb. The
-- hole is closed before the first reply is ever written.
--
-- WHAT THIS MIGRATION DELIBERATELY DOES NOT DO. It does not touch anyone's xp_total. The 110
-- unattributed XP that led here belongs to a worker with 13 live posts, 0 deleted posts and 0 replies,
-- and platform-wide the ledger holds ZERO `first_post` rows and ZERO reaction rows for 15 posting
-- authors — migration 59's backfill created `safety_post` rows only. So the shortfall is an INCOMPLETE
-- BACKFILL of historical awards, not minted XP, and 185 is the same pre-existing total the
-- PB-community-057 walk recorded before it farmed. Provenance of that legacy figure is not
-- determinable from the data, and reducing a real worker's XP on an unproven premise would be a
-- destructive repair. It is recorded as a finding instead.

BEGIN;

-- ── the ledger ────────────────────────────────────────────────────────────────────────────────────
-- Key is reply_id alone, unlike the post ledger's (post_id, reason): a reply earns exactly one award,
-- for existing at all, so there is no second reason to collide with.
CREATE TABLE IF NOT EXISTS public.community_reply_xp_awards (
  reply_id    uuid        PRIMARY KEY,          -- NO FK: see the CASCADE note above
  post_id     uuid        NOT NULL,
  author_name text        NOT NULL,
  hive_id     uuid        NOT NULL,
  xp_awarded  integer     NOT NULL CHECK (xp_awarded > 0),
  awarded_at  timestamptz NOT NULL DEFAULT now(),
  reversed_at timestamptz
);

-- The reversal looks a row up by reply_id, which the primary key already serves. Index the author
-- rollup instead, because that is what the conservation check in validate_community_xp_ledger.py runs.
CREATE INDEX IF NOT EXISTS community_reply_xp_awards_author_live_idx
  ON public.community_reply_xp_awards (author_name, hive_id) WHERE reversed_at IS NULL;

-- Mirror both sibling ledgers exactly: no client role may read or write it. The ledger is the ONLY
-- record of what has been paid, so a client that can edit it can mint or erase reputation — and
-- community_xp feeds get_community_reputation and v_marketplace_sellers_truth, which is a COMMERCIAL
-- trust signal, not only a gamification number.
ALTER TABLE public.community_reply_xp_awards ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.community_reply_xp_awards FROM anon, authenticated;

-- ── awarding: claim first, pay only if the claim was ours ─────────────────────────────────────────
-- The ledger insert IS the guard, the idiom proven by handle_community_reaction_xp: two concurrent
-- inserts of the same reply_id leave exactly one with ROW_COUNT = 1, so exactly one pays.
CREATE OR REPLACE FUNCTION public.handle_community_reply_xp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  claimed integer;
BEGIN
  INSERT INTO public.community_reply_xp_awards (reply_id, post_id, author_name, hive_id, xp_awarded)
  VALUES (NEW.id, NEW.post_id, NEW.author_name, NEW.hive_id, 10)
  ON CONFLICT (reply_id) DO NOTHING;
  GET DIAGNOSTICS claimed = ROW_COUNT;
  IF claimed = 1 THEN
    PERFORM public.increment_community_xp(NEW.author_name, NEW.hive_id, 10);
  END IF;
  RETURN NEW;
END;
$function$;

-- ── reversal: on DELETE, because that is the only delete replies have ────────────────────────────
-- Stamps reversed_at instead of deleting the row, so a re-inserted reply with the same id cannot be
-- paid twice. The UPDATE's own WHERE clause carries the idempotency: it matches only a LIVE award, so
-- a second reversal debits nothing rather than double-debiting.
CREATE OR REPLACE FUNCTION public.reverse_community_reply_xp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  reversed integer;
  amount   integer;
BEGIN
  UPDATE public.community_reply_xp_awards
     SET reversed_at = now()
   WHERE reply_id = OLD.id AND reversed_at IS NULL
  RETURNING xp_awarded INTO amount;
  GET DIAGNOSTICS reversed = ROW_COUNT;
  IF reversed = 1 THEN
    -- increment_community_xp's negative branch is UPDATE-only by design: no row means nothing was
    -- ever credited, and a reversal that INSERTED a row would resurrect totals a reset had cleared.
    PERFORM public.increment_community_xp(OLD.author_name, OLD.hive_id, -amount);
  END IF;
  RETURN OLD;
END;
$function$;

DROP TRIGGER IF EXISTS trg_community_reply_delete_xp ON public.community_replies;
CREATE TRIGGER trg_community_reply_delete_xp
  AFTER DELETE ON public.community_replies
  FOR EACH ROW EXECUTE FUNCTION public.reverse_community_reply_xp();

-- ── register the ledger so the gate can assert it exists ─────────────────────────────────────────
-- Guarded by NOT EXISTS rather than ON CONFLICT: canonical_sources is keyed on `domain` alone
-- (PRIMARY KEY (domain)) and carries no unique constraint on source_name, so ON CONFLICT (source_name)
-- has nothing to match and raises.
INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, contract, description, registered_at)
SELECT
  'community_reply_xp', 'table', 'community_reply_xp_awards', 'community', 'on_demand',
  jsonb_build_object(
    'key', jsonb_build_array('reply_id'),
    'reads', 'none - RLS is enabled with NO policy and anon/authenticated are revoked, so no client '
             'role can select from it',
    'writes', 'handle_community_reply_xp() awards; reverse_community_reply_xp() stamps reversed_at. '
              'Both SECURITY DEFINER.',
    'reversal', 'reversed_at is stamped, never deleted - deleting the row would re-open the reply to '
                'being paid again, and the reply itself is HARD-deleted so the ledger must outlive it',
    'authority', 'the primary key IS the invariant: one row per reply means the 10 XP is paid at most '
                 'once, race-safe under concurrent inserts',
    'award_rule', '10 for each reply, reversed when the reply is deleted',
    'no_fk', 'reply_id intentionally carries NO foreign key: ON DELETE CASCADE would erase the award '
             'row at the moment the reversal needs it, unlike the post ledger where soft-delete means '
             'the cascade never fires'),
  'One row per community reply that has been paid 10 XP. Closes the third and last unledgered XP '
  'path; replies were left out of both 20260804000049 (reactions) and 20260806000059 (posts).',
  now()
WHERE NOT EXISTS (
  SELECT 1 FROM public.canonical_sources WHERE source_name = 'community_reply_xp_awards');

COMMIT;
