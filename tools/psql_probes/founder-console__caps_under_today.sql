-- caps_under_today (P-C cap is not a total, 2026-09-05): founder-console reads service_vouchers with
-- .limit(30) and paints "N campaigns" (or "latest 30 campaigns shown" at the cap), sums voucher
-- redemptions under .limit(500), lists platform_feedback under .limit(500) with "of N+" past the cap,
-- and sums ai_cost_log under .limit(20000). A cap the page cannot see is honest only while the table
-- sits under it; these hold that, so a silent cap cannot make a sum or a count read smaller than truth.
-- expect: vouchers_under_30 \| t
-- expect: redemptions_under_500 \| t
-- expect: feedback_under_500 \| t
-- expect: cost_log_under_20000 \| t
SELECT 'vouchers_under_30 | ' || ((SELECT count(*) FROM service_vouchers) < 30);
SELECT 'redemptions_under_500 | ' || ((SELECT count(*) FROM service_voucher_redemptions) < 500);
SELECT 'feedback_under_500 | ' || ((SELECT count(*) FROM platform_feedback) < 500);
SELECT 'cost_log_under_20000 | ' || ((SELECT count(*) FROM ai_cost_log) < 20000);
