-- L08 Persona-Knowledge layer (companion wiring roadmap W6, 2026-06-12).
-- A per-persona curated DOMAIN knowledge base: SKILL.md sources + free external
-- authoritative standards, contextually chunked (Anthropic Contextual Retrieval —
-- a one-line context header is prepended BEFORE embedding) and persona-SCOPED so
-- Hezekiah (technical) and Zaniah (strategic) retrieve different corpora, both
-- sharing the 'shared' scope. 384-dim to match the platform's other pgvector KBs
-- (fault_knowledge / pm_knowledge / skill embeddings). Distinct from skill_knowledge
-- (that is a WORKER-SKILL/competency table, not a document store) — a dedicated
-- table keeps the scope isolation clean (the O10 security wire) and avoids
-- overloading an unrelated domain.
create extension if not exists vector;

create table if not exists persona_knowledge (
  id             uuid primary key default gen_random_uuid(),
  persona_scope  text not null check (persona_scope in ('technical', 'strategic', 'shared')),
  source         text not null,             -- e.g. 'maintenance-expert/SKILL.md' or 'ISO-14224'
  source_type    text not null default 'skill_md' check (source_type in ('skill_md', 'external_standard', 'pdf')),
  section        text,                      -- the source heading the chunk came from
  chunk_index    int  not null,
  context_header text,                      -- Anthropic Contextual Retrieval header (prepended before embedding)
  content        text not null,             -- the chunk body
  content_hash   text not null,             -- sha256(content) for idempotent refresh / supersede
  embedding      vector(384),               -- 384-dim (Jina free / MiniLM fallback), nullable = best-effort degrade
  embedding_model text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (source, chunk_index)              -- idempotent upsert key (O5)
);

create index if not exists persona_knowledge_scope_idx on persona_knowledge (persona_scope);
create index if not exists persona_knowledge_source_idx on persona_knowledge (source);

-- pgvector ANN index for persona-scoped retrieval (cosine). ivfflat needs rows to
-- train; created here, populated by the ingest tool.
do $$
begin
  if not exists (select 1 from pg_class where relname = 'persona_knowledge_embedding_idx') then
    begin
      create index persona_knowledge_embedding_idx on persona_knowledge
        using ivfflat (embedding vector_cosine_ops) with (lists = 10);
    exception when others then
      raise notice 'persona_knowledge ivfflat index deferred (populate then re-create): %', sqlerrm;
    end;
  end if;
end $$;

-- Persona-scoped retrieval RPC (mirrors match_procedural_memories). Returns the
-- top-k chunks for the caller's scope set — technical+shared for Hezekiah,
-- strategic+shared for Zaniah — above a cosine-similarity threshold. SECURITY: the
-- scope filter is enforced server-side so a strategist can NEVER receive a
-- technical-scope chunk (the O10 isolation wire).
create or replace function match_persona_knowledge(
  query_embedding vector(384),
  scopes          text[],
  match_count     int default 4,
  min_similarity  float default 0.25
)
returns table (
  id            uuid,
  persona_scope text,
  source        text,
  section       text,
  content       text,
  similarity    float
)
language sql stable
as $$
  select pk.id, pk.persona_scope, pk.source, pk.section, pk.content,
         1 - (pk.embedding <=> query_embedding) as similarity
  from persona_knowledge pk
  where pk.embedding is not null
    and pk.persona_scope = any(scopes)
    and 1 - (pk.embedding <=> query_embedding) >= min_similarity
  order by pk.embedding <=> query_embedding
  limit match_count;
$$;
