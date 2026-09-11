-- plan_links_not_duplicates (dayplanner): a planned item that becomes a logbook entry is LINKED, not
-- duplicated - the reference is an id, so the plan and the entry stay one object seen twice.
--
-- ★WHAT THE DATABASE DOES AND DOES NOT ENFORCE, measured before this was written. `schedule_items`
-- carries `logbook_ref`, and that column has NO foreign key: its only constraints are the primary key
-- and an auth_uid FK. So "linked, not duplicated" is APPLICATION behaviour, and a dangling reference
-- is possible by construction. This recipe therefore does two honest things and does not pretend to a
-- third: it LOCKS the invariant forward (no dangling ref, no ref reused, linking adds no logbook row)
-- and it proves the detector for each of those actually fires. It does NOT claim the database
-- prevents them.
--
-- ★AND THE LIVE CORPUS CANNOT EXERCISE IT: 231 schedule items, ZERO carrying a logbook_ref (the walk
-- that made one correctly reversed it). Asserting "no dangling refs" over no refs is the vacuous green
-- this bank keeps re-learning, so the population is PRINTED - an empty set cannot masquerade as
-- agreement - and the teeth below manufacture both the good link and the broken one inside
-- BEGIN/ROLLBACK.
-- Two schema facts this cost a draft to learn: `schedule_items.id` is TEXT, NOT NULL and has NO
-- default (the client supplies it), and `date` is TEXT rather than a date column - so a bare
-- current_date fails the type. Recorded here so the next reader does not pay for them again.
-- expect: refs_present_in_live_data \| 0
-- expect: dangling_refs \| 0
-- expect: refs_reused \| 0
-- expect: linking_added_no_logbook_row \| t
-- expect: detector_sees_a_dangling_ref \| t
-- expect: detector_sees_a_reused_ref \| t
-- expect: rows_restored_after_rollback \| t
SELECT 'refs_present_in_live_data | ' || (SELECT count(*) FROM schedule_items WHERE logbook_ref IS NOT NULL);
SELECT 'dangling_refs | ' || (SELECT count(*) FROM schedule_items s WHERE s.logbook_ref IS NOT NULL
        AND NOT EXISTS (SELECT 1 FROM logbook l WHERE l.id = s.logbook_ref));
SELECT 'refs_reused | ' || (SELECT count(*) FROM (
        SELECT logbook_ref FROM schedule_items WHERE logbook_ref IS NOT NULL
         GROUP BY logbook_ref HAVING count(*) > 1) x);

CREATE TEMP TABLE _pfix AS
SELECT (SELECT count(*) FROM logbook)                                   AS log0,
       (SELECT count(*) FROM schedule_items)                            AS sched0,
       (SELECT id FROM logbook ORDER BY created_at DESC LIMIT 1)        AS real_entry,
       (SELECT worker_name FROM logbook ORDER BY created_at DESC LIMIT 1) AS who;

BEGIN;
-- THE GOOD LINK: planning a real logbook entry writes ONE schedule row that points at it, and the
-- logbook itself does not grow - that is the whole difference between linking and copying.
INSERT INTO schedule_items (id, worker_name, title, date, logbook_ref, item_status)
SELECT 'probe-' || replace(gen_random_uuid()::text,'-',''), who,
       'probe: planned from an existing entry', current_date::text, real_entry, 'planned' FROM _pfix;
SELECT 'linking_added_no_logbook_row | ' || ((SELECT count(*) FROM logbook) = (SELECT log0 FROM _pfix));

-- TEETH 1: a ref pointing nowhere must be VISIBLE to the dangling detector above.
INSERT INTO schedule_items (id, worker_name, title, date, logbook_ref, item_status)
SELECT 'probe-' || replace(gen_random_uuid()::text,'-',''), who,
       'probe: deliberately dangling', current_date::text, 'no-such-logbook-id', 'planned' FROM _pfix;
SELECT 'detector_sees_a_dangling_ref | ' || ((SELECT count(*) FROM schedule_items s
        WHERE s.logbook_ref IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM logbook l WHERE l.id = s.logbook_ref)) > 0);

-- TEETH 2: the same entry planned twice must be VISIBLE to the reuse detector above.
INSERT INTO schedule_items (id, worker_name, title, date, logbook_ref, item_status)
SELECT 'probe-' || replace(gen_random_uuid()::text,'-',''), who,
       'probe: the same entry planned twice', current_date::text, real_entry, 'planned' FROM _pfix;
SELECT 'detector_sees_a_reused_ref | ' || ((SELECT count(*) FROM (
        SELECT logbook_ref FROM schedule_items WHERE logbook_ref IS NOT NULL
         GROUP BY logbook_ref HAVING count(*) > 1) y) > 0);
ROLLBACK;

SELECT 'rows_restored_after_rollback | ' || (
        (SELECT count(*) FROM schedule_items) = (SELECT sched0 FROM _pfix)
    AND (SELECT count(*) FROM logbook)        = (SELECT log0   FROM _pfix));
DROP TABLE _pfix;
