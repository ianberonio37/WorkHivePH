-- 20260707000005_fix_store_memory_turn_notnull.sql
--
-- FIX: store_memory_turn() was silently failing on EVERY call (found live 2026-07-07,
-- deep-walk dim-4/dim-13). Its INSERT into agent_memory omitted THREE columns that are
-- NOT NULL with no default -- worker_name, agent_id, kind -- so every companion turn's
-- client-side session-memory write threw a not-null violation, which voice-handler.js
-- _storeTurn swallows (console.warn). Net: the "current session, highest fidelity" memory
-- layer that voice-handler._fetchRecentMemory reads (by session_id) was 100% dead -- the
-- companion silently fell back to the voice_journal_entries 24h window + the in-memory turn
-- array. (Recall still worked via the gateway saveTurn path, which is why this went unseen.)
-- Proven live: `SELECT store_memory_turn(...)` and `GROUP BY session_id` -> 0 rows ever had
-- a session_id. Root cause: an agent_memory schema refactor added worker_name/agent_id/kind
-- as NOT NULL columns (for the gateway saveTurn rows) but this legacy RPC was never updated.
--
-- This RPC is companion-only (sole caller: voice-handler.js), so agent_id is a constant here.
-- kind = 'session_turn' (deliberately NOT 'turn'): the gateway loadMemory (_shared/memory.ts)
-- recalls rows WHERE kind='turn' via turn_text -- these RPC rows use user_input/assistant_response
-- and are read by the CLIENT (_fetchRecentMemory) by session_id, so they must live in their OWN
-- kind namespace or loadMemory would inject empty turn_text turns into the server recall block.
-- worker_name is derived from the hive_members row the tenant-gate already checks; auth_uid is
-- now stamped too (was only worker_id) for attribution hygiene. Signature is UNCHANGED, so no
-- client change is required.
--
-- agent_memory_kind_check previously allowed only ('turn','summary'); we add 'session_turn' so the
-- client session layer has a first-class, gateway-invisible namespace (loadMemory reads 'turn'/'summary').

ALTER TABLE public.agent_memory DROP CONSTRAINT IF EXISTS agent_memory_kind_check;
ALTER TABLE public.agent_memory ADD CONSTRAINT agent_memory_kind_check
  CHECK (kind = ANY (ARRAY['turn'::text, 'summary'::text, 'session_turn'::text]));

CREATE OR REPLACE FUNCTION public.store_memory_turn(
  p_hive_id uuid,
  p_session_id text,
  p_turn_num integer,
  p_user_input text,
  p_assistant_response text,
  p_intent text,
  p_confidence real,
  p_response_time_ms integer
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
declare
  v_hash        text;
  v_worker_name text;
  v_is_service  boolean;
begin
  v_is_service := coalesce(nullif(current_setting('request.jwt.claims', true), '')::json ->> 'role', '') = 'service_role';

  -- Arc G tenant-gate + worker_name derivation in ONE lookup: authenticated callers may only
  -- act on a hive they actively belong to; service_role (cron/edge) bypasses. The membership
  -- row also supplies the NOT NULL worker_name (the RPC signature never took it).
  select hm.worker_name
    into v_worker_name
  from hive_members hm
  where hm.hive_id = p_hive_id
    and hm.auth_uid = auth.uid()
    and hm.status = 'active'
  limit 1;

  if not v_is_service and v_worker_name is null then
    raise exception 'not authorized for hive %', p_hive_id using errcode = '42501';
  end if;

  v_hash := md5(p_user_input);

  insert into agent_memory (
    hive_id, worker_name, auth_uid, worker_id, agent_id, kind,
    session_id, turn_num,
    user_input, user_input_hash, assistant_response,
    intent_classification, intent_confidence, response_time_ms,
    expires_at
  )
  values (
    p_hive_id,
    coalesce(v_worker_name, 'system'),   -- NOT NULL: derived from membership (or 'system' on the service path)
    auth.uid(),
    auth.uid(),
    'voice-companion',                   -- NOT NULL: this RPC is companion-only (sole caller voice-handler.js)
    'session_turn',                      -- NOT NULL: own namespace; gateway loadMemory reads kind='turn' only
    p_session_id, p_turn_num,
    p_user_input, v_hash, p_assistant_response,
    p_intent, p_confidence, p_response_time_ms,
    now() + interval '24 hours'
  );

  return json_build_object(
    'ok', true,
    'turn_num', p_turn_num,
    'session_id', p_session_id
  );
end;
$function$;
