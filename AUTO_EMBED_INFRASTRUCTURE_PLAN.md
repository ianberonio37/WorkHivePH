# AUTO-EMBED — the indexing contract

> **Ian, 2026-07-31:** *"public users should have the ability that anything they put inside their account
> should have an auto embedder."*
> **Locked with Ian:** visibility **mirrors the source row**; scope is **everything**, phased.
> **Method:** researched internally first. Every external pattern this plan needs was **already in the
> substrate** — no crawl was spent ([[feedback_retrieve_first_no_workflow_for_known_knowledge]]).

## §1 · The ask, restated as a contract

Not *"an auto embedder"* (a component someone wires per table) but an **indexing contract**:

> **If a user put it in their account, it is findable — and only by whoever could already see it.**

Indexing becomes part of the write, not a side-effect someone remembered to hook up. The user never thinks
about it, and neither does the next engineer adding a surface.

## §2 · Where we actually stand — measured 2026-07-31, not estimated

| user surface | rows | knowledge table | retrievable |
|---|---:|---|---:|
| `logbook` | 3,811 | `fault_knowledge` | **14.0%** |
| `pm_completions` | 1,591 | `pm_knowledge` | **0%** |
| `voice_journal_entries` | 212 | — | **no path** |
| `skill_badges` | 148 | `skill_knowledge` | ~19% |
| `community_posts` | 112 | — | **no path** |
| `project_progress_logs` | 58 | — | **no path** |
| `projects` | 12 | `project_knowledge` | **0%** |
| `project_change_orders` | 12 | — | **no path** |

**~5,950 user-authored rows · ~560 retrievable · ≈9%.** Two knowledge tables exist and are **empty**; four
surfaces have no path at all. The denominator is honest: `embed-entry` skips entries under 50 composed
characters, and **zero** rows are that short, so this is a real gap and not a filter artifact
(gate `knowledge-is-retrievable`).

## §3 · Why the current shape cannot deliver the contract

Today: **three hand-created dashboard webhooks** fire HTTP *directly from a trigger* into one edge function
with a `switch` over table names.

| failure mode | evidence |
|---|---|
| **Silent** | fire-and-forget from a trigger — no retry, no backpressure; a `500` sat in `net._http_response` and nothing noticed |
| **Unsafe** | the URL **and a service-role key** are baked into the trigger body — which is how local writes reached production (gate `local-triggers-dont-call-prod`) |
| **Unscalable** | each surface needs a new dashboard hook *and* a new branch; four surfaces never got one |
| **Unmeasured** | nothing asked "what fraction is retrievable?", so 9% looked like success |

**The decisive precedent:** `SERVICE_HAILING_ROADMAP` §4b evaluated the transactional outbox for `service_*`
and correctly **declined** it — those triggers write only to this DB in the same transaction, so an outbox
would *add* an inconsistency window. Its discriminating test was `prosrc !~ http_request|pg_net|net.http`.
**The embed triggers are precisely the case that test was built to find.** Same platform, opposite verdict,
because the premise differs ([[feedback_check_the_premise_before_building_the_pattern]]).

## §4 · Non-negotiables inherited from our own scar tissue

These are not preferences; each one is a bug we already paid for.

1. **The embedding model is a property of the CORPUS — pinned, never inferred.** A blind failover chain
   (Voyage→Jina→Gemini) that switches provider switches **vector space**: cosine becomes noise and retrieval
   returns nothing, *with no error*. Keep failover for uptime, but pin per corpus and log a loud
   `SPACE-DIVERGENCE`. A validator must assert ingest-default == edge-pin and that a corpus holds exactly one
   `embedding_model`.
2. **Never trust an ANN index built before the data existed.** An `ivfflat` created on a near-empty table
   trains its centroids on noise and *silently* drops high-similarity rows as the corpus grows. At our scale
   (hundreds → a few thousand per corpus) use **exact** cosine search — sub-millisecond, 100% recall. ANN
   only earns its trade-off past ~10k rows, and then only built/REINDEXed **after** load.
