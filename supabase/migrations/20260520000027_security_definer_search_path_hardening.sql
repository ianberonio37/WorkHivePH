-- 2026-05-20 Flywheel Turn #3: SECURITY DEFINER search_path hardening
-- =====================================================================
-- Every SECURITY DEFINER function MUST set an explicit search_path to
-- prevent search-path injection. Without `SET search_path = ''` an
-- attacker who can create objects in any schema earlier on the
-- function's search_path can shadow a builtin (e.g. array_to_string)
-- and run with the definer's elevated rights.
--
-- This migration adds `SET search_path = ''` to the 8 SECURITY DEFINER
-- functions flagged by validate_security_definer_search_path.py:
--   handle_community_post_xp
--   handle_community_reaction_xp
--   handle_community_reply_xp
--   increment_community_xp(text, uuid, integer)
--   increment_listing_view(uuid)
--   sync_auth_uid_on_signup        (3 declarations across migrations)
-- ALTER FUNCTION is the right tool — we only modify the attribute,
-- not the body, so no logic changes ship with this migration.

ALTER FUNCTION public.handle_community_post_xp() SET search_path = '';
ALTER FUNCTION public.handle_community_reaction_xp() SET search_path = '';
ALTER FUNCTION public.handle_community_reply_xp() SET search_path = '';
ALTER FUNCTION public.increment_community_xp(text, uuid, integer) SET search_path = '';
ALTER FUNCTION public.increment_listing_view(uuid) SET search_path = '';
ALTER FUNCTION public.sync_auth_uid_on_signup() SET search_path = '';
