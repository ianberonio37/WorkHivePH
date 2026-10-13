-- ★PROJECT KNOWLEDGE COULD NOT BE SAVED AT ALL (2026-10-12, UFAI edge walk W4713).
--
-- embed-entry stamps every knowledge row with the provider that embedded it (row.embedding_model - "a label nobody
-- writes is a label nobody can trust"). fault_knowledge, skill_knowledge and pm_knowledge carry that column;
-- project_knowledge never got it, so every project embedding failed with "Could not find the 'embedding_model'
-- column of 'project_knowledge' in the schema cache" - a 500 the page never shows (the embed is fire-and-forget), and
-- the project side of the RAG index stopped growing from the day the stamp landed. The column the other three have.

alter table public.project_knowledge add column if not exists embedding_model text;

notify pgrst, 'reload schema';
