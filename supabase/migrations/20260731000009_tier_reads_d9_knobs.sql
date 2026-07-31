-- 20260731000009_tier_reads_d9_knobs.sql
--
-- FINISH THE D9 KNOBS. 20260731000007 created the trust thresholds and 20260731000008 wired only the
-- timing/reach half. `tier_silver_sales` / `tier_gold_sales` were read by NOTHING but the resolver itself —
-- write-only configuration, which is the exact failure the S9 cell's own principle names (a knob nobody
-- reads is not a knob). Shipping half a feature and calling the obligation closed would have been a weak
-- green of the kind this arc exists to refuse.
--
-- PER-HIVE IS COHERENT HERE, and the premise was checked rather than assumed: marketplace_sellers carries
-- hive_id, so a seller belongs to a hive and that hive's bar applies to them. Combined with the TIGHTEN-ONLY
-- floors from 20260731000007, a gold seller from ANY hive has earned AT LEAST the platform ladder — the
-- cross-hive comparability of the badge survives, because a hive can only make its own sellers work harder.
--
-- Read from the DEFINING MIGRATION (20260724000008), not from prosrc. Everything but the threshold lookup is
-- byte-identical: the same sold-count query, the same announced `workhive.seller_system_write` GUC for the
-- trust guard, the same no-op guard clause, the same idempotent WHERE that lets a reopened or deleted
-- listing self-correct.

CREATE OR REPLACE FUNCTION public.recompute_seller_sales_and_tier(p_seller_name text)
 RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $function$
DECLARE
  v_sold   integer;
  v_hive   uuid;
  v_silver integer;
  v_gold   integer;
  v_tier   text;
BEGIN
  IF p_seller_name IS NULL OR btrim(p_seller_name) = '' THEN RETURN; END IF;

  SELECT COUNT(*)::integer INTO v_sold
    FROM public.marketplace_listings
   WHERE seller_name = p_seller_name AND status = 'sold';

  -- The seller's OWN hive sets the bar. A seller with no hive resolves to the platform ladder, which is what
  -- service_knob() returns for an unknown hive, so the solo path needs no special case.
  SELECT hive_id INTO v_hive FROM public.marketplace_sellers WHERE worker_name = p_seller_name;
  v_silver := public.service_knob(v_hive, 'tier_silver_sales');
  v_gold   := public.service_knob(v_hive, 'tier_gold_sales');

  v_tier := CASE WHEN v_sold >= v_gold   THEN 'gold'
                 WHEN v_sold >= v_silver THEN 'silver'
                 ELSE 'bronze' END;

  PERFORM set_config('workhive.seller_system_write', 'on', true);  -- announce to the trust guard

  UPDATE public.marketplace_sellers
     SET total_sales = v_sold,
         tier = v_tier,
         updated_at = now()
   WHERE worker_name = p_seller_name
     AND (total_sales IS DISTINCT FROM v_sold OR tier IS DISTINCT FROM v_tier);
END;
$function$;

COMMENT ON FUNCTION public.recompute_seller_sales_and_tier(text) IS
  'Recomputes marketplace_sellers.total_sales from listings marked sold and derives tier from the seller''s '
  'OWN hive D9 thresholds (service_knob tier_silver_sales/tier_gold_sales), defaulting to the platform '
  '11/51 ladder. Because those knobs are TIGHTEN-ONLY, a gold badge from any hive still means at least the '
  'platform bar. Idempotent by design so a reopened or deleted listing self-corrects. MK1 trust-signal '
  'integrity.';
