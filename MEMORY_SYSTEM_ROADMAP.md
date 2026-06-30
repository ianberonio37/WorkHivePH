# Memory-System Roadmap (Memento + auto-memory) — anti-drift spine

> **Scope:** the agent's own long-term memory — the Memento SQLite-FTS5 retriever, its hooks/indexer,
> and the `MEMORY.md` index hygiene. Grounded 2026-06-24 by a 2-agent scout (inventory of the live
> codebase + adversarially-filtered enhancement proposals). **Honest headline: the system is already
> very mature; what remains is small and prioritized — and the rule is _measure before you upgrade_.**

---

## M0 — DONE (the system as-built, do not rebuild)
SQLite/FTS5 schema v10, 10,395 chunks · hybrid retriever (BM25 + sparse TF-IDF cosine + RRF + type-aware
recency decay + importance + honesty gate + 2,500-token knapsack) · UserPromptSubmit auto-injection ·
PreToolUse(Edit/Write) curated-lesson injection + Read-nudge · SessionStart git-SHA handoff injection ·
incremental Stop-hook refresh across 14+ source walkers + live-session transcript · stale-handoff
auto-archival (>30d) · health dashboard (founder-console) · precision audit + prune-candidate proposer ·
token-savings audit · **MEMORY.md hygiene tool+gate (this session)**. → No work needed.

---

## ★ COMPLETION SCOREBOARD (honest % — 0 / 15 helper-exists / 30 +gate-baseline / 50 / 75 / 100)

| ID | Item | ★ | Effort | **%** | What the % reflects |
|---|---|---|---|---|---|
| **M0** | Foundation (retriever + hooks + hygiene tool/gate) | — | — | **100%** | as-built; do not rebuild |
| **M1.1** | DB backup + restore drill (`memory.db`) | ★ | S | **100%** ✅ | `tools/memory_db_backup.py` — online-backup snapshot + 5-deep rotation + bundled curated `.md` half; SessionStart auto-trigger (throttled 6h); `--drill` gate proves the full round-trip (integrity + chunk-count + schema + **real FTS5 query on the restored copy**); registered in `run_platform_checks` group "Memory System" |
| M1.2 | VACUUM after delete-bearing refresh | | S | **100%** ✅ | folded into `memory_db_backup.py` `--vacuum` (bloat-gated, runs in the SessionStart backup path; reclaims only when free pages >15%) + `--vacuum-drill` (proves delete→VACUUM shrinks a file 16.4MB→3.3MB); drill registered in the M1.1 gate |
| **M2.1** | recall@k eval harness (~25 golden pairs) | ★ | M | **100%** ✅ | `tools/memory_recall_eval.py` — 25 grounded (query→canonical-memory) golden pairs vs the LIVE retriever; baseline R@1 .32 / R@3 .80 / R@5 1.00 / MRR .56; gated on fixed health floors (R@3≥.60, R@5≥.80, MRR≥.40); `--selftest` proves teeth (bad knob → recall 0.00 → FAIL); registered in `run_platform_checks` |
| M2.2 | Health regression gate | | S | **100%** ✅ | `tools/memory_health_gate.py` wraps the SAME `build_payload()` the dashboard uses in thresholds (silent_rate≤40%, p95≤3000ms, file-grounded≥50%, index non-empty); honors the warming-up honesty flag (defers activity thresholds at <10 retrievals); `--self-test` teeth; registered (runs in --fast) |
| **M3.1** | Write-quality gate (topic-file frontmatter) | ★ | S | **100%** ✅ | `tools/memory_write_quality.py` — imports the REAL indexer (`parse_frontmatter`+`detect_type`) so the lint can't drift; ERRs on `type=unknown`/missing name/description/over-long index line; `--self-test` teeth. **Found+fixed 6 live recall bugs** (3 doctrine memories restored, 3 zero-byte junk deleted); now 0 ERR/358 files; registered in `run_platform_checks` (runs in --fast) |
| M3.2 | `supersedes:` field + retriever penalty | | S | **100%** ✅ | `tools/memory_supersedes.py` scans `supersedes:` frontmatter → writes `meta.supersedes_map`; `memento_retrieve.load_supersedes()` down-ranks the superseded chunk (×0.4), guarded so an empty map is a strict no-op (recall@k byte-identical after the change); refreshed on SessionStart; `--self-test` proves frontmatter→map→loader→down-rank; registered |
| M4.1 | Transcript retention / pruning | | S | **100%** ✅ | `tools/memory_prune_transcripts.py` — backup-guarded eviction of old never-retrieved transcripts (FK-cascades vectors, VACUUMs); `--scheduled` (weekly, 60d) wired into SessionStart; proved live (10490→10437 chunks, −3.0MB, recall+health still PASS); `--self-test` on a real-schema scratch DB; registered |
| M4.2 | Auto-compact INDEX on over-hard-cap | | S | **100%** ✅ | added `compact_memory_index.py --auto` (deterministically `--apply` ONLY when over the HARD load cap; no-op under it) + wired into SessionStart; verified: live (21.4KB) no-ops, a 47KB scratch index auto-compacts to 1.6KB; backed up + keeps all feedback |
| M5 | Embeddings / graph-walk / auto-tune / LLM-compaction / `/recall` | — | — | **0% (parked)** | intentionally deferred behind M2.1 (adversary verdict: over-engineering today) |

