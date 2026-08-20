-- TWO FUNCTIONS DEFINED THE SELLER TIER, AND ONLY ONE READ THE KNOBS.
--
-- Found 2026-08-20 walking community's CI domain-truth `seller_badge_one_meaning` ("a seller badge
-- here means the same thing as in the marketplace").
--
-- Across SURFACES the badge was already consistent, and for a good reason: community,
-- marketplace, marketplace-seller, marketplace-seller-profile, marketplace-admin and
-- founder-console all read marketplace_sellers.tier through v_marketplace_sellers_truth, which
-- exposes the stored column rather than recomputing it. Six surfaces, one column, no second
-- definition to drift.
--
-- The drift was one level down, in who WRITES that column:
--
--   update_seller_tier                (TRIGGER on marketplace_orders) -> hardcoded >= 51 / >= 11
--   recompute_seller_sales_and_tier   (callable, no trigger)          -> service_knob(hive, 'tier_gold_sales' / 'tier_silver_sales')
--
-- Today they agree, which is precisely why this is worth fixing now rather than after an incident:
-- the knob DEFAULTS are 11 and 51, identical to the hardcoded numbers, so the disagreement is
-- invisible. The moment a hive sets tier_silver_sales or tier_gold_sales to anything else, the
-- configured value governs whenever the recompute is called and is ignored by the trigger that
-- actually runs on every released order. A seller would cross a threshold the platform advertised
-- and not get the badge, or hold a badge the current setting no longer justifies.
--
-- The trigger now reads the same knobs. One definition, honoured by both writers, with the same
-- defaults as before so no seller's tier changes as a result of this migration.
--
-- service_knob is called with NULL for the hive because marketplace_sellers is keyed by worker_name
-- alone and carries no hive column; NULL resolves the platform default, which is what the hardcoded
-- constants were. Passing a hive here would require a seller-to-hive resolution this table cannot
-- support, and inventing one would change behaviour rather than unify it.

CREATE OR REPLACE FUNCTION public.update_seller_tier()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_silver integer := public.service_knob(NULL, 'tier_silver_sales');
  v_gold   integer := public.service_knob(NULL, 'tier_gold_sales');
BEGIN
  IF NEW.status = 'released' AND OLD.status <> 'released' THEN
    PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce system recompute to the guard
    INSERT INTO public.marketplace_sellers (worker_name, total_sales, tier)
    VALUES (NEW.seller_name, 1, 'bronze')
    ON CONFLICT (worker_name) DO UPDATE SET
      total_sales = marketplace_sellers.total_sales + 1,
      tier = CASE
        WHEN marketplace_sellers.total_sales + 1 >= v_gold   THEN 'gold'
        WHEN marketplace_sellers.total_sales + 1 >= v_silver THEN 'silver'
        ELSE 'bronze' END,
      updated_at = now();
  END IF;
  RETURN NEW;
END;
$$;
