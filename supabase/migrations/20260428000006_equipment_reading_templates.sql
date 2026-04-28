-- Equipment Reading Templates
-- Replaces the hardcoded READINGS_BY_CATEGORY map in logbook.html.
-- Supervisors can add new equipment categories via Supabase dashboard
-- without requiring a code deploy.
--
-- Usage: logbook.html fetches this table on load and caches in memory.
-- When a Breakdown entry is logged, the matching category's readings
-- appear as quick-fill number inputs.

CREATE TABLE IF NOT EXISTS equipment_reading_templates (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category     text NOT NULL,           -- matches logbook f-category values
  reading_key  text NOT NULL,           -- key stored in readings_json JSONB
  label        text NOT NULL,           -- display label shown to field worker
  unit         text NOT NULL,           -- unit shown next to input
  placeholder  text NOT NULL,           -- example value shown as hint
  sort_order   int  DEFAULT 0,          -- display order within category
  created_at   timestamptz DEFAULT now()
);

-- One category can have multiple readings
CREATE UNIQUE INDEX IF NOT EXISTS idx_reading_templates_cat_key
  ON equipment_reading_templates (category, reading_key);

CREATE INDEX IF NOT EXISTS idx_reading_templates_category
  ON equipment_reading_templates (category, sort_order);

-- ── Seed: current hardcoded READINGS_BY_CATEGORY from logbook.html ────────────

INSERT INTO equipment_reading_templates (category, reading_key, label, unit, placeholder, sort_order) VALUES

-- Mechanical
('Mechanical', 'temperature_c', 'Temperature', '°C',    '85',    1),
('Mechanical', 'vibration_mms', 'Vibration',   'mm/s',  '4.5',   2),
('Mechanical', 'pressure_bar',  'Pressure',    'bar',   '4.2',   3),

-- Electrical
('Electrical', 'voltage_v',     'Voltage',     'V',     '220',   1),
('Electrical', 'current_a',     'Current',     'A',     '15',    2),
('Electrical', 'temperature_c', 'Temperature', '°C',    '65',    3),

-- Hydraulic
('Hydraulic',  'pressure_bar',  'Pressure',    'bar',   '180',   1),
('Hydraulic',  'flow_lpm',      'Flow',        'L/min', '45',    2),
('Hydraulic',  'temperature_c', 'Oil Temp',    '°C',    '55',    3),

-- Pneumatic
('Pneumatic',  'pressure_bar',  'Pressure',    'bar',   '6.5',   1),
('Pneumatic',  'temperature_c', 'Temperature', '°C',    '40',    2),

-- Instrumentation
('Instrumentation', 'signal_ma',     'Signal',      'mA',  '12',  1),
('Instrumentation', 'temperature_c', 'Temperature', '°C',  '35',  2),

-- Lubrication
('Lubrication', 'temperature_c', 'Oil Temp', '°C',  '60',   1),
('Lubrication', 'pressure_bar',  'Pressure', 'bar', '3.5',  2)

ON CONFLICT (category, reading_key) DO NOTHING;

-- ── RLS: allow all authenticated reads, restrict writes to supervisors ─────────
-- Currently open (no RLS) — consistent with platform's pre-auth approach.
-- When Supabase Auth is implemented, add:
--   CREATE POLICY "anon read" ON equipment_reading_templates FOR SELECT USING (true);
--   CREATE POLICY "supervisor write" ON equipment_reading_templates FOR ALL
--     USING (auth.jwt() ->> 'role' = 'supervisor');
