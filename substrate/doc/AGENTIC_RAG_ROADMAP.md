---
name: doc-AGENTIC_RAG_ROADMAP
type: doc
source: file:AGENTIC_RAG_ROADMAP.md
source_sha: 99e90266633d10b8
last_verified: 2026-07-13
supersedes: null
---
## doc · AGENTIC_RAG_ROADMAP

**Status:** Spec only — no code written. Awaiting per-phase build approval.

**Sections:** Agentic RAG Roadmap · 1. Why this exists · 2. What WorkHive already has (do not rebuild) · 2.5 Allowed Models (HARD CONSTRAINT — read before designing anything) · The complete allowed chain (ordered, fallback is automatic) · Banned (do not add to the chain, do not reference in any spec) · Task → primary model recommendation (fallback handled by `_shared/ai-chain.ts`) · Cost framing rule · 3. Mapping the 7 data architectures (from the user's reference image) to WorkHive · 4. The core architectural principle · 5. The 8 phases · Phase 1 — Agentic RAG Loop (Router → Retriever → Grader → Generator → Checker) · Phase 2 — Hierarchical Period Summaries · Phase 3 — Temporal Decomposition Orchestrator (Python, parameterized prompts) · Phase 4 — Tiered Model Router (right model per task) · Phase 5 — Data Fabric Normalizer (unified ingest layer) · Phase 6 — Cold Lakehouse Archive (Parquet + DuckDB for >18-month data) · Phase 7 — Agent Episodic Memory (long-term across sessions) · Phase 8 — Observability + Cost Governance · 6. Sequencing diagram · 7. Cross-phase invariants (apply to every phase) · 8. Open decisions (need your call before any phase ships) · 9. What this roadmap does NOT propose · 10. Approval gates

(Deep source: `file:AGENTIC_RAG_ROADMAP.md` — retrieve this TOC to know WHICH section to read.)
