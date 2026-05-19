-- canonical_lineage_edges: explicit edge graph backing the four-tier
-- canonical contract (FUEL -> ENGINE -> BRAIN -> DASHBOARD).
--
-- Every edge encodes: this thing (source) feeds that thing (target).
-- A row at each layer-boundary makes the chain queryable:
--   capture -> table column   ('how is the fuel persisted')
--   table   -> view           ('which v_*_truth wraps the table')
--   view    -> formula        ('which engine math the view feeds')
--   formula -> agent          ('which AI consumer reads the formula')
--   agent   -> tile            ('which dashboard surface renders the result')
--   tile    -> dashboard      ('which HTML surface owns the tile')
--
-- The audit_calm_dashboard_canonical.py + audit_phantom_captures.py +
-- audit_phantom_columns.py tools today INFER edges via text patterns.
-- This table makes the chain authoritative: a tile that can't be walked
-- back to a capture is a "broken anchor"; a capture that can't be walked
-- forward to a tile is a "phantom".
--
-- File-based registries (canonical/{capture,formula,agent}_contracts.json
-- + lineage_edges.json) hold the same edges in source so the contract
-- ships in code. The Postgres table is a queryable mirror.

BEGIN;

CREATE TABLE IF NOT EXISTS public.canonical_lineage_edges (
  id           bigserial PRIMARY KEY,
  source_kind  text NOT NULL CHECK (source_kind IN ('capture', 'column', 'table', 'view', 'formula', 'agent', 'tile', 'dashboard')),
  source_id    text NOT NULL,
  target_kind  text NOT NULL CHECK (target_kind IN ('capture', 'column', 'table', 'view', 'formula', 'agent', 'tile', 'dashboard')),
  target_id    text NOT NULL,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_kind, source_id, target_kind, target_id)
);

-- Forward-walk index: tile.X -> ??? (find what feeds X)
CREATE INDEX IF NOT EXISTS canonical_lineage_edges_target_idx
  ON public.canonical_lineage_edges (target_kind, target_id);

-- Reverse-walk index: capture.Y -> ??? (find what Y feeds)
CREATE INDEX IF NOT EXISTS canonical_lineage_edges_source_idx
  ON public.canonical_lineage_edges (source_kind, source_id);

-- The graph is platform-canonical (not hive-scoped); read-only for the
-- world, write only by the seed migration + automated lineage tooling.
ALTER TABLE public.canonical_lineage_edges ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS canonical_lineage_edges_read ON public.canonical_lineage_edges;
CREATE POLICY canonical_lineage_edges_read
  ON public.canonical_lineage_edges
  FOR SELECT
  TO anon, authenticated
  USING (true);

GRANT SELECT ON public.canonical_lineage_edges TO anon, authenticated;
GRANT USAGE, SELECT ON SEQUENCE public.canonical_lineage_edges_id_seq TO anon, authenticated;

COMMENT ON TABLE public.canonical_lineage_edges IS
  'Layer -1.5 canonical contract: explicit edge graph linking capture/column/table/view/formula/agent/tile/dashboard nodes. Audited by tools/audit_phantom_*.py and tools/audit_calm_dashboard_canonical.py. File mirror: canonical/lineage_edges.json.';

-- Register in canonical_sources so the canonical-anchor gate sees the
-- table as a known canonical entity (fuel-tier registration check).
INSERT INTO public.canonical_sources (domain, source_kind, source_name, owner_skill, freshness, contract, description, registered_at)
VALUES (
  'lineage_edges',
  'table',
  'canonical_lineage_edges',
  'architect',
  'realtime',
  '{"columns":["id","source_kind","source_id","target_kind","target_id","notes","created_at"]}'::jsonb,
  'Explicit edge graph backing the four-tier canonical contract (Fuel/Engine/Brain/Dashboard). Queryable mirror of canonical/lineage_edges.json.',
  now()
)
ON CONFLICT (domain) DO UPDATE
  SET source_name = EXCLUDED.source_name,
      contract    = EXCLUDED.contract,
      description = EXCLUDED.description;

COMMIT;
