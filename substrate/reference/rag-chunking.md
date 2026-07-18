---
name: reference-rag-chunking
type: reference
source: firecrawl.dev/blog/best-chunking-strategies-rag + databricks + clinical study PMC12649634
source_sha: review-date-anchored
last_verified: 2026-07-13
supersedes: null
---

## reference · RAG chunking strategy (how to chunk the substrate)

Distilled durable rules for chunk granularity (governs `tools/build_substrate.py`).

- **Semantic / topic-boundary chunks beat fixed-size.** A clinical study measured 87% accuracy for
  adaptive topic-boundary chunking vs 13% for fixed-size. Chunk by MEANING (one page's writes, one
  table's RLS, one RPC's guard), never by an arbitrary N-token window.
- **Document-aware chunking of structured content (Markdown/HTML/technical docs) has the highest
  effectiveness-to-cost ratio.** WorkHive's pages/edge-fns/migrations are structured — parse them
  structurally, don't blob them.
- **Metadata prefix ("prefix-fusion") on every chunk lifts retrieval most** (highest MRR/NDCG in the
  benchmark) — a uniform header (name/type/source) so retrieval carries context. The PKS frontmatter
  does this.
- **Don't over-chunk.** For short, single-purpose facts, document-level (one chunk) is best.
  Target most chunks 200-1,200 tokens; a task retrieves 3-5 (~2-5K) vs a 500K file read.
- **Semantic embedding-boundary chunking is only marginally better than recursive splitting (e.g.
  91% vs 88% recall) at ~10x the processing cost** — not worth it unless recall is the bottleneck.
  For a code/platform substrate, deterministic structural parsing (free, exact) wins over embeddings.
- **Parent-context / late chunking** helps when a chunk needs long-range document signal; the PKS
  approximates this with the metadata prefix + `[[links]]` to sibling chunks.

Sources: Firecrawl (best chunking strategies), Databricks chunking guide, clinical RAG chunking study
(PMC), Atlan (chunking trade-offs). See [[reference-context-engineering]].
