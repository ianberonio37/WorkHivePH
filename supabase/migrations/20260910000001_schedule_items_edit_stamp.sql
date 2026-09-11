-- schedule_items: the day plan's own edit stamp, so two devices cannot silently overwrite a plan
-- (W3-LC "two tabs or two people overwrite each other silently", row W31395, 2026-09-10).
--
-- WHY THIS TABLE, AFTER AN EARLIER WALK SAID THERE WAS NOTHING TO GUARD HERE. The 2026-09-08
-- migration (oc_stamps_for_listings_and_hives) recorded dayplanner.html as the one page in that
-- census with no racing edit: "its only update is `logbook.status = 'Closed'`, an idempotent state
-- change ... Two tabs closing the same entry reach the same place. Nothing to guard." That reading
-- was right about every `.update(` on the page and still wrong about the page, because the day
-- plan is not saved with an update at all - it is saved with
--
--     await db.from('schedule_items').upsert(row)          -- dayplanner.html:829
--
-- and an upsert of a full row is the most complete overwrite there is: title, date, both times,
-- category, notes, status and provenance, all replaced by whatever that tab last had in memory. A
-- census that greps for `.update(` cannot see it. This is the same lesson as counting a helper NAME
-- instead of measuring a property - the write was never hidden, only spelled differently.
--
-- WHO ACTUALLY COLLIDES HERE, because a guard is only worth its cost if two writers exist. Three
-- paths write a worker's day, and they are not all that worker:
--   * the worker's own two tabs, or a phone and a shared terminal - the ordinary case;
--   * 20260729000006_accepted_job_lands_on_dayplan.sql, which lands an ACCEPTED marketplace job on
--     the worker's plan from a different actor's action entirely;
--   * the offline queue draining after a brownout (wh_dayplanner_offline), which replays a row
--     composed before the reconnect.
-- So a day plan is genuinely multi-writer, and today the last writer wins with nothing shown to
-- anybody.
--
-- WHY SERVER-SIDE. Identical to the three reasons the inventory_items and listings migrations set
-- out: a client's `new Date()` comes from a field phone whose clock may be wrong; a future save path
-- that forgets the field would silently disable the guard with nothing failing; and the ten other
-- guarded tables already work this way, so this keeps one pattern rather than a per-table special
-- case. Additive, re-runnable, behaviour-preserving - NOT NULL with a default is catalogue-only in
-- PG11+, so no table rewrite.

ALTER TABLE public.schedule_items
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DROP TRIGGER IF EXISTS tg_schedule_items_touch_updated ON public.schedule_items;

CREATE TRIGGER tg_schedule_items_touch_updated
  BEFORE UPDATE ON public.schedule_items
  FOR EACH ROW
  EXECUTE FUNCTION public.touch_updated_at();

-- A stamp nobody may READ is a guard nobody can use: the optimistic-concurrency filter re-sends a
-- value the page had to select first. dayplanner.html already reads this table with `select('*')`
-- under its existing worker/auth_uid RLS, so the column joins that read rather than opening a new
-- one.
COMMENT ON COLUMN public.schedule_items.updated_at IS
  'Server-authoritative edit stamp (tg_schedule_items_touch_updated). Re-sent as an '
  'optimistic-concurrency filter by dayplanner.html''s save so a second device holding a stale '
  'stamp is refused and told, rather than silently replacing the whole row. The OFFLINE queue is '
  'deliberately exempt: a row composed before a reconnect cannot hold a fresh stamp, and refusing '
  'it would lose the capture the queue exists to protect.';
