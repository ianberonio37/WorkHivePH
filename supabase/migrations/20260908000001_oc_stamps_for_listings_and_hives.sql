-- marketplace_listings + hives: give the two remaining racing edits a server-authoritative stamp
-- (W3-LC "two tabs or two people overwrite each other silently", 2026-09-08).
--
-- WHAT THE WALK FOUND. Eight pages carry that row. Five are covered by the concurrency census -
-- their edit re-sends the row's last-seen `updated_at` as a filter, so a second writer holding a
-- stale stamp matches no row and is TOLD. Three were not, and reading each one's updates apart
-- rather than counting them showed they are not the same case:
--
--   dayplanner.html    its only update is `logbook.status = 'Closed'`, an idempotent state change
--                      that already returns `.select('id')` so a zero-row RLS no-op is detected.
--                      Two tabs closing the same entry reach the same place. Nothing to guard.
--
--   hive.html          five updates. Three are idempotent transitions (promote to supervisor,
--                      set a member kicked, a one-shot backfill). TWO ARE FREE-TEXT EDITS with no
--                      guard at all: the hive's NAME and its INTENT. Two supervisors editing the
--                      hive on two devices - which is exactly what a supervisor pair does - and
--                      the second save silently discards the first, with nothing shown either way.
--
--   marketplace-seller.html   the listing edit rewrites NINE fields at once (title, category,
--                      condition, description, price, location, contact, image, status) filtered
--                      only on `id` and `seller_name`. A seller editing a listing in two tabs, or
--                      on a phone and a laptop, loses whichever save lands first - including the
--                      PRICE. This is the costliest of the three and the least visible.
--
-- WHY A TRIGGER RATHER THAN TRUSTING THE PAGE. `marketplace_listings` already carries `updated_at`
-- and the page already stamps it in its own payload, so a guard would work today. It is added
-- server-side for the three reasons the inventory_items migration set out and which apply
-- unchanged here: the client's `new Date()` comes from a phone whose clock may be wrong; a future
-- edit path that forgets the field would silently disable the guard with nothing failing; and the
-- other nine guarded tables already work this way, so this makes the pattern uniform rather than
-- per-table-special.
--
-- `hives` has no `updated_at` at all, so it gets the column first. Additive, re-runnable, and
-- behaviour-preserving: `touch_updated_at()` is the same function every other guarded table uses.

-- ── marketplace_listings ──────────────────────────────────────────────────────────────────────
DROP TRIGGER IF EXISTS tg_marketplace_listings_touch_updated ON public.marketplace_listings;

CREATE TRIGGER tg_marketplace_listings_touch_updated
  BEFORE UPDATE ON public.marketplace_listings
  FOR EACH ROW
  EXECUTE FUNCTION public.touch_updated_at();

-- ── hives ─────────────────────────────────────────────────────────────────────────────────────
-- NOT NULL with a default is safe on an existing table in PG11+: the default is stored in the
-- catalogue rather than rewritten into every row.
ALTER TABLE public.hives
  ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

DROP TRIGGER IF EXISTS tg_hives_touch_updated ON public.hives;

CREATE TRIGGER tg_hives_touch_updated
  BEFORE UPDATE ON public.hives
  FOR EACH ROW
  EXECUTE FUNCTION public.touch_updated_at();

-- A stamp nobody may READ is a guard nobody can use: the optimistic-concurrency filter re-sends a
-- value the page had to select first. `hives` is already readable by its members through RLS, and
-- this column is added to that existing read rather than opening a new one.
COMMENT ON COLUMN public.hives.updated_at IS
  'Server-authoritative edit stamp (tg_hives_touch_updated). Re-sent as an optimistic-concurrency '
  'filter by hive.html''s name and intent edits so a second writer with a stale stamp is refused '
  'and told, rather than silently overwriting the first.';
