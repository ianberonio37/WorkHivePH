-- Failure Signature Detection: Phase 1.2
-- Stores detected pre-failure alerts per machine per hive.
-- The failure-signature-scan Edge Function populates this table on a schedule.
-- Supervisors acknowledge alerts from the hive dashboard.

CREATE TABLE IF NOT EXISTS failure_signature_alerts (
  id              uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id         uuid        REFERENCES hives(id) ON DELETE CASCADE,
  machine         text        NOT NULL,
  category        text,
  rule_id         text        NOT NULL,  -- which rule fired: 'repeat_failure' | 'escalating_frequency' | 'multi_symptom' | 'missed_pm'
  alert_title     text        NOT NULL,  -- short human-readable title
  alert_detail    text,                  -- AI-generated explanation of the pattern
  evidence        jsonb,                 -- supporting data: occurrences, dates, root causes
  days_to_failure float,                 -- estimated days until next failure (null = unknown)
  severity        text        DEFAULT 'warning',  -- 'info' | 'warning' | 'critical'
  status          text        DEFAULT 'active',   -- 'active' | 'acknowledged' | 'resolved'
  acknowledged_by text,
  acknowledged_at timestamptz,
  detected_at     timestamptz DEFAULT now(),
  expires_at      timestamptz,           -- alert auto-expires after this (re-detected if still present)
  UNIQUE (hive_id, machine, rule_id)    -- one active alert per machine per rule
);

CREATE INDEX IF NOT EXISTS idx_fsa_hive_status
  ON failure_signature_alerts (hive_id, status, detected_at DESC);

CREATE INDEX IF NOT EXISTS idx_fsa_machine
  ON failure_signature_alerts (hive_id, machine);
