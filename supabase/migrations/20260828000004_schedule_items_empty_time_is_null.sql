-- T75 (2026-08-28): schedule_items.start_time / end_time carried TWO spellings of "no time set" --
-- NULL (126 rows) and empty string (2 rows). They mean the same thing to a person and sort
-- differently to a database: '' precedes '07:00' lexicographically, so once the planner started
-- ordering the day by start_time (dayplanner.html loadSchedule, nullsFirst:false), the NULL rows
-- correctly fell to the end of the day while the '' rows floated to the TOP of it -- the same
-- untimed item landing in opposite places depending on which spelling happened to be stored.
--
-- Normalising '' to NULL is the fix, not widening the ordering to special-case '': one meaning
-- should have one representation, and every future filter, sort and "is it scheduled?" test then
-- gets the same answer without knowing this history.
--
-- Idempotent and re-runnable: the UPDATE matches nothing on a second run, and the CHECK is added
-- only when absent so the pair cannot drift apart again.

UPDATE public.schedule_items SET start_time = NULL WHERE start_time = '';
UPDATE public.schedule_items SET end_time   = NULL WHERE end_time   = '';

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
     WHERE conrelid = 'public.schedule_items'::regclass
       AND conname  = 'schedule_items_times_not_empty'
  ) THEN
    ALTER TABLE public.schedule_items
      ADD CONSTRAINT schedule_items_times_not_empty
      CHECK (start_time <> '' AND end_time <> '');
  END IF;
END $$;
