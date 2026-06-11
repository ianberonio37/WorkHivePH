-- F5 (roadmap findings ledger): parts_spike_v1 contract vs producer mismatch.
-- python-api/analytics/predictive.py calc_parts_consumption_spike emits
-- spike_factor: null for the NEW_USAGE signal (a part with ZERO baseline
-- consumption has no ratio — null is the honest value, and analytics.html
-- already renders it as "New usage"). The contract said {"type":"number"},
-- so every NEW_USAGE row violated it. Fix the CONTRACT, not the producer:
-- allow null, keep the key optional (016 realignment already dropped it from
-- required). Forward migration per the migration-immutability rule — never
-- edit 20260512000016 in place.

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
          "spike_factor":        { "type": ["number", "null"] },
          "signal":              { "type": "string", "enum": ["NEW_USAGE", "WARNING", "CRITICAL"] },
          "interpretation":      { "type": "string" }
        }
      }
    },
    "note":     { "type": "string" }
  }
}'::jsonb,
    registered_at = now()
WHERE contract_id = 'parts_spike_v1';
