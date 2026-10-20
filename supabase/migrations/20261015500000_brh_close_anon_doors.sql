-- BRH (2026-10-21): two doors production left open to anyone holding the public key.
--
-- Supabase's security advisor (emailed 2026-10-20, "Action required: security vulnerabilities detected", read through
-- the claude.ai Supabase connector with get_advisors) listed 94 SECURITY DEFINER functions the anon role can execute.
-- Two kinds among them need nothing but the public key to do harm, and neither needs anon at all:
--
-- 1. TEN HAND-MADE debug_* FUNCTIONS THAT NO MIGRATION CREATES. They exist only in production, left from a debugging
--    session, and anon may run every one. debug_definer_all_workers() runs as the owner, past every row policy, and
--    returns the ten highest-level workers' names and account ids; debug_table_policies() hands out the text of any
--    table's row policies; the rest list objects, grants and RLS state, or read the first row / the count of any table
--    the caller can see. Nothing in the product calls them. They are dropped, every overload, by name.
--
-- 2. SIX SERVER-ONLY FUNCTIONS THAT CHECK NO CALLER AND WRITE. Every caller is the service role (the ai-gateway's
--    adminClient, the voice and RAG functions' service-role clients) or another SECURITY DEFINER function, so anon and
--    authenticated never needed them - but they had them by default:
--      enqueue_user_push        queues a Web Push to ANY account ids with any title, body and link - a phishing channel
--                               through our own notifications
--      consume_ai_global_budget spends the platform-wide daily AI budget; drained, every AI feature refuses everyone
--      ai_cache_bump, ai_cache_sweep_expired, prune_embedding_cache, record_ai_chain_depth
--                               write cache counters, delete cache rows, record telemetry
--    EXECUTE is taken from PUBLIC, anon and authenticated, and granted to service_role explicitly. Every overload is
--    covered by name, so a signature that differs between environments (production's enqueue_user_push has a fifth
--    p_category argument this database does not) is closed too.
--
-- 3. EVERY HIVE'S KPIs TO A SIGNED-OUT VISITOR. v_kpi_truth is a MATERIALIZED view, which row-level security cannot
--    filter, and anon could select it: 123 rows of seven hives' MTBF, MTTR, downtime and failure counts to anyone with
--    the public key. Its one reader (voice-handler.js) asks only when the person has a hive, so a signed-out visitor
--    never needed it. (Signed-in members can still read OTHER hives' rows; that is closed with a membership-checked
--    read and the handler's change, its own row.)
--
-- ★WHY enqueue_user_push WAS OPEN: 20260803000033 revoked the 4-argument function from PUBLIC, anon and authenticated;
-- 20260901000002 DROPPED it and created a 5-argument one (p_category). DROP + CREATE gives a function the default
-- privileges again - EXECUTE to PUBLIC - so the earlier revoke silently stopped applying in production from that day.
--
-- Idempotent: a function that is absent is skipped; a revoke that was already made changes nothing.

do $$
declare
  r record;
begin
  for r in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname in ('debug_anon_all_workers', 'debug_anon_first_row', 'debug_anon_role', 'debug_anon_visible_count',
                        'debug_column_privs', 'debug_definer_all_workers', 'debug_list_objects', 'debug_table_policies',
                        'debug_table_privs', 'debug_table_rls_state')
  loop
    execute format('drop function if exists %s', r.sig);
  end loop;

  for r in
    select p.oid::regprocedure as sig
    from pg_proc p join pg_namespace n on n.oid = p.pronamespace
    where n.nspname = 'public'
      and p.proname in ('enqueue_user_push', 'consume_ai_global_budget', 'ai_cache_bump', 'ai_cache_sweep_expired',
                        'prune_embedding_cache', 'record_ai_chain_depth')
  loop
    execute format('revoke execute on function %s from public, anon, authenticated', r.sig);
    execute format('grant execute on function %s to service_role', r.sig);
  end loop;

  if to_regclass('public.v_kpi_truth') is not null then
    revoke all on public.v_kpi_truth from anon;
  end if;
end
$$;
