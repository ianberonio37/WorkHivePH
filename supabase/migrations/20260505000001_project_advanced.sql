-- Project Manager Phase 5 — Advanced features
--   5B — Multi-role assignments (project_roles table)
--   5D — Change order tracking (project_change_orders table)
--
-- Resource leveling (5A) and Schedule risk (5C) are pure compute on existing
-- columns — no schema change needed, only python-api additions.
--
-- Backward compatibility: projects.owner_name remains the canonical "owner".
-- project_roles is additive; existing projects continue to work without
-- a roles row. Owner role can be derived from owner_name OR from a
-- project_roles row with role='owner' (clients should accept both).

-- ============================================================================
-- 1. project_roles — multi-role assignments per project
-- ============================================================================
CREATE TABLE IF NOT EXISTS project_roles (
  id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  hive_id       uuid NOT NULL,
  worker_name   text NOT NULL,
  role          text NOT NULL CHECK (role IN
                  ('owner', 'planner', 'safety_officer', 'cost_engineer', 'reviewer')),
  assigned_by   text,
  assigned_at   timestamptz NOT NULL DEFAULT now(),
  notes         text
);

-- Same worker can hold multiple roles on the same project; same role can be
-- held by multiple workers (e.g. 2 reviewers). But a (project, worker, role)
-- triple should be unique.
CREATE UNIQUE INDEX IF NOT EXISTS project_roles_unique
  ON project_roles(project_id, worker_name, role);
CREATE INDEX IF NOT EXISTS project_roles_project ON project_roles(project_id);
CREATE INDEX IF NOT EXISTS project_roles_worker  ON project_roles(hive_id, worker_name);

-- ============================================================================
-- 2. project_change_orders — formal scope change tracking with approval
-- ============================================================================
CREATE TABLE IF NOT EXISTS project_change_orders (
  id                  uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id          uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  hive_id             uuid NOT NULL,
  co_number           text NOT NULL,                   -- e.g. "CO-001" sequential per project
  title               text NOT NULL,
  scope_change        text NOT NULL,                   -- prose description of what's changing
  reason              text,                            -- why (cost, safety, regulatory, scope clarification)
  cost_impact_php     numeric(14,2),                   -- positive = increase, negative = credit
  schedule_impact_days integer,                        -- positive = adds days, negative = saves days
  status              text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
  requested_by        text NOT NULL,
  requested_at        timestamptz NOT NULL DEFAULT now(),
  approved_by         text,
  approved_at         timestamptz,
  rejection_reason    text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_change_orders_project
  ON project_change_orders(project_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS project_change_orders_co_number
  ON project_change_orders(project_id, co_number);

-- ============================================================================
-- 3. Atomic CO number generator (mirrors generate_project_code)
-- ============================================================================
CREATE OR REPLACE FUNCTION generate_change_order_number(p_project_id uuid)
RETURNS text AS $$
DECLARE
  next_seq integer;
BEGIN
  SELECT COALESCE(MAX(
    CAST(SUBSTRING(co_number FROM '\d+$') AS integer)
  ), 0) + 1
  INTO next_seq
  FROM project_change_orders
  WHERE project_id = p_project_id;
  RETURN 'CO-' || LPAD(next_seq::text, 3, '0');
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 4. Realtime publication (per architect skill)
-- ============================================================================
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'project_roles'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE project_roles';
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'project_change_orders'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE project_change_orders';
  END IF;
END $$;
