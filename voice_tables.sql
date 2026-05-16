CREATE TABLE IF NOT EXISTS public.kb_documents (id bigserial primary key, hive_id uuid, title text, content_type text, embedding_status text default 'pending', created_at timestamptz default now());
CREATE TABLE IF NOT EXISTS public.kb_chunks (id bigserial primary key, doc_id bigint, chunk_num int, text text, embedding vector(384), created_at timestamptz default now());
CREATE TABLE IF NOT EXISTS public.anomaly_alerts (id bigserial primary key, hive_id uuid, alert_type text, severity text, description text, action_suggested text, detected_at timestamptz default now(), created_at timestamptz default now());
CREATE TABLE IF NOT EXISTS public.conversation_analytics (id bigserial primary key, session_id text, hive_id uuid, created_at timestamptz default now());
