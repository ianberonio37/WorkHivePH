-- Arc G G2 — hive_members INSERT hardening (auth-migration enforcement, step 4).
--
-- After 20260620000003 closed hive_members SELECT/DELETE/UPDATE, the last always-true policy on the
-- membership root was `anon_insert_members` (INSERT WITH CHECK true) — any ANONYMOUS client could insert
-- an arbitrary membership row (e.g. add a fake supervisor to any hive). Drop it. The proper
-- `hive_members_insert` policy remains (CHECK: auth.uid() IS NOT NULL AND (auth_uid = auth.uid() OR
-- auth_uid IS NULL)), which still covers both authenticated app flows:
--   * join  (hive.html:1445) — inserts the caller's OWN row (auth_uid = self),
--   * create-hive (hive.html:1352) — upserts the caller's supervisor row with auth_uid unset (NULL).
--
-- VERIFIED LIVE (ROLLBACK'd, 2026-06-20): self-join PASS · create-hive (auth_uid NULL) PASS ·
--   inserting ANOTHER user's linked row BLOCKED · anonymous insert BLOCKED.
--
-- RESIDUAL (tracked NEXT, needs an app co-fix): an authenticated user can still insert an auth_uid=NULL
-- row into an arbitrary hive (the create-hive path). Closing it requires create-hive to set
-- auth_uid = self (all 5 insert sites), then tightening hive_members_insert to auth_uid = auth.uid()
-- (drop the NULL clause) + a role-escalation guard. App + policy co-change — a separate focused step.

drop policy if exists anon_insert_members on public.hive_members;
