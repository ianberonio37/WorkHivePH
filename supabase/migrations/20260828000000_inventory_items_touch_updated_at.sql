-- inventory_items: make updated_at server-authoritative (T138, 2026-08-28).
--
-- HARDENING, NOT A BUG FIX, and the distinction is recorded because I first shipped this file
-- claiming the opposite.
--
-- WHAT I THOUGHT I HAD FOUND: inventory.html guards a part edit with an optimistic-concurrency
-- filter on the row's last-seen updated_at. inventory_items had no trigger touching that column,
-- and its DEFAULT now() applies on INSERT only, so I concluded the stamp never moved and the
-- guard could never fire. A probe agreed: writer A wrote, the stamp stayed put, writer B holding
-- the stale stamp still matched and overwrote A.
--
-- WHY THAT WAS WRONG: my probe issued `UPDATE ... SET qty_on_hand = ...`, and the PAGE issues
-- `UPDATE ... SET qty_on_hand = ..., updated_at = <now>` - its payload carries updated_at
-- explicitly (inventory.html:1510). The stamp moves because the caller moves it. Re-raced with
-- two product-shaped writers and the trigger dropped: A rows=1, B rows=0, A's value survived.
-- The guard has always worked. I had measured a shape the product never sends - right reading,
-- wrong subject.
--
-- WHY THE TRIGGER IS STILL WORTH ADDING, on its own merits rather than the ones I invented:
--   1. it makes updated_at SERVER-authoritative. Today the value comes from `new Date()` on the
--      client, so a device with a wrong clock writes a wrong stamp - and phones with skewed
--      clocks are common. A BEFORE UPDATE trigger overrides it with the database's own clock.
--   2. it removes the guard's dependence on every caller remembering to send the field. A future
--      edit path that omits it would silently disable the concurrency check with nothing failing.
--   3. it matches the eight other guarded tables, so the pattern is uniform rather than
--      per-table-special.
--
-- Additive, re-runnable, and behaviour-preserving for the existing path: touch_updated_at() is
-- the same function the other eight tables already use.

DROP TRIGGER IF EXISTS tg_inventory_items_touch_updated ON public.inventory_items;

CREATE TRIGGER tg_inventory_items_touch_updated
  BEFORE UPDATE ON public.inventory_items
  FOR EACH ROW
  EXECUTE FUNCTION public.touch_updated_at();
