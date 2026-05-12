-- Tier C contract realignment (2026-05-12).
--
-- The 7 brain output schemas registered in 20260512000013 were aspirational
-- shapes. Before wiring runtime JSON Schema validation, the schemas need to
-- match what the producing code ACTUALLY returns today (otherwise every
-- valid response would be rejected as a contract violation on rollout).
--
-- This migration UPDATEs the json_schema column on canonical_agent_contracts
-- so each contract reflects the real production shape:
--
--   - analytics_action_plan_v1  -> { summary, this_week[], watch_list[] }
--     (was: { summary, priorities[] } — wrong)
--   - parts_stockout_v1         -> { stockout_risk[], at_risk_count?, period_days? }
--     (was: { reorder[] } — completely different key name)
--   - anomaly_baseline_v1       -> { baselines[]?, anomalies[], anomaly_count?, machines_tracked? }
--     (was: { assets[] } — wrong key)
--   - health_score_v1           -> v_risk_truth row shape with asset_name (not asset)
--   - next_failure_forecast_v1, parts_spike_v1, priority_ranking_v1: minor
--     adjustments so additional summary keys don't fail validation
--
-- All schemas use additionalProperties:true (default) so summary fields like
-- at_risk_count / standard / period_days don't fail validation. Only the
-- minimally-required keys are listed in required[].
--
-- Skills consulted: ai-engineer (schemas that survive real LLM/Python
-- output variance), platform-guardian (forward-only ratchet — schemas can
-- only become more permissive without a version bump).

BEGIN;

UPDATE public.canonical_agent_contracts
SET json_schema = '{
  "type": "object",
  "required": ["summary", "this_week", "watch_list"],
  "properties": {
    "summary":     { "type": "string", "minLength": 1 },
    "this_week":   { "type": "array", "items": { "type": "string" } },
    "watch_list":  { "type": "array", "items": { "type": "string" } }
  }
}'::jsonb,
    registered_at = now()
WHERE contract_id = 'analytics_action_plan_v1';

UPDATE public.canonical_agent_contracts
SET json_schema = '{
  "type": "object",
  "required": ["predictions"],
  "properties": {
    "predictions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["machine"],
        "properties": {
          "machine":         { "type": "string" },
          "predicted_next":  { "type": ["string", "null"] },
          "risk":            { "type": "string", "enum": ["HIGH", "MEDIUM", "LOW"] },
          "basis":           { "type": "string" }
        }
      }
    },
    "high_risk":     { "type": "integer" },
    "medium_risk":   { "type": "integer" },
    "total_tracked": { "type": "integer" }
  }
}'::jsonb,
    registered_at = now()
WHERE contract_id = 'next_failure_forecast_v1';

UPDATE public.canonical_agent_contracts
SET json_schema = '{
  "type": "object",
  "required": ["stockout_risk"],
  "properties": {
    "stockout_risk": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["part_name"],
        "properties": {
          "part_name":            { "type": "string" },
          "qty_on_hand":          { "type": "number" },
          "days_until_stockout":  { "type": ["number", "null"] },
          "urgency":              { "type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"] }
        }
      }
    },
    "at_risk_count": { "type": "integer" },
    "period_days":   { "type": "integer" }
  }
}'::jsonb,
    registered_at = now()
WHERE contract_id = 'parts_stockout_v1';

UPDATE public.canonical_agent_contracts
SET json_schema = '{
  "type": "object",
  "required": ["asset_name"],
  "properties": {
    "asset_name":         { "type": "string" },
    "hive_id":            { "type": "string" },
    "risk_score":         { "type": ["number", "null"] },
    "risk_level":         { "type": ["string", "null"] },
    "health_score":       { "type": ["number", "null"] },
    "mtbf_days":          { "type": ["number", "null"] },
    "days_until_failure": { "type": ["number", "null"] },
    "top_factors":        { "type": ["array", "object", "null"] }
  }
}'::jsonb,
    registered_at = now()
WHERE contract_id = 'health_score_v1';

UPDATE public.canonical_agent_contracts
SET json_schema = '{
  "type": "object",
  "required": ["anomalies"],
  "properties": {
    "baselines": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "machine":  { "type": "string" },
          "mean":     { "type": "number" },
          "stddev":   { "type": "number" }
        }
      }
    },
    "anomalies": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["machine"],
        "properties": {
          "machine":           { "type": "string" },
          "value":             { "type": "number" },
          "deviation_sigma":   { "type": "number" },
          "quality_flag":      { "type": "string", "enum": ["OK", "WATCH", "ANOMALY", "STALE"] }
        }
      }
    },
    "anomaly_count":    { "type": "integer" },
    "machines_tracked": { "type": "integer" }
  }
}'::jsonb,
    registered_at = now()
WHERE contract_id = 'anomaly_baseline_v1';

UPDATE public.canonical_agent_contracts
SET json_schema = '{
  "type": "object",
  "required": ["spikes"],
  "properties": {
    "spikes": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["part_name"],
        "properties": {
          "part_name":           { "type": "string" },
          "current_rate":        { "type": "number" },
          "previous_rate":       { "type": "number" },
          "spike_factor":        { "type": "number" }
        }
      }
    },
    "note":     { "type": "string" }
  }
}'::jsonb,
    registered_at = now()
WHERE contract_id = 'parts_spike_v1';

UPDATE public.canonical_agent_contracts
SET json_schema = '{
  "type": "object",
  "required": ["ranking"],
  "properties": {
    "ranking": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["machine"],
        "properties": {
          "machine":              { "type": "string" },
          "priority":             { "type": "string", "enum": ["P1", "P2", "P3", "P4"] },
          "priority_score":       { "type": "number" },
          "contributing_factors": { "type": "array" }
        }
      }
    },
    "p1_count":     { "type": "integer" },
    "p2_count":     { "type": "integer" },
    "top_priority": { "type": ["string", "null"] }
  }
}'::jsonb,
    registered_at = now()
WHERE contract_id = 'priority_ranking_v1';

COMMIT;
