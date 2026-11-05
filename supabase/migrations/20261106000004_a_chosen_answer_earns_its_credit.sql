-- ★AN ANSWER CHOSEN AS THE BEST EARNED NOTHING (2026-11-06, GJ M9 J7 hand-off 4: "the credit the accepted answer
-- earned").
--
-- A worker who answers a teammate's question is pushed "Your answer was chosen" (notify_reply_accepted) - and then the
-- achievements page, which lists what every action earns ("the rates below are the ones the platform actually awards"),
-- shows nothing for it: set_community_best_answer pays nothing, and a reply's own +10 goes to the separate community
-- tally the achievements page does not read. The work a Q&A rewards most - the answer that solved someone's problem -
-- was the one the record of work done here left out.
--
-- A reply becoming the best answer now pays its author 30 XP on voice_of_hive ("Post and reply in the community"), in
-- the achievement log the page reads (source_action best_answer, source_id = the reply). It is taken back the way a
-- deleted post's is (reverse_community_post_xp): un-choosing it, or moving the best answer to another reply, reverses
-- the award with a negative line. Choosing your own reply on your own question pays nothing. A trigger, so every path
-- that flips is_accepted pays or takes back - not only set_community_best_answer.

BEGIN;

CREATE OR REPLACE FUNCTION public.tg_best_answer_xp()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
  v_asker uuid;
  r record;
BEGIN
  IF NEW.is_accepted IS NOT DISTINCT FROM OLD.is_accepted THEN
    RETURN NEW;
  END IF;

  IF NEW.is_accepted THEN
    SELECT p.auth_uid INTO v_asker FROM public.community_posts p WHERE p.id = NEW.post_id;
    -- your own reply on your own question earns nothing; an award already standing is not paid twice
    IF NEW.author_name IS NOT NULL AND (NEW.auth_uid IS NULL OR NEW.auth_uid IS DISTINCT FROM v_asker)
       AND NOT EXISTS (SELECT 1 FROM public.achievement_xp_log l
                        WHERE l.source_action = 'best_answer' AND l.source_id = NEW.id::text
                          AND l.reversed_at IS NULL AND l.xp_earned > 0) THEN
      PERFORM public.award_achievement_xp(NEW.author_name, 'voice_of_hive', 30, 'best_answer', NEW.id::text);
    END IF;
  ELSE
    FOR r IN
      SELECT id, worker_name, achievement_id, xp_earned, source_action
        FROM public.achievement_xp_log
       WHERE source_action = 'best_answer' AND source_id = NEW.id::text
         AND reversed_at IS NULL AND xp_earned > 0
       FOR UPDATE
    LOOP
      UPDATE public.worker_achievements
         SET xp_total = GREATEST(0, xp_total - r.xp_earned)
       WHERE worker_name = r.worker_name AND achievement_id = r.achievement_id;
      UPDATE public.achievement_xp_log SET reversed_at = now() WHERE id = r.id;
      INSERT INTO public.achievement_xp_log (worker_name, achievement_id, xp_earned, source_action, source_id, reversed_at)
      VALUES (r.worker_name, r.achievement_id, -r.xp_earned, r.source_action, NEW.id::text, now());
    END LOOP;
  END IF;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_best_answer_xp ON public.community_replies;
CREATE TRIGGER trg_best_answer_xp
  AFTER UPDATE OF is_accepted ON public.community_replies
  FOR EACH ROW EXECUTE FUNCTION public.tg_best_answer_xp();

REVOKE ALL ON FUNCTION public.tg_best_answer_xp() FROM PUBLIC, anon, authenticated;

COMMIT;
