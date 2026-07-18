-- Q6 live-verify: global org-shared LLM budget guard. Calls the atomic RPC directly
-- with tiny caps (env overrides don't reach the local runtime; the DB fn is the unit).
UPDATE ai_global_budget SET minute_count=0, minute_window_start=NULL, day_count=0, day_window_start=NULL, shed_count_today=0, deny_count_today=0 WHERE id='global';

\echo '=== TEST 1: DAILY CIRCUIT-BREAKER (rpd=3): calls 1-3 allowed, 4-5 denied global-day ==='
SELECT 'call1' tag, * FROM consume_ai_global_budget(100, 3, false);
SELECT 'call2' tag, * FROM consume_ai_global_budget(100, 3, false);
SELECT 'call3' tag, * FROM consume_ai_global_budget(100, 3, false);
SELECT 'call4' tag, * FROM consume_ai_global_budget(100, 3, false);
SELECT 'call5' tag, * FROM consume_ai_global_budget(100, 3, false);
\echo '--- after test1: day_count=3, deny_count_today=2 expected ---'
SELECT minute_count, day_count, shed_count_today, deny_count_today FROM ai_global_budget WHERE id='global';

\echo '=== TEST 2: PER-MINUTE BURST SMOOTHER (rpm=2): 2 allowed, 3rd background SHED, 4th voice PASSES ==='
UPDATE ai_global_budget SET minute_count=0, minute_window_start=NULL, day_count=0, day_window_start=NULL, shed_count_today=0, deny_count_today=0 WHERE id='global';
SELECT 'm1_bg'         tag, * FROM consume_ai_global_budget(2, 10000, true);
SELECT 'm2_bg'         tag, * FROM consume_ai_global_budget(2, 10000, true);
SELECT 'm3_bg_SHED'    tag, * FROM consume_ai_global_budget(2, 10000, true);
SELECT 'm4_voice_PASS' tag, * FROM consume_ai_global_budget(2, 10000, false);
\echo '--- after test2: shed_count_today=1 expected; voice passed despite minute wall ---'
SELECT minute_count, day_count, shed_count_today, deny_count_today FROM ai_global_budget WHERE id='global';

\echo '=== TEST 3: MINUTE WINDOW RESET (stale window -> fresh count) ==='
UPDATE ai_global_budget SET minute_count=999, minute_window_start=now() - interval '2 minutes', day_count=5, day_window_start=now() WHERE id='global';
SELECT 'stale_reset_PASS' tag, * FROM consume_ai_global_budget(2, 10000, true);
\echo '--- expected: allowed=true (minute window stale -> reset to 1), day_count continues at 6 ---'
SELECT minute_count, day_count FROM ai_global_budget WHERE id='global';

-- clean up to a neutral state
UPDATE ai_global_budget SET minute_count=0, minute_window_start=NULL, day_count=0, day_window_start=NULL, shed_count_today=0, deny_count_today=0 WHERE id='global';
