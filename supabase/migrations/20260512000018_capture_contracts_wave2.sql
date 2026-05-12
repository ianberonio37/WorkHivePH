-- Tier F / Layer 0 — Capture Contracts Wave 2 (2026-05-12).
--
-- Wave 1 (migration 17) seeded the 5 most-touched captures. Wave 2
-- registers 15 more across the platform — every page that was flagged
-- with `<!-- capture-allow: -->` in Wave 1.5 gets a real contract here,
-- plus a few additional high-impact capture surfaces (hive invite,
-- skill exam, community post, dayplanner schedule item, asset wizard,
-- AI chat input).
--
-- Pattern matches Wave 1: fields[], target_table, target_columns[],
-- validates_at, contract_schema (JSON Schema), consumers[].
-- Where surfaces span multiple tables (e.g. CMMS imports write to
-- logbook + inventory + pm_assets), target_table is the PRIMARY
-- write target; secondary tables are documented in notes.
--
-- Skills consulted: architect (registry growth pattern), frontend
-- (form -> column mapping), data-engineer (target_table choices),
-- ai-engineer (chat / voice extraction), security (input policy as
-- capture contract), multitenant-engineer (hive-scoped writes).

BEGIN;

INSERT INTO public.canonical_capture_contracts
  (capture_id, surface, source_page, fields, target_table, target_columns, validates_at, contract_schema, consumers, notes)
VALUES

-- ─── 1. Landing page early-access signup ───────────────────────────────────
('early_access_signup_v1', 'form', 'index.html',
 '[
   {"name":"email","type":"email","required":true,"max_len":120},
   {"name":"source","type":"text","required":false,"max_len":40}
 ]'::jsonb,
 'early_access_emails',
 ARRAY['email','source','created_at'],
 'edge',
 '{
   "type":"object",
   "required":["email"],
   "properties":{
     "email":{"type":"string","format":"email","maxLength":120},
     "source":{"type":"string","maxLength":40}
   }
 }'::jsonb,
 ARRAY['index.html'],
 'Marketing waitlist. Bot-protection deferred; email uniqueness enforced at DB.'),

-- ─── 2. CMMS import (external sync) ────────────────────────────────────────
('cmms_import_v1', 'import', 'integrations.html',
 '[
   {"name":"system_type","type":"enum","required":true,"values":["maximo","emaint","fiix","upkeep","custom"]},
   {"name":"entity_type","type":"enum","required":true,"values":["asset","logbook","pm_completion","inventory_item","pm_scope_item"]},
   {"name":"source_payload","type":"jsonb","required":true},
   {"name":"batch_id","type":"text","required":true,"max_len":80}
 ]'::jsonb,
 'external_sync',
 ARRAY['system_type','entity_type','source_payload','batch_id','sync_payload','hive_id','created_at'],
 'edge',
 '{
   "type":"object",
   "required":["system_type","entity_type","batch_id","source_payload"],
   "properties":{
     "system_type":{"type":"string","enum":["maximo","emaint","fiix","upkeep","custom"]},
     "entity_type":{"type":"string","enum":["asset","logbook","pm_completion","inventory_item","pm_scope_item"]},
     "batch_id":{"type":"string","minLength":1,"maxLength":80},
     "source_payload":{"type":"object"}
   }
 }'::jsonb,
 ARRAY['integrations.html','cmms-webhook-receiver','audit-log.html'],
 'Cross-table writes (logbook, inventory, pm_*). target_table=external_sync is the AUDIT row; per-row writes follow STATUS_MAP. Idempotent via batch_id.'),

