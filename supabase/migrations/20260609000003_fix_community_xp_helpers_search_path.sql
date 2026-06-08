-- Finish the community search_path fix started in 20260609000002.
--
-- A sweep of all SECURITY DEFINER functions with `SET search_path TO ''` turned
-- up two more carrying the same unqualified-reference defect:
--
--   increment_community_xp()        — INSERT INTO community_xp ... ON CONFLICT
--                                     ... community_xp.xp_total  (unqualified)
--   handle_community_reaction_xp()  — FROM community_reactions / FROM
--                                     community_posts / PERFORM
--                                     increment_community_xp  (all unqualified)
--
-- Impact each:
--   * increment_community_xp is invoked by handle_community_post_xp on a user's
--     FIRST post and on any 'safety' post — so even after 20260609000002 a brand
--     new author's first post would still abort (the qualified call reaches a
--     function whose own body can't resolve community_xp).
--   * handle_community_reaction_xp is the AFTER INSERT trigger on
--     community_reactions, so EVERY reaction insert raised 42P01 — reactions
--     were 100% broken platform-wide, same as posts were.
--
-- Fix: keep `search_path = ''` and fully schema-qualify every reference.
-- Forward-only; CREATE OR REPLACE preserves trigger bindings.

CREATE OR REPLACE FUNCTION public.increment_community_xp(p_worker_name text, p_hive_id uuid, p_amount integer)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
BEGIN
  INSERT INTO public.community_xp (worker_name, hive_id, xp_total, updated_at)
  VALUES (p_worker_name, p_hive_id, p_amount, now())
  ON CONFLICT (worker_name, hive_id) DO UPDATE
  SET xp_total   = public.community_xp.xp_total + p_amount,
      updated_at = now();
END;
$function$;

CREATE OR REPLACE FUNCTION public.handle_community_reaction_xp()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO ''
AS $function$
DECLARE
  reaction_count integer;
  v_author       text;
  v_hive_id      uuid;
BEGIN
  SELECT COUNT(*) INTO reaction_count
  FROM public.community_reactions WHERE post_id = NEW.post_id;

  IF reaction_count = 3 THEN
    SELECT author_name, hive_id INTO v_author, v_hive_id
    FROM public.community_posts WHERE id = NEW.post_id;
    IF v_author IS NOT NULL THEN
      PERFORM public.increment_community_xp(v_author, v_hive_id, 20);
    END IF;
  END IF;

  RETURN NEW;
END;
$function$;
