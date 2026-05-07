-- external_sync: bridge table for CMMS/ERP integration (Tier 1-3).
-- Stores every record ingested from an external system (SAP PM, Maximo, Generic).
-- The UNIQUE constraint on (system_type, external_id, entity_type) is the
-- deduplication key -- upsert on this triple prevents phantom duplicates
-- when the same CSV or API response is processed more than once.

CREATE TABLE IF NOT EXISTS external_sync (
  id             uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id        uuid,                               -- null = test / no-hive context
  system_type    text        NOT NULL,               -- 'sap_pm' | 'maximo' | 'generic'
  external_id    text        NOT NULL,               -- AUFNR | WONUM | work_order_no
  entity_type    text        NOT NULL,               -- 'work_order' | 'asset' | 'pm_schedule' | 'inventory'
  workhive_table text,                               -- target table: 'logbook' | 'assets' | etc.
  status         text,                               -- normalized WorkHive status
  sync_payload   jsonb,                              -- full normalized WorkHive record
  last_synced_at timestamptz DEFAULT now(),
  sync_status    text        DEFAULT 'active',       -- 'active' | 'deleted' | 'error'

  UNIQUE (system_type, external_id, entity_type)
);

CREATE INDEX IF NOT EXISTS idx_external_sync_hive
  ON external_sync (hive_id, system_type, entity_type);

CREATE INDEX IF NOT EXISTS idx_external_sync_ext_id
  ON external_sync (system_type, external_id);

CREATE INDEX IF NOT EXISTS idx_external_sync_synced
  ON external_sync (last_synced_at DESC);

-- integration_configs: per-hive CMMS connection settings.
-- Stores API credentials (encrypted at Supabase Vault level), field mappings,
-- sync schedule, and connection metadata for Tier 2+ integrations.

CREATE TABLE IF NOT EXISTS integration_configs (
  id             uuid        DEFAULT gen_random_uuid() PRIMARY KEY,
  hive_id        uuid        REFERENCES hives(id) ON DELETE CASCADE,
  system_type    text        NOT NULL,               -- 'sap_pm' | 'maximo' | 'generic'
  label          text,                               -- human-readable name ("SAP Plant PH01")
  endpoint_url   text,                               -- base URL of the CMMS API
  auth_method    text        DEFAULT 'api_key',      -- 'api_key' | 'oauth' | 'basic'
  field_map      jsonb       DEFAULT '{}',           -- their field names -> WorkHive field names
  sync_freq      text        DEFAULT 'daily',        -- 'manual' | 'hourly' | 'daily'
  enabled        boolean     DEFAULT true,
  last_sync_at   timestamptz,
  last_sync_count integer,
  created_at     timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_integration_configs_hive
  ON integration_configs (hive_id);
