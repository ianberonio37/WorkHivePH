-- stat_tiles_canonical (P-C tile == DB canonical, 2026-09-05): marketplace-admin paints five stat tiles
-- from count-only reads (marketplace-admin.html ~541-548): draft / published / removed listings from
-- v_marketplace_listings_truth by status, sellers from v_marketplace_sellers_truth, and
-- unverified = sellers - kyb_verified. The canonical the tiles paint is those views; they must agree
-- with their base tables status-by-status, and the derived tile must be exactly the difference.
-- expect: draft_view_equals_table \| t
-- expect: published_view_equals_table \| t
-- expect: removed_view_equals_table \| t
-- expect: sellers_view_equals_table \| t
-- expect: unverified_is_difference \| t
SELECT 'draft_view_equals_table | ' || ((SELECT count(*) FROM v_marketplace_listings_truth WHERE status='draft') = (SELECT count(*) FROM marketplace_listings WHERE status='draft'));
SELECT 'published_view_equals_table | ' || ((SELECT count(*) FROM v_marketplace_listings_truth WHERE status='published') = (SELECT count(*) FROM marketplace_listings WHERE status='published'));
SELECT 'removed_view_equals_table | ' || ((SELECT count(*) FROM v_marketplace_listings_truth WHERE status='removed') = (SELECT count(*) FROM marketplace_listings WHERE status='removed'));
SELECT 'sellers_view_equals_table | ' || ((SELECT count(*) FROM v_marketplace_sellers_truth) = (SELECT count(*) FROM marketplace_sellers));
SELECT 'unverified_is_difference | ' || (
  (SELECT count(*) FROM v_marketplace_sellers_truth) - (SELECT count(*) FROM v_marketplace_sellers_truth WHERE kyb_verified)
  = (SELECT count(*) FROM v_marketplace_sellers_truth WHERE NOT kyb_verified OR kyb_verified IS NULL));
