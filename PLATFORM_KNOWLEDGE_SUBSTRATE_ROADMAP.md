# Platform Knowledge Substrate (PKS) Roadmap

**Mandate (Ian, 2026-07-13):** the Workflow fan-out is not sustainable — it burns hundreds of
thousands of tokens re-deriving the platform from scratch every run. Instead: **chunk/tokenize the
platform + distilled reputable sources ONCE into durable files Memento can reach, keep them from
regressing with cheap deterministic gates, and RETRIEVE the relevant slice instead of re-scanning.**
This doc is the plan-of-record. No code ships until Ian reviews it.

> One-line thesis: **re-derivation → retrieval.** Fan-out is O(pages × agents) *every run, forever*.
> The substrate is O(pages) *once* + O(**changed files**) to maintain + ~0 to retrieve.

---

## 0 · The problem — fan-out re-derives everything, every run

Workflow spawns one *isolated Claude instance per `agent()`*, each with its own full context window.
A 30-page bug-hunt pays, per agent: system prompt (~8K) + tool schemas (~12K) + instructions/catalog
(~3K) + the file it reads (logbook ~40K, engineering-design ~500K) + psql + reasoning. **~20K of
cold-start tax BEFORE any work, ×30 = ~600K just to boot**, then ×(30-60) verifiers again. Our first
run reported **502,680 subagent tokens and mostly errored**; a full run is 1-3M tokens.

Three structural leaks: (1) **zero shared memory** — every agent re-reads the same RLS policies and
re-derives the same facts; (2) **cold-start tax ×N**; (3) **brute-force exhaustiveness** — it
re-discovers the whole platform from scratch *every* run, so on an evolving platform the cost is
O(pages × agents) forever.

**External validation.** Augment's Context Engine "solved tasks at effectively the same rate as Claude
Code while using materially fewer tokens, by sending only the slice the task touches rather than
replaying broad file searches." Agents "perform *worse* with a 100K-token codebase summary than with a
5K-token targeted retrieval on the same task." The winning discipline is context engineering: "the
agent that picks the right retrieval strategy for each sub-problem outperforms the one that defaults to
one paradigm for everything." (sources §9)

---

## 1 · Thesis — chunk-once, gate-fresh, retrieve-many

1. **Chunk-once** — build a durable index of platform facts + distilled sources ONE time.
2. **Gate-fresh** — each chunk is anchored to its source by a hash; a deterministic gate re-checks it
   every run and flags only the STALE ones, so maintenance is O(changed-files), not O(all-files).
3. **Retrieve-many** — any task pulls the 3-5 relevant chunks (Memento) instead of re-scanning; the
   Agent (me) reasons over the retrieved slice.
4. **Fan-out is demoted, not banned** — it stays the deliberate tool for genuinely novel one-shot
   breadth or adversarial-verify panels (§5), approved case-by-case, never the default.

---

## 2 · Architecture — four layers

### L1 · The chunks (what + granularity)
Chunk by **semantic unit, not token window**, with a **metadata prefix** on each chunk. Research is
decisive: topic-boundary chunking hit 87% vs 13% for fixed-size; document-aware chunking of structured
content (Markdown/HTML/technical docs) has the highest effectiveness-to-cost ratio; "naive chunking
*with prefix-fusion*" scored the highest MRR (§9). One chunk = one **job-sized fact**:
- a page's **write-affordances** (what it writes, to which table, via which client call)
- a table's **RLS posture** (policies + guard triggers, per the security sweeps)
- an **RPC** signature + membership guard + EXECUTE grant
- a **KPI's** canonical derivation (one metric = one official formula)
- a **reputable source's** distilled rules (L4)

**Do NOT chunk** short single-purpose facts — "for short, single-purpose documents, document-level
chunking is best." Over-chunking loses meaning and inflates the index.

### L2 · Freshness gates (the anti-regression Ian asked for) — MAKE-OR-BREAK
Treat the substrate **as code**: "code goes through review/CI/merge gates; docs go through nothing."
Each chunk's frontmatter carries `source: <file>` + `source_sha: <hash of the distilled slice>`. A new
gate `tools/validate_substrate_freshness.py` (registered in `run_platform_checks`, skip_if_fast=False —
it is pure-static + fast) recomputes the hash every run: **mismatch = STALE → re-chunk just that unit.**
This is Drift-Link's mechanism ("anchors markdown specs to source code; when the anchored code changes,
drift check catches it in CI"). Optional 0-100 freshness score from last-verified + source-commit
recency + broken-link check (§9). The gate NEVER silently passes a stale chunk — a STALE chunk fails CI
exactly like a code regression.

