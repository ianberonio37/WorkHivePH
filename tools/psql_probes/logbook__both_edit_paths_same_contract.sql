-- both_edit_paths_same_contract: the online editor and the offline drain hit the SAME RLS contract
-- — logbook UPDATE/DELETE policies are owner-scoped (auth_uid = auth.uid()), SELECT is hive-scoped,
-- so neither path can widen the other.
-- expect: update_owner_scoped \| t
-- expect: delete_owner_scoped \| t
-- expect: select_hive_scoped \| t
SELECT 'update_owner_scoped | ' || EXISTS (
  SELECT 1 FROM pg_policy WHERE polrelid='logbook'::regclass AND polcmd='w'
   AND pg_get_expr(polqual, polrelid) ILIKE '%auth_uid = auth.uid()%');
SELECT 'delete_owner_scoped | ' || EXISTS (
  SELECT 1 FROM pg_policy WHERE polrelid='logbook'::regclass AND polcmd='d'
   AND pg_get_expr(polqual, polrelid) ILIKE '%auth_uid = auth.uid()%');
SELECT 'select_hive_scoped | ' || EXISTS (
  SELECT 1 FROM pg_policy WHERE polrelid='logbook'::regclass AND polcmd='r'
   AND pg_get_expr(polqual, polrelid) ILIKE '%hive_%');
