-- ============================================================================
-- A HIRING POST IS NOT A SALE (2026-10-26)
--
-- The PHP500 floor (20260803000036) refuses any listing going live under the
-- minimum, reading a missing price as PHP0. A Hiring post (section 'jobs') has
-- no price - the post form leaves it blank and the seeder writes null - so the
-- section marketplace.html offers as "Hiring" could never be published: every
-- one would be refused with "The lowest price WorkHive lists is PHP500. This
-- one is PHP0".
--
-- Found when the local reseed stopped on it. Production holds no jobs listing
-- yet (measured 2026-10-26), so nobody has met the refusal there.
--
-- The floor's own reasons are about a SALE: the buyer's reward is 10% of the
-- price, and the reservation a listing holds is priced from it. A job is not
-- bought, earns no reward and holds no reservation (listing_reservation_amount
-- of a null price is 0, which guard_listing_requires_reservation already lets
-- through). So the floor keeps every sale section and leaves Hiring out.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.guard_listing_meets_minimum()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'pg_catalog', 'public'
AS $function$
DECLARE
  v_min integer;
BEGIN
  -- Only polices a listing going LIVE. A draft may be saved at any price while the seller works on it;
  -- refusing mid-draft would lose their typing to a rule about publication.
  IF NEW.status IS DISTINCT FROM 'published' THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.status IS NOT DISTINCT FROM 'published' THEN
    RETURN NEW;   -- already live; editing other fields is not a re-publication
  END IF;
  -- a Hiring post is not bought: no price, no buyer reward, no reservation (20261026000001)
  IF NEW.section = 'jobs' THEN
    RETURN NEW;
  END IF;

  v_min := public.service_knob(NEW.hive_id, 'min_listing_price');
  IF coalesce(NEW.price, 0) < v_min THEN
    RAISE EXCEPTION 'The lowest price WorkHive lists is PHP%. This one is PHP% — bundle it with '
                    'something, or raise the price.',
                    to_char(v_min, 'FM999G999G990'), to_char(coalesce(NEW.price, 0), 'FM999G999G990')
      USING errcode = 'check_violation';
  END IF;
  RETURN NEW;
END;
$function$;
