-- VEHICLE SEED (2026-09-02): teach the logbook CAPTURE CONTRACT the 'Vehicle' category.
--
-- Found live on the VM3 walk: logbook.html gained the Vehicle discipline option (unlocking the
-- odometer_km/fuel_l reading templates), but the tier-F capture contract logbook_add_entry_v1
-- still carried the original 7-value enum, so the save was BLOCKED at the contract:
--   'value must be one of ["Mechanical",...,"Other"]; got "Vehicle"'.
-- The a-new-roster-kind-must-teach-every-consumer class: the enum lives in TWO jsonb spots on
-- ONE row (fields[] + contract_schema.properties.category.enum) — the JS validator reads this
-- row, so no page code carries a copy. Enum sweep confirmed logbook_add_entry_v1 is the only
-- contract with the discipline enum.

UPDATE public.canonical_capture_contracts
SET contract_schema = jsonb_set(
      contract_schema,
      '{properties,category,enum}',
      '["Mechanical","Electrical","Instrumentation","Hydraulic","Pneumatic","Lubrication","Vehicle","Other"]'::jsonb),
    fields = (
      SELECT jsonb_agg(
        CASE WHEN f->>'name' = 'category'
             THEN jsonb_set(f, '{values}',
                  '["Mechanical","Electrical","Instrumentation","Hydraulic","Pneumatic","Lubrication","Vehicle","Other"]'::jsonb)
             ELSE f END)
      FROM jsonb_array_elements(fields) f)
WHERE capture_id = 'logbook_add_entry_v1';
