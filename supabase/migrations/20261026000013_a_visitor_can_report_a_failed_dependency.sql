-- 20261026000013_a_visitor_can_report_a_failed_dependency.sql
--
-- A FAILED DEPENDENCY SEEN BY SOMEONE NOT SIGNED IN REACHED NO ONE (OWN dependency lens, 2026-10-26). The pages now log a
-- dependency that failed under them as context 'dependency:<host>:<kind>' (utils.js whDependency), and the operator
-- console groups those rows (founder_client_errors, 20261026000012). But the anonymous insert policy
-- (20261021000003) admits only the uncaught net and the told-* sentences, at most 40 characters - so the breach
-- check at sign-up, the map on a public page, every failure a visitor met, was refused at the insert. Measured: three
-- refused breach checks during sign-up walks, zero rows.
--
-- The visitor's row keeps every limit the policy already had - no identity (the trigger binds none), no hive, bounded
-- page and agent - and may now carry a dependency context of at most 80 characters ('dependency:' + a host + a kind).

drop policy if exists client_errors_insert_anon on public.client_errors;
create policy client_errors_insert_anon on public.client_errors
  for insert to anon
  with check (
    (select auth.uid()) is null
    and hive_id is null and worker_name is null and auth_uid is null
    and (
      ((context = any (array['uncaught-error', 'unhandled-rejection']) or context like 'told-%') and char_length(context) <= 40)
      or (context like 'dependency:%' and char_length(context) <= 80)
    )
    and (page is null or char_length(page) <= 300)
    and (user_agent is null or char_length(user_agent) <= 300)
  );
