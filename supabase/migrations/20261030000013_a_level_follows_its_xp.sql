-- HS (2026-10-30, the hive at thirty - found by the psql suite after a day of reversals): a worker's achievement LEVEL
-- stood above the XP behind it. award_achievement_xp raises current_level when XP crosses a threshold ("persist level only
-- if it improved"), and nothing ever lowers it: trg_logbook_xp_reverse (a deleted entry's XP, since 2026-08) and
-- reverse_community_post_xp (a deleted post's achievement XP, 20261030000011) take XP away and leave the level. The banked
-- invariant achievements__level_recomputed - the level is the highest n whose threshold floor(100 * n^1.8) the XP meets,
-- the page's own xpForLevel - read 51 rows disagreeing once a day of walks' rows had been taken back.
-- Now the level follows the XP on every write of xp_total, whichever path writes it (an award, a reversal, a repair):
-- one function computes it from that threshold, capped at 100 as the award caps it. Every row is recomputed once - with
-- trg_iron_worker held off for that one pass, so a repair can never hand out the legendary award nobody earned by it.

CREATE OR REPLACE FUNCTION public.achievement_level_for_xp(p_xp bigint)
 RETURNS int
 LANGUAGE plpgsql
 IMMUTABLE
 SET search_path TO ''
AS $function$
DECLARE n int;
BEGIN
  n := LEAST(floor(power(GREATEST(coalesce(p_xp, 0), 0)::float / 100.0, 1.0 / 1.8))::int, 100);
  -- settled against the page's own threshold, so float rounding at a boundary cannot put the level one off
  WHILE n < 100 AND floor(100 * power(n + 1, 1.8)) <= p_xp LOOP n := n + 1; END LOOP;
  WHILE n > 0 AND floor(100 * power(n, 1.8)) > p_xp LOOP n := n - 1; END LOOP;
  RETURN n;
END;
$function$;

CREATE OR REPLACE FUNCTION public.worker_achievement_level_follows_xp()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO ''
AS $function$
BEGIN
  NEW.current_level := public.achievement_level_for_xp(NEW.xp_total);
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_worker_achievement_level_follows_xp ON public.worker_achievements;
CREATE TRIGGER trg_worker_achievement_level_follows_xp BEFORE INSERT OR UPDATE OF xp_total ON public.worker_achievements
  FOR EACH ROW EXECUTE FUNCTION public.worker_achievement_level_follows_xp();

-- the one-time repair writes levels only; no award may fire from it
ALTER TABLE public.worker_achievements DISABLE TRIGGER trg_iron_worker;
UPDATE public.worker_achievements
   SET current_level = public.achievement_level_for_xp(xp_total)
 WHERE current_level IS DISTINCT FROM public.achievement_level_for_xp(xp_total);
ALTER TABLE public.worker_achievements ENABLE TRIGGER trg_iron_worker;
