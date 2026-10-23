-- attributed_from_jwt: every journal entry is attributed by the JWT, not by a body field — all four
-- policies bind auth.uid() = auth_uid, and every stored row carries its auth_uid.
-- expect: policies_bind_uid \| 4
-- expect: rows_missing_uid \| 0
SELECT 'policies_bind_uid | ' || count(*) FROM pg_policy
WHERE polrelid = 'voice_journal_entries'::regclass
  -- either spelling of the same binding: auth.uid() = auth_uid, or the once-per-statement
  -- ( SELECT auth.uid() AS uid) = auth_uid that LB2 (20261020000003) rewrote the policies into
  AND (COALESCE(pg_get_expr(polqual, polrelid), '') ~* 'auth\.uid\(\)( AS uid\))? = auth_uid'
       OR COALESCE(pg_get_expr(polwithcheck, polrelid), '') ~* 'auth\.uid\(\)( AS uid\))? = auth_uid');
SELECT 'rows_missing_uid | ' || count(*) FROM voice_journal_entries WHERE auth_uid IS NULL;
