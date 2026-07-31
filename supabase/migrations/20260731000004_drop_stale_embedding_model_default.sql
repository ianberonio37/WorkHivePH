-- 20260731000004_drop_stale_embedding_model_default.sql
--
-- The `embedding_model` column on the knowledge tables defaults to 'nomic-embed-text-v1_5' — a model that is
-- NOT in the embedding chain's provider roster and therefore cannot have produced any vector in this
-- database. `embed-entry` does not set the column, so EVERY row it writes is LABELLED nomic no matter which
-- provider actually answered.
--
-- That default cost real time today. The space-integrity gate correctly reported fault_knowledge as split
-- (717 rows "nomic" vs 534 "bge-local"), and I read the label as the truth: diagnosed a silent provider
-- failover, chased a container-DNS address, added a strict no-failover ingest mode, and re-embedded ~1,000
-- rows. The vectors were almost certainly bge-local all along. The GATE was right that something was wrong;
-- my conclusion about WHAT was wrong came from trusting a column whose value nothing was writing
-- ([[feedback_check_the_premise_before_building_the_pattern]] — again, and this time against a DEFAULT).
--
-- A column default is a claim nobody is making. Dropping it means an unlabelled row reads NULL, which the
-- gate already treats as a failure ("a NULL embedding_model makes the space unprovable") — an honest unknown
-- instead of a confident lie. The writer must then state the provider it actually used, which is what
-- generateEmbeddingTagged() returns and what the next slice wires in.
--
-- The address fix and the strict ingest mode STAY: both are correct on their own merits (an unreachable
-- embedder really would fail over, and an ingest really should not). They were just not today's cause.

BEGIN;

ALTER TABLE public.fault_knowledge ALTER COLUMN embedding_model DROP DEFAULT;
ALTER TABLE public.pm_knowledge    ALTER COLUMN embedding_model DROP DEFAULT;
ALTER TABLE public.skill_knowledge ALTER COLUMN embedding_model DROP DEFAULT;

COMMIT;
