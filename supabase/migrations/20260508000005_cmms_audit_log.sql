-- CMMS Audit Log
-- Records every import, live sync, webhook, and push-back operation.
-- batch_id groups all rows from one import/sync run so you can undo
-- or replay a specific operation. quality_score stores field-level
-- completeness metrics computed immediately after the operation.

CREATE TABLE IF NOT EXISTS cmms_audit_log (
  id             uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id        uuid        REFERENCES hives(id) ON DELETE CASCADE,
  batch_id       text        NOT NULL,          -- e.g. 'import-1746700000000'
  operation      text        NOT NULL,          -- 'file_import' | 'live_sync' | 'webhook' | 'push_completion'
  entity_type    text,                          -- 'work_order' | 'asset' | 'pm_schedule' | 'inventory'
  system_type    text,                          -- 'sap_pm' | 'maximo' | 'generic'
  rows_attempted integer     DEFAULT 0,
  rows_written   integer     DEFAULT 0,
  rows_failed    integer     DEFAULT 0,
  quality_score  jsonb,                         -- { pct_machine: 95, pct_problem: 87, pct_closed_at: 100 }
  triggered_by   text,                          -- worker_name or 'cmms-sync' / 'cmms-webhook-receiver'
  created_at     timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cmms_audit_hive
  ON cmms_audit_log (hive_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cmms_audit_batch
  ON cmms_audit_log (batch_id);
