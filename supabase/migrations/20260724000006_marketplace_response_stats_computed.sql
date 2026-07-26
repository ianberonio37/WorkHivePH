-- ============================================================================
-- Marketplace RESPONSE-SLA HONESTY — actually COMPUTE the responsiveness a buyer is shown
-- (Marketplace Deepwalk EXPANSION arc, J14/MK9, 2026-07-24)
-- ----------------------------------------------------------------------------
-- THE DEFECT: the listing detail sheet promises a buyer "Responds in ~1h · 95% reply rate" from
--   marketplace_sellers.response_rate / response_time_h. Those two columns are DECLARED in the
--   schema and DEFENDED by the trust guard (a seller may not self-assign them, 20260712000001)...
--   but NOTHING EVER COMPUTES THEM. No trigger, no function, no edge fn, no cron. So the value a
--   buyer reads is whatever was seeded, frozen forever: a trust-bearing promise about future
--   behaviour that no real event can ever create, correct, or invalidate.
--   (The seller's OWN dashboard and the public profile compute the same idea correctly and live,
--   straight from marketplace_inquiries -- so the platform already agreed on the definition; only
--   the buyer-facing column was orphaned.)
--
-- THE FIX: maintain both columns from the real inquiry record, mirroring update_seller_rating.
--   response_time_h = AVG(replied_at - created_at) in hours over REPLIED inquiries
--   response_rate   = replied inquiries / total inquiries  (0..1, matching the render's *100)
--   Only counts inquiries whose replied_at is set; a seller with no replies stays NULL, which the
--   UI already renders honestly as "-" / "No replies yet" instead of inventing a number.
--   The recompute announces itself through the existing workhive.seller_system_write GUC so the
--   trust guard lets the SYSTEM write what a SELLER still may not.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.update_seller_response_stats()
 RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
DECLARE
  v_seller   text;
  v_total    integer;
  v_replied  integer;
  v_avg_h    numeric(6,1);
  v_rate     numeric(5,2);
BEGIN
  -- seller_name is denormalised onto the inquiry; fall back to the listing when absent.
  v_seller := COALESCE(NEW.seller_name,
                       (SELECT l.seller_name FROM public.marketplace_listings l WHERE l.id = NEW.listing_id));
  IF v_seller IS NULL THEN RETURN NEW; END IF;

  SELECT COUNT(*)::integer,
         COUNT(*) FILTER (WHERE i.replied_at IS NOT NULL)::integer,
         ROUND(AVG(EXTRACT(EPOCH FROM (i.replied_at - i.created_at)) / 3600.0)
               FILTER (WHERE i.replied_at IS NOT NULL)::numeric, 1)
    INTO v_total, v_replied, v_avg_h
    FROM public.marketplace_inquiries i
   WHERE i.seller_name = v_seller;

  -- No replies yet -> leave both NULL. The UI shows "-" / "No replies yet"; inventing a 0% reply
  -- rate would punish a brand-new seller for having no history, which is its own dishonesty.
  IF v_replied = 0 OR v_total = 0 THEN
    v_rate  := NULL;
    v_avg_h := NULL;
  ELSE
    v_rate := ROUND((v_replied::numeric / v_total::numeric), 2);
  END IF;

  PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce to the trust guard
  INSERT INTO public.marketplace_sellers (worker_name, response_rate, response_time_h, updated_at)
  VALUES (v_seller, v_rate, v_avg_h, now())
  ON CONFLICT (worker_name) DO UPDATE SET
    response_rate   = v_rate,
    response_time_h = v_avg_h,
    updated_at      = now();

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_update_seller_response_stats ON public.marketplace_inquiries;
CREATE TRIGGER trg_update_seller_response_stats
  AFTER INSERT OR UPDATE OF replied_at, status ON public.marketplace_inquiries
  FOR EACH ROW EXECUTE FUNCTION public.update_seller_response_stats();

COMMENT ON FUNCTION public.update_seller_response_stats() IS
  'Computes marketplace_sellers.response_rate + response_time_h from the real marketplace_inquiries record (avg replied_at-created_at in hours, replied/total). Before this the buyer-facing "Responds in ~Nh / N% reply rate" came from seeded columns nothing ever maintained. Stays NULL until a first reply so a new seller is not shown a fabricated 0%. MK9 response-SLA honesty, 2026-07-24.';

-- Backfill from the existing record so the displayed numbers stop being seed artefacts immediately.
DO $backfill$
DECLARE r record;
BEGIN
  PERFORM set_config('workhive.seller_system_write', 'on', true);
  FOR r IN
    SELECT i.seller_name AS seller,
           COUNT(*)::integer AS total,
           COUNT(*) FILTER (WHERE i.replied_at IS NOT NULL)::integer AS replied,
           ROUND(AVG(EXTRACT(EPOCH FROM (i.replied_at - i.created_at)) / 3600.0)
                 FILTER (WHERE i.replied_at IS NOT NULL)::numeric, 1) AS avg_h
      FROM public.marketplace_inquiries i
     WHERE i.seller_name IS NOT NULL
     GROUP BY i.seller_name
  LOOP
    UPDATE public.marketplace_sellers
       SET response_rate   = CASE WHEN r.replied = 0 THEN NULL ELSE ROUND((r.replied::numeric / r.total::numeric), 2) END,
           response_time_h = CASE WHEN r.replied = 0 THEN NULL ELSE r.avg_h END,
           updated_at      = now()
     WHERE worker_name = r.seller;
  END LOOP;
  -- Sellers with NO inquiry record at all must not keep a seeded promise either.
  UPDATE public.marketplace_sellers s
     SET response_rate = NULL, response_time_h = NULL, updated_at = now()
   WHERE NOT EXISTS (SELECT 1 FROM public.marketplace_inquiries i WHERE i.seller_name = s.worker_name)
     AND (s.response_rate IS NOT NULL OR s.response_time_h IS NOT NULL);
END
$backfill$;
