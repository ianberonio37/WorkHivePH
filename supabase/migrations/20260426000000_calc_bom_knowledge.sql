-- Phase 2 — Calc + BOM Knowledge Tables
-- Adds calc_knowledge and bom_knowledge so engineering calculation results
-- and BOM/SOW outputs become searchable via semantic-search.
-- No existing tables or functions are modified.
-- Edge function wiring (embed-entry + semantic-search updates) done separately
-- after engineering design testing is complete.

-- ── CALC KNOWLEDGE (from Engineering Calc Agent) ─────────────────────────────
-- One row per completed calculation. Embedding is generated from:
-- calc_type + key_inputs + key_outputs + notes combined.
-- Used to answer: "What pump size did we use for Building B last year?"

CREATE TABLE IF NOT EXISTS calc_knowledge (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid REFERENCES hives(id) ON DELETE CASCADE,
  calc_type     text,                        -- e.g. "pump_sizing", "duct_sizing"
  project_ref   text,                        -- optional project name/reference
  key_inputs    jsonb,                        -- snapshot of main input values
  key_outputs   jsonb,                        -- snapshot of main result values
  notes         text,                        -- engineer notes / location context
  embedding     vector(384),                 -- nomic-embed-text-v1.5 (Groq, free)
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_calc_knowledge_hive
  ON calc_knowledge (hive_id);

CREATE INDEX IF NOT EXISTS idx_calc_knowledge_calc_type
  ON calc_knowledge (calc_type);

CREATE INDEX IF NOT EXISTS idx_calc_knowledge_embedding
  ON calc_knowledge USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- ── BOM KNOWLEDGE (from Engineering BOM/SOW Agent) ───────────────────────────
-- One row per generated BOM/SOW document. Embedding is generated from:
-- project_name + calc_type + key_spec + notes combined.
-- Used to answer: "What spec did we use for the chiller in Plant A?"

CREATE TABLE IF NOT EXISTS bom_knowledge (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  hive_id       uuid REFERENCES hives(id) ON DELETE CASCADE,
  project_name  text,                        -- e.g. "Building B CWS"
  calc_type     text,                        -- linked calc type
  key_spec      text,                        -- main equipment spec as plain text
  item_count    int DEFAULT 0,               -- number of BOM line items
  notes         text,                        -- location, client, scope notes
  embedding     vector(384),
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bom_knowledge_hive
  ON bom_knowledge (hive_id);

CREATE INDEX IF NOT EXISTS idx_bom_knowledge_embedding
  ON bom_knowledge USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 50);

-- ── SEARCH: CALC KNOWLEDGE ────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION search_calc_knowledge(
  query_embedding vector(384),
  match_hive_id   uuid,
  match_count     int DEFAULT 5
)
RETURNS TABLE (
  id           uuid,
  calc_type    text,
  project_ref  text,
  key_inputs   jsonb,
  key_outputs  jsonb,
  notes        text,
  similarity   float
)
LANGUAGE sql STABLE AS $$
  SELECT
    id, calc_type, project_ref, key_inputs, key_outputs, notes,
    1 - (embedding <=> query_embedding) AS similarity
  FROM calc_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;

-- ── SEARCH: BOM KNOWLEDGE ─────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION search_bom_knowledge(
  query_embedding vector(384),
  match_hive_id   uuid,
  match_count     int DEFAULT 5
)
RETURNS TABLE (
  id            uuid,
  project_name  text,
  calc_type     text,
  key_spec      text,
  item_count    int,
  notes         text,
  similarity    float
)
LANGUAGE sql STABLE AS $$
  SELECT
    id, project_name, calc_type, key_spec, item_count, notes,
    1 - (embedding <=> query_embedding) AS similarity
  FROM bom_knowledge
  WHERE hive_id = match_hive_id
    AND embedding IS NOT NULL
  ORDER BY embedding <=> query_embedding
  LIMIT match_count;
$$;
