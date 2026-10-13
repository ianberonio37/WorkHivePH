-- 20261013000004 - DURABLE AI MEMORY BELONGS TO AN ACCOUNT, NOT A DISPLAY NAME (2026-10-13).
--
-- agent_episodic_memory has had an auth_uid column (FK to auth.users, ON DELETE SET NULL) and an RLS read policy keyed
-- on it (aem_read: auth.uid() = auth_uid), but persistEpisodic never wrote it: 0 of 120 local rows carried one. So the
-- policy could never show a person their own memories, and every recall was keyed by worker_name - a display name that
-- a rename frees and the next person to join the hive under it inherits. The functions now write the account and read
-- by it (_shared/episodic-memory.ts, ai-gateway, agent-memory-store, agentic-rag-loop). This backfills the rows already
-- written, so nobody's durable memory goes missing when the account becomes the key. SHIP THIS BEFORE THOSE FUNCTIONS.
--
-- Three attributions, each only where it is unambiguous:
--   1. a hive row, by the member who holds that name in that hive (hive_members is UNIQUE (hive_id, worker_name));
--   2. a row stamped with an e-mail address (the multi-hive maybeSingle bug wrote user.email as worker_name), by that
--      e-mail's account;
--   3. a solo row (no hive), by the one profile with that display name - skipped when two profiles share it.
-- Rows none of these reach (locally: 27 machine-written "status" notes and one empty name) stay without an account:
-- they are nobody's personal memory, and only a hive-wide recall (no person) reads them.

update public.agent_episodic_memory e
   set auth_uid = hm.auth_uid
  from public.hive_members hm
 where e.auth_uid is null
   and e.hive_id is not null
   and hm.hive_id = e.hive_id
   and hm.worker_name = e.worker_name
   and hm.auth_uid is not null;

update public.agent_episodic_memory e
   set auth_uid = u.id
  from auth.users u
 where e.auth_uid is null
   and e.worker_name like '%@%'
   and lower(u.email) = lower(e.worker_name);

update public.agent_episodic_memory e
   set auth_uid = p.auth_uid
  from public.worker_profiles p
 where e.auth_uid is null
   and e.hive_id is null
   and p.display_name = e.worker_name
   and p.auth_uid is not null
   and (select count(*) from public.worker_profiles p2 where p2.display_name = e.worker_name) = 1;

-- recall and the per-person cap now filter by account within a scope
create index if not exists idx_aem_auth_type
    on public.agent_episodic_memory (auth_uid, memory_type, last_used_at desc nulls last)
 where auth_uid is not null;
