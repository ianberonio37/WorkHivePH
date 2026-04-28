-- Add readings_json field to logbook
-- Stores numeric sensor readings at time of failure (temperature, vibration, pressure, etc.)
-- Unlocks anomaly detection and sensor-based predictive analytics (ISO 13381-1:2015)
-- Schema: { "temperature_c": 85.5, "vibration_mms": 12.3, "pressure_bar": 4.2 }
-- NULL = not recorded (optional field, legacy rows unaffected)

ALTER TABLE logbook
  ADD COLUMN IF NOT EXISTS readings_json jsonb;