3. **Batch the embedding calls.** Providers accept `input:[...]`; a 38-chunk source costs ~2 calls, not 38.
   This is the difference between a feasible backfill and a rate-limit wall.
4. **Re-embedding to a new model requires DELETE-first.** A hash-keyed upsert will not replace a vector when
   only the *model* changed, not the content.
5. **Dimensions must match the column.** `vector(384)`: bge-small-en-v1.5 is 384 native; Gemini needs
   `dimensions:384` **plus** an L2-normalize on both sides; **Mistral-embed is 1024 and cannot join.**
6. **Free-tier only**, per standing constraint.

## §5 · The architecture

```
user write ──▶ [tiny trigger] ──▶ embedding_outbox        (same transaction: no network, no secrets)
                                        │
                              pg_cron ──┤ claim batch  FOR UPDATE SKIP LOCKED
                                        ▼
                                   relay worker  ──▶ embed-entry (batched)  ──▶ *_knowledge (+ vector)
                                        │                                        ▲
                                        └── retry w/ backoff → dead-letter        └── RLS mirrors source
```

**A. Outbox, not webhook.** The trigger writes one row — `(source_table, row_id, hive_id, auth_uid, op,
enqueued_at)` — and nothing else. No network call, no secret in the catalog, and it **rolls back with the
user's transaction**, so a failed write never leaves a phantom index entry. This single change fixes silence,
retries, rollback semantics, and the key exposure together.

**B. The relay is `pg_cron` + `FOR UPDATE SKIP LOCKED`** — the pattern already in
`substrate/external/external-postgres-skip-locked-job-queue-worker-dispatch.md`. N workers claim disjoint
rows, with attempt counts, exponential backoff and a dead-letter after N tries. `pgmq 1.5.1` is **available
but not installed**; the skip-locked table is fewer moving parts and matches the substrate we already own, so
it is the default — pgmq stays the documented fallback if we ever want visibility timeouts for free.

**C. A registry, not a switch statement.** One row per embeddable surface:

| column | meaning |
|---|---|
| `source_table` | `logbook`, `community_posts`, … |
| `text_template` | which columns, in what order, with what labels |
| `target_table` | `fault_knowledge`, … |
| `conflict_key` | `logbook_id` — re-embed on edit **replaces** |
| `min_chars` | the near-empty skip (currently 50) |
| `embedding_model` | the per-corpus pin from §4.1 |
| `visibility` | how the RLS mirror is derived |

Adding a surface becomes **a config row + a two-line trigger**, not a new branch in an edge function. This is
the piece that makes "anything they put in" tractable rather than a growing pile of special cases.

