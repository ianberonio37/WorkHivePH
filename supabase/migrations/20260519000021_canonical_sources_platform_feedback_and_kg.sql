-- ============================================================
-- Canonical Sources: register platform_feedback / votes / KG facts (2026-05-19)
-- ============================================================
-- The 2026-05-19 batch landed three new tables that need canonical_sources
-- entries so the fuel-layer anchor gate passes:
--   - platform_feedback           (universal user feedback inbox)
--   - platform_feedback_votes     (upvotes / downvotes on feedback)
--   - platform_knowledge_graph_facts (platform-wide KG, hive-agnostic)
--
-- Without these registrations the canonical-anchor gate counts them as
-- un-anchored fuel and the Mega Gate fails.
-- ============================================================

INSERT INTO public.canonical_sources
  (domain, source_kind, source_name, owner_skill, freshness, description, contract)
VALUES
  ('platform_feedback_inbox',
   'table', 'platform_feedback', 'community', 'realtime',
   'Universal feedback inbox: reviews, bug reports, feature ideas, questions, praise. Polymorphic `kind` discriminator + optional rating + triage workflow (new → triaged → in_progress → resolved). Anonymous submissions allowed via contact_email.',
   '{"key":["id"],"hive_scoped":false,"kinds":["review","bug","feature","question","praise","other"],"status_values":["new","triaged","in_progress","resolved","wont_fix","duplicate"]}'::jsonb),

  ('platform_feedback_vote',
   'table', 'platform_feedback_votes', 'community', 'realtime',
   'Upvote / downvote ledger on platform_feedback rows. One row per (feedback_id, worker_name) — UNIQUE constraint enforces vote-once semantics.',
   '{"key":["id"],"hive_scoped":false,"unique_on":["feedback_id","worker_name"],"vote_values":["up","down"]}'::jsonb),

  ('platform_knowledge_graph',
   'table', 'platform_knowledge_graph_facts', 'ai-engineer', 'realtime',
   'Platform-wide knowledge graph facts (hive-agnostic, like industry_standards). Powers semantic_search_platform_kg_facts RPC used by ai-orchestrator / assistant for industry-grade answers.',
   '{"key":["id"],"hive_scoped":false,"embedding_dim":384,"search_rpc":"semantic_search_platform_kg_facts"}'::jsonb)
-- 2026-05-20 fix: canonical_sources PK is `domain`, not `source_name`
ON CONFLICT (domain) DO NOTHING;
