-- Hive Audit Log
-- Records every supervisor power action: approve, reject, kick, join
-- Workers never see this table. Supervisors see it on the HiveBoard.

CREATE TABLE IF NOT EXISTS hive_audit_log (
  id          uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id     uuid REFERENCES hives(id) ON DELETE CASCADE NOT NULL,
  actor       text NOT NULL,       -- worker_name of supervisor who took the action
  action      text NOT NULL,       -- 'approve_item' | 'reject_item' | 'kick_member' | 'member_joined'
  target_type text,                -- 'inventory_items' | 'assets' | 'hive_members'
  target_id   text,                -- id of the affected row
  target_name text,                -- human-readable label (part name, asset id, worker name)
  meta        jsonb,               -- extra context: submitted_by, rejection reason, etc.
  created_at  timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX idx_hive_audit_log_hive_created
  ON hive_audit_log (hive_id, created_at DESC);
