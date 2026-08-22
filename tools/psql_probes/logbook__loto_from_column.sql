-- loto_from_column: LOTO status is a COLUMN a worker set, never an inference — logbook.loto_applied
-- exists as boolean, rows carry it, and no function re-derives LOTO from free text (a regex reading
-- "applied" out of prose would be a safety record invented by a pattern).
-- expect: column_present \| t
-- expect: rows_carrying_loto \| [1-9][0-9]*
-- expect: text_inference_functions \| 0
SELECT 'column_present | ' || EXISTS (
  SELECT 1 FROM information_schema.columns
  WHERE table_name='logbook' AND column_name='loto_applied' AND data_type='boolean');
SELECT 'rows_carrying_loto | ' || count(*) FROM logbook WHERE loto_applied IS NOT NULL;
SELECT 'text_inference_functions | ' || count(*) FROM pg_proc
WHERE prosrc ~* $x$loto|lock\s?out$x$ AND prosrc ~* $x$action\s*~|action\s+ILIKE$x$;
