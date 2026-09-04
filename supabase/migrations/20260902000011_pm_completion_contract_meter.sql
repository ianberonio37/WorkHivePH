-- VEHICLE SEED (2026-09-02): teach pm_completion_v1 the meter_at_completion field.
-- pm-scheduler now stamps the vehicle's current odometer on km-interval completions (without
-- it next_due_km never advances past baseline+interval). The contract's additionalProperties
-- is unset so the key already passes — this records it as a TYPED part of the capture, the
-- same one-roster-kind-teaches-every-consumer discipline as 20260902000010.

UPDATE public.canonical_capture_contracts
SET contract_schema = jsonb_set(
      contract_schema,
      '{properties,meter_at_completion}',
      '{"type": ["number", "null"], "minimum": 0}'::jsonb),
    fields = fields || '[{"name": "meter_at_completion", "type": "number", "required": false,
                          "note": "vehicle odometer at completion; drives next_due_km"}]'::jsonb
WHERE capture_id = 'pm_completion_v1'
  AND NOT (fields::text LIKE '%meter_at_completion%');
