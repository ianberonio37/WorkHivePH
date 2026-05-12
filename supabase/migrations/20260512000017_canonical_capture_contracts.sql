-- Tier F (Layer 0): canonical_capture_contracts — the input contract
-- registry. (2026-05-12)
--
-- Every HTML form, voice capture, QR scan, file upload, CSV import, and
-- webhook on the platform produces structured data that lands in a fuel
-- table. Today those mappings are implicit — change a form field and
-- nobody knows which fuel column was meant to receive it. This registry
-- makes the contract explicit and machine-readable:
--
--     [User / Sensor / External]
--             |
--             v
--  CAPTURE CONTRACT (Tier F / L0)   <-- this table
--             |
--             v
--           FUEL
--             |
--             v
--          ENGINE -> BRAIN -> DASHBOARD -> DRIVER
--
-- A capture row pins down:
--   - the surface (form / voice / qr / import / upload / sensor / webhook)
--   - which page or edge fn houses it
--   - which fuel table + columns it writes to
--   - the JSON Schema of the captured payload
--   - where validation happens (client / edge / db trigger / all)
--
-- The Canonical Anchor Gate (L8) then enforces that every capture
-- surface in code is anchored to a registered capture_id (or carries
-- `// capture-allow: <reason>`). The Tier C-style fixture validator
-- (validate_capture_contracts.py, shipped later) tests good/bad
-- payloads against each schema.
--
-- Wave 1 (this migration): the 5 most-touched captures across the
-- platform. Waves 2-3 land in follow-up migrations as we audit
-- per-page surfaces.
--
-- Skills consulted: architect (registry pattern + FK to fuel column
-- names), data-engineer (target_table + target_columns lineage),
-- ai-engineer (voice/AI extraction shape), security (capture as input
-- validation policy), mobile-maestro (QR payload standardisation),
-- frontend (form -> column mapping), qa (fixture-driven coverage).

BEGIN;

CREATE TABLE IF NOT EXISTS public.canonical_capture_contracts (
  capture_id      text PRIMARY KEY,                                    -- e.g. 'logbook_add_entry_v1'
  surface         text NOT NULL                                         -- where the capture lives
                  CHECK (surface IN ('form', 'voice', 'qr', 'import', 'upload', 'sensor', 'webhook', 'chat')),
  source_page     text NOT NULL,                                        -- 'logbook.html' or 'voice-journal-agent'
  fields          jsonb NOT NULL DEFAULT '[]'::jsonb,                   -- [{name, type, required, validation, max_len, ...}]
  target_table    text NOT NULL,                                        -- which fuel table receives the data
  target_columns  text[] NOT NULL DEFAULT '{}',                         -- which columns it can write
  validates_at    text NOT NULL DEFAULT 'edge'                          -- where validation happens
                  CHECK (validates_at IN ('client', 'edge', 'db_trigger', 'all')),
  contract_schema jsonb NOT NULL,                                       -- JSON Schema for the captured payload
  consumers       text[] NOT NULL DEFAULT '{}',                         -- pages/dashboards reading downstream of this capture
  notes           text,
  registered_at   timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.canonical_capture_contracts IS
  'Tier F (Layer 0): registry of every capture surface (form, voice, qr, import, upload, sensor, webhook, chat) on the platform. Each row pins the input contract to its target fuel table+columns so a form-field drift FAILs CI instead of silently dropping data.';

CREATE INDEX IF NOT EXISTS idx_canonical_capture_contracts_target
  ON public.canonical_capture_contracts (target_table);

CREATE INDEX IF NOT EXISTS idx_canonical_capture_contracts_surface
  ON public.canonical_capture_contracts (surface);

GRANT SELECT ON public.canonical_capture_contracts TO anon, authenticated;
ALTER TABLE public.canonical_capture_contracts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS canonical_capture_contracts_read ON public.canonical_capture_contracts;
CREATE POLICY canonical_capture_contracts_read ON public.canonical_capture_contracts FOR SELECT
  USING (true);
DROP POLICY IF EXISTS canonical_capture_contracts_locked ON public.canonical_capture_contracts;
CREATE POLICY canonical_capture_contracts_locked ON public.canonical_capture_contracts FOR ALL
  USING (false) WITH CHECK (false);


-- =============================================================================
-- WAVE 1: the 5 most-touched captures on the platform.
-- =============================================================================

INSERT INTO public.canonical_capture_contracts
  (capture_id, surface, source_page, fields, target_table, target_columns, validates_at, contract_schema, consumers, notes)
VALUES

-- 1. logbook add-entry form (the most-written-to capture on the platform)
('logbook_add_entry_v1', 'form', 'logbook.html',
 '[
   {"name":"worker_name","type":"text","required":true,"max_len":50},
   {"name":"date","type":"datetime","required":true},
   {"name":"machine","type":"text","required":true,"max_len":80},
   {"name":"category","type":"enum","required":true,"values":["Mechanical","Electrical","Instrumentation","Hydraulic","Pneumatic","Lubrication","Other"]},
   {"name":"maintenance_type","type":"enum","required":true,"values":["Breakdown / Corrective","Preventive Maintenance","Inspection","Calibration","Modification","Other"]},
   {"name":"status","type":"enum","required":true,"values":["Open","Closed","In Progress"]},
   {"name":"problem","type":"text","required":true,"max_len":2000},
   {"name":"action","type":"text","required":false,"max_len":2000},
   {"name":"root_cause","type":"text","required":false,"max_len":500},
   {"name":"failure_consequence","type":"text","required":false,"max_len":200},
   {"name":"downtime_hours","type":"numeric","required":false,"min":0,"max":8760},
   {"name":"parts_used","type":"jsonb","required":false},
   {"name":"asset_node_id","type":"uuid","required":false},
   {"name":"knowledge","type":"text","required":false,"max_len":2000}
 ]'::jsonb,
 'logbook',
 ARRAY['worker_name','date','machine','category','maintenance_type','status','problem','action','root_cause','failure_consequence','downtime_hours','parts_used','asset_node_id','knowledge','hive_id','auth_uid'],
 'edge',
 '{
   "type":"object",
   "required":["worker_name","date","machine","category","maintenance_type","status","problem"],
   "properties":{
     "worker_name":{"type":"string","minLength":1,"maxLength":50},
     "date":{"type":"string"},
     "machine":{"type":"string","minLength":1,"maxLength":80},
     "category":{"type":"string","enum":["Mechanical","Electrical","Instrumentation","Hydraulic","Pneumatic","Lubrication","Other"]},
     "maintenance_type":{"type":"string"},
     "status":{"type":"string","enum":["Open","Closed","In Progress"]},
     "problem":{"type":"string","minLength":1,"maxLength":2000},
     "action":{"type":["string","null"],"maxLength":2000},
     "root_cause":{"type":["string","null"]},
     "downtime_hours":{"type":["number","null"],"minimum":0}
   }
 }'::jsonb,
 ARRAY['hive.html','analytics.html','asset-hub.html','predictive.html'],
 'Most-written capture on the platform. Field count drift (add/remove fields) needs the contract bumped to v2 + a follow-up to update consumers.'),

