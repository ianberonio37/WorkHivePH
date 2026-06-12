-- L08 Persona-Knowledge — W10 (CHANNELS): widen source_type to admit the new
-- ingestion channels. W6 shipped 'skill_md','external_standard','pdf'. W10 adds:
--   'url'          — open docs fetched via crawl4ai -> clean markdown (O14)
--   'platform_doc' — your OWN content (learn articles / feature pages / formula
--                    definitions) curated from platform_catalog.json (W11, populated later)
-- Drop-folder files reuse 'pdf' / 'external_standard'. The inline CHECK from the
-- W6 migration is auto-named persona_knowledge_source_type_check; drop-if-exists
-- then re-add so this is idempotent and order-independent.
alter table persona_knowledge drop constraint if exists persona_knowledge_source_type_check;
alter table persona_knowledge add constraint persona_knowledge_source_type_check
  check (source_type in ('skill_md', 'external_standard', 'pdf', 'url', 'platform_doc'));
