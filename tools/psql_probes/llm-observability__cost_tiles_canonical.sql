-- cost_tiles_canonical (P-C tile == DB canonical / window & label / cap is not a total, 2026-09-05):
-- llm-observability paints Total calls, Cache hit rate, Fallback rate, Tokens used and Error rate from
-- ai_cost_log rows with created_at >= now - <window>h (1/6/24/168 h options; 24 h selected), read with
-- .limit(5000). The tiles are honest only if: the status vocabulary the page branches on holds
-- ('fallback' feeds the fallback + error tiles), token counts are non-negative (they are SUMMED),
-- the widest window (168 h) sits under the 5,000-row cap (otherwise "Total calls" is a cap, not a
-- total - the page discloses the cap when it bites), and cache rows are detectable the way the page
-- detects them (provider ~ 'ai_cache' or model 'cache:%'), so a 0% cache rate is a fact, not a blind spot.
-- expect: status_vocabulary_held \| t
-- expect: no_negative_tokens \| t
-- expect: widest_window_under_cap \| t
-- expect: cache_rows_detectable \| t
SELECT 'status_vocabulary_held | ' || ((SELECT count(*) FROM ai_cost_log WHERE status IS NULL OR status NOT IN ('success','fallback','error')) = 0);
SELECT 'no_negative_tokens | ' || ((SELECT count(*) FROM ai_cost_log WHERE prompt_tokens < 0 OR output_tokens < 0) = 0);
SELECT 'widest_window_under_cap | ' || ((SELECT count(*) FROM ai_cost_log WHERE created_at >= now() - interval '168 hours') < 5000);
SELECT 'cache_rows_detectable | ' || ((SELECT count(*) FROM ai_cost_log WHERE (provider ILIKE '%ai_cache%' OR model LIKE 'cache:%')) = (SELECT count(*) FROM ai_cost_log WHERE provider ILIKE '%cache%' OR model ILIKE '%cache%'));
