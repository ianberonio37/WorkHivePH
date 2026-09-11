-- producer_alive (llm-observability, P-K health is a living producer, 2026-09-05): the page paints figures rolled up from
-- ai_cost_log and calls them live. A producer that stopped writing would leave the tiles quietly frozen, so the
-- recipe holds that the log's newest row is under 7 days old and the page's default window has rows in it.
-- expect: newest_row_under_7d \| t
-- expect: window_has_rows \| t
SELECT 'newest_row_under_7d | ' || ((SELECT max(created_at) FROM ai_cost_log) > now() - interval '7 days');
SELECT 'window_has_rows | ' || ((SELECT count(*) FROM ai_cost_log WHERE created_at >= now() - interval '30 days') > 0);