-- ─── 3. Project create form ────────────────────────────────────────────────
('project_create_v1', 'form', 'project-manager.html',
 '[
   {"name":"name","type":"text","required":true,"max_len":120},
   {"name":"project_type","type":"enum","required":true,"values":["workorder","shutdown","capex","contractor"]},
   {"name":"priority","type":"enum","required":true,"values":["low","medium","high","critical"]},
   {"name":"status","type":"enum","required":false,"values":["planning","active","on_hold","complete","cancelled"]},
   {"name":"owner_name","type":"text","required":false,"max_len":50},
   {"name":"budget_php","type":"numeric","required":false,"min":0},
   {"name":"start_date","type":"date","required":false},
   {"name":"end_date","type":"date","required":false},
   {"name":"description","type":"text","required":false,"max_len":2000}
 ]'::jsonb,
 'projects',
 ARRAY['name','project_type','priority','status','owner_name','budget_php','start_date','end_date','description','hive_id','worker_name','auth_uid','project_code'],
 'edge',
 '{
   "type":"object",
   "required":["name","project_type","priority"],
   "properties":{
     "name":{"type":"string","minLength":1,"maxLength":120},
     "project_type":{"type":"string","enum":["workorder","shutdown","capex","contractor"]},
     "priority":{"type":"string","enum":["low","medium","high","critical"]},
     "budget_php":{"type":["number","null"],"minimum":0}
   }
 }'::jsonb,
 ARRAY['project-manager.html','project-report.html','hive.html'],
 'project_code is server-generated via generate_project_code RPC.'),

-- ─── 4. Project change order ───────────────────────────────────────────────
('project_change_order_v1', 'form', 'project-manager.html',
 '[
   {"name":"project_id","type":"uuid","required":true},
   {"name":"title","type":"text","required":true,"max_len":120},
   {"name":"scope_change","type":"text","required":true,"max_len":2000},
   {"name":"reason","type":"text","required":false,"max_len":1000},
   {"name":"cost_impact_php","type":"numeric","required":false},
   {"name":"schedule_impact_days","type":"integer","required":false},
   {"name":"requested_by","type":"text","required":true,"max_len":50}
 ]'::jsonb,
 'project_change_orders',
 ARRAY['project_id','title','scope_change','reason','cost_impact_php','schedule_impact_days','requested_by','hive_id','co_number','status'],
 'edge',
 '{
   "type":"object",
   "required":["project_id","title","scope_change","requested_by"],
   "properties":{
     "project_id":{"type":"string"},
     "title":{"type":"string","minLength":1,"maxLength":120},
     "scope_change":{"type":"string","minLength":1,"maxLength":2000},
     "cost_impact_php":{"type":["number","null"]},
     "schedule_impact_days":{"type":["integer","null"]}
   }
 }'::jsonb,
 ARRAY['project-manager.html','project-report.html'],
 'co_number generated server-side via generate_change_order_number RPC. Drives v_project_truth.approved_change_orders + approved_co_cost_php aggregates.'),

-- ─── 5. Project progress log ───────────────────────────────────────────────
('project_progress_log_v1', 'form', 'project-manager.html',
 '[
   {"name":"project_id","type":"uuid","required":true},
   {"name":"log_date","type":"date","required":true},
   {"name":"pct_complete","type":"integer","required":true,"min":0,"max":100},
   {"name":"hours_worked","type":"numeric","required":false,"min":0},
   {"name":"notes","type":"text","required":false,"max_len":2000},
   {"name":"blockers","type":"text","required":false,"max_len":1000},
   {"name":"reported_by","type":"text","required":true,"max_len":50}
 ]'::jsonb,
 'project_progress_logs',
 ARRAY['project_id','log_date','pct_complete','hours_worked','notes','blockers','reported_by','hive_id'],
 'edge',
 '{
   "type":"object",
   "required":["project_id","log_date","pct_complete","reported_by"],
   "properties":{
     "project_id":{"type":"string"},
     "log_date":{"type":"string"},
     "pct_complete":{"type":"integer","minimum":0,"maximum":100},
     "hours_worked":{"type":["number","null"],"minimum":0}
   }
 }'::jsonb,
 ARRAY['project-manager.html','project-report.html','v_project_truth'],
 'Append-only. v_project_truth.last_progress_at reads max(created_at).'),

