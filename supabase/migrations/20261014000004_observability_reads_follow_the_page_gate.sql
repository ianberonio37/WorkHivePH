-- SL AU4 (2026-10-14): three observability tables were readable by EVERY active member of a hive, while the pages that
-- show them refuse anyone but the hive's supervisor or a platform admin. Asked of the server directly as Bryan Garcia
-- (a worker of Baguio Textile Mills, not an admin), with role authenticated and his JWT claims:
--   gateway_audit_log    32 rows  - per person: worker_name, auth_uid, ip_hash, ua_fingerprint (plant-connections is
--                                   supervisors-only)
--   ai_cost_log        1,467 rows - per person: worker_name, model, cost, prompt_hash, user_feedback (ai-quality is a
--                                   supervisor surface; founder-console and llm-observability are platform-admin only)
--   agentic_rag_traces    44 rows - per person: worker_name, question, final_answer (agentic-rag-observability is
--                                   platform-admin only)
-- A worker could read what a teammate asked the AI, its answer, and each teammate's device fingerprint, through the API,
-- behind pages that refuse the same worker. The page gate decided who SAW it; nothing decided who could READ it.
--
-- Each read now follows the page that shows it: the hive's active supervisor, or a platform admin; ai_cost_log also keeps
-- a person's OWN rows (it carries auth_uid). agentic_rag_traces has no auth_uid, and ownership by display name is not an
-- identity, so it keeps no own-rows clause. Writes are unchanged (service role only, as before). The grafana_reader
-- policies are untouched.

drop policy if exists gateway_audit_read on public.gateway_audit_log;
create policy gateway_audit_read on public.gateway_audit_log
  for select using (
    auth.uid() is not null and (
      public.is_platform_admin()
      or (hive_id is not null and exists (
            select 1 from public.hive_members hm
             where hm.hive_id = gateway_audit_log.hive_id and hm.auth_uid = auth.uid()
               and hm.status = 'active' and hm.role = 'supervisor'))));

drop policy if exists ai_cost_log_read on public.ai_cost_log;
create policy ai_cost_log_read on public.ai_cost_log
  for select using (
    auth.uid() is not null and (
      public.is_platform_admin()
      or auth_uid = auth.uid()
      or (hive_id is not null and exists (
            select 1 from public.hive_members hm
             where hm.hive_id = ai_cost_log.hive_id and hm.auth_uid = auth.uid()
               and hm.status = 'active' and hm.role = 'supervisor'))));

drop policy if exists agentic_rag_traces_read on public.agentic_rag_traces;
create policy agentic_rag_traces_read on public.agentic_rag_traces
  for select using (
    auth.uid() is not null and (
      public.is_platform_admin()
      or (hive_id is not null and exists (
            select 1 from public.hive_members hm
             where hm.hive_id = agentic_rag_traces.hive_id and hm.auth_uid = auth.uid()
               and hm.status = 'active' and hm.role = 'supervisor'))));
