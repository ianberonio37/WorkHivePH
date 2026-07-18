-- 20260713000011_post_inventory_attribution_pin.sql
--
-- community_posts + inventory_items attribution-forgery (MED) — bug-hunt 2026-07-14, found by the
-- Platform Knowledge Substrate attribution pre-filter (a table with a display-identity column +
-- a client write policy + NO bind_ trigger is a suspect), then LIVE-CONFIRMED (rolled back):
--
--  * community_posts: `community_posts_insert` CHECK pins auth_uid but NOT author_name — attacker
--    Bryan Garcia (Baguio) posted with author_name='Leandro Marquez' and it stored the forged author.
--    mig 007 pinned community_replies + community_reactions but MISSED community_posts (the parent).
--  * inventory_items: `inventory_items_write` CHECK pins auth_uid=auth.uid() in both branches (so the
--    AUTH row is honest + cross-hive is blocked) but leaves worker_name AND submitted_by unpinned —
--    attacker stored worker_name='Leandro Marquez' + submitted_by='Leandro Marquez' (forged registrant
--    on the parts ledger / approval queue).
--
-- The marketplace_sellers self-forge (trust cols) was PROBED and is already BLOCKED by
-- trg_guard_seller_trust ("KYB/cert/tier/rating/sales set by WorkHive, not self-assigned") — no change.
--
-- FIX (mirror bind_pm_asset_submitter / mig 010): a BEFORE INSERT OR UPDATE trigger that pins the
-- display-identity to the caller on INSERT and PRESERVES it on UPDATE (attribution immutable; a
-- supervisor moderating a post, or the qty-RPC updating stock, does not re-attribute authorship).
-- Service-role/seeder (auth.uid() NULL) bypass = batch trust. RLS policies UNCHANGED. Idempotent.

BEGIN;

-- 1. community post author pin -------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.bind_community_post_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' THEN
    NEW.auth_uid    := OLD.auth_uid;
    NEW.author_name := OLD.author_name;
    RETURN NEW;
  END IF;
  NEW.auth_uid := auth.uid();
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN NEW.author_name := v_name; END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_community_post ON public.community_posts;
CREATE TRIGGER trg_bind_submitter_community_post BEFORE INSERT OR UPDATE ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.bind_community_post_submitter();

-- 2. inventory item registrant pin (worker_name + submitted_by) -----------------------------------
CREATE OR REPLACE FUNCTION public.bind_inventory_item_submitter() RETURNS trigger
  LANGUAGE plpgsql SECURITY DEFINER SET search_path TO 'public' AS $fn$
DECLARE v_name text;
BEGIN
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;
  IF TG_OP = 'UPDATE' THEN
    NEW.auth_uid      := OLD.auth_uid;
    NEW.worker_name   := OLD.worker_name;
    NEW.submitted_by  := OLD.submitted_by;
    RETURN NEW;
  END IF;
  NEW.auth_uid := auth.uid();
  IF NEW.hive_id IS NOT NULL THEN
    SELECT worker_name INTO v_name FROM public.hive_members
      WHERE auth_uid = auth.uid() AND hive_id = NEW.hive_id AND status = 'active' LIMIT 1;
    IF v_name IS NOT NULL THEN
      NEW.worker_name  := v_name;
      NEW.submitted_by := v_name;
    END IF;
  END IF;
  RETURN NEW;
END; $fn$;
DROP TRIGGER IF EXISTS trg_bind_submitter_inventory_item ON public.inventory_items;
CREATE TRIGGER trg_bind_submitter_inventory_item BEFORE INSERT OR UPDATE ON public.inventory_items
  FOR EACH ROW EXECUTE FUNCTION public.bind_inventory_item_submitter();

COMMIT;
