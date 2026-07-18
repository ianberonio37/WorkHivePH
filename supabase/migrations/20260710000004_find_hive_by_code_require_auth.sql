-- Hive Board Deep Arc (PDDA, 2026-07-10) — I3: require auth for find_hive_by_code.
-- The fn is SECURITY DEFINER and was EXECUTE-granted to `anon`. With no rate-limit, the
-- 6-char / 32-alphabet join-code space (~1.07e9) is enumerable by an UNauthenticated caller,
-- and a matched code auto-activates membership. The only caller (hive.html) is behind the
-- board's auth gate (redirects `!_authUid` to sign-in), so anon has no legitimate use of it.
-- Requiring authentication removes the unauthenticated enumeration surface. (Authenticated
-- brute-force is still bounded by the session + auth_uid attribution on the join write.)
-- NOTE: a function's EXECUTE is granted to PUBLIC by default (anon inherits it), so revoking
-- from anon alone is NOT enough — revoke from PUBLIC + anon, then grant back explicitly.
REVOKE EXECUTE ON FUNCTION public.find_hive_by_code(text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.find_hive_by_code(text) FROM anon;
GRANT  EXECUTE ON FUNCTION public.find_hive_by_code(text) TO authenticated, service_role;
