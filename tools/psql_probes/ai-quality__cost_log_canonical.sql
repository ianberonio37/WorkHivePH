-- cost_log_canonical (P-C tile == DB canonical, 2026-09-05): ai-quality's tiles are straight sums over
-- ai_cost_log for the hive + window (cost_usd, total_tokens, per-fn calls/failures/latency) and a thumbs
-- rate over ai_reply_feedback.rating (aggregate(), ai-quality.html ~470-520). The page adds; it does not
-- interpret. So the canonical the tiles rest on is the ROW truth: tokens are the sum of their parts,
-- cost is never negative, status and rating stay inside the vocabularies the page branches on.
-- expect: tokens_are_sum_of_parts \| t
-- expect: cost_never_negative \| t
-- expect: status_vocabulary_held \| t
-- expect: rating_vocabulary_held \| t
SELECT 'tokens_are_sum_of_parts | ' || ((SELECT count(*) FROM ai_cost_log
  WHERE prompt_tokens IS NOT NULL AND output_tokens IS NOT NULL AND total_tokens IS NOT NULL
    AND total_tokens <> prompt_tokens + output_tokens) = 0);
SELECT 'cost_never_negative | ' || ((SELECT count(*) FROM ai_cost_log WHERE cost_usd < 0 OR total_tokens < 0) = 0);
SELECT 'status_vocabulary_held | ' || ((SELECT count(*) FROM ai_cost_log
  WHERE status IS NOT NULL AND status NOT IN ('ok','success','error','failed','fallback','cached','rate_limited','refused','timeout')) = 0);
SELECT 'rating_vocabulary_held | ' || ((SELECT count(*) FROM ai_reply_feedback
  WHERE rating IS NOT NULL AND rating::text NOT IN ('up','down','1','-1','0','helpful','unhelpful','thumbs_up','thumbs_down')) = 0);
