-- ─────────────────────────────────────────────────────────────────────────────
-- fault_knowledge.logbook_id gets the foreign key it never had.
--
-- FOUND BY THE LG8 MEASUREMENT (2026-07-28, LOGBOOK_DEEPWALK_EXPANSION_ROADMAP):
-- fault_knowledge mirrors corrective logbook entries into the RAG corpus via logbook_id, but the
-- table's ONLY foreign key was hive_id. logbook_id was a bare text column pointing at nothing in
-- particular, so deleting a logbook entry left its knowledge row behind — still embedded, still
-- retrievable, still citing an entry that no longer exists. Measured 21 dangling rows against the
-- "529/529 valid" reading taken on 2026-07-12.
--
-- ON DELETE CASCADE, because the knowledge row is DERIVED, not independently authored: embed-entry
-- writes it from the entry. If the entry is retracted, the derived knowledge is unfounded, and a
-- retrieval that cites a deleted entry is worse than no retrieval at all. This is the same
-- provenance rule the platform already applies to trust signals: a claim needs a living producer.
--
-- NOT VALID is deliberate, and it is the honest part of this migration. It enforces the constraint
-- on everything from here forward without retroactively judging rows that predate it. The cleanup
-- below removes the 20 dangling rows that are unambiguously test residue (K2-PROBE-* and the two
-- D2 helper/refix probes left by earlier sessions' walks — the "live MCP writes pollute the test
-- DB" class). It deliberately does NOT touch the one remaining dangling row, which is real content:
--
--     logbook_id 'log-3f8360c61f28' — WLD-001, Pablo Aguilar, "Output current unstable, weld
--     quality poor" / "Mechanical Damage" / "Replaced 4 carbon brushes, cleaned commutator" /
--     "Carbon brushes 80% worn"
--
-- That entry was deleted during this arc's LB7 walk to prove the silent-loss defect, and this
-- mirror is the surviving record of it. Whether to delete the knowledge row or restore the entry
-- from it is a data decision for a human, not something a migration should make quietly. Run
-- `ALTER TABLE fault_knowledge VALIDATE CONSTRAINT fault_knowledge_logbook_id_fkey;` once it is
-- resolved, and the constraint becomes fully verified.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Remove dangling rows that are unambiguously probe residue from earlier walks.
DELETE FROM fault_knowledge fk
WHERE  fk.logbook_id IS NOT NULL
  AND  NOT EXISTS (SELECT 1 FROM logbook l WHERE l.id = fk.logbook_id)
  AND  (fk.problem LIKE 'K2-PROBE-%' OR fk.problem IN ('D2 helper probe', 'D2 refix probe'));

-- 2. The constraint itself. NOT VALID: enforced going forward, existing rows left for a human.
ALTER TABLE fault_knowledge
  ADD CONSTRAINT fault_knowledge_logbook_id_fkey
  FOREIGN KEY (logbook_id) REFERENCES logbook(id) ON DELETE CASCADE
  NOT VALID;
