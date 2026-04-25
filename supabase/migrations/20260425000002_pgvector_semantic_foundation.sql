-- Phase 1.1 — Semantic Foundation: pgvector + Knowledge Tables
-- Enables meaning-based search across logbook, skill matrix, and PM health.
-- Every save on those pages will embed the entry and store it here.
-- The AI assistant queries all three tables before answering any question.

-- ── EXTENSIONS ───────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS vector;

-- ── FAULT KNOWLEDGE (from Logbook) ───────────────────────────────────────────
-- One row per logbook entry. Embedding is generated from:
-- machine + problem + root_cause + action + knowledge fields combined.

CREATE TABLE IF NOT EXISTS fault_knowledge (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid REFERENCES hives(id) ON DELETE CASCADE,
  logbook_id    text,                        -- original logbook entry id
  machine       text,
  category      text,
  problem       text,
  root_cause    text,
  action        text,
  knowledge     text,
  worker_name   text,
  embedding     vector(384),                 -- nomic-embed-text-v1.5 (Groq, free)
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_fault_knowledge_hive
  ON fault_knowledge (hive_id);

CREATE INDEX IF NOT EXISTS idx_fault_knowledge_embedding
  ON fault_knowledge USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- ── SKILL KNOWLEDGE (from Skill Matrix) ──────────────────────────────────────
-- One row per worker per discipline. Embedding is generated from:
-- worker_name + discipline + level + primary_skill combined.
-- Used to answer: "Who is best qualified for this job?"

CREATE TABLE IF NOT EXISTS skill_knowledge (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid REFERENCES hives(id) ON DELETE CASCADE,
  worker_name   text,
  discipline    text,
  level         int,                         -- 1-5 skill level
  primary_skill text,
  embedding     vector(384),
  updated_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_skill_knowledge_hive
  ON skill_knowledge (hive_id);

CREATE INDEX IF NOT EXISTS idx_skill_knowledge_embedding
  ON skill_knowledge USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- ── PM KNOWLEDGE (from PM Health / Hiveboard) ─────────────────────────────────
-- One row per asset health snapshot. Embedding is generated from:
-- asset name + category + overdue tasks + last completion combined.
-- Used to answer: "Which assets are at risk?" and "Was this preventable?"

CREATE TABLE IF NOT EXISTS pm_knowledge (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id         uuid REFERENCES hives(id) ON DELETE CASCADE,
  asset_id        uuid,
  asset_name      text,
  category        text,
  overdue_count   int DEFAULT 0,
  last_completed  timestamptz,
  health_summary  text,                      -- human-readable snapshot text
  embedding       vector(384),
  updated_at      timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pm_knowledge_hive
  ON pm_knowledge (hive_id);

CREATE INDEX IF NOT EXISTS idx_pm_knowledge_embedding
  ON pm_knowledge USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- ── SEMANTIC SEARCH FUNCTIONS ─────────────────────────────────────────────────
-- Called by the semantic-search edge function.
-- Returns top N matches ordered by cosine similarity (1 = identical, 0 = unrelated).

-- Search fault history by meaning:
CREATE OR REPLACE FUNCTION search_fault_knowledge(
  query_embedding vector(384),
  match_hive_id   uuid,
  match_count     int DEFAULT 5
)
RETURNS TABLE (
  id          uuid,
  machine     text,
  problem     text,
  root_cause  text,
  action      text,
  knowledge   text,
  worker_name text,
  similarity  float
)
LANGUAGE sql STABLE AS $$
  SELECT
    id, machine, problem, root_cause, action, knowledge, worker_name,
    1 - (embedding <=> query_embedding) AS similarity
  FROM fault_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;

-- Search skill profiles by meaning:
CREATE OR REPLACE FUNCTION search_skill_knowledge(
  query_embedding vector(384),
  match_hive_id   uuid,
  match_count     int DEFAULT 5
)
RETURNS TABLE (
  id            uuid,
  worker_name   text,
  discipline    text,
  level         int,
  primary_skill text,
  similarity    float
)
LANGUAGE sql STABLE AS $$
  SELECT
    id, worker_name, discipline, level, primary_skill,
    1 - (embedding <=> query_embedding) AS similarity
  FROM skill_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;

-- Search PM health by meaning:
CREATE OR REPLACE FUNCTION search_pm_knowledge(
  query_embedding vector(384),
  match_hive_id   uuid,
  match_count     int DEFAULT 5
)
RETURNS TABLE (
  id             uuid,
  asset_name     text,
  category       text,
  overdue_count  int,
  last_completed timestamptz,
  health_summary text,
  similarity     float
)
LANGUAGE sql STABLE AS $$
  SELECT
    id, asset_name, category, overdue_count, last_completed, health_summary,
    1 - (embedding <=> query_embedding) AS similarity
  FROM pm_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;

-- ── UNIFIED CROSS-REFERENCE SEARCH ───────────────────────────────────────────
-- Searches all 3 tables at once and returns results tagged by source.
-- Used by the orchestrator to get full context in one call.

CREATE OR REPLACE FUNCTION search_all_knowledge(
  query_embedding vector(384),
  match_hive_id   uuid,
  match_count     int DEFAULT 3    -- top 3 from each source = 9 results max
)
RETURNS TABLE (
  source      text,
  summary     text,
  similarity  float
)
LANGUAGE sql STABLE AS $$
  SELECT source, summary, similarity FROM (
    SELECT 'fault' AS source,
      CONCAT('Machine: ', machine, ' | Problem: ', problem,
             ' | Root cause: ', root_cause, ' | Fix: ', action) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM fault_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) f

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'skill' AS source,
      CONCAT('Worker: ', worker_name, ' | Discipline: ', discipline,
             ' | Level: ', level::text, ' | Primary: ', primary_skill) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM skill_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) s

  UNION ALL

  SELECT source, summary, similarity FROM (
    SELECT 'pm' AS source,
      CONCAT('Asset: ', asset_name, ' | Category: ', category,
             ' | Overdue tasks: ', overdue_count::text, ' | ', health_summary) AS summary,
      1 - (embedding <=> query_embedding) AS similarity
    FROM pm_knowledge
    WHERE hive_id = match_hive_id AND embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding LIMIT match_count
  ) p;
$$;
