-- Phase 6: Offline Resilience & Graceful Degradation

-- Offline snapshot cache (IndexedDB-backed)
create table if not exists offline_snapshot_cache (
  id bigserial primary key,
  worker_id uuid not null,
  hive_id uuid not null,
  snapshot_data jsonb not null,
  snapshot_hash text,  -- detect staleness
  cached_at timestamptz default now(),
  expires_at timestamptz
);

create index if not exists idx_offline_cache_worker_hive on offline_snapshot_cache(worker_id, hive_id, cached_at desc);

-- Response queue for offline queries
create table if not exists voice_response_queue (
  id bigserial primary key,
  worker_id uuid not null,
  session_id text,
  transcript text not null,
  response text,
  status text default 'queued',  -- queued, sent, failed
  created_at timestamptz default now(),
  sent_at timestamptz
);

create index if not exists idx_response_queue_worker on voice_response_queue(worker_id, status, created_at);

-- Fallback model metadata (lightweight ONNX FAQ model)
create table if not exists fallback_model_faq (
  id bigserial primary key,
  question_embedding vector(384),  -- smaller model for device inference
  answer text not null,
  category text,  -- mtbf, mttr, pm, inventory, etc.
  accuracy_score real default 0.6
);

create index if not exists idx_faq_embedding on fallback_model_faq using ivfflat (question_embedding vector_cosine_ops);
