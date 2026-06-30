-- Arc G G2 — restore isolation on the last 3 legacy-open hive tables (auth-migration enforcement, step 3).
--
-- ai_user_rate_limits, parts_records, wh_traces each carried a legacy permissive `USING (true)` ALL policy
-- (`ai_user_rl_service_all`, `allow_anon_all`, `wh_traces_service_all`) defeating tenant isolation. Evidence:
--   * service_role has BYPASSRLS=true, so these `_service_all` policies are NOT needed for the edge's
--     service-role writes (it bypasses RLS regardless) — they were pure anon/authenticated exposure.
--   * All three have ZERO frontend readers (grep: edge/service-only) — no app path reads them directly.
-- So the always-true policies can go. To avoid leaving an orphan-RLS table (RLS on, no policy — which the
-- Arc E "0 orphan-RLS" invariant flags), add a minimal scoped policy where none else exists:
--   * wh_traces already has wh_traces_hive_read (JWT hive_id claim scope) — just drop the true one.
--   * parts_records (hive_id uuid): add a hive-member-scoped policy (reuses public.user_hive_ids()).
--   * ai_user_rate_limits (user_id text): add an own-user-scoped policy.
-- After this the service-role edge path is unchanged (bypassrls); anon/authenticated can no longer read or
-- write another hive's rows. Ratchet validate_rls_no_permissive_bypass 3 -> 0.

-- wh_traces: scoped read already exists; drop the redundant always-true ALL policy.
drop policy if exists wh_traces_service_all on public.wh_traces;

-- parts_records: replace the always-true ALL policy with a hive-member-scoped one.
create policy parts_records_hive_rw on public.parts_records for all
  using      (auth.uid() is not null and hive_id in (select public.user_hive_ids()))
  with check (auth.uid() is not null and hive_id in (select public.user_hive_ids()));
drop policy if exists allow_anon_all on public.parts_records;

-- ai_user_rate_limits: replace the always-true ALL policy with an own-user-scoped one
-- (a user may read their own rate-limit row; the edge writes via service_role bypass).
create policy ai_user_rate_limits_own on public.ai_user_rate_limits for all
  using      (auth.uid() is not null and user_id = auth.uid()::text)
  with check (auth.uid() is not null and user_id = auth.uid()::text);
drop policy if exists ai_user_rl_service_all on public.ai_user_rate_limits;