-- ─── 6. Marketplace listing create ────────────────────────────────────────
('marketplace_listing_v1', 'form', 'marketplace-seller.html',
 '[
   {"name":"title","type":"text","required":true,"max_len":120},
   {"name":"category","type":"text","required":true,"max_len":40},
   {"name":"price_php","type":"numeric","required":true,"min":0},
   {"name":"description","type":"text","required":true,"max_len":5000},
   {"name":"photos","type":"text[]","required":false},
   {"name":"status","type":"enum","required":false,"values":["draft","active","paused","sold"]},
   {"name":"location","type":"text","required":false,"max_len":120}
 ]'::jsonb,
 'marketplace_listings',
 ARRAY['title','category','price_php','description','photos','status','location','seller_id','created_at'],
 'edge',
 '{
   "type":"object",
   "required":["title","category","price_php","description"],
   "properties":{
     "title":{"type":"string","minLength":1,"maxLength":120},
     "category":{"type":"string","minLength":1,"maxLength":40},
     "price_php":{"type":"number","minimum":0},
     "description":{"type":"string","minLength":1,"maxLength":5000}
   }
 }'::jsonb,
 ARRAY['marketplace.html','marketplace-seller.html','marketplace-seller-profile.html'],
 'Photos field is URL array post-upload; raw blobs land in storage.'),

-- ─── 7. Marketplace buyer inquiry ──────────────────────────────────────────
('marketplace_inquiry_v1', 'form', 'marketplace.html',
 '[
   {"name":"listing_id","type":"uuid","required":true},
   {"name":"buyer_name","type":"text","required":true,"max_len":50},
   {"name":"message","type":"text","required":true,"max_len":2000}
 ]'::jsonb,
 'marketplace_inquiries',
 ARRAY['listing_id','buyer_name','message','created_at'],
 'edge',
 '{
   "type":"object",
   "required":["listing_id","buyer_name","message"],
   "properties":{
     "listing_id":{"type":"string"},
     "buyer_name":{"type":"string","minLength":1,"maxLength":50},
     "message":{"type":"string","minLength":1,"maxLength":2000}
   }
 }'::jsonb,
 ARRAY['marketplace-seller.html','marketplace.html'],
 'Cross-hive buyer-seller comms; pre-order conversation thread.'),

-- ─── 8. Marketplace order placement ────────────────────────────────────────
('marketplace_order_v1', 'form', 'marketplace.html',
 '[
   {"name":"listing_id","type":"uuid","required":true},
   {"name":"quantity","type":"integer","required":true,"min":1},
   {"name":"shipping_address","type":"text","required":true,"max_len":500},
   {"name":"payment_method","type":"enum","required":true,"values":["gcash","maya","bank_transfer","cod","credit_card"]}
 ]'::jsonb,
 'marketplace_orders',
 ARRAY['listing_id','buyer_name','quantity','shipping_address','payment_method','status','total_php','idempotency_key'],
 'edge',
 '{
   "type":"object",
   "required":["listing_id","quantity","shipping_address","payment_method"],
   "properties":{
     "listing_id":{"type":"string"},
     "quantity":{"type":"integer","minimum":1},
     "payment_method":{"type":"string","enum":["gcash","maya","bank_transfer","cod","credit_card"]}
   }
 }'::jsonb,
 ARRAY['marketplace.html','marketplace-seller.html','marketplace-checkout edge fn'],
 'Money-movement. Stripe Idempotency-Key required on POST (PRODUCTION_FIXES #34).'),

-- ─── 9. Hive member invite ─────────────────────────────────────────────────
('hive_invite_v1', 'form', 'hive.html',
 '[
   {"name":"worker_name","type":"text","required":true,"max_len":50},
   {"name":"role","type":"enum","required":true,"values":["worker","supervisor"]}
 ]'::jsonb,
 'hive_members',
 ARRAY['worker_name','role','hive_id','status'],
 'edge',
 '{
   "type":"object",
   "required":["worker_name","role"],
   "properties":{
     "worker_name":{"type":"string","minLength":1,"maxLength":50},
     "role":{"type":"string","enum":["worker","supervisor"]}
   }
 }'::jsonb,
 ARRAY['hive.html','v_worker_truth','v_worker_assignment_truth'],
 'Status starts as pending until accepted.'),

