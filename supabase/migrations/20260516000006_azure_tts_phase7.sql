-- Phase 7: Azure Speech Services TTS

create table if not exists tts_cache (
  id bigserial primary key,
  text_hash text unique not null,
  text_content text not null,
  persona text not null,  -- james, rosa
  audio_data bytea,
  audio_format text default 'mp3',
  duration_ms int,
  created_at timestamptz default now(),
  expires_at timestamptz
);

create index if not exists idx_tts_cache_hash on tts_cache(text_hash);

-- TTS quality metrics
create table if not exists tts_quality_log (
  id bigserial primary key,
  worker_id uuid,
  hive_id uuid,
  persona text,
  latency_ms int,
  error_message text,
  created_at timestamptz default now()
);

create index if not exists idx_tts_quality_hive on tts_quality_log(hive_id, created_at desc);
