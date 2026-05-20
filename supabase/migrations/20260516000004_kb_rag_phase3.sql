-- Phase 3: Semantic RAG & Knowledge Base Integration
-- PDF ingestion, chunking, semantic search, reranking

create table if not exists kb_documents (
  id bigserial primary key,
  hive_id uuid not null,
  uploaded_by uuid not null,
  title text not null,
  file_path text,  -- gs://bucket/path or local reference
  content_type text,  -- application/pdf, text/markdown, etc.
  total_chunks int default 0,
  embedding_status text default 'pending',  -- pending, in_progress, complete, failed
  file_size_bytes bigint,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create index if not exists idx_kb_documents_hive on kb_documents(hive_id, created_at desc);
create index if not exists idx_kb_documents_status on kb_documents(embedding_status);

-- Knowledge base chunks (vectors for semantic search)
create table if not exists kb_chunks (
  id bigserial primary key,
  doc_id bigint not null references kb_documents(id) on delete cascade,
  chunk_num int not null,
  text text not null,
  embedding vector(384),  -- 384-dim: Voyage (512 truncated) or Jina (native)
  relevance_score real,  -- cached from last rerank
  created_at timestamptz default now()
);

create index if not exists idx_kb_chunks_doc on kb_chunks(doc_id, chunk_num);
create index if not exists idx_kb_chunks_embedding on kb_chunks using ivfflat (embedding vector_cosine_ops);

-- RLS policies
-- 2026-05-20 fix: blueprint referenced non-existent `worker_hives`;
-- platform uses `hive_members` (hive_id, auth_uid, status='active').
alter table kb_documents enable row level security;
drop policy if exists "kb_documents_hive_access" on kb_documents;
create policy "kb_documents_hive_access" on kb_documents
  for select
  using (
    exists (
      select 1 from public.hive_members hm
      where hm.hive_id = kb_documents.hive_id
        and hm.auth_uid = auth.uid()
        and hm.status = 'active'
    )
  );

alter table kb_chunks enable row level security;
drop policy if exists "kb_chunks_hive_access" on kb_chunks;
create policy "kb_chunks_hive_access" on kb_chunks
  for select
  using (
    exists (
      select 1 from public.kb_documents kd
      join public.hive_members hm on hm.hive_id = kd.hive_id
      where kd.id = kb_chunks.doc_id
        and hm.auth_uid = auth.uid()
        and hm.status = 'active'
    )
  );

-- GRANTs required for anon/authenticated roles
grant select, insert, update, delete on kb_documents to anon, authenticated;
grant select, insert, update, delete on kb_chunks to anon, authenticated;

-- View: kb freshness
create or replace view v_kb_freshness_truth as
select
  doc_id,
  max(created_at) as last_accessed,
  count(*) as chunk_count,
  bool_and(embedding is not null) as embedding_complete
from kb_chunks
group by doc_id;

-- RPC: semantic search (top N chunks by cosine similarity)
create or replace function semantic_search_kb(
  p_hive_id uuid,
  p_query_embedding vector,
  p_similarity_threshold real default 0.7,
  p_limit int default 5
)
returns table (
  chunk_id bigint,
  doc_id bigint,
  doc_title text,
  chunk_text text,
  similarity_score real
) as $$
begin
  return query
  select
    kc.id,
    kc.doc_id,
    kd.title,
    kc.text,
    (kc.embedding <=> p_query_embedding) as sim
  from kb_chunks kc
  join kb_documents kd on kc.doc_id = kd.id
  where kd.hive_id = p_hive_id
    and kc.embedding is not null
    and (kc.embedding <=> p_query_embedding) <= (1 - p_similarity_threshold)
  order by kc.embedding <=> p_query_embedding
  limit p_limit;
end;
$$ language plpgsql security definer set search_path = public;

-- RPC: rerank chunks by relevance (LLM evaluates top 5 semantically similar)
create or replace function rerank_kb_chunks(
  p_chunk_ids bigint[],
  p_query text
)
returns table (
  chunk_id bigint,
  rerank_score real
) as $$
declare
  chunk_id bigint;
begin
  -- Placeholder: actual reranking via LLM happens in edge function
  -- For now, return chunks with incremental scores (caller will invoke LLM)
  foreach chunk_id in array p_chunk_ids
  loop
    return query select chunk_id, 0.95::real;
  end loop;
end;
$$ language plpgsql security definer set search_path = public;
