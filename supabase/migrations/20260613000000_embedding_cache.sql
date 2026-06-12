-- Query-embedding cache (2026-06-13) — the "many users" lever. Embedding APIs are
-- rate-limited and every conversational turn embeds the query (~2 embeds/turn). At
-- scale, many users ask SIMILAR questions ("what is OEE", "who is Hezekiah"). Caching
-- (normalized query, model) -> embedding makes the embed-API load scale with the number
-- of UNIQUE questions, not total questions: a repeat is a DB read, not an API call.
--
-- Keyed by (query_hash, model) so a model switch never returns a stale-space vector.
-- Best-effort: the edge degrades to a live embed if the cache is unavailable.
create extension if not exists vector;

create table if not exists embedding_cache (
  query_hash  text        not null,          -- sha256(normalized query text)
  model       text        not null,          -- the embedding model/provider the vector is in
  embedding   vector(384) not null,
  hits        int         not null default 1,
  created_at  timestamptz not null default now(),
  last_used   timestamptz not null default now(),
  primary key (query_hash, model)
);

-- prune helper: drop cold entries (call from a cron if the cache grows large).
create index if not exists embedding_cache_last_used_idx on embedding_cache (last_used);
