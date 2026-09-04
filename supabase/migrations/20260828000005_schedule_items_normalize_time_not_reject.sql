-- T192 (2026-08-28): supersedes the CHECK added in ...004, which was the WRONG SHAPE of guard.
--
-- ...004 normalised existing '' times to NULL and then added CHECK (start_time <> '' AND
-- end_time <> '') to stop the split recurring. But dayplanner sends the raw value of an
-- <input type="time">, which is '' when the worker leaves it blank -- so that CHECK would have
-- REJECTED every untimed task. The client is fixed in the same change (start_time: item.startTime
-- || null at the single send boundary), but a CHECK still leaves a real hazard this trajectory
-- exists to catch: a page ALREADY OPEN in a worker's browser, or prod between the migration
-- landing and the HTML deploying, is an "old client" that keeps sending ''. A guard that rejects
-- turns that window into failed saves for the majority case -- 126 of 228 rows are untimed.
--
-- A BEFORE trigger NORMALISES instead of refusing: an old client's '' is silently corrected to
-- NULL, the invariant "one meaning, one representation" still holds, and no write that used to
-- succeed starts failing. Same protection, no ordering hazard, no lost work.
-- (feedback_a_new_guard_breaks_the_triggers_that_already_write -- this time caught before deploy.)

ALTER TABLE public.schedule_items DROP CONSTRAINT IF EXISTS schedule_items_times_not_empty;

CREATE OR REPLACE FUNCTION public.tg_schedule_items_blank_time_is_null()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.start_time = '' THEN NEW.start_time := NULL; END IF;
  IF NEW.end_time   = '' THEN NEW.end_time   := NULL; END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tg_schedule_items_blank_time_is_null ON public.schedule_items;
CREATE TRIGGER tg_schedule_items_blank_time_is_null
  BEFORE INSERT OR UPDATE ON public.schedule_items
  FOR EACH ROW EXECUTE FUNCTION public.tg_schedule_items_blank_time_is_null();

-- Re-run the normalisation in case anything slipped in between ...004 and this.
UPDATE public.schedule_items SET start_time = NULL WHERE start_time = '';
UPDATE public.schedule_items SET end_time   = NULL WHERE end_time   = '';
