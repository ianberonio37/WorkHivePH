-- caps_under_today (P-C cap is not a total, 2026-09-05): founder-console reads service_vouchers with
-- .limit(30) and paints "N campaigns" (or "latest 30 campaigns shown" at the cap), sums voucher
-- redemptions under .limit(500), lists platform_feedback under .limit(500) with "of N+" past the cap,
-- and sums ai_cost_log under .limit(20000). A cap the page cannot see is honest only while the table
-- sits under it; these hold that, so a silent cap cannot make a sum or a count read smaller than truth.
-- 2026-10-29: the AI cost no longer has a cap to sit under - the console asks founder_ai_cost(), which sums every
-- row of the window in the database (the old client read saw a fraction past 1,000 rows; the local table now holds
-- ~30k). So the probe holds THAT: the sum and the count are taken over the whole window, server-side.
-- expect: vouchers_under_30 \| t
-- expect: redemptions_under_500 \| t
-- expect: feedback_under_500 \| t
-- expect: ai_cost_summed_in_database \| t
SELECT 'vouchers_under_30 | ' || ((SELECT count(*) FROM service_vouchers) < 30);
SELECT 'redemptions_under_500 | ' || ((SELECT count(*) FROM service_voucher_redemptions) < 500);
SELECT 'feedback_under_500 | ' || ((SELECT count(*) FROM platform_feedback) < 500);
SELECT 'ai_cost_summed_in_database | ' || (SELECT pg_get_functiondef('public.founder_ai_cost'::regproc) ~ 'sum\(cost_usd\)'
  AND pg_get_functiondef('public.founder_ai_cost'::regproc) ~ 'count\(\*\)');
