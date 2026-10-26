-- 20261027000001 - a derived knowledge row is bounded by what it is derived from, not by a cap of its own.
--
-- fault_knowledge has been insert-locked for every client since 20260513000003 (policy fault_knowledge_insert_locked,
-- WITH CHECK (false)): only the service writes it - embed-entry, one row per logbook entry; cmms-sync, pdf-ingest and
-- visual-defect-capture from their own (capped or rate-limited) inputs. The per-day cap 20260705000004 added on top
-- (check_daily_row_cap: 500 a hive, 200 a worker name) therefore stopped no person - nobody can insert - and throttled
-- only the platform's own index of entries that were already accepted:
--
--   measured locally 2026-10-26: 322 refused inserts in the edge log ("You have reached today's free limit (200)"),
--   each AFTER its embedding call; embed-entry answers the refusal with a 500 and the embedding relay retries a 500 up
--   to 48 times (20261026000011), re-embedding every time - in production that is Gemini quota spent on rows that
--   cannot land until midnight. A CMMS import or a heavy day past 200 entries leaves the assistant's knowledge silently
--   short until then.
--
-- The migration that added the cap states its own rule: system-generated tables are excluded. This is one. The gate
-- that required it (validate_quota_coverage) now requires the client lock instead, so unlocking client inserts makes the
-- cap mandatory again.

DROP TRIGGER IF EXISTS trg_daily_cap_fault_knowledge ON public.fault_knowledge;
