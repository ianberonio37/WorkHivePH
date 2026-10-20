-- BRH-T (2026-10-21): every public function resolves names through a search_path it sets itself, never the caller's.
--
-- Supabase's advisor (function_search_path_mutable, emailed with the 2026-10-20 security notice) listed 73 functions
-- that resolve unqualified names through the CALLER's search_path - five were the hand-made debug_* functions dropped in
-- 20261015500000; 68 remained, 67 of them SECURITY INVOKER (the text-length caps and the actor binders on every write,
-- the knowledge searches, the reliability KPIs, the rate limiters, the touch-updated triggers). A caller who can create
-- an object earlier in their path - a temporary table or function - can stand it in for the one the body means.
--
-- Each is pinned to `public, extensions, pg_temp`: the same resolution the API roles have today (their database default
-- is "$user", public, extensions; no per-user schema exists), with pg_temp LAST so a temporary object can never shadow
-- a real one. So no body resolves a name differently - only the caller can no longer choose. This pins every public
-- function that has no search_path of its own, not only the advisor's list, so the rule holds for all of them; a
-- function that already sets one (e.g. search_path = '') keeps it, and extension members are left to their extension.

do $$
declare
  r record;
begin
  for r in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.prokind in ('f', 'p')
      and not exists (select 1 from unnest(coalesce(p.proconfig, '{}'::text[])) c where c like 'search_path=%')
      and not exists (select 1 from pg_depend d where d.classid = 'pg_proc'::regclass and d.objid = p.oid and d.deptype = 'e')
  loop
    execute format('alter function %s set search_path = public, extensions, pg_temp', r.sig);
  end loop;
end
$$;
