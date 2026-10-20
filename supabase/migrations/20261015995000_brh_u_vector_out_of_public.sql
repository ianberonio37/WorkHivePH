-- BRH-U (2026-10-21): the vector extension lives in the extensions schema, not beside the API's own objects.
--
-- Supabase's advisor (extension_in_public, emailed with the 2026-10-20 security notice) named two extensions installed in
-- public, the schema PostgREST exposes: vector and pg_net. pgvector is relocatable, so it moves; its type, operators and
-- operator classes move with it, every vector column and index keeps working (they hold the type's identity, not its
-- schema), and an RPC that takes or returns a vector is unchanged.
--
-- What could break is a function that uses a vector OPERATOR (<=>, <->, <#>) or the type by name under a search_path that
-- does not include extensions - operators are found through the search_path. Nine did locally (the semantic_search_*
-- family, match_procedural_memories, search_skill_knowledge, search_voice_journal_entries, two trash triggers whose text
-- matched). Each such function gets `extensions` appended to the search_path it already sets, chosen in this database at
-- apply time, so production's own definitions are covered too. Then the extension moves.

do $$
declare
  r record;
  cur text;
begin
  for r in
    select p.oid::regprocedure as sig,
           (select substring(c from 'search_path=(.*)') from unnest(coalesce(p.proconfig, '{}'::text[])) c
             where c like 'search_path=%' limit 1) as path
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.prokind in ('f', 'p')
      and not exists (select 1 from pg_depend d where d.classid = 'pg_proc'::regclass and d.objid = p.oid and d.deptype = 'e')
      and (p.prosrc ~ '<=>|<->|<#>|::vector|vector\(' or pg_get_function_arguments(p.oid) ~ 'vector'
           or pg_get_function_result(p.oid) ~ 'vector')
  loop
    cur := r.path;
    if cur is not null and cur !~ '(^|[ ,])extensions([ ,]|$)' then
      execute format('alter function %s set search_path = %s, extensions', r.sig, cur);
    end if;
  end loop;

  if exists (select 1 from pg_extension e join pg_namespace n on n.oid = e.extnamespace
             where e.extname = 'vector' and n.nspname = 'public') then
    alter extension vector set schema extensions;
  end if;
end
$$;
