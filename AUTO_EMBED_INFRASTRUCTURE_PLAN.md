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

## §11 · PRODUCTION USERS — "their own auto embedder infra", not mine

> **Ian, 2026-07-31:** *"it works for me because I am using local, but you have to consider the production
> users that they are using their own devices — that's what I mean, that they have their own auto embedder
> infras."*

§10 was solved for the wrong machine. `tools/embed_server.py` on `:8901` is **my laptop**. A maintenance
worker on their own Android phone in a plant has no such server, so "we own the embedder" is only true for
development. The requirement is: **no external LLM embedding API, and it must work for every production
user** — which is a different problem with two honest answers.

### §11.1 · The two runtimes, and the one rule that binds them

| | **A · Our own hosted embedder** | **B · On-device (in-browser)** |
|---|---|---|
| where | one small service we run (CPU-only ONNX/fastembed `bge-small-en-v1.5`) | the user's browser, via transformers.js / ONNX-WASM |
| user device needs | nothing | ~33 MB quantized model, one-time download + cache |
| offline write | embeds on sync | **embeds immediately, offline** |
| cost | one always-on small container (~100 MB RAM), no per-call fee | zero infra, spends the user's battery/CPU |
| PH mobile reality | works on the cheapest handset | a low-end Android will be slow; the 33 MB download is real on mobile data |
| privacy | text reaches our server (it already does — it is our DB) | text never leaves the device to be embedded |

**THE RULE THAT MATTERS MORE THAN THE CHOICE: one model, one space.** Whatever runs where, it must be
`bge-small-en-v1.5` at 384d on *both* sides. A device embedding with one model and the server querying with
another is the SPLIT-SPACE bug at fleet scale — and §10 just caught that exact failure with a single row
(`nomic` vs `bge-local`), silently, with no error. This is why the registry pins `embedding_model` per corpus
and why a gate must assert each corpus holds exactly one.

### §11.2 · The recommendation

**A as the floor, B as the enhancement.** Ship the hosted embedder first: it makes auto-embed true for
*every* user on *any* device with nothing to install, and it is the only option that can also backfill the
existing corpus. Then add on-device embedding for the offline-first case — a worker who logs a fault with no
signal gets it indexed on the spot, and it syncs already-embedded, which is a genuine advantage for this
product's actual field conditions.

What must NOT happen is B alone: a user on a device too weak to run the model would silently get no indexing,
which fails the contract in §1 precisely for the users least able to notice.

### §11.3 · What this changes in the plan

- §6's backfill: runs against **A**, not my laptop — and is still quota-free, since we host it.
- The relay (§10.1) points at the hosted embedder's URL by config, not `127.0.0.1`.
- `embedding_model` stays pinned to `bge-small-en-v1.5`; the runtime may vary, the SPACE may not.
- The self-hosted service is the one new piece of infrastructure this whole plan requires. Everything else —
  outbox, registry, relay, gates — is already built and does not care where the vectors come from.

### §11.4 · Correction — the hosted embedder is NOT new infrastructure; it is already built and running

§11.3 called the self-hosted service "the ONE new piece of infrastructure this whole plan requires." That is
wrong, and checking beat assuming again. It already exists:

```
image      workhive-embed-server:selfheal   (and :latest)
container  embed-server                      Up 3 days
```

Built in a prior session with `--restart unless-stopped` (survives reboots, unlike a nohup), on the Supabase
network plus a host port, and with the self-heal sweep **baked in** (`WH_EMBED_SELFHEAL_MIN`, an env DSN to
`supabase_db_workhive:5432`, `psycopg2`, and `reembed_dirty_knowledge.py` copied inside). It serves fastembed
`BAAI/bge-small-en-v1.5` at 384d with no rate limit.

So **option A of §11.1 is a packaged, restart-surviving, self-healing container that has been running for
three days** — not a thing to design. What remains is genuinely outward and Ian's: *where it runs* for
production users (a host, a cost, a URL), after which the relay points at that URL by config instead of
`127.0.0.1:8901`.

Two build gotchas recorded from when it was made, so a rebuild does not relearn them: a pip-layer change
busts the cached ~130 MB model layer (install `psycopg2` AFTER the model bake), and when a fresh model
download stalls, `docker cp` + `docker commit` off the running model-baked container sidesteps it.

**This is the third time this arc that "we need to build X" turned out to be "X exists, check first"** — after
the state inducers and the CDC contract. The rule is now explicit at the top of §15.4 of the deepwalk roadmap:
check the ~700 gates and the existing tools before adding, every time.

## §12 · The backfill ran through the KNOWN-BROKEN path, and the gate caught it mid-flight

I diagnosed in §10.1 that the edge function cannot reach the host embedder and falls back to another
provider — then started the 3,278-row backfill **through that exact path anyway**. Coverage climbed 14.0% →
31.6%, and `fault_knowledge` went **split-space: 717 rows in nomic against 534 in bge-local.**