-- 2. inventory add-part form
('inventory_add_part_v1', 'form', 'inventory.html',
 '[
   {"name":"part_number","type":"text","required":true,"max_len":80},
   {"name":"part_name","type":"text","required":true,"max_len":200},
   {"name":"category","type":"text","required":false,"max_len":80},
   {"name":"unit","type":"text","required":false,"max_len":20},
   {"name":"qty_on_hand","type":"integer","required":true,"min":0},
   {"name":"min_qty","type":"integer","required":false,"min":0},
   {"name":"bin_location","type":"text","required":false,"max_len":80},
   {"name":"linked_asset_node_ids","type":"uuid[]","required":false},
   {"name":"notes","type":"text","required":false,"max_len":1000},
   {"name":"photo","type":"text","required":false}
 ]'::jsonb,
 'inventory_items',
 ARRAY['part_number','part_name','category','unit','qty_on_hand','min_qty','bin_location','linked_asset_node_ids','notes','photo','hive_id','worker_name','auth_uid','submitted_by','status'],
 'edge',
 '{
   "type":"object",
   "required":["part_number","part_name","qty_on_hand"],
   "properties":{
     "part_number":{"type":"string","minLength":1,"maxLength":80},
     "part_name":{"type":"string","minLength":1,"maxLength":200},
     "qty_on_hand":{"type":"integer","minimum":0},
     "min_qty":{"type":["integer","null"],"minimum":0},
     "linked_asset_node_ids":{"type":["array","null"],"items":{"type":"string"}}
   }
 }'::jsonb,
 ARRAY['hive.html','analytics.html','alert-hub.html','parts-tracker.html'],
 'Approval workflow gated downstream via inventory_items.status. Photo is base64 today; should be storage URL.'),

