-- Ten schedule_items rows carry a category vocabulary NOTHING IN THIS REPOSITORY WRITES, and four
-- of them cannot be saved from the Day Planner at all.
--
-- THIS IS THE SIBLING OF 20260916000001, AND DELIBERATELY THE OPPOSITE FIX. That migration widens
-- the contract to accept `item_status = 'planned'`; this one leaves the contract alone and corrects
-- the data. The difference is not style, it is evidence about WHO WRITES THE VALUE:
--
--   planned      written by a LIVE PRODUCT PATH - land_accepted_job_on_dayplan() in migration
--                20260729000006 inserts item_status 'planned' on every accepted marketplace job.
--                A value a shipping trigger writes is part of the vocabulary, so the CONTRACT is
--                what is wrong, and widening it is the honest fix.
--
--   pm/admin/    written by NOTHING. The dayplanner seeder (test-data-seeder/seeders/dayplanner.py)
--   corrective/  emits the correct CATEGORIES list; the marketplace trigger above writes 'CM'; no
--   parts        migration, fixture or page produces these ten. They are orphaned rows from an
--                earlier demo whose titles ("Collect bearing 6310 C3 from store") match no
--                generator on disk. Widening the contract for them would legitimise a vocabulary
--                no writer produces - going green by lowering the bar, which is the drift these
--                contracts exist to stop.
--
-- WHAT IS BROKEN TODAY (measured 2026-09-16, all ten rows belong to Pablo Aguilar, created
-- 2026-08-05, dated 08-05..08-07):
--
--   category      rows   reaches the contract as        result on save
--   ----------    ----   ------------------------       ------------------------------------------
--   pm               4   'PM'   (case-fixed on read)    saves; self-heals to PM on first save
--   admin            2   'Admin'(case-fixed on read)    saves; self-heals to Admin on first save
--   corrective       2   'corrective' (unchanged)       REFUSED - [capture-violation], rolled back
--   parts            2   'parts'      (unchanged)       REFUSED - [capture-violation], rolled back
--
-- dayplanner.html's _dpNormalizeCat() matches the row's category case-insensitively against the
-- page's own list and, finding no match, deliberately LEAVES IT ALONE rather than guessing - the
-- right call, and the reason `corrective` and `parts` arrive at wh-capture-validate.js verbatim and
-- are refused before the write leaves the browser. The reader edits a title, is told "Could not
-- save that change", and retrying is the one action that cannot work.
--
-- The four case-only rows are not blocked, because the page rewrites their case on read. They are
-- still corrected here: every OTHER reader of this table (analytics, exports, the assistant's
-- grounding) does an exact-key lookup, so a lowercase `pm` is a different category from `PM` to
-- everything except the one page that happens to normalise it.
--
-- THE MAPPING, and the repository evidence for each:
--   pm         -> PM       case only.
--   admin      -> Admin    case only.
--   corrective -> CM       land_accepted_job_on_dayplan() files corrective service work as 'CM',
--                          so CM is this product's word for corrective maintenance.
--   parts      -> Other    no category models a stores errand ("Collect bearing 6310 C3 from
--                          store", "Stock count - critical spares"). `Other` is the designated
--                          bucket for work the list does not model and asserts nothing the data
--                          does not support. Admin was rejected: the seeder files "Spare parts
--                          review" under Admin, but these two are shop-floor errands, not
--                          paperwork, and guessing a wrong category is worse than naming none.
--
-- Forward-only and idempotent: it matches the exact off-contract spellings, so re-running changes
-- no further rows, and a row already holding PM/CM/Admin/Other is not touched. No row is deleted
-- and no category is invented - each of the four targets already exists in the contract enum
-- ["PM","CM","Inspection","Training","Admin","Meeting","Other",null] set by 20260609000004.
--
-- Pairs tools/prove_capture_enums_cover_the_data.py, which found all of this by asking the database
-- one question the product never asked: is the enum a true claim about the column?

UPDATE public.schedule_items SET category = 'PM'    WHERE category = 'pm';
UPDATE public.schedule_items SET category = 'Admin' WHERE category = 'admin';
UPDATE public.schedule_items SET category = 'CM'    WHERE category = 'corrective';
UPDATE public.schedule_items SET category = 'Other' WHERE category = 'parts';

-- Proof the gate's question now answers clean for this column. Fails the migration loudly rather
-- than leaving a silent partial normalisation behind.
DO $$
DECLARE n integer;
BEGIN
  SELECT count(*) INTO n
  FROM public.schedule_items
  WHERE category IS NOT NULL
    AND category NOT IN ('PM','CM','Inspection','Training','Admin','Meeting','Other');
  IF n > 0 THEN
    RAISE EXCEPTION 'schedule_items still holds % row(s) with a category the contract forbids', n;
  END IF;
END $$;