### L3 · Retrieval (already exists — Memento)
Chunks are `.md` → Memento already indexes, semantic-ranks, git-SHA-anchors, and honors `supersedes:`
for contradiction handling (an old fact can't co-surface next to its reversal). For heavier per-task
injection, the knowledge-manager skill already **designed + paused** `project_memento_local_memory_cache`
— a local SQLite FTS5+TF-IDF layer that injects `<2.5K-token` prompt-matched chunks instead of the whole
index. That is the retrieval engine, already speced; activate it only once the chunk corpus justifies it.

### L4 · Reputable-source distillation pipeline
When we study NN/g, WCAG, OWASP, NFPA, ISO, SMRP, etc.: distill ONCE into `references/<topic>.md`
(durable rules + citation + `source_sha` of the finding), **never re-fetch**. Working prototype already
exists: `CONTENT_MESSAGING_RESEARCH.md` is "chunked, Memento-indexed, read before writing any marketing
copy." Generalize it into a `references/` tree, one file per topic, freshness-gated like any chunk
(source_sha = the URL's fetched-content hash or a manual review-date anchor).

> **SHIPPED 2026-07-14 — L4 is now AUTOMATED by the Night Crawler (`tools/night_crawler.py`, [[project_night_crawler]]).**
> The hand-authored `substrate/reference/*.md` chunks were the manual proof; the Night Crawler produces them
> on demand: `--query` (retrieve-first, 0 tokens) → crawl4ai → free-tier `call_ai` distill → `substrate/external/<slug>.md`
> (frontmatter `source` URLs + `source_sha` of the crawled markdown + `fetched_at`/`last_verified`/`ttl_days`), auto-indexed
> by Memento `walk_substrate_dir`. External freshness is TTL-governed (web sources can't be locally hash-re-derived) via a
> NON-BLOCKING gate `night-crawler-freshness` (`tools/validate_night_crawler_freshness.py`) + `--refresh-stale`. Safety:
> SSRF denylist + prompt-injection-as-data + free-tier-only + same-domain spider. SOP: `workflows/night_crawler.md`.

---

## 3 · Chunk schema (concrete — dogfood the memory-file frontmatter)

```markdown
---
name: <kebab-slug>                     # stable id, Memento key
type: page-writes | table-rls | rpc | kpi-derivation | reference | edge-fn
source: <repo-relative file or URL>    # what this chunk distills
source_sha: <sha256 of the distilled slice / fetched content>
last_verified: 2026-07-13
supersedes: <slug|null>                # contradiction handling
---

## <metadata prefix line — repeated context so retrieval carries it>
<the distilled fact: 5-40 lines, opinionated, example-driven, no raw dump.>
Links: [[other-chunk-slug]]
```

Granularity target: **most chunks 200-1,200 tokens.** A task retrieves 3-5 → ~2-5K tokens of exact
context vs a 500K-token file read or a 1M-token fan-out.

---

## 4 · We already have ~70% of this — UNIFY, don't rebuild

| PKS layer | Already exists (scattered) |
|---|---|
| L1 platform-fact chunks | `canonical_registry.json` (162 RPCs/surfaces/edge-fns), `lineage_map.json`, `ai_seams_catalog.json`, dozens of `*_baseline.json`, `content_substrate_manifest.json` |
| L2 freshness gates | `run_platform_checks.py` (100+ gates), `mine_canonical_registry.py`, migration-immutability, `compact_memory_index.py`, the Prevent→Detect→Fix→Govern discipline |
| L3 retrieval | Memento (live, git-SHA-anchored, `supersedes`-aware) + the paused SQLite FTS5 cache design |
| L4 source distillation | `CONTENT_MESSAGING_RESEARCH.md`, the `reference_*` memories, the 30+ skills |

The gap is not tooling — it is that these are **scattered, human-oriented, and not unified** into one
retrievable, freshness-gated substrate with a metadata-prefixed chunk schema and a single index.

---

## 5 · When fan-out STILL earns its cost (demote, don't ban)

Fan-out remains correct for: (a) a genuinely **novel one-shot breadth** task with no prior index (the
first-ever audit of a brand-new subsystem), or (b) an **adversarial-verify panel** where N independent
perspectives are the deliverable. Rule: **PKS-retrieval is the default; fan-out is the deliberate,
Ian-approved exception.** Every fan-out must first ask "can the substrate answer this?" — and if it
runs, its findings **fold back into the substrate** so the next run retrieves instead of re-deriving.

---

## 6 · Phases (measured exit criteria; nothing ships pre-review)

- **P0 · This doc — DONE + Ian-approved (2026-07-13).** Full design, phases, citations, Memento-indexed.
- **P1 · Unify + freshness gate — DONE (2026-07-13; +memory & +gate types 2026-07-14).** Built
  `tools/build_substrate.py` (**13 chunk types**: the original 6 [table-rls · rpc · page · edge-fn · skill · doc]
  plus 7 added 2026-07-14 — **memory** (curated-corpus freshness manifest, 478 files fingerprinted — brings
  the auto-memory under the same no-regress source_sha discipline; teeth-verified) · **gate** (catalogs all
  591 registered `run_platform_checks.py` VALIDATORS → the "what's already gated" brain — grep it before
  building a gate; prevented 2 rebuilds this session [XSS suite, cron gate]) · **view** (49 `v_*` defs:
  security_invoker + trust-cols + sources) · **config** (per-fn verify_jwt + env + a baked-in edge-fn BOLA
  verdict) · **migration** (330-mig object catalog) · **ops** (16 cron jobs + 33-table realtime publication) ·
  **fk** (145-FK relational-integrity graph: unindexed + cascade-blast-radius) — all via DETERMINISTIC parse,
  so the big files [logbook.html 301KB, etc.] NEVER enter the agent's context). **483 chunks** in `substrate/`, each
  metadata-prefixed with a `source_sha`. Shipped `tools/validate_substrate_freshness.py` (registered
  `substrate-freshness` in `run_platform_checks`) — drift-loop VERIFIED (fresh→PASS, corrupt-anchor→FAIL
  with exact diff, rebuild→PASS). Wired `substrate/**/*.md` into Memento (`walk_substrate_dir` in
  `memento_indexer.py`, guarded on the dir existing = zero impact on other projects); indexed +
  retrievable. **Measured win:** logbook.html 301KB file → 1KB page chunk (300× smaller) listing its 10
  DB writes, RPC, 5 edge-invokes, 5 truth-views, 126 fns. The bug-hunt now RETRIEVES this instead of
  re-reading the file. The table-rls chunker auto-surfaced 2 real attribution suspects (community_xp,
  platform_feedback) deterministically — the substrate already does part of the P5 hunt.
- **P2 · References distillation tree — SEEDED (2026-07-13).** `substrate/reference/<topic>.md` — the
  3 reputable-source topics behind the PKS itself distilled once (`context-engineering`, `rag-chunking`,
  `doc-freshness`): durable rules + citations + `last_verified` review-date anchor (hand-authored, so
  `build_substrate --check` correctly does NOT hash-gate them; Memento still indexes them via
  `walk_substrate_dir`). The pattern generalizes `CONTENT_MESSAGING_RESEARCH.md`: study a source ONCE →
  distill → cite → file → read-before-work, never re-fetch. Backfill more topics (NN/g, WCAG, OWASP,
  NFPA, ISO, SMRP) as they're studied. **Exit (met for the seed set):** a topic is distilled, cited,
  review-anchored, retrievable.
- **P3 · Retrieval cache — DONE (2026-07-14).** Reconciliation: the SQLite FTS5+TF-IDF cache was ALREADY
  BUILT — `project_memento_local_memory_cache` P0-P10 (2026-06-06): `memento_db.py`/`memento_indexer.py`/
  `memento_retrieve.py`/`memento_hook.py` deliver the prompt-matched memory slice (<2.5K tokens) per prompt
  (the `<relevant-memory>` UserPromptSubmit injection). The remaining gap was the CONSUMPTION side: the
  NATIVE memory feature ALSO loads `MEMORY.md` whole, and it had grown to **24.2KB — ~150 bytes from the
  24.4KB hard cap** (silent-truncation cliff). Fixed by `tools/memory_cache.py` (`--retrieve` on-demand
  FTS5 · `--check` coverage+budget gate · `--slim` proactive partition): keep MEMORY.md a slim DOCTRINE-CORE
  (all feedback) + 24 recent refs; move older refs to RETRIEVAL-ONLY (the cache delivers them). **MEMORY.md
  24.2KB → 16.3KB** (50 refs moved, all verified FTS5-retrievable — a moved ref like
  `reference_inventory_p6_lost_update` retrieves in ~70 tokens). Gate `memory-cache-coverage` registered in
  `run_platform_checks` (FAILs on a coverage gap or over the hard cap) — the budget pressure is
  structurally ended. (Note: `memory_cache.py` is a project-specific slim+gate on THIS project's MEMORY.md,
  so it lives in project `tools/` like `compact_memory_index.py`; the project-agnostic Memento CORE stays
  under `~/.claude-memento/tools/`.)
- **P4 · Fan-out fold-back.** Any remaining fan-out writes its findings INTO the substrate. **Exit:** the
  per-page bug-hunt runs from retrieved chunks; fan-out only for net-new subsystems.

---

## 7 · Anti-regression governance (Prevent → Detect → Fix → Govern)

Reuse the exact discipline that governs `MEMORY.md`:
- **Prevent:** a new chunk is a tight semantic unit with a `source_sha`; detail in the chunk, pointer in
  the index. No raw dumps.
- **Detect:** `validate_substrate_freshness.py` every run — WARN on aging `last_verified`, FAIL on
  `source_sha` mismatch (a stale chunk = a code regression).
- **Fix:** re-chunk the single stale unit (O(delta)); a `--apply` path re-hashes + re-distills.
- **Govern:** this roadmap + the knowledge-manager skill SOP make it standing; when the freshness gate
  fires, the move is re-chunk, never hand-roll.

---

## 8 · Token economics (the whole point)

| | Fan-out (today) | PKS retrieval (target) |
|---|---|---|
| Per bug-hunt run | 0.5-3M tokens (re-derive all) | ~5-30K (retrieve touched slices) |
| Marginal cost as platform grows | grows O(pages×agents) forever | grows O(changed files) only |
| Prompt-cache benefit | low (fresh agents) | high (stable substrate) — "without caching a task costs 2.5x more" |
| Freshness | none (re-scan hopes to catch drift) | gated (source_sha catches drift deterministically) |

---

## 9 · Reputable sources (distill into `references/` in P2)

- Context engineering / token cost: [Augment Context Engine](https://www.augmentcode.com/context-engine),
  [Sourcegraph — Context Engineering (2026)](https://sourcegraph.com/blog/context-engineering),
  [Martin Fowler — Context Engineering for Coding Agents](https://martinfowler.com/articles/exploring-gen-ai/context-engineering-coding-agents.html),
  [Packmind — large codebases](https://packmind.com/context-engineering-ai-coding/context-engineering-large-codebases/).
- Chunking: [Databricks chunking guide](https://community.databricks.com/t5/technical-blog/the-ultimate-guide-to-chunking-strategies-for-rag-applications/ba-p/113089),
  [Firecrawl — best chunking strategies](https://www.firecrawl.dev/blog/best-chunking-strategies-rag),
  [Clinical RAG chunking study (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC12649634/),
  [Atlan — chunking trade-offs](https://atlan.com/know/chunking-strategies-rag/).
- Freshness / drift-as-code: [doc-drift (GitHub)](https://github.com/jbrockSTL/doc-drift),
  [Dosu — freshness score in CI](https://dosu.dev/blog/score-documentation-freshness-in-ci),
  [Doc Drift Detection in CI](https://understandingdata.com/posts/doc-drift-detection-ci/),
  [Falconer — docs as code](https://falconer.com/guides/docs-as-code).

---

## NEXT

`NEXT: Ian reviews this roadmap. On approval, start P1 — define the chunk-schema frontmatter, stand up
substrate/ from the existing registry/lineage/baseline JSON + a first slate of page-writes + table-rls
chunks, and ship validate_substrate_freshness.py (source_sha gate) into run_platform_checks. Do NOT
build before review. Pairs the knowledge-manager Prevent→Detect→Fix→Govern SOP + the paused
project_memento_local_memory_cache design + the CONTENT_MESSAGING_RESEARCH.md prototype.`
