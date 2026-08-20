-- LOGBOOK XP WAS PAID WITH NO WAY BACK — the same defect a third time, on the LARGEST source.
--
-- Found 2026-08-20 walking the achievements CD invariant `xp_reverses` ("revoked source activity
-- reverses its XP; earning is not one-way if the reason disappears").
--
-- 20260804000049 closed reactions. 20260806000059 closed posts. 20260812000060 closed replies, and
-- opened by calling itself "the third award kind, left out twice." All three are COMMUNITY. Nobody
-- ever came back for the logbook, which pays more XP than all of them together:
--
--   trg_logbook_achievement_xp -> award_achievement_xp(...)   INSERT/UPDATE only, no DELETE branch
--   reverse_community_post_xp  \
--   reverse_community_reply_xp  }  exist
--   restore_community_post_xp  /
--   reverse_*_logbook_*            does not exist
--
-- The gap here is NOT the one migrations 59/60 fixed. achievement_xp_log already IS a ledger: it
-- records worker, achievement, amount, source_action and source_id. What is missing is the way BACK
-- — no reversal path, and no marker to stop a reversal being applied twice.
--
-- MEASURED, with a control so the join is known to work: of 399 logbook-sourced XP rows carrying a
-- source_id, 110 still resolve to a logbook row and 289 do not (272 logbook_submit + 17
-- logbook_close). Those 289 paid for work that is no longer in the system. logbook has no
-- soft-delete column, so the delete is a hard DELETE and the row is simply gone.
--
-- WHY THE 289 ARE NOT CLAWED BACK HERE. They were earned under a contract that never promised
-- reversal, and this database's logbook has been reseeded, so an unknown share of them are fixture
-- churn rather than a person's deleted work. Deducting them now would move real totals on the
-- strength of a guess about which. This migration closes the path FORWARD and records the historical
-- residue in the open rather than silently absorbing it. A deliberate claw-back, if wanted, is a
-- separate decision with its own evidence.
--
-- SHAPE. Mirrors reverse_community_post_xp deliberately: only unreversed positive awards are
-- reversed, the original row SURVIVES and is stamped reversed_at (20260806000058's warning — a
-- deleted ledger row makes the source payable a second time), and a compensating negative row is
-- written for audit, itself pre-stamped so it can never be reversed in turn. xp_total floors at 0.
-- current_level is deliberately NOT lowered: award_achievement_xp only ever persists a level that
-- improved, so levels do not regress in this system, and this migration does not change that rule.
--
-- Exposed as a TRIGGER FUNCTION only, never a callable helper, so there is no user-invokable
-- "reverse this worker's XP" surface (the DEFINER-helper-is-callable-by-default hazard).

ALTER TABLE public.achievement_xp_log
  ADD COLUMN IF NOT EXISTS reversed_at timestamptz;

COMMENT ON COLUMN public.achievement_xp_log.reversed_at IS
  'Set when this award was reversed because its source was deleted. The row survives so the source cannot be paid twice. Compensating negative rows are written pre-stamped and are never themselves reversible.';

CREATE OR REPLACE FUNCTION public.trg_logbook_xp_reverse()
RETURNS trigger
LANGUAGE plpgsql
-- SECURITY DEFINER, matching award_achievement_xp (20260508000002:158), which this reverses.
-- Without it the function runs as the CALLING user, and a worker holds only SELECT on
-- achievement_xp_log (20260508000002:152) -- deliberately, since a client that can write its own XP
-- can self-deal. So the INSERT below raised 42501 inside the trigger and took the user's own logbook
-- DELETE down with it. No EXECUTE revoke is needed: PostgreSQL refuses direct calls to a
-- RETURNS trigger function, so this exposes no user-callable helper.
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT id, worker_name, achievement_id, xp_earned, source_action
      FROM public.achievement_xp_log
     WHERE source_id = OLD.id::text
       AND reversed_at IS NULL
       AND xp_earned > 0
     FOR UPDATE
  LOOP
    UPDATE public.worker_achievements
       SET xp_total = GREATEST(0, xp_total - r.xp_earned)
     WHERE worker_name = r.worker_name
       AND achievement_id = r.achievement_id;

    UPDATE public.achievement_xp_log
       SET reversed_at = now()
     WHERE id = r.id;

    INSERT INTO public.achievement_xp_log
      (worker_name, achievement_id, xp_earned, source_action, source_id, reversed_at)
    VALUES
      (r.worker_name, r.achievement_id, -r.xp_earned, r.source_action, OLD.id::text, now());
  END LOOP;

  RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS trg_logbook_xp_reverse ON public.logbook;
CREATE TRIGGER trg_logbook_xp_reverse
  AFTER DELETE ON public.logbook
  FOR EACH ROW
  EXECUTE FUNCTION public.trg_logbook_xp_reverse();
