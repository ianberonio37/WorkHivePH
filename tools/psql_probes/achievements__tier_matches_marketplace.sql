-- tier_matches_marketplace: the tier achievements.html reads from v_service_provider_truth must
-- equal the view's own stated rule (completed_jobs>=25 AND rating_avg>=4.5 -> gold;
-- completed_jobs>=10 -> silver; else bronze). Recomputed per row, zero disagreements, population
-- printed (non-vacuity: 0-of-0 is not agreement).
-- expect: providers_checked \| [1-9][0-9]*
-- expect: tier_disagreements \| 0
SELECT 'providers_checked | ' || count(*) FROM v_service_provider_truth;
SELECT 'tier_disagreements | ' || count(*) FROM v_service_provider_truth
WHERE tier IS DISTINCT FROM (CASE
  WHEN completed_jobs >= 25 AND rating_avg >= 4.5 THEN 'gold'
  WHEN completed_jobs >= 10 THEN 'silver'
  ELSE 'bronze' END);
