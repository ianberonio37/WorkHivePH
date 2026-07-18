-- ============================================================================
-- Register the two canonical objects the 2026-07-17/18 bug-hunt drive added, so
-- validate_canonical_anchor.py's fuel_anchor + engine_anchor ratchets see them
-- (un-anchored count had ticked UP: fuel 5 -> 6, engine 2 -> 3):
--   * ops_artifact_metrics (fuel/table) — Operator-Console artifact-metrics table
--     (20260718000001): service-role/seeder-written (clients REVOKE'd), read for
--     the ops observability dashboard.
--   * get_seller_community_reputation (engine/rpc) — the cross-hive marketplace
--     seller-reputation bridge (20260717000004): aggregate-only, auth-gated,
--     opted-in sellers, allowlisted in validate_definer_membership_gate.
--
-- canonical_sources PK is `domain`; `contract` has a DEFAULT so it is omitted.
-- Idempotent via ON CONFLICT (domain) DO NOTHING.
-- ============================================================================

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, description) VALUES
  ('ops_artifact_metrics', 'table', 'ops_artifact_metrics', 'devops', 'on_snapshot',
   'Operator-Console artifact-metrics fuel table: per-artifact size/count observability snapshots. Service-role/seeder-written (anon/authenticated REVOKE''d); grafana_reader reads it for the ops dashboard.'),
  ('seller_community_reputation', 'rpc', 'get_seller_community_reputation', 'marketplace', 'realtime',
   'DEFINER RPC returning a seller''s cross-hive, aggregate-only community reputation for the marketplace seller card (auth-gated, opted-in sellers only; the intentional cross-hive reputation bridge allowlisted in validate_definer_membership_gate).')
ON CONFLICT (domain) DO NOTHING;
