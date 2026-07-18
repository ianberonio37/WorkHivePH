-- 20260713000013_index_unindexed_cascade_fks.sql
--
-- Perf/availability: index the 14 UNINDEXED foreign keys that are ON DELETE CASCADE — surfaced by the
-- substrate FK-graph lens (substrate/fk/_graph.md), 2026-07-14. An unindexed cascade FK forces a
-- SEQUENTIAL SCAN (+ a lock) of the child table every time a parent row is deleted, to find the rows to
-- cascade. For a hot/large child (e.g. sensor_readings time-series, asset_edges graph) that makes a
-- single asset_node/hive deletion slow AND write-blocking — a multi-tenant availability risk when an
-- admin removes an asset or a hive. Indexing the child FK column turns the cascade lookup into an index
-- scan. (Non-security; the per-page security bug-hunt's substrate lenses came back clean this session.)
--
-- Regular CREATE INDEX (not CONCURRENTLY) so it runs inside the migration txn — fine locally + for the
-- current data sizes. For a PROD deploy against a large table, prefer CREATE INDEX CONCURRENTLY out of
-- band. Idempotent via IF NOT EXISTS.

BEGIN;

-- FKs into hives (hive deletion cascade) --------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ai_quality_escalation_hive_id ON public.ai_quality_escalation(hive_id);
CREATE INDEX IF NOT EXISTS idx_community_xp_hive_id           ON public.community_xp(hive_id);
CREATE INDEX IF NOT EXISTS idx_drone_inspections_hive_id      ON public.drone_inspections(hive_id);
CREATE INDEX IF NOT EXISTS idx_mentor_relay_queue_hive_id     ON public.mentor_relay_queue(hive_id);

-- FKs into asset_nodes (asset deletion cascade) -------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_asset_edges_from_node_id       ON public.asset_edges(from_node_id);
CREATE INDEX IF NOT EXISTS idx_asset_edges_to_node_id         ON public.asset_edges(to_node_id);
CREATE INDEX IF NOT EXISTS idx_pf_intervals_asset_id          ON public.pf_intervals(asset_id);
CREATE INDEX IF NOT EXISTS idx_rcm_fmea_modes_asset_id        ON public.rcm_fmea_modes(asset_id);
CREATE INDEX IF NOT EXISTS idx_sensor_readings_asset_id       ON public.sensor_readings(asset_id);
CREATE INDEX IF NOT EXISTS idx_sensor_topic_map_asset_id      ON public.sensor_topic_map(asset_id);
CREATE INDEX IF NOT EXISTS idx_weibull_fits_asset_id          ON public.weibull_fits(asset_id);

-- FK into pm_assets -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_pm_scope_items_asset_id        ON public.pm_scope_items(asset_id);

-- FKs into auth.users ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_resume_versions_auth_uid       ON public.resume_versions(auth_uid);
CREATE INDEX IF NOT EXISTS idx_worker_achievements_auth_uid   ON public.worker_achievements(auth_uid);

COMMIT;
