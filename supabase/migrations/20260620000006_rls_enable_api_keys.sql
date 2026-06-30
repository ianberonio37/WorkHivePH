-- Arc G G1 — enable RLS on api_keys (a non-RLS hive-scoped table = full cross-tenant exposure).
--
-- api_keys (per-hive API key records: key_prefix, key_hash, label, enabled, call_count) had RLS DISABLED
-- and EXECUTE/SELECT granted to anon + authenticated — so any client could read every hive's key metadata
-- and INSERT/UPDATE/DELETE keys for any hive (disable a victim hive's integration, or mint keys). It stores
-- a HASH (not the raw secret) and is currently empty, and its only reader is the authenticated integrations
-- page — so enabling RLS with a hive-member-scoped policy is safe (anon -> 0; member -> own hive; the edge
-- uses service_role which is BYPASSRLS). Reuses the public.user_hive_ids() DEFINER helper from
-- 20260620000003 (recursion-safe membership lookup).

alter table public.api_keys enable row level security;

-- RLS policies require BOTH a table GRANT and a permissive policy; without the GRANT the role 401s.
grant select, insert, update, delete on public.api_keys to authenticated;

drop policy if exists api_keys_hive_rw on public.api_keys;
create policy api_keys_hive_rw on public.api_keys for all
  using      (auth.uid() is not null and hive_id in (select public.user_hive_ids()))
  with check (auth.uid() is not null and hive_id in (select public.user_hive_ids()));
