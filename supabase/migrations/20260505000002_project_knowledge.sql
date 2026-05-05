-- Project Manager Phase 6.5 — Semantic search over projects
--
-- Mirrors fault_knowledge / pm_knowledge / skill_knowledge tables. Each row
-- holds an embedding vector + the original facts so semantic-search can
-- surface "find projects similar to this one" and the AI template
-- suggestions agent can cross-reference past lessons learned.
--
-- Source rows: projects.description, project_items (each scope item title +
-- notes), and projects.meta.lessons_learned text.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS project_knowledge (
  id            uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id       uuid,                                        -- nullable for global learning
  project_id    uuid REFERENCES projects(id) ON DELETE CASCADE,
  source_type   text NOT NULL CHECK (source_type IN
                  ('project_description', 'project_item', 'project_lesson')),
  source_id     uuid,                                         -- e.g. project_items.id when source_type='project_item'
  project_code  text,                                         -- denormalised for quick scan results
  project_type  text,                                         -- workorder / shutdown / capex / contractor
  discipline    text,                                         -- inferred from category or freq_phase
  text_chunk    text NOT NULL,                                -- the text that was embedded (1-2 sentences)
  embedding     vector(384),                                  -- 384 dims to match _shared/embedding-chain.ts TARGET_DIM (Voyage/Jina truncated)
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_knowledge_hive
  ON project_knowledge(hive_id);
CREATE INDEX IF NOT EXISTS project_knowledge_project
  ON project_knowledge(project_id);
CREATE INDEX IF NOT EXISTS project_knowledge_source
  ON project_knowledge(source_type);

-- Vector similarity index (HNSW for cosine, same as fault_knowledge)
CREATE INDEX IF NOT EXISTS project_knowledge_embedding
  ON project_knowledge
  USING hnsw (embedding vector_cosine_ops);

-- pg_cron jobs for the 2 new scheduled-agents report_types.
-- These call scheduled-agents weekly (Monday + Wednesday) so the suggestions
-- and risk reports stay fresh without burning daily AI tokens on small hives.
-- Note: requires app.supabase_functions_url + app.service_role_key settings
-- (already configured in 20260425000003_scheduled_agents.sql). Wrapped in DO
-- blocks so it's a no-op if pg_cron isn't enabled (e.g. local dev without
-- Supabase managed extensions).
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    -- Project suggestions: every Monday 06:00 UTC (= 14:00 PHT)
    PERFORM cron.unschedule('project-suggestions-weekly');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'project-suggestions-weekly',
      '0 6 * * 1',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/scheduled-agents'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key'')), body := ''{"report_type":"project_suggestions"}''::jsonb);'
    );
    -- Project risk: every Wednesday 06:00 UTC
    PERFORM cron.unschedule('project-risk-weekly');
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_cron') THEN
    PERFORM cron.schedule(
      'project-risk-weekly',
      '0 6 * * 3',
      'SELECT net.http_post(url := current_setting(''app.supabase_functions_url'') || ''/scheduled-agents'', headers := jsonb_build_object(''Authorization'', ''Bearer '' || current_setting(''app.service_role_key'')), body := ''{"report_type":"project_risk"}''::jsonb);'
    );
  END IF;
EXCEPTION WHEN OTHERS THEN NULL;
END $$;