**The gate built an hour earlier is what caught it.** Every one of those 717 writes SUCCEEDED — right shape,
non-null vector, job marked done, coverage number rising. A row count could not tell them apart. Only
`embedding_model` could, and only because something was reading it.

Recovery, in order: **pause the queue** (2,563 jobs held on `next_attempt_at`), then heal with the existing
sweep — 753 + 27 rows re-embedded into bge-local space, `PASS` restored. The stragglers appeared because the
drain loop was still finishing while the healer ran; a second pass closed it, which is what "idempotent
self-healing" buys.

**Three lessons, none of them new — which is the point:**

1. **A diagnosed defect is not a fixed defect.** Writing "§10.1: the relay should embed directly" and then
   running 3,278 rows through the old path is the same class as
   [[feedback_a_silently_failed_edit_becomes_a_false_report]]: the analysis was right and the *action* did
   not follow it.
2. **A rising metric is not a healthy one.** 14% → 31.6% looked like exactly the success I wanted, which is
   precisely when a second, independent instrument matters. The retrievability gate and the space gate
   disagreeing is what exposed it — the same shape as the self-healer's blind column map, caught the same way.
3. **Backfill AFTER the pipeline is right, never before.** §8's phasing said spine-first for this reason and
   I overran it. The remaining 2,498 stay queued and paused until the relay embeds via the host embedder
   directly (§10.1) — the path that has put every correct row in this database.

**Status: 1,314 of 3,811 retrievable (34.5%), all in one space, 2,498 queued and paused pending the relay fix.**

## §13 · The principle the second split taught: FAILOVER IS SAFE FOR READS, POISON FOR WRITES

Fixing the address (§12) was necessary and not sufficient. With `embed-server` correctly reachable, three
test rows landed in bge-local — then resuming the backfill put **241 more rows into nomic**. The embedder was
not misconfigured any more; it was intermittently slow or busy under sustained load, and on each stumble the
chain did what it was designed to do: **fail over to the next provider.**

That behaviour is correct for a QUERY and catastrophic for an INGEST:

| | failover on a **read** | failover on a **write** |
|---|---|---|
| effect | a slightly worse answer, this once | a **permanent** vector in a foreign space |
| visibility | the user sees a result | every signal says success — job done, count rises |
| recovery | nothing to undo | DELETE-first re-embed of every affected row |

A read failover degrades one response. A write failover **persists** the degradation, and because the vector
is well-formed and non-null, nothing downstream can tell it apart from a good one. This is why the corpus was
poisoned twice in one session by a system that reported success both times.

**THE RULE: ingest must be PINNED and NO-FAILOVER.** If the pinned embedder cannot answer, the correct
outcome is to FAIL THE JOB — the outbox already exists precisely to retry it with backoff, and a queued row
is recoverable while a foreign-space row is not. Failover stays for query paths, where a degraded answer beats
no answer.

That is a small change to `generateEmbeddingTagged` (an ingest flag that refuses to walk the provider list)
plus the relay passing it. It is the last thing standing between the paused 2,221 rows and a safe backfill —
and it is the reason those rows stay paused rather than draining tonight.

**Corrected status: the backfill is BLOCKED on a chain that fails over, not on quota, not on the address, and
not on the embedder.** Everything else — outbox, registry, relay, upserts, dedup, both gates, the healing
sweep — is built and proven.

## §14 · BACKFILL COMPLETE — 14.0% → 99.97%, one space, queue empty

| | before | after |
|---|---:|---:|
| logbook entries retrievable | 533 (14.0%) | **3,810 (99.97%)** |
| written-only | 3,278 | **1** |
| distinct vector spaces in `fault_knowledge` | 2 | **1** |
| outbox queue | 3,278 | **0** |

Both gates PASS: `knowledge-is-retrievable` ratcheted 3,278 → 1, and `embedding-space-integrity` confirms
every corpus (fault 3,810 · persona 434 · skill 4) sits in exactly one declared space.

**What made the difference was not effort, it was removing the broker.** The first two attempts pushed rows
through the edge function and produced mislabelled, rate-limited, failover-prone writes. Going straight from
the relay to the self-hosted embedder — host process to host process — drained 3,278 rows with **zero
deferrals** once the abuse cap had a sanctioned operator path.

**The one remaining row is honest, not swept:** it is a single logbook entry the pipeline could not compose
past `min_chars`, which is the function's own rule working. The gate keeps counting it rather than rounding
99.97% up to 100%.

**Everything now holds by construction rather than by vigilance:** the trigger enqueues inside the user's
transaction, the relay retries with backoff and dead-letters loudly, the conflict keys make a re-embed
replace, the dropped default means an unlabelled row reads NULL instead of lying, ingest is pinned with no
failover, and two independent gates disagree loudly whenever any of that stops being true.

**Remaining, and outward:** where the (already-built, already-running) embedder container runs for production
users, and rotating the exposed production service-role key.
