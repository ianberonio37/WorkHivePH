-- Voice Companion Tables (simplified, no dependencies)

CREATE TABLE IF NOT EXISTS public.kb_documents (
    id bigserial primary key,
    hive_id uuid not null,
    title text not null,
    content_type text,
    embedding_status text default 'pending',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_kb_documents_hive ON public.kb_documents(hive_id);

CREATE TABLE IF NOT EXISTS public.kb_chunks (
    id bigserial primary key,
    doc_id bigint not null,
    chunk_num int,
    text text not null,
    embedding vector(384),
    created_at timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_kb_chunks_doc ON public.kb_chunks(doc_id);

CREATE TABLE IF NOT EXISTS public.anomaly_alerts (
    id bigserial primary key,
    hive_id uuid not null,
    asset_id uuid,
    alert_type text,
    severity text,
    metric_name text,
    metric_value numeric,
    metric_threshold numeric,
    deviation_percent numeric,
    description text,
    action_suggested text,
    detected_at timestamptz default now(),
    suppressed_until timestamptz,
    acknowledged_at timestamptz,
    created_at timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_alerts_hive ON public.anomaly_alerts(hive_id);

CREATE TABLE IF NOT EXISTS public.conversation_analytics (
    id bigserial primary key,
    session_id text,
    turn_num int,
    worker_id uuid,
    hive_id uuid,
    question_category text,
    answer_quality_rating int,
    confidence_score numeric,
    response_time_ms int,
    created_at timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_conversation_analytics_session ON public.conversation_analytics(session_id);
