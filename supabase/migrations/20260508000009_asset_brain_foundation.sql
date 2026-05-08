-- Asset Brain Phase 0: foundation schema.
-- Three new tables (asset_nodes, asset_edges, asset_embeddings) plus a read-side view.
-- No data is duplicated from existing modules. asset_nodes is the canonical graph node;
-- legacy_asset_id and pm_asset_id link back to the existing assets/pm_assets rows so
-- nothing is broken and no data migration is required.
--
-- Skills consulted before writing:
--   architect (shared catalog pattern, FK type matching, GRANT requirement),
--   multitenant-engineer (hive membership join RLS, GRANT, auth_uid sync),
--   data-engineer (indexes at creation, vector(384) for nomic-embed-text-v1_5),
--   realtime-engineer (publication opt-in, REPLICA IDENTITY FULL),
--   security (RLS membership join, supervisor role check),
--   devops (pg_cron commented out by default),
--   performance (composite indexes for hive scoping).

BEGIN;

-- 0. ai_rate_limits: per-hive AI call counter. Required by every AI-calling
--    edge function (asset-brain-query, shift-planner-orchestrator, etc.).
--    The ai-engineer skill mandates this table before any model call so a bot
--    cannot drain the AI budget. Created here because Asset Brain's edge
--    function is the first to depend on it; all subsequent AI functions reuse it.

