-- pii_rule_holds: "your voice recording is not kept" — the DB half of that promise: the journal
-- table stores TEXT only (no audio/blob/url column anywhere on it), and no storage bucket exists
-- for voice audio. The page-side wording is the browser provers' subject; the absence of a place
-- to keep audio is this probe's.
-- expect: audio_columns \| 0
-- expect: voice_buckets \| 0
SELECT 'audio_columns | ' || count(*) FROM information_schema.columns
WHERE table_name = 'voice_journal_entries'
  AND (column_name ILIKE '%audio%' OR column_name ILIKE '%recording%' OR column_name ILIKE '%blob%'
       OR data_type = 'bytea');
SELECT 'voice_buckets | ' || count(*) FROM storage.buckets
WHERE name ILIKE '%voice%' OR name ILIKE '%audio%' OR name ILIKE '%recording%';
