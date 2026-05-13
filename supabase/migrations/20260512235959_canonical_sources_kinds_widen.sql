-- Widen canonical_sources.source_kind CHECK to accept 'column'.
--
-- Discovered during the 2026-05-13 walkthrough: Phase 3+ migrations register
-- column-shaped sources (hives.intent, hives.federated_benchmark_opted_in)
-- but the baseline CHECK only allowed view/table/rpc. The intent capture
-- modal save fired 400s on a fresh local stack because the Phase 3
-- migration could not apply its INSERTs.
--
-- This is a forward-only constraint widen — existing rows stay valid; the
-- new kind value 'column' becomes acceptable for future inserts.

BEGIN;

ALTER TABLE public.canonical_sources
  DROP CONSTRAINT IF EXISTS canonical_sources_source_kind_check;

ALTER TABLE public.canonical_sources
  ADD CONSTRAINT canonical_sources_source_kind_check
  CHECK (source_kind = ANY (ARRAY['view', 'table', 'rpc', 'column']));

COMMIT;
