-- Canonical Sources Phase A.1: foundation registry.
--
-- One table that holds the contract for every domain concept on the platform.
-- AI agents read this registry first when asked about a registered domain, so
-- the answer is consistent across orchestrators, edge functions, and UI pages.
-- The registry itself is metadata about other tables/views; it has no user
-- data, so it is service-role only with anon read access for AI agent lookups.
--
-- Skills consulted: architect (registry + contract pattern), data-engineer
-- (immutable schema, narrow lookups), security (locked write policy, anon
-- read for AI lookup), multitenant-engineer (no hive_id - this is a global
-- platform contract, not hive data).

BEGIN;

CREATE TABLE IF NOT EXISTS public.canonical_sources (
  domain         text PRIMARY KEY,                               -- e.g. 'asset_truth', 'risk_truth'
  source_kind    text NOT NULL
                 CHECK (source_kind IN ('view','table','rpc')),  -- how to read
  source_name    text NOT NULL,                                  -- e.g. 'v_asset_truth'
  owner_skill    text NOT NULL,                                  -- which skill owns the contract
  freshness      text NOT NULL,                                  -- 'realtime'|'1h_cache'|'daily_13_pht'|'7d_cache'|...
  contract       jsonb NOT NULL DEFAULT '{}'::jsonb,             -- declared columns + types
  description    text NOT NULL,                                  -- human-readable purpose
  registered_at  timestamptz NOT NULL DEFAULT now(),
  last_validated timestamptz,                                    -- updated by validator on PASS
  notes          text                                            -- migration plan, gotchas
);

COMMENT ON TABLE public.canonical_sources IS
  'Single-source-of-truth registry. Every AI agent reads this first when asked about a registered domain. Drift caught by validate_canonical_sources.py.';

-- Index by owner_skill so audits can roll up ownership cheaply.
CREATE INDEX IF NOT EXISTS idx_canonical_sources_owner
  ON public.canonical_sources (owner_skill);

-- Index by freshness so the validator can find non-realtime sources to check SLA.
CREATE INDEX IF NOT EXISTS idx_canonical_sources_freshness
  ON public.canonical_sources (freshness);

-- Grants. Anon + authenticated need SELECT so AI agents (which run with anon
-- key from edge functions) can look up canonicals. Service role writes only.
GRANT SELECT ON public.canonical_sources TO anon, authenticated;

-- RLS. Service role bypasses; anon/authenticated read everything (this is
-- platform metadata, not hive data). Writes are locked.
ALTER TABLE public.canonical_sources ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS canonical_sources_read ON public.canonical_sources;
CREATE POLICY canonical_sources_read ON public.canonical_sources FOR SELECT
  USING (true);

DROP POLICY IF EXISTS canonical_sources_locked ON public.canonical_sources;
CREATE POLICY canonical_sources_locked ON public.canonical_sources FOR ALL
  USING (false) WITH CHECK (false);

-- ─── Seed: register the truths that are already aligned (Tier 3 from the audit)
-- Each row is opt-in metadata, not a constraint on existing tables. Future
-- views (asset_truth, risk_truth, pm_compliance_truth) get inserted as they land.

INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, description, contract) VALUES
  ('shift_state',
   'table', 'shift_plans', 'architect', 'realtime',
   'Current shift plan per (hive, shift_date, shift_window). Orchestrator upserts draft, supervisor publishes.',
   '{"key":["hive_id","shift_date","shift_window"],"status_values":["draft","published","archived"]}'::jsonb),

  ('asset_graph_edges',
   'table', 'asset_edges', 'architect', 'realtime',
   'Typed relationships between asset_nodes (parent_of, feeds, supplies, sister, peer_class, redundant_with, controls, monitors).',
   '{"key":["id"],"hive_scoped":true,"edge_types":["parent_of","feeds","supplies","sister","peer_class","redundant_with","controls","monitors"]}'::jsonb),

  ('community_thread',
   'table', 'community_posts', 'community', 'realtime',
   'Hive community discussion thread. Soft-delete via deleted_at, public flag for cross-hive feed, edit trail via edited_at.',
   '{"key":["id"],"hive_scoped":true,"soft_delete":"deleted_at"}'::jsonb),

  ('engineering_calc_history',
   'table', 'engineering_calcs', 'architect', 'realtime',
   'Engineering calculator history. Each row is a complete snapshot (inputs + results + narrative JSONB) so re-render does not recompute.',
   '{"key":["id"],"snapshot":true,"jsonb_columns":["inputs","results","narrative"]}'::jsonb),

  ('cmms_external_link',
   'table', 'external_sync', 'data-engineer', 'realtime',
   'Per-row mapping between WorkHive entities and upstream CMMS records. Unique on (system_type, external_id, entity_type).',
   '{"key":["system_type","external_id","entity_type"],"systems":["sap_pm","maximo","generic"]}'::jsonb),

  ('ai_rate_limit',
   'table', 'ai_rate_limits', 'ai-engineer', 'realtime',
   'Per-hive AI call counter. Reset every hour by edge-function-side logic. Service role only.',
   '{"key":["hive_id"],"window":"1h"}'::jsonb),

  ('automation_log',
   'table', 'automation_log', 'data-engineer', 'realtime',
   'pg_cron + edge function results. Job status, batch counts, freshness for cross-cutting reliability tracking.',
   '{"key":["id"],"status_values":["success","failed","skipped"]}'::jsonb),

  ('hive_audit_log',
   'table', 'hive_audit_log', 'multitenant-engineer', 'realtime',
   'Supervisor moderation actions (approve, kick, mod queue, soft-delete). Append-only, hive-scoped.',
   '{"key":["id"],"hive_scoped":true,"append_only":true}'::jsonb),

  ('cmms_audit_log',
   'table', 'cmms_audit_log', 'integration-engineer', 'realtime',
   'CMMS sync batch results per hive. quality_score JSONB shows field-fill rates per import.',
   '{"key":["id"],"hive_scoped":true,"operations":["file_import","live_sync","webhook","push_completion"]}'::jsonb)
ON CONFLICT (domain) DO NOTHING;

COMMIT;
