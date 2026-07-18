-- Q5-b live-verify: embedding_cache LRU prune (stale removed, fresh kept). Non-destructive.
DO $$
DECLARE dim int; vec text; del int;
BEGIN
  SELECT (regexp_match(format_type(atttypid, atttypmod),'\((\d+)\)'))[1]::int INTO dim
    FROM pg_attribute WHERE attrelid='public.embedding_cache'::regclass AND attname='embedding';
  IF dim IS NULL THEN dim := 384; END IF;
  vec := '[' || array_to_string(array_fill(0.0::real, ARRAY[dim]), ',') || ']';
  INSERT INTO public.embedding_cache (query_hash, model, embedding, created_at, last_used)
  VALUES ('q5b_stale', 'test', vec::vector, now()-interval '60 days', now()-interval '60 days'),
         ('q5b_fresh', 'test', vec::vector, now(), now());
  SELECT public.prune_embedding_cache(45) INTO del;
  RAISE NOTICE 'Q5B: pruned=% (expect >=1); stale_present=% (expect f); fresh_present=% (expect t)',
    del,
    EXISTS(SELECT 1 FROM public.embedding_cache WHERE query_hash='q5b_stale'),
    EXISTS(SELECT 1 FROM public.embedding_cache WHERE query_hash='q5b_fresh');
  DELETE FROM public.embedding_cache WHERE query_hash IN ('q5b_stale','q5b_fresh');
END $$;
