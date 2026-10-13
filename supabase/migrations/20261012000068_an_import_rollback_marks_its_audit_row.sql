-- AN IMPORT ROLLBACK MARKS ITS AUDIT ROW (2026-10-12, UFAI W4284, walked as a Lucena supervisor on integrations.html).
--
-- The rollback deletes the imported rows, then marks the batch's audit entry:
--   db.from('cmms_audit_log').update({ operation: 'file_import_rolled_back' }).eq('batch_id', ..).eq('hive_id', ..)
-- cmms_audit_log has row policies for INSERT and SELECT only - none for UPDATE - so under RLS that update matched
-- ZERO rows for every person, and PostgREST answered 204 exactly as it does for a real update. The page said
-- "Import rolled back. 1 imported row removed." while the audit entry still read file_import, and the import history
-- (which lists operation = 'file_import') kept showing the rolled-back batch with its Rollback button.
--
-- The repair is as narrow as the action: a member of the hive may change an IMPORT row of that hive, and only into a
-- rolled-back row (USING requires operation = 'file_import', WITH CHECK requires 'file_import_rolled_back'); and the
-- table-level UPDATE privilege becomes a column-level one, so the only column a person can touch is `operation` -
-- the counts, the batch id, who triggered it stay as the import wrote them. Every other writer of this table is the
-- service role (edge functions), which grants do not govern here.

-- re-runnable: a replay of this file must not fail on the policy it already created (idempotency gate, 2026-10-13)
drop policy if exists cmms_audit_log_mark_rolled_back on public.cmms_audit_log;
create policy cmms_audit_log_mark_rolled_back on public.cmms_audit_log
  for update to authenticated
  using (auth.uid() is not null and hive_id in (select public.user_hive_ids()) and operation = 'file_import')
  with check (auth.uid() is not null and hive_id in (select public.user_hive_ids()) and operation = 'file_import_rolled_back');

revoke update on public.cmms_audit_log from anon, authenticated;
grant update (operation) on public.cmms_audit_log to authenticated;

notify pgrst, 'reload schema';
