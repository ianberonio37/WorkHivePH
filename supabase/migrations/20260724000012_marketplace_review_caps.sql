-- ============================================================================
-- Marketplace REVIEWS — text caps + a per-day write cap for the newly-opened review flow
-- (Marketplace Deepwalk EXPANSION arc, MK13 follow-through, 2026-07-24)
-- ----------------------------------------------------------------------------
-- Opening the review form (20260724000011) added a NEW client write path, and the per-page quota audit
-- correctly failed the build: every feature-page write table must be capped or documented-excluded, and
-- marketplace_reviews was neither. An uncapped, user-writable table is a spam surface, and on a
-- reputation feature spam is not merely noise — it is the attack.
--
-- TWO CAPS, mirroring what marketplace_inquiries and marketplace_listings already do:
--   1. TEXT CAP (trigger, same shape as cap_marketplace_inquiries_text): truncate rather than reject,
--      so an over-long comment is trimmed instead of throwing a raw error at a buyer mid-review.
--   2. PER-DAY CAP: at most REVIEW_DAILY_CAP reviews per reviewer per day. The standing rule already
--      requires an inquiry per listing, so the realistic ceiling is low; this bounds the pathological
--      case (a scripted client hammering many listings it has inquired on) without ever getting in a
--      real buyer's way — nobody legitimately reviews 10 purchases in one day on this marketplace.
--
-- The cap RAISES a clear error rather than silently dropping, because a review the user believes they
-- posted but which vanished is the same broken-receipt class MK12 exists to prevent.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.cap_marketplace_reviews_text()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.reviewer_name IS NOT NULL THEN NEW.reviewer_name := left(NEW.reviewer_name, 120);  END IF;
  IF NEW.comment       IS NOT NULL THEN NEW.comment       := left(NEW.comment,       600);  END IF;
  RETURN NEW;
END; $$;
ALTER FUNCTION public.cap_marketplace_reviews_text() OWNER TO postgres;

DROP TRIGGER IF EXISTS trg_text_caps_mkt_reviews ON public.marketplace_reviews;
CREATE TRIGGER trg_text_caps_mkt_reviews BEFORE INSERT OR UPDATE ON public.marketplace_reviews
  FOR EACH ROW EXECUTE FUNCTION public.cap_marketplace_reviews_text();


CREATE OR REPLACE FUNCTION public.enforce_marketplace_review_daily_cap()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
  REVIEW_DAILY_CAP CONSTANT integer := 10;
  v_today integer;
BEGIN
  -- Service-role / seeder writes carry no auth.uid(); they are not the spam surface this guards.
  IF auth.uid() IS NULL THEN RETURN NEW; END IF;

  SELECT COUNT(*) INTO v_today
    FROM public.marketplace_reviews
   WHERE reviewer_name = NEW.reviewer_name
     AND created_at >= date_trunc('day', now());

  IF v_today >= REVIEW_DAILY_CAP THEN
    RAISE EXCEPTION 'Daily review limit reached (% per day). Your earlier reviews are saved.', REVIEW_DAILY_CAP
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END; $$;

DROP TRIGGER IF EXISTS trg_review_daily_cap ON public.marketplace_reviews;
CREATE TRIGGER trg_review_daily_cap BEFORE INSERT ON public.marketplace_reviews
  FOR EACH ROW EXECUTE FUNCTION public.enforce_marketplace_review_daily_cap();

COMMENT ON FUNCTION public.enforce_marketplace_review_daily_cap() IS
  'Bounds the review flow opened in 20260724000011 to 10 reviews per reviewer per day. Standing already requires an inquiry per listing, so this only bites a scripted abuser, never a real buyer. Raises rather than silently dropping, so the user is never told a review posted when it did not.';
