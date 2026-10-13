-- ★THE ADAPTIVE CACHE SERVED ONE HIVE'S ANSWER TO ANOTHER (2026-10-07, found by the eval-bench work).
--
-- ai-gateway's adaptive cache is what a person is served instead of a 429 when they are rate-limited, or instead of the
-- platform-busy refusal when the org budget is spent. It was keyed on sha256('ai-gateway-adaptive:gateway:<agent>:<message>')
-- - no tenant at all - and every answer it holds is grounded in the asker's own hive (live ops snapshot, the machine's
-- logbook history, the team) or, for a hive-less person, their own logbook, journal and memory. So a rate-limited person
-- in hive B who typed the same words as someone in hive A was served hive A's answer, and an anonymous voice-journal
-- caller could be served a signed-in person's.
--
-- The code fix (supabase/functions/_shared/cache.ts answerCacheTenant/answerCacheLookup/answerCacheStore) keys the row on
-- the VERIFIED tenant - the hive the gateway proved membership of plus the verified auth uid - stores that tenant in
-- response_json, and refuses to serve a row whose stored tenant is not the caller's. A row written before the fix has no
-- tenant and could never be served again; this deletes them anyway, so none lingers until its TTL.
--
-- agentic-rag-loop's Grader and Checker caches were scoped to the tenant in the same change (their outputs name and
-- quote one tenant's records, and their keys covered only a prefix of those records). Their pre-fix rows hold no tenant
-- either; they are a 2-3 h derived cache, so they are dropped whole and simply recompute.
--
-- Idempotent: re-running deletes only rows that still lack a tenant (and the rag-stage rows, which recompute).

DELETE FROM public.ai_cache
 WHERE model = 'ai-gateway-adaptive'
   AND NOT (response_json ? 'tenant');

DELETE FROM public.ai_cache
 WHERE model IN ('agentic-rag-grader', 'agentic-rag-checker');