**Roll-up:** Foundation **M0 = 100%** ✅ · **Active roadmap (M1–M4, 8/8 items) = 100%** ✅ — **the whole active M-series is DONE**: M1.1+M1.2 durability, M2.1+M2.2 measurement, M3.1+M3.2 write-quality, M4.1+M4.2 scale. 7 new Memento gates registered in `run_platform_checks` group "Memory System" (+ the pre-existing `memory_index_budget` = 8). The 3★ spine (M1.1/M2.1/M3.1) caught+fixed 6 live recall bugs in passing. · **M5 = still parked BY MEASUREMENT**: M2.1's baseline (R@5 1.00, no paraphrase-miss class observed) does NOT justify embeddings/graph-walk — the measure-before-upgrade gate working exactly as designed. **M5 stays parked until recall@k shows a persistent semantic-miss class.**
Update each `%` as the item is built; an item is **100%** only at full adoption + its acceptance bar green + (where applicable) registered in `run_platform_checks`.

---

## The prioritized roadmap (M1–M5). ★ = do-first. Each: value · effort · acceptance bar.

### M1 — Durability & safety  (the real gap; do first)
- **M1.1 ★ DB backup + restore.** *The single highest-value gap.* `memory.db` is 93MB of durable,
  hard-to-reconstruct state (transcript/vocab/event history + the index) with **zero backup** — and
  SQLite files corrupt on interrupted writes (hooks write mid-session). Build: `sqlite3 .backup` (or
  timestamped copy) on SessionStart, 5-deep rotation; **verify the curated `.md` topic files are in
  git** (they're the only reproducible half). · **S** · _Acceptance:_ a restore drill rebuilds a
  working DB from a snapshot.
- **M1.2 VACUUM after a refresh that deleted rows.** SQLite never reclaims space from deletes; the DB
  is already 93MB and full-scans `chunks_vectors` every retrieval. One line after a delete-bearing
  refresh. · **S** · _Acceptance:_ DB file shrinks after delete+vacuum.

### M2 — Measurable quality  (turn ranking from vibes → measurement)
- **M2.1 ★ recall@k eval harness (small golden set).** Retrieval quality is currently **unguarded** —
  every knob (`IMPORTANCE`, half-lives, `MIN_FINAL_SCORE`, the 1.7 transcript boost, RRF k) was tuned
  by eyeballing. ~25 hand-written `(query → expected-source)` pairs, run as a gate, so a tuning change
  that silently drops recall fails CI. Keep it ~25, not a benchmark suite (that'd be over-engineering).
  · **M** · _Acceptance:_ a deliberately-bad knob change fails the gate; a good config passes.
- **M2.2 Health regression gate.** The metrics exist (silent_rate, latency, file-grounded %) but are
  only on a dashboard. Wrap them in a gate with thresholds. · **S** · _Acceptance:_ a degraded metric
  (e.g. silent_rate spike) fails the gate instead of needing a human to look.

### M3 — Write-side quality  (prevent bad memories at the source — WAT-deterministic)
- **M3.1 ★ Write-quality gate for topic-file frontmatter.** The indexer depends on frontmatter+filename
  for type/importance; a malformed file silently falls to `type='unknown'` (degraded recall forever).
  Deterministic lint: required `name/description/metadata.type`, a known type prefix, the ≤200-char
  index-line rule, duplicate-topic detection. Pairs with the MEMORY.md hygiene tool. · **S** ·
  _Acceptance:_ a malformed/typeless topic file fails; a well-formed one passes.
- **M3.2 `supersedes:` frontmatter + retriever penalty.** The 80/20 of contradiction-detection (full
  LLM-judge is over-scoped). A hand-filled `supersedes: <slug>` field; the retriever down-ranks the
  superseded chunk so an old decision can't co-surface as current with its reversal. · **S** ·
  _Acceptance:_ a superseded memory ranks below its replacement for the same query.

### M4 — Scale headroom  (only when the corpus warrants — transcripts are 3,208 of 10,395 chunks)
- **M4.1 Transcript retention/pruning.** The report-only `prune-candidates` exists but is never
  scheduled; the DB grows unbounded and `vector_query` full-scans every row (p50 already climbed to
  ~301ms, 1611ms tail). Schedule it to actually evict never-retrieved transcripts >Nd (safe once M1.1
  backup exists). · **S** · _Acceptance:_ chunk count + p50 latency drop after a prune.
- **M4.2 Auto-compact the INDEX on over-HARD-cap (deterministic only).** Today `--apply` is manual, so
  between detection and fix the index can truncate at session start. Auto-run the **deterministic**
  `compact_memory_index.py --apply` (dedup/collapse, backed-up) when over the *hard* cap — index only,
  **never** LLM-rewrite of topic files. · **S** · _Acceptance:_ the index never exceeds the cap at load.

### M5 — DEFERRED behind measurement  (do NOT build until M2.1 justifies — adversary verdict: over-engineering today)
- **Dense embeddings (bge/nomic) vs TF-IDF** — the corpus is the dev's own jargon (arc/tool/flag names)
  where lexical FTS5 is strong; adds a heavy dep + dev/prod vector drift. Build **only if** recall@k
  shows a persistent semantic-miss class (paraphrased queries sharing no terms with the right chunk).
- **Wikilink graph-walk retrieval** — only if recall@k shows "linked-but-missed" is a real miss class;
  otherwise it spends the scarce token budget on 2nd-degree chunks.
- **Importance/half-life auto-tuning** — needs a labeled reward signal we don't have; tune manually via
  M2.1 instead (keeps retrieval reproducible/debuggable).
- **Auto-LLM-compaction of curated topic files** — risky autonomous rewrite of durable memory; keep
  compaction manual + tool-assisted.
- **`/recall` slash command** — opt-in manual escape hatch; nice-to-have, low priority.

---

## Decision rule (the through-line)
**Build M1 (don't lose it) and M2 (measure it) first; let the measurement justify M5, never the reverse.**
M3 prevents bad memories at the source; M4 is scale headroom triggered by the corpus, not the calendar.
Recommended order: **M1.1 → M2.1 → M3.1 → (M1.2, M2.2, M3.2) → M4 → M5-only-if-measured.**

_Linked from PLATFORM_ROADMAP.md Part 0 (foundation › memory system). Grounded by scout `w3g0otxt1`._
