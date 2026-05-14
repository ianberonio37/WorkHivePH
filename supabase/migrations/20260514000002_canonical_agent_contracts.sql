-- Canonical Anchor Tier C: AI Output JSON Schemas
-- Registers JSON schemas for all AI-generated outputs (voice companion, agents, etc.)
-- Used by canonical_anchor validator for L4 validation
-- Date: 2026-05-14

CREATE TABLE IF NOT EXISTS public.canonical_agent_contracts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_name VARCHAR(128) NOT NULL UNIQUE, -- e.g., "voice-companion", "semantic-router", "platform-scraper"
  output_schema JSONB NOT NULL,            -- JSON Schema for output validation
  version INT DEFAULT 1,                   -- Schema version
  description TEXT,                        -- Human-readable purpose
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.canonical_agent_contracts ENABLE ROW LEVEL SECURITY;

-- Public read access (schema registry is public)
CREATE POLICY "canonical_agent_contracts_read" ON public.canonical_agent_contracts
  FOR SELECT
  USING (true);

-- Service role write (only internal code)
CREATE POLICY "canonical_agent_contracts_write" ON public.canonical_agent_contracts
  FOR ALL
  USING (auth.role() = 'service_role');

-- Seed with Voice Companion agents
INSERT INTO public.canonical_agent_contracts (agent_name, output_schema, description)
VALUES
  (
    'semantic-router',
    '{
      "type": "object",
      "required": ["route", "confidence"],
      "properties": {
        "route": {
          "type": "string",
          "enum": ["platform-data", "semantic-depth", "simple-reply"],
          "description": "Intent classification route"
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1,
          "description": "Confidence of classification (0-1)"
        },
        "intents": {
          "type": "array",
          "items": {"type": "string"},
          "description": "Recognized intents in user query"
        },
        "narration": {"type": "string"},
        "asset_resolution": {"type": "object"}
      }
    }',
    'Voice Companion Phase 0 semantic router output'
  ),
  (
    'platform-scraper',
    '{
      "type": "object",
      "properties": {
        "equipment_status": {"type": "object", "description": "Equipment counts by state"},
        "risk_assets": {"type": "array", "description": "Top risky assets"},
        "pm_status": {"type": "object", "description": "PM due/overdue counts"},
        "inventory_alerts": {"type": "object", "description": "Stock alerts"},
        "adoption": {"type": "object", "description": "Adoption metrics"},
        "timestamp": {"type": "string", "format": "date-time"},
        "errors": {"type": "array", "items": {"type": "string"}}
      }
    }',
    'Voice Companion Phase 1 platform scraper KPI output'
  ),
  (
    'voice-model-call',
    '{
      "type": "object",
      "required": ["response", "model_used"],
      "properties": {
        "response": {"type": "string", "description": "LLM response text"},
        "model_used": {
          "type": "string",
          "enum": ["scout", "qwen", "voyage", "jina"],
          "description": "Which model was used"
        },
        "latency_ms": {"type": "number", "description": "Response latency in ms"},
        "tokens_used": {"type": "integer", "description": "Total tokens consumed"},
        "fallback_attempts": {"type": "integer", "description": "How many fallbacks tried"}
      }
    }',
    'Voice Companion Phase 2 multi-model orchestrator output'
  )
ON CONFLICT (agent_name) DO NOTHING;

GRANT SELECT ON public.canonical_agent_contracts TO authenticated, anon;
