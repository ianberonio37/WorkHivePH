-- Register the 4 new agentic-RAG infrastructure tables in canonical_sources
-- so validate_canonical_anchor.py's fuel-anchor check passes. These tables
-- are infrastructure (audit log, rollup cache, episodic memory store,
-- unified event ingest) — not user-facing truth views. They register with
-- source_kind='table' (not 'view') because they're the data substrate,
-- not a canonical KPI source.
--
-- Phase 1-7 of AGENTIC_RAG_ROADMAP.md. Added 2026-05-21 by the Mega Gate
-- paydown — without this registration, every CREATE TABLE migration that
-- doesn't already register itself fails L1 fuel anchor.

INSERT INTO public.canonical_sources (
  domain, source_kind, source_name, owner_skill, freshness, description, contract, notes
) VALUES
  ('agentic_rag_traces', 'table', 'agentic_rag_traces', 'ai-engineer', 'realtime',
   'Per-run agentic-rag-loop audit log. Captures route, stages, retrievals, grader/checker outcomes, retries, citation count, latency. No cost_usd column (free-tier chain by constraint).',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('hive_id','worker_name'),
     'derived_columns', jsonb_build_array('grader_passed','checker_passed','citation_count','latency_ms')
   ),
   'AGENTIC_RAG_ROADMAP.md Phase 1. Append-only audit log; not a user-facing truth source.'),
  ('canonical_period_summaries', 'table', 'canonical_period_summaries', 'ai-engineer', 'hourly',
   'Hierarchical Daily/Weekly/Monthly/Quarterly/Yearly digests per hive per asset. Retriever pulls the appropriate level for the query horizon instead of dumping raw rows into the LLM context.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('hive_id','asset_tag','level','period_end'),
     'derived_columns', jsonb_build_array('summary_text','summary_json','embedding')
   ),
   'AGENTIC_RAG_ROADMAP.md Phase 2. Infrastructure rollup cache.'),
  ('agent_episodic_memory', 'table', 'agent_episodic_memory', 'ai-engineer', 'on-demand',
   'Durable agent memory facts extracted at end of successful agentic-rag-loop runs. Four kinds: factual / procedural / episodic / semantic. Loaded as system-prompt context at start of each run.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('hive_id','worker_name','kind'),
     'derived_columns', jsonb_build_array('importance','use_count','last_used_at')
   ),
   'AGENTIC_RAG_ROADMAP.md Phase 7. LRU eviction by importance x log(1+use_count). Caps: 200/worker, 1000/hive.'),
  ('unified_events', 'table', 'unified_events', 'integration-engineer', 'realtime',
   'Canonical event ingest table that normalizes SAP / Maximo / OPC-UA / MQTT / voice / photo OCR / manual log / sensor / email into one shape so the Retriever queries across all sources in a single hive-scoped pass.',
   jsonb_build_object(
     'key',             jsonb_build_array('id'),
     'hive_scoped',     true,
     'soft_delete',     false,
     'bridge_columns',  jsonb_build_array('hive_id','asset_tag','source','source_id','occurred_at'),
     'derived_columns', jsonb_build_array('payload_text','event_type','hash','embedding')
   ),
   'AGENTIC_RAG_ROADMAP.md Phase 5. Idempotent on (source, source_id) via hash column.')
ON CONFLICT (domain) DO UPDATE
  SET source_kind = EXCLUDED.source_kind, source_name = EXCLUDED.source_name,
      owner_skill = EXCLUDED.owner_skill, freshness = EXCLUDED.freshness,
      description = EXCLUDED.description, contract = EXCLUDED.contract,
      notes       = EXCLUDED.notes;
