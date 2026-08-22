-- raw_survives_polish: polishing never destroys what the person actually said — every entry keeps a
-- non-empty transcript, and where a polished reply exists it is a SECOND field that differs from
-- the raw text rather than replacing it.
-- expect: entries \| [1-9][0-9]*
-- expect: empty_transcripts \| 0
-- expect: replies_that_replaced_raw \| 0
SELECT 'entries | ' || count(*) FROM voice_journal_entries;
SELECT 'empty_transcripts | ' || count(*) FROM voice_journal_entries
WHERE transcript IS NULL OR btrim(transcript) = '';
SELECT 'replies_that_replaced_raw | ' || count(*) FROM voice_journal_entries
WHERE reply IS NOT NULL AND btrim(reply) <> '' AND reply = transcript;