-- ─── 10. Skill exam attempt ────────────────────────────────────────────────
('skill_exam_attempt_v1', 'form', 'skillmatrix.html',
 '[
   {"name":"worker_name","type":"text","required":true,"max_len":50},
   {"name":"discipline","type":"text","required":true,"max_len":40},
   {"name":"level","type":"integer","required":true,"min":1,"max":5},
   {"name":"answers","type":"jsonb","required":true},
   {"name":"score","type":"integer","required":false,"min":0,"max":100}
 ]'::jsonb,
 'skill_exam_attempts',
 ARRAY['worker_name','discipline','level','answers','score','passed','created_at'],
 'edge',
 '{
   "type":"object",
   "required":["worker_name","discipline","level","answers"],
   "properties":{
     "worker_name":{"type":"string","minLength":1,"maxLength":50},
     "discipline":{"type":"string","minLength":1},
     "level":{"type":"integer","minimum":1,"maximum":5},
     "answers":{"type":"object"}
   }
 }'::jsonb,
 ARRAY['skillmatrix.html','v_worker_skill_truth'],
 'Pass threshold logic in edge fn; cooldown enforced server-side.'),

-- ─── 11. Community post ────────────────────────────────────────────────────
('community_post_v1', 'form', 'community.html',
 '[
   {"name":"worker_name","type":"text","required":true,"max_len":50},
   {"name":"body","type":"text","required":true,"max_len":5000},
   {"name":"is_public","type":"boolean","required":false},
   {"name":"mentions","type":"text[]","required":false}
 ]'::jsonb,
 'community_posts',
 ARRAY['worker_name','body','is_public','mentions','hive_id','created_at','edited_at','deleted_at'],
 'edge',
 '{
   "type":"object",
   "required":["worker_name","body"],
   "properties":{
     "worker_name":{"type":"string","minLength":1,"maxLength":50},
     "body":{"type":"string","minLength":1,"maxLength":5000},
     "is_public":{"type":["boolean","null"]}
   }
 }'::jsonb,
 ARRAY['community.html','public-feed.html','hive.html'],
 'Soft-delete via deleted_at. is_public flag controls cross-hive visibility.'),

-- ─── 12. Day planner schedule item ─────────────────────────────────────────
('schedule_item_v1', 'form', 'dayplanner.html',
 '[
   {"name":"worker_name","type":"text","required":true,"max_len":50},
   {"name":"date","type":"date","required":true},
   {"name":"start_time","type":"time","required":false},
   {"name":"end_time","type":"time","required":false},
   {"name":"title","type":"text","required":true,"max_len":120},
   {"name":"category","type":"enum","required":false,"values":["planning","execution","review","admin"]},
   {"name":"item_status","type":"enum","required":false,"values":["pending","in_progress","done","blocked","skipped"]},
   {"name":"notes","type":"text","required":false,"max_len":1000}
 ]'::jsonb,
 'schedule_items',
 ARRAY['worker_name','date','start_time','end_time','title','category','item_status','notes','auth_uid'],
 'client',
 '{
   "type":"object",
   "required":["worker_name","date","title"],
   "properties":{
     "worker_name":{"type":"string","minLength":1,"maxLength":50},
     "title":{"type":"string","minLength":1,"maxLength":120},
     "category":{"type":["string","null"],"enum":["planning","execution","review","admin",null]},
     "item_status":{"type":["string","null"],"enum":["pending","in_progress","done","blocked","skipped",null]}
   }
 }'::jsonb,
 ARRAY['dayplanner.html','assistant.html'],
 'Worker-scoped (not hive-scoped). Used by AI assistant context for "today schedule".'),

