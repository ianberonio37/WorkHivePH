-- failed_transcribe_no_ghost (voice-journal): a recording that fails to transcribe creates no entry
-- that LOOKS like a real one. The failure mode is not an error message - it is a row in the journal
-- with nothing in it, or with the transcriber's apology stored as if the worker had said it. Either
-- one is worse than no row at all: the person believes their note was kept.
--
-- ★WHY THIS IS WORTH A LOCK TODAY (2026-09-10). `voice-transcribe` was fixed this morning: it did
-- `form.get("audio") as File` - a cast, not a check - so a non-file passed both size guards, reached
-- the audio chain, and ended in a 500 that blamed the transcription providers. While that was true,
-- every malformed submission was one code path away from writing exactly the ghost this cell forbids.
-- It now answers 400 "The audio field must be a file, not a text value" and writes nothing.
--
-- Measured: 483 entries, and NOT ONE has a null, blank or near-empty transcript, or carries a
-- failure phrase. That is a real population, so this is not a vacuous green - but the teeth below
-- manufacture each ghost shape anyway, because a detector that has never seen its subject is a claim
-- about a query, not about the product.
-- expect: entries_present \| [1-9][0-9]*
-- expect: no_null_transcript \| t
-- expect: no_blank_transcript \| t
-- expect: no_failure_text_stored_as_speech \| t
-- expect: detector_sees_a_blank_ghost \| t
-- expect: detector_sees_an_apology_ghost \| t
-- expect: rows_restored_after_rollback \| t
SELECT 'entries_present | ' || (SELECT count(*) FROM voice_journal_entries);

SELECT 'no_null_transcript | ' || (
  (SELECT count(*) FROM voice_journal_entries WHERE transcript IS NULL) = 0);
SELECT 'no_blank_transcript | ' || (
  (SELECT count(*) FROM voice_journal_entries WHERE btrim(coalesce(transcript,'')) = '') = 0);

-- the transcriber's own failure sentence, stored where the worker's words belong
SELECT 'no_failure_text_stored_as_speech | ' || (
  (SELECT count(*) FROM voice_journal_entries
    WHERE transcript ILIKE '%[inaudible]%'
       OR transcript ILIKE '%transcription failed%'
       OR transcript ILIKE '%could not transcribe%'
       OR transcript ILIKE '%all whisper models%') = 0);

CREATE TEMP TABLE _vfix AS
-- `auth_uid` is NOT NULL on this table (a first draft omitted it and both teeth aborted, reading as
-- MISSING - which looks exactly like a product finding and is not). Taken from a live row so the
-- fixture is grounded rather than invented.
SELECT count(*) AS n0,
       (SELECT worker_name FROM voice_journal_entries WHERE auth_uid IS NOT NULL LIMIT 1) AS who,
       (SELECT hive_id     FROM voice_journal_entries WHERE auth_uid IS NOT NULL LIMIT 1) AS hid,
       (SELECT auth_uid    FROM voice_journal_entries WHERE auth_uid IS NOT NULL LIMIT 1) AS uid;

BEGIN;
-- TEETH 1: the empty ghost - a row that renders as an entry with nothing in it
INSERT INTO voice_journal_entries (worker_name, hive_id, auth_uid, transcript, reply)
SELECT who, hid, uid, '   ', 'probe' FROM _vfix;
SELECT 'detector_sees_a_blank_ghost | ' || (
  (SELECT count(*) FROM voice_journal_entries WHERE btrim(coalesce(transcript,'')) = '') > 0);
ROLLBACK;

BEGIN;
-- TEETH 2: the apology ghost - the transcriber's failure sentence saved as if it were speech
INSERT INTO voice_journal_entries (worker_name, hive_id, auth_uid, transcript, reply)
SELECT who, hid, uid, 'All Whisper models unavailable, try again in a moment', 'probe' FROM _vfix;
SELECT 'detector_sees_an_apology_ghost | ' || (
  (SELECT count(*) FROM voice_journal_entries
    WHERE transcript ILIKE '%all whisper models%') > 0);
ROLLBACK;

-- ★A COUNT-BASED RESTORATION CHECK IS BROKEN BY ANY CONCURRENT WRITER (2026-09-10). This compared
-- count-at-start with count-at-end and reported `false` while the rollbacks had worked perfectly -
-- an archetype walk wrote two real journal entries between the two readings. The count moved for a
-- reason that had nothing to do with this probe, and a probe that fails when the platform is BUSY
-- teaches people to re-run reds until they go green. Asserting on the MARKER instead is
-- concurrency-safe and strictly stronger: it proves MY rows are gone whatever else happened.
SELECT 'rows_restored_after_rollback | ' || (
  (SELECT count(*) FROM voice_journal_entries
    WHERE reply = 'probe' OR btrim(coalesce(transcript,'')) = ''
       OR transcript ILIKE '%all whisper models%') = 0);
DROP TABLE _vfix;
