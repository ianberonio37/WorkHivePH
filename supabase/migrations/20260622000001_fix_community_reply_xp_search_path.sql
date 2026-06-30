-- 20260622000001_fix_community_reply_xp_search_path.sql
-- ============================================================================
-- FIX (Arc K K3 caught it live): posting a community REPLY fails with HTTP 500 —
--   "function increment_community_xp(text, uuid, integer) does not exist" (42883)
-- so the entire reply feature is broken (every reply insert is rolled back by the
-- failing AFTER-INSERT XP trigger).
--
-- ROOT CAUSE: a security-hardening pass set `SET search_path TO ''` on the XP
-- trigger functions (correct — pins the path so an attacker can't shadow a function),
-- but handle_community_reply_xp still calls increment_community_xp UNQUALIFIED. With an
-- empty search_path an unqualified name cannot resolve → 42883, even though
-- public.increment_community_xp(text,uuid,integer) exists. The sibling
-- handle_community_post_xp does it correctly (calls public.increment_community_xp),
-- which is why posting works but replying does not.
--
-- FIX: schema-qualify the call (public.increment_community_xp), matching the post
-- trigger. Pure correctness fix; no signature/behaviour change.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.handle_community_reply_xp()
  RETURNS trigger
  LANGUAGE plpgsql
  SECURITY DEFINER
  SET search_path TO ''
AS $function$
BEGIN
  PERFORM public.increment_community_xp(NEW.author_name, NEW.hive_id, 10);
  RETURN NEW;
END;
$function$;
