-- seller_badge_one_meaning: every surface's seller tier badge means ONE thing — the stored
-- marketplace_sellers.tier, exposed unchanged by v_marketplace_sellers_truth, maintained by writers
-- that ALL read the SAME per-hive knob thresholds (mig ...065's fix: two functions once defined
-- tier differently and agreed only while the defaults matched; now both update_seller_tier and
-- recompute_seller_sales_and_tier take silver/gold from service_knob('tier_silver_sales'/'tier_gold_sales')).
-- expect: view_exposes_stored_tier \| t
-- expect: trigger_live \| t
-- expect: writers_share_knobs \| t
SELECT 'view_exposes_stored_tier | ' ||
  (pg_get_viewdef('v_marketplace_sellers_truth'::regclass) ILIKE '%tier%');
SELECT 'trigger_live | ' || EXISTS (
  SELECT 1 FROM pg_trigger WHERE tgrelid='marketplace_orders'::regclass AND tgname='trg_seller_tier'
   AND tgenabled <> 'D');
SELECT 'writers_share_knobs | ' || (
  SELECT bool_and(prosrc ILIKE '%tier_silver_sales%' AND prosrc ILIKE '%tier_gold_sales%')
  FROM pg_proc WHERE proname IN ('update_seller_tier', 'recompute_seller_sales_and_tier'));