CREATE TABLE IF NOT EXISTS public.ai_rate_limits (
  hive_id      uuid PRIMARY KEY REFERENCES public.hives(id) ON DELETE CASCADE,
  call_count   integer NOT NULL DEFAULT 0,
  window_start timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ai_rate_limits_hive
  ON public.ai_rate_limits (hive_id);

COMMENT ON TABLE public.ai_rate_limits IS
  'Per-hive AI call counter. Reset every hour by edge-function-side logic. Service role bypasses RLS.';

-- Service role writes only; anon/authenticated never read or modify directly.
GRANT SELECT, INSERT, UPDATE, DELETE ON public.ai_rate_limits TO service_role;

ALTER TABLE public.ai_rate_limits ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ai_rate_limits_locked ON public.ai_rate_limits;
CREATE POLICY ai_rate_limits_locked ON public.ai_rate_limits FOR ALL
  USING (false) WITH CHECK (false);

-- 1. asset_nodes: canonical graph node, ISO 14224 hierarchy.

CREATE TABLE IF NOT EXISTS public.asset_nodes (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  auth_uid        uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  worker_name     text,
  parent_id       uuid REFERENCES public.asset_nodes(id) ON DELETE SET NULL,
  level           text NOT NULL DEFAULT 'equipment'
                  CHECK (level IN ('enterprise','site','plant','unit','equipment','component')),
  tag             text NOT NULL,
  name            text NOT NULL,
  iso_class       text,
  criticality     text NOT NULL DEFAULT 'medium'
                  CHECK (criticality IN ('low','medium','high','critical')),
  location        text,
  manufacturer    text,
  model           text,
  serial_no       text,
  install_date    date,
  external_ids    jsonb NOT NULL DEFAULT '{}'::jsonb,
  legacy_asset_id text REFERENCES public.assets(id) ON DELETE SET NULL,
  pm_asset_id     uuid REFERENCES public.pm_assets(id) ON DELETE SET NULL,
  status          text NOT NULL DEFAULT 'approved'
                  CHECK (status IN ('pending','approved','rejected')),
  submitted_by    text,
  approved_by     text,
  approved_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT asset_nodes_tag_unique_per_hive UNIQUE (hive_id, tag)
);

COMMENT ON TABLE public.asset_nodes IS
  'Asset Brain canonical graph node. ISO 14224 hierarchy. Links optionally to legacy assets.id (text) and pm_assets.id (uuid) so existing data stays intact.';

CREATE INDEX IF NOT EXISTS idx_asset_nodes_hive_status
  ON public.asset_nodes (hive_id, status);
CREATE INDEX IF NOT EXISTS idx_asset_nodes_hive_level
  ON public.asset_nodes (hive_id, level);
CREATE INDEX IF NOT EXISTS idx_asset_nodes_parent
  ON public.asset_nodes (parent_id);
CREATE INDEX IF NOT EXISTS idx_asset_nodes_iso_class
  ON public.asset_nodes (iso_class);
CREATE INDEX IF NOT EXISTS idx_asset_nodes_legacy
  ON public.asset_nodes (legacy_asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_nodes_pm_asset
  ON public.asset_nodes (pm_asset_id);
CREATE INDEX IF NOT EXISTS idx_asset_nodes_auth_uid
  ON public.asset_nodes (auth_uid);
CREATE INDEX IF NOT EXISTS idx_asset_nodes_created
  ON public.asset_nodes (hive_id, created_at DESC);

-- 2. asset_edges: typed relationships between asset_nodes.

CREATE TABLE IF NOT EXISTS public.asset_edges (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  auth_uid      uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  from_node_id  uuid NOT NULL REFERENCES public.asset_nodes(id) ON DELETE CASCADE,
  to_node_id    uuid NOT NULL REFERENCES public.asset_nodes(id) ON DELETE CASCADE,
  edge_type     text NOT NULL
                CHECK (edge_type IN ('parent_of','feeds','supplies','sister','peer_class','redundant_with','controls','monitors')),
  properties    jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT asset_edges_no_self_loop CHECK (from_node_id <> to_node_id),
  CONSTRAINT asset_edges_unique UNIQUE (hive_id, from_node_id, to_node_id, edge_type)
);

COMMENT ON TABLE public.asset_edges IS
  'Typed edges between asset_nodes. parent_of duplicates asset_nodes.parent_id for graph traversal convenience.';

CREATE INDEX IF NOT EXISTS idx_asset_edges_hive_from
  ON public.asset_edges (hive_id, from_node_id);
CREATE INDEX IF NOT EXISTS idx_asset_edges_hive_to
  ON public.asset_edges (hive_id, to_node_id);
CREATE INDEX IF NOT EXISTS idx_asset_edges_type
  ON public.asset_edges (edge_type);

-- 3. asset_embeddings: vector(384) summary embedding per asset for semantic neighbor search.
--    Dimension matches the nomic-embed-text-v1_5 model used by _shared/ai-chain.ts.

CREATE TABLE IF NOT EXISTS public.asset_embeddings (
  node_id        uuid PRIMARY KEY REFERENCES public.asset_nodes(id) ON DELETE CASCADE,
  hive_id        uuid NOT NULL REFERENCES public.hives(id) ON DELETE CASCADE,
  summary        text,
  embedding      vector(384),
  refreshed_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.asset_embeddings IS
  'Per-asset summary embedding. Refreshed nightly or on significant logbook activity. vector(384) matches nomic-embed-text-v1_5 in _shared/ai-chain.ts.';

CREATE INDEX IF NOT EXISTS idx_asset_embeddings_hive
  ON public.asset_embeddings (hive_id);

-- ivfflat requires data to build well. Lists count is small for now (will grow with data).
-- The CONCURRENTLY flag is unsafe inside a transaction, so ship the simple form first
-- and rebuild the index later when row count justifies tuning.
CREATE INDEX IF NOT EXISTS idx_asset_embeddings_vec
  ON public.asset_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

-- 4. asset_brain_overview: read-side view for the hub. Regular view, not materialized,
--    so changes are instantly visible. Switch to MATERIALIZED + nightly refresh later
--    if observed render latency exceeds budget.

CREATE OR REPLACE VIEW public.asset_brain_overview AS
SELECT
  n.id              AS node_id,
  n.hive_id,
  n.tag,
  n.name,
  n.level,
  n.iso_class,
  n.criticality,
  n.location,
  n.parent_id,
  n.legacy_asset_id,
  n.pm_asset_id,
  (SELECT count(*) FROM public.logbook l
     WHERE l.hive_id = n.hive_id
       AND l.asset_ref_id = n.legacy_asset_id) AS lifetime_logbook_entries,
  (SELECT max(l.created_at) FROM public.logbook l
     WHERE l.hive_id = n.hive_id
       AND l.asset_ref_id = n.legacy_asset_id
       AND l.maintenance_type = 'Breakdown / Corrective') AS last_failure_at,
  (SELECT count(*) FROM public.pm_completions pc
     WHERE pc.hive_id = n.hive_id
       AND pc.asset_id = n.pm_asset_id) AS pm_completed_count,
  (SELECT count(*) FROM public.asset_edges e
     WHERE e.hive_id = n.hive_id
       AND (e.from_node_id = n.id OR e.to_node_id = n.id)) AS edge_count
FROM public.asset_nodes n
WHERE n.status = 'approved';

COMMENT ON VIEW public.asset_brain_overview IS
  'Read-side aggregate of an asset_node and its cross-module footprint. Drives the asset-hub.html header.';

-- 5. Grants. Required for migrations because the dashboard auto-grant only fires on GUI table creation.

GRANT SELECT, INSERT, UPDATE, DELETE ON public.asset_nodes      TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.asset_edges      TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.asset_embeddings TO anon, authenticated;
GRANT SELECT                          ON public.asset_brain_overview TO anon, authenticated;

-- 6. Row Level Security. Hive-membership-join pattern from the multitenant skill.

ALTER TABLE public.asset_nodes      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_edges      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_embeddings ENABLE ROW LEVEL SECURITY;

-- Read: any active hive member.

DROP POLICY IF EXISTS asset_nodes_read ON public.asset_nodes;
CREATE POLICY asset_nodes_read ON public.asset_nodes FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS asset_edges_read ON public.asset_edges;
CREATE POLICY asset_edges_read ON public.asset_edges FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS asset_embeddings_read ON public.asset_embeddings;
CREATE POLICY asset_embeddings_read ON public.asset_embeddings FOR SELECT
  USING (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Write: own row OR hive supervisor. Workers can submit (status=pending), supervisors can approve.

DROP POLICY IF EXISTS asset_nodes_write ON public.asset_nodes;
CREATE POLICY asset_nodes_write ON public.asset_nodes FOR ALL
  USING (
    auth.uid() IS NOT NULL
    AND (
      auth_uid = auth.uid()
      OR EXISTS (
        SELECT 1 FROM public.hive_members hm
        WHERE hm.hive_id = asset_nodes.hive_id
          AND hm.auth_uid = auth.uid()
          AND hm.role = 'supervisor'
          AND hm.status = 'active'
      )
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

DROP POLICY IF EXISTS asset_edges_write ON public.asset_edges;
CREATE POLICY asset_edges_write ON public.asset_edges FOR ALL
  USING (
    auth.uid() IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM public.hive_members hm
      WHERE hm.hive_id = asset_edges.hive_id
        AND hm.auth_uid = auth.uid()
        AND hm.role = 'supervisor'
        AND hm.status = 'active'
    )
  )
  WITH CHECK (
    auth.uid() IS NOT NULL
    AND hive_id IN (
      SELECT hm.hive_id FROM public.hive_members hm
      WHERE hm.auth_uid = auth.uid() AND hm.status = 'active'
    )
  );

-- Embeddings are written by the edge function only (service_role bypasses RLS).
-- Authenticated users get read-only via the SELECT policy above.

DROP POLICY IF EXISTS asset_embeddings_write ON public.asset_embeddings;
CREATE POLICY asset_embeddings_write ON public.asset_embeddings FOR ALL
  USING (false) WITH CHECK (false);

-- 7. updated_at trigger on asset_nodes.

CREATE OR REPLACE FUNCTION public.tg_asset_nodes_touch_updated()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS asset_nodes_touch_updated ON public.asset_nodes;
CREATE TRIGGER asset_nodes_touch_updated
  BEFORE UPDATE ON public.asset_nodes
  FOR EACH ROW EXECUTE FUNCTION public.tg_asset_nodes_touch_updated();

-- 8. Extend the existing trg_sync_auth_uid_on_signup trigger to also link asset_nodes.
--    The trigger is created in the auth migration. We replace it with a version that
--    includes the new table.

CREATE OR REPLACE FUNCTION public.sync_auth_uid_on_signup()
RETURNS trigger AS $$
BEGIN
  UPDATE public.hive_members          SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.logbook               SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.inventory_items       SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.inventory_transactions SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.assets                SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.pm_assets             SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.pm_completions        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.schedule_items        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_profiles        SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_badges          SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.skill_exam_attempts   SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.engineering_calcs     SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  UPDATE public.asset_nodes           SET auth_uid = NEW.auth_uid WHERE worker_name = NEW.display_name AND auth_uid IS NULL;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 9. Realtime publication. Per realtime-engineer skill, opt-in is required.
--    Wrapped in DO blocks because ADD TABLE errors if the table is already in the publication.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'asset_nodes'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.asset_nodes';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'asset_edges'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE public.asset_edges';
  END IF;
END
$$;

-- REPLICA IDENTITY FULL on asset_nodes so DELETE filters on hive_id work.
-- Trade WAL volume for filterable DELETE events; row volume on this table is low.

ALTER TABLE public.asset_nodes REPLICA IDENTITY FULL;
ALTER TABLE public.asset_edges REPLICA IDENTITY FULL;

COMMIT;

-- 10. pg_cron block (commented out per devops skill rule).
--     Run manually after enabling pg_cron extension in Supabase Dashboard.
--     Refreshes asset_embeddings nightly and recomputes the materialized view if we
--     promote asset_brain_overview to MATERIALIZED later.
--
-- /*
-- SELECT cron.schedule(
--   'asset-brain-embed-refresh',
--   '0 3 * * *',
--   $$ SELECT net.http_post(
--     url     := 'https://YOUR_PROJECT.supabase.co/functions/v1/asset-brain-embed-refresh',
--     headers := '{"Authorization": "Bearer YOUR_SERVICE_ROLE_KEY", "Content-Type": "application/json"}'::jsonb,
--     body    := '{}'::jsonb
--   ) $$
-- );
-- */