-- 3. PM completion form
('pm_completion_v1', 'form', 'pm-scheduler.html',
 '[
   {"name":"asset_id","type":"uuid","required":true},
   {"name":"scope_item_id","type":"uuid","required":false},
   {"name":"worker_name","type":"text","required":true,"max_len":50},
   {"name":"completed_at","type":"datetime","required":true},
   {"name":"status","type":"enum","required":true,"values":["done","skipped","partial"]},
   {"name":"notes","type":"text","required":false,"max_len":1000}
 ]'::jsonb,
 'pm_completions',
 ARRAY['asset_id','scope_item_id','worker_name','completed_at','status','notes','hive_id','auth_uid'],
 'edge',
 '{
   "type":"object",
   "required":["asset_id","worker_name","completed_at","status"],
   "properties":{
     "asset_id":{"type":"string"},
     "worker_name":{"type":"string","minLength":1,"maxLength":50},
     "completed_at":{"type":"string"},
     "status":{"type":"string","enum":["done","skipped","partial"]},
     "notes":{"type":["string","null"],"maxLength":1000}
   }
 }'::jsonb,
 ARRAY['hive.html','analytics.html','asset-hub.html','shift-brain.html'],
 'PM compliance computation reads v_pm_compliance_truth which aggregates these.'),

-- 4. voice-journal capture (audio -> transcript -> AI-extracted summary)
('voice_journal_capture_v1', 'voice', 'voice-journal-agent',
 '[
   {"name":"audio_blob","type":"binary","required":true,"max_mb":10},
   {"name":"worker_name","type":"text","required":true,"max_len":50},
   {"name":"transcript","type":"text","required":true,"max_len":5000,"derived_by":"whisper"},
   {"name":"summary","type":"text","required":false,"max_len":1000,"derived_by":"groq"},
   {"name":"category","type":"text","required":false,"derived_by":"groq"},
   {"name":"machine","type":"text","required":false,"derived_by":"groq"},
   {"name":"actions","type":"jsonb","required":false,"derived_by":"groq"}
 ]'::jsonb,
 'voice_journal_entries',
 ARRAY['worker_name','transcript','summary','category','machine','actions','audio_url','hive_id','auth_uid','created_at'],
 'edge',
 '{
   "type":"object",
   "required":["worker_name","transcript"],
   "properties":{
     "worker_name":{"type":"string","minLength":1,"maxLength":50},
     "transcript":{"type":"string","minLength":1,"maxLength":5000},
     "summary":{"type":["string","null"],"maxLength":1000},
     "category":{"type":["string","null"]},
     "machine":{"type":["string","null"]},
     "actions":{"type":["array","null"]}
   }
 }'::jsonb,
 ARRAY['voice-journal.html','hive.html','assistant.html'],
 'Multi-stage capture: audio_blob -> Whisper transcript -> Groq extraction. Each stage adds derived fields. Validates_at=edge ensures the FINAL extracted payload matches the schema before write.'),

-- 5. QR asset lookup (the surface that doesn't have a generator-side canonical today)
('qr_asset_lookup_v1', 'qr', 'asset-hub.html',
 '[
   {"name":"qr_payload","type":"text","required":true,"format":"wh-asset-v1"},
   {"name":"asset_tag","type":"text","required":true,"derived":"parsed from qr_payload","max_len":50},
   {"name":"hive_id","type":"uuid","required":false,"derived":"resolved from asset_nodes lookup"}
 ]'::jsonb,
 'asset_nodes',
 ARRAY['tag','hive_id'],
 'client',
 '{
   "type":"object",
   "required":["qr_payload","asset_tag"],
   "properties":{
     "qr_payload":{"type":"string","pattern":"^wh-asset-v1:[a-z0-9_-]+:[a-z0-9_-]+$"},
     "asset_tag":{"type":"string","minLength":1,"maxLength":50},
     "hive_id":{"type":["string","null"]}
   }
 }'::jsonb,
 ARRAY['asset-hub.html','logbook.html','inventory.html'],
 'QR payload format: "wh-asset-v1:{hive_slug}:{asset_tag}". Both generator (when building printable QR tags) and scanner (asset-hub camera) MUST conform to this contract. Today the format is implicit; this is the moment we lock it down.')

ON CONFLICT (capture_id) DO UPDATE
  SET surface         = EXCLUDED.surface,
      source_page     = EXCLUDED.source_page,
      fields          = EXCLUDED.fields,
      target_table    = EXCLUDED.target_table,
      target_columns  = EXCLUDED.target_columns,
      validates_at    = EXCLUDED.validates_at,
      contract_schema = EXCLUDED.contract_schema,
      consumers       = EXCLUDED.consumers,
      notes           = EXCLUDED.notes,
      registered_at   = now();

COMMIT;