**D. Visibility mirrors the source (Ian's decision).** Each knowledge row carries `hive_id` **and**
`auth_uid`, and its RLS policy is derived from the source table's own policy — hive content stays
hive-searchable, private content stays private to its author. **Indexing must never widen who can see
something**; that is the property the whole feature lives or dies on.

## §6 · Backfill — a costed, resumable job

~5,400 rows across the surfaces above. Batched (§4.3), resumable, idempotent via `conflict_key`, and
dedupe-aware against the existing `embedding_cache`. It reuses machinery we already have —
`batch_embed_voice_journal.py`, `companion_reembed_procedural.py`, `day3_embed_industry_standards.py` — rather
than a new script. It is a **deliberate, costed run**, never something a gate performs silently.

## §7 · How we will know it is true

- **`knowledge-is-retrievable`** (built, registered, forward-only) — generalized from `logbook` to **every
  registered surface**: % retrievable per surface. "Auto" stays a measurement, not an aspiration.
- **`local-triggers-dont-call-prod`** (built, registered) — no trigger may call out or carry a key. The outbox
  makes this structurally true instead of merely enforced.
- **A space-divergence validator** — ingest-default == edge-pin, one `embedding_model` per corpus (§4.1).
- **An ANN-index guard** — no approximate index on a corpus below the threshold, and none created before load
  (§4.2).
- **A round-trip bank cell (S9)** — write as a user → drain → assert the row is *findable by that user* and
  **not** by a foreign hive. The tenancy half is the one that matters.

## §8 · Phasing

| phase | scope | why this order |
|---|---|---|
| **P1** | Outbox + relay + registry, `logbook` only | the highest-volume surface, already has a knowledge table; proves the spine end-to-end |
| **P2** | Fix the wired-but-broken: `pm_completions` (0%), `projects` (0%), `skill_badges` | tables and branches already exist — these are broken, not missing |
| **P3** | Backfill the ~5,400 | once the spine is proven, so the backfill lands in a pipeline that keeps it true |
| **P4** | New surfaces: progress logs, change orders, community posts/replies | registry rows, not new code |
| **P5** | `voice_journal_entries` | highest privacy sensitivity — lands only after the mirror-RLS model is proven in P1–P4 |

## §9 · Open, and Ian's

- **Rotate the exposed production service-role key** (found this session; local triggers contained, but
  containment is not rotation).
- **What production's own embed triggers should do** — they are still live there and still fire-and-forget.
- Whether P1 ships behind the outbox *before* the backfill, or the backfill runs first on the current path.
  Recommendation: **spine first**, so the backfill lands into something that keeps it true.

## §10 · OWN EMBEDDER — Ian's correction, and the split-space it exposed

> **Ian, 2026-07-31:** *"what I mean we should have our own, not relying on external llm embedders."*

**We already own it, and it is already running.** `tools/embed_server.py` serves fastembed
`BAAI/bge-small-en-v1.5` (384d) on `:8901` — `{"ok": true, "model": "bge-small-en-v1.5", "dim": 384}` — with
**no rate limit**. So the backfill I framed as "a costed decision needing ~5,400 free-tier calls" is not costed
at all: it is local CPU time. That framing was wrong and is withdrawn.

**But measuring which space each corpus is in found a live split:**

| corpus | rows | embedding_model |
|---|---:|---|
| `fault_knowledge` | 534 | `bge-small-en-v1.5-local` ✅ |
| `pm_knowledge` | 1 | `nomic-embed-text-v1_5` ❌ |

The 534 fault rows are in **our** space because they were written by a HOST script
(`reembed_fault_knowledge.py` → `127.0.0.1:8901`). The pm row went through the **edge function**, whose chain
is configured correctly (`BGE_EMBED_URL=http://host.docker.internal:8901/embed`, `SUPABASE_URL=http://kong:8000`
→ `_IS_LOCAL_EMBED` true → primary `bge-local`) — and still answered from **nomic**, so the bge-local call
failed at runtime and the chain failed over. That is precisely the SPLIT-SPACE bug
([[feedback_bge_local_false_ceiling_own_embedder]] and the ai-engineer chain lesson): a vector in a foreign
space is not merely useless, it is *silently* useless — cosine returns noise with no error.

The foreign-space row was deleted rather than kept, and `pm_completions`/`skill_badges` were returned to
`active=false`. **A surface must be in the right space before it is wired**, exactly as it must be upsertable
before it is wired (§P2).

### §10.1 · The architectural consequence — embed in the RELAY, not the edge function

The relay is a **host process**. It can call `127.0.0.1:8901` directly, the same path that put 534 fault rows
in the correct space, instead of asking a container to reach back out to the host. That removes the failure
entirely rather than debugging container→host networking, and it matches Ian's requirement more literally:
**our own embedder, in our own process, with no external provider chain in the path.**

The edge function keeps its role for browser-initiated embeds; the outbox relay stops depending on it.

**NEXT:** (1) embed in the relay via `127.0.0.1:8901`, writing the knowledge row directly with
`embedding_model='bge-small-en-v1.5-local'` and the registry's conflict key; (2) a gate asserting every corpus
holds exactly ONE `embedding_model` — the split above would have been caught the day it happened; (3) then the
backfill, which is now free.
