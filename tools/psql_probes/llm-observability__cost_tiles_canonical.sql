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
-- expect: cache_rows_detectable \| t
-- the vocabulary is the table's own CHECK (success / failed / fallback); 'error' was a stale expectation that the
-- constraint forbids, and the page now counts 'failed' in its error tile (2026-10-13)
SELECT 'status_vocabulary_held | ' || ((SELECT count(*) FROM ai_cost_log WHERE status IS NULL OR status NOT IN ('success','fallback','failed')) = 0);
SELECT 'no_negative_tokens | ' || ((SELECT count(*) FROM ai_cost_log WHERE prompt_tokens < 0 OR output_tokens < 0) = 0);
-- widest_window_under_cap is gone (2026-10-27): it asserted the DATA stayed under the page's 5,000-row read, and a
-- local outbox drain of 11,944 embeddings in one day broke it with the page behaving exactly as designed - the read
-- asks for 5,001 and says "showing the latest 5,000" when the 5,001st exists. That sentence is SL LB1's to hold
-- (list-caps-say-more covers llm-observability.html); a probe about the tiles' truth does not assert a volume.
SELECT 'cache_rows_detectable | ' || ((SELECT count(*) FROM ai_cost_log WHERE (provider ILIKE '%ai_cache%' OR model LIKE 'cache:%')) = (SELECT count(*) FROM ai_cost_log WHERE provider ILIKE '%cache%' OR model ILIKE '%cache%'));