-- ─── 13. Asset wizard (multi-step create) ──────────────────────────────────
('asset_wizard_v1', 'form', 'asset-hub.html',
 '[
   {"name":"tag","type":"text","required":true,"max_len":50},
   {"name":"name","type":"text","required":true,"max_len":120},
   {"name":"iso_class","type":"text","required":false,"max_len":40},
   {"name":"criticality","type":"enum","required":true,"values":["Critical","High","Medium","Low"]},
   {"name":"location","type":"text","required":false,"max_len":120},
   {"name":"manufacturer","type":"text","required":false,"max_len":80},
   {"name":"model","type":"text","required":false,"max_len":80},
   {"name":"serial_no","type":"text","required":false,"max_len":80},
   {"name":"install_date","type":"date","required":false},
   {"name":"parent_id","type":"uuid","required":false},
   {"name":"photo","type":"text","required":false}
 ]'::jsonb,
 'asset_nodes',
 ARRAY['tag','name','iso_class','criticality','location','manufacturer','model','serial_no','install_date','parent_id','hive_id','status'],
 'edge',
 '{
   "type":"object",
   "required":["tag","name","criticality"],
   "properties":{
     "tag":{"type":"string","minLength":1,"maxLength":50},
     "name":{"type":"string","minLength":1,"maxLength":120},
     "criticality":{"type":"string","enum":["Critical","High","Medium","Low"]},
     "parent_id":{"type":["string","null"]}
   }
 }'::jsonb,
 ARRAY['asset-hub.html','logbook.html','inventory.html','pm-scheduler.html','v_asset_truth'],
 'Status starts as pending; supervisor approves to flip to approved. ISO 14224 iso_class taxonomy enforced separately.'),

-- ─── 14. Voice intent for report dispatch ──────────────────────────────────
('voice_report_intent_v1', 'voice', 'voice-report-intent',
 '[
   {"name":"audio_blob","type":"binary","required":true,"max_mb":10},
   {"name":"worker_name","type":"text","required":true,"max_len":50},
   {"name":"transcript","type":"text","required":true,"derived_by":"whisper"},
   {"name":"intent","type":"enum","required":true,"derived_by":"groq","values":["send_now","schedule","add_recipient","cancel","unknown"]},
   {"name":"recipients","type":"text[]","required":false,"derived_by":"groq"},
   {"name":"schedule_iso","type":"datetime","required":false,"derived_by":"groq"}
 ]'::jsonb,
 'automation_log',
 ARRAY['job_name','hive_id','status','detail'],
 'edge',
 '{
   "type":"object",
   "required":["worker_name","transcript","intent"],
   "properties":{
     "worker_name":{"type":"string","minLength":1,"maxLength":50},
     "transcript":{"type":"string","minLength":1},
     "intent":{"type":"string","enum":["send_now","schedule","add_recipient","cancel","unknown"]},
     "recipients":{"type":["array","null"]}
   }
 }'::jsonb,
 ARRAY['report-sender.html','send-report-email'],
 'Triggers downstream send-report-email or scheduled-agents jobs. target_table=automation_log is the audit trail; actual dispatch writes to ai_reports + email queue.'),

-- ─── 15. AI assistant chat input ───────────────────────────────────────────
('ai_chat_input_v1', 'chat', 'assistant.html',
 '[
   {"name":"question","type":"text","required":true,"max_len":2000},
   {"name":"worker_name","type":"text","required":false,"max_len":50},
   {"name":"hive_id","type":"uuid","required":false},
   {"name":"context_page","type":"text","required":false,"max_len":40},
   {"name":"history_size","type":"integer","required":false,"min":0,"max":50}
 ]'::jsonb,
 'agent_memory',
 ARRAY['worker_name','hive_id','agent','question','answer','created_at'],
 'edge',
 '{
   "type":"object",
   "required":["question"],
   "properties":{
     "question":{"type":"string","minLength":1,"maxLength":2000},
     "worker_name":{"type":["string","null"],"maxLength":50},
     "context_page":{"type":["string","null"]}
   }
 }'::jsonb,
 ARRAY['assistant.html','ai-orchestrator','ai-gateway'],
 'Floating-AI cross-page conversation. agent_memory append-only audit trail; ai_cost_log captures token usage separately.')

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
