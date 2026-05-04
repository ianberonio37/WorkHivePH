-- Project Manager: unified project tracking across 4 flavors
--   workorder   = bundle existing logbook entries + PM completions + parts under one umbrella
--   shutdown    = multi-week plant outages, critical path, daily progress
--   capex       = improvement / install projects, budget + milestones
--   contractor  = outside-vendor job folder, scope + BOM + SOW + sign-off
-- All four share one schema; UI does progressive disclosure per project_type.

-- ============================================================================
-- 1. projects (header)
-- ============================================================================
CREATE TABLE IF NOT EXISTS projects (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id         uuid NOT NULL,                                    -- hive-scoped (team data)
  worker_name     text NOT NULL,                                    -- creator
  auth_uid        uuid,
  project_code    text NOT NULL,                                    -- e.g. "SHD-2026-001"
  name            text NOT NULL,
  project_type    text NOT NULL CHECK (project_type IN
                    ('workorder','shutdown','capex','contractor')),
  status          text NOT NULL DEFAULT 'planning' CHECK (status IN
                    ('planning','active','on_hold','complete','cancelled','archived')),
  priority        text NOT NULL DEFAULT 'medium' CHECK (priority IN
                    ('low','medium','high','critical')),
  owner_name      text,
  description     text,
  start_date      date,
  end_date        date,
  budget_php      numeric(14,2),
  meta            jsonb NOT NULL DEFAULT '{}'::jsonb,                -- type-specific overflow
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  closed_at       timestamptz,
  deleted_at      timestamptz                                        -- soft-delete
);

CREATE UNIQUE INDEX IF NOT EXISTS projects_code_per_hive
  ON projects(hive_id, project_code) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS projects_status_hive
  ON projects(hive_id, status) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS projects_type_hive
  ON projects(hive_id, project_type) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS projects_owner_hive
  ON projects(hive_id, owner_name) WHERE deleted_at IS NULL;

-- ============================================================================
-- 2. project_items (scope / WBS)
-- ============================================================================
CREATE TABLE IF NOT EXISTS project_items (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  hive_id         uuid NOT NULL,                                    -- denormalized for fast filter
  wbs_code        text,                                              -- "1.2.3" outline numbering
  title           text NOT NULL,
  owner_name      text,
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN
                    ('pending','in_progress','done','blocked','skipped')),
  pct_complete    smallint NOT NULL DEFAULT 0 CHECK (pct_complete BETWEEN 0 AND 100),
  planned_start   date,
  planned_end     date,
  actual_start    date,
  actual_end      date,
  predecessors    jsonb NOT NULL DEFAULT '[]'::jsonb,                -- array of project_item ids (drives critical path)
  estimated_hours numeric(8,2),
  actual_hours    numeric(8,2),
  notes           text,
  sort_order      integer NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_items_project ON project_items(project_id);
CREATE INDEX IF NOT EXISTS project_items_hive_status ON project_items(hive_id, status);

-- ============================================================================
-- 3. project_links (polymorphic links to existing entities)
--    workorder mode primarily uses this to bundle existing logbook + PMs + parts
-- ============================================================================
CREATE TABLE IF NOT EXISTS project_links (
  id              uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  hive_id         uuid NOT NULL,
  link_type       text NOT NULL CHECK (link_type IN
                    ('asset','logbook','pm_completion','inventory_item',
                     'engineering_calc','marketplace_listing','contractor')),
  link_id         text,                                              -- nullable for free-text links; text (not uuid) because target tables have mixed id types (inventory_items.id is text, assets.id is text, pm_completions.id is uuid)
  label           text,                                              -- human-readable cache (asset name, PO no, contractor name)
  meta            jsonb NOT NULL DEFAULT '{}'::jsonb,                -- per-link extras (qty, cost, contact)
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_links_project ON project_links(project_id);
CREATE INDEX IF NOT EXISTS project_links_target ON project_links(link_type, link_id);

-- ============================================================================
-- 4. project_progress_logs (daily progress entries with supervisor sign-off)
-- ============================================================================
CREATE TABLE IF NOT EXISTS project_progress_logs (
  id                  uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  project_id          uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  hive_id             uuid NOT NULL,
  log_date            date NOT NULL DEFAULT CURRENT_DATE,
  reported_by         text NOT NULL,
  pct_complete        smallint NOT NULL DEFAULT 0 CHECK (pct_complete BETWEEN 0 AND 100),
  hours_worked        numeric(8,2),
  notes               text,
  blockers            text,
  acknowledged_by     text,
  acknowledged_at     timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_progress_project_date
  ON project_progress_logs(project_id, log_date DESC);

-- ============================================================================
-- 5. updated_at trigger (reuses existing pattern)
-- ============================================================================
CREATE OR REPLACE FUNCTION set_projects_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_projects_updated_at ON projects;
CREATE TRIGGER trg_projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION set_projects_updated_at();

DROP TRIGGER IF EXISTS trg_project_items_updated_at ON project_items;
CREATE TRIGGER trg_project_items_updated_at
  BEFORE UPDATE ON project_items
  FOR EACH ROW EXECUTE FUNCTION set_projects_updated_at();

-- ============================================================================
-- 6. Atomic project_code generator (server-side to avoid race on parallel inserts)
-- ============================================================================
CREATE OR REPLACE FUNCTION generate_project_code(p_hive_id uuid, p_type text, p_year integer)
RETURNS text AS $$
DECLARE
  prefix text;
  next_seq integer;
  result text;
BEGIN
  prefix := CASE p_type
    WHEN 'workorder'  THEN 'WO'
    WHEN 'shutdown'   THEN 'SHD'
    WHEN 'capex'      THEN 'CAP'
    WHEN 'contractor' THEN 'CON'
    ELSE 'PRJ'
  END;

  SELECT COALESCE(MAX(
    CAST(SUBSTRING(project_code FROM '\d+$') AS integer)
  ), 0) + 1
  INTO next_seq
  FROM projects
  WHERE hive_id = p_hive_id
    AND project_code LIKE prefix || '-' || p_year || '-%'
    AND deleted_at IS NULL;

  result := prefix || '-' || p_year || '-' || LPAD(next_seq::text, 3, '0');
  RETURN result;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- 7. Realtime publication (per architect skill — opt-in per table)
-- ============================================================================
DO $$
BEGIN
  -- projects: live status / progress fan-out to teammates
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'projects'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE projects';
  END IF;

  -- project_items: live scope status updates
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'project_items'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE project_items';
  END IF;

  -- project_progress_logs: live daily-log fan-out for supervisor acknowledgement
  IF NOT EXISTS (
    SELECT 1 FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime' AND tablename = 'project_progress_logs'
  ) THEN
    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE project_progress_logs';
  END IF;
END $$;
