# Companion WIRING Probe Study — testing every function inside the AI

> **Comprehensive study (2026-06-12).** The existing [COMPANION_PROBE_TAXONOMY.md](COMPANION_PROBE_TAXONOMY.md)
> is a **behaviour-axis** taxonomy (A–I: does the companion route / recall / ground / refuse correctly).
> This study adds the **wiring-axis**: a probe for **every internal function the companion is actually built
> from** — every gateway pipeline stage, every layer of the 7-layer memory stack, every shared primitive,
> the model chain, and every routed agent path. Goal: stop testing only *what the companion says* and start
> testing *that every wire inside it fires*.
>
> Grounded in the real code, not a generic framework. Owner: Ian.

---

## 0. The honest headline — what we are NOT testing today

The entire current brain-probe battery (`__CSURF.runProbe`, the A–H live walk) drives the **floating launcher**,
which routes to the **`voice-journal`** agent. But the companion's memory stack and enrichment layers are
**per-agent opt-in** (see `ai-gateway/index.ts:98-146`). `voice-journal` opts into only **2 of the 7 layers**.

**=> 4 of the 7 memory layers, and 5 of the ~7 conversational agent paths, have ZERO probe coverage** — not
because they are untested behaviourally, but because **no probe ever drives the agent that wires them in.**

| Memory layer | Module | Agents that wire it | Probed today? |
|---|---|---|---|
| L01 Working (10-turn + summary) | `memory.ts` | ALL | ✅ (C family, via voice-journal) |
| L02 Episodic (durable) | `episodic-memory.ts` | asset-brain, analytics, shift, project, assistant | ❌ none drive these |
| L03 Semantic recall (journal) | `journal-recall.ts` | voice-journal | 🟡 partial (C2, not the layer itself) |
| L04 Procedural (skill-library) | `skill-library.ts` | asset-brain, shift | ❌ none |
| L05 Cold-archive / hierarchical | `cold-archive.ts`, `hierarchical-summarizer` | temporal-rag, archive | ❌ none (B9 authored, never live) |
| L06 Prospective (followups) | `followups.ts` | (FOLLOWUP_AGENTS) | 🟡 C7 behavioural only |
| L07 Verified-state (shared truth) | `verified-state.ts` | asset-brain, shift | ❌ none |

That is the core expansion: **probe the agents and layers the launcher can't reach.**

---

## 1. The complete wiring map (what MUST be probed)

### 1a. The gateway pipeline — ~26 cross-cutting stages, in order (`ai-gateway/index.ts`)
Every request flows through these. Each is a wire that can silently break (the `.data`-unwrap "flop" was one).

| # | Stage | Module / fn | Wire-probe assertion |
|---|---|---|---|
| P1 | CORS (dynamic origin) | `cors.ts getCorsHeaders` | OPTIONS → 204 + echoed origin |
| P2 | Request envelope / trace | `envelope.ts beginRequest` | response carries `trace_id` |
| P3 | Auth resolve + anon gate | `getUser` + `ANON_OK_AGENTS` | anon voice-journal OK; assistant → 401 |
| P4 | Worker + persona resolve | `clampPersona`, `preferred_persona` | persona honored from profile/ctx |
| P5 | Persona hydration into ctx | `context.persona` set | downstream sees the persona |
| P6 | Rate-limit (hive + per-user) | `rate-limit.ts checkUserRateLimit` | bucket exhausted → honest 429 (I2) |
| P7 | Adaptive cache degrade | `cache.ts cacheLookup` | repeat Q under cap → cached answer, not 429 |
| P8 | Gibberish guard | inline vowel-ratio | "asdfqwer…" → "couldn't make out" |
| P9 | PII redact (+map) | `redactPII.ts redactPIIWithMap` | email in msg → `<EMAIL_1>` reaches LLM |
| P10 | **L01** working memory load | `memory.ts loadMemory` | last-10 turns injected |
| P11 | **L03** semantic recall | `journal-recall.ts loadJournalRecall` | similar past entry surfaces |
| P12 | **L02** episodic recall | `episodic-memory.ts recallEpisodic` | durable memory injected (asset-brain) |
| P13 | **L07** verified-state | `verified-state.ts resolveAssetState` | asset's one-truth state injected |
| P14 | **L04** procedural match | `skill-library.ts matchProcedures` | proven fix procedure injected |
| P15 | **L06** prospective surface | `followups.ts recallDueFollowups` | due follow-up surfaces |
| P16 | Forward to specialist | `AGENT_ROUTES[agent].fn` | correct fn invoked |
| P17 | Response extract | `answer ?? summary ?? message ?? narration` | prose surfaces for every shape |
| P18 | Structured passthrough | `STRUCTURED_PASSTHROUGH_AGENTS` | `route_result` survives the envelope |
| P19 | PII hydrate (whole payload) | `redactPII.ts hydratePII` | `<EMAIL_1>` restored in answer + nested |
| P20 | **L01** persist turn | `memory.ts saveTurn` | agent_memory gains the pair |
| P21 | **L02** episodic persist | `persistEpisodic` | specialist `memories[]` stored |
| P22 | **L06** prospective enqueue | `enqueueFollowups` | specialist `followups[]` queued |
| P23 | L03 journal persist | `persistJournalEntry` | voice_journal_entries + embedding |
| P24 | Model-hop record | `recordModelHop` | model_chain in response |
| P25 | Cost log | `cost-log.ts logAICost` | ai_cost_log row written |
| P26 | Envelope wrap | `envelope.ts ok` | `{ok, data:{answer}, ...}` shape |

### 1b. The model chain (`ai-chain.ts`)
19-provider fallback (Groq→Cerebras→Gemini→Mistral→OpenRouter…), `provider-health.ts`, sticky `sessionKey`,
`max_tokens`, 413/429→skip-not-fail. Wire-probes need **fault injection** (force a provider down → answer still lands).

### 1c. The routed agent paths (each is its own wiring)
`voice-journal` (launcher/journal) · `voice-action` (router) · `assistant` (orchestrator) · `asset-brain` ·
`analytics` · `shift` · `project` · narrated specialists. Each opts into a DIFFERENT subset of P10–P15/P20–P23.

### 1d. The 27 shared primitives
`ai-chain · audio-chain · cache · cold-archive · context-budget · cors · cost-log · embedding-chain · envelope ·
episodic-memory · error-tracker · followups · health · journal-recall · logger · mappings · memory · persona ·
provider-health · rate-limit · redactPII · resume-taxonomy · semantic-facts · skill-library · validate-contract ·
validateAgentContract · verified-state`.

---

## 2. THE WIRING-AXIS PROBE FAMILIES (the expansion: J–N)

Behaviour families A–I stay. These NEW families test the wiring directly. Each probe names its **assertion
method**: `structural` (block appears in the forwarded prompt) · `behavioural` (it surfaces in the answer) ·
`db-effect` (a row is written) · `fault-injection` (break a wire → graceful) · `contract` (response shape).

### J. Pipeline-stage coverage (the gateway spine) → dim `pipeline`
| # | Probe | Stage | Method |
|---|---|---|---|
| J1 | PII redaction reaches the LLM, not the provider | P9 | structural (LLM sees `<EMAIL_1>`) |
| J2 | PII hydration restores in answer + nested `route_result` | P19 | behavioural |
| J3 | Gibberish guard fires before burning a model call | P8 | behavioural |
| J4 | Adaptive cache serves a repeat Q under rate-limit | P7 | behavioural + db |
| J5 | Rate-limit honesty (hive vs per-user scope message) | P6 | behavioural (I2 promoted) |
| J6 | Envelope `.data` unwrap — reply RENDERS (the flop class) | P26 | contract (L0 delivery gate) |
| J7 | Structured passthrough — `route_result` survives | P18 | contract |
| J8 | Response-extract fallback chain (narration→answer) | P17 | contract |
| J9 | Cost log row written per turn | P25 | db-effect |
| J10 | Model-hop / trace_id present | P2/P24 | contract |

### K. Memory-layer coverage (all 7 layers, each via an agent that wires it) → dim `memory`
| # | Probe | Layer / agent | Method |
|---|---|---|---|
| K1 | L01 working — recall within session (✅ C1/C6) | memory.ts / voice-journal | behavioural |
| K2 | **L02 episodic — a durable memory persisted persists across sessions** | episodic / asset-brain | db-effect + behavioural |
| K3 | **L02 recall — a stored episodic memory is injected next turn** | episodic / asset-brain | structural |
| K4 | L03 semantic — a similar PAST journal entry surfaces | journal-recall / voice-journal | behavioural |
| K5 | **L04 procedural — a proven fix procedure is injected for a fix-Q** | skill-library / asset-brain, shift | structural |
| K6 | **L05 cold-archive — a >18mo fact retrieves (B9 live)** | cold-archive / temporal-rag | behavioural |
| K7 | L06 prospective — a due follow-up surfaces (C7) | followups | behavioural |
| K8 | **L07 verified-state — asset one-truth state injected (no stale event)** | verified-state / asset-brain | structural |
| K9 | L06 enqueue — specialist `followups[]` actually queued | followups | db-effect |
| K10 | Summary collapse — buffer >12 turns → summary row written | memory.ts summarise | db-effect |
| K11 | **Per-identity isolation — my memory ≠ teammate's (RLS)** (C9) | memory key | security |

### L. Cross-agent path coverage (drive the agents the launcher can't) → dim `agent`/`rag`
| # | Probe | Agent path | Method |
|---|---|---|---|
| L1 | `asset-brain` answers grounded + cites (✅ B, via direct invoke) | asset-brain-query | behavioural |
| L2 | **`assistant` (7-agent orchestrator) fans out + synthesizes** | ai-orchestrator | behavioural |
| L3 | **`shift` handover composes from open jobs + checklist** | shift-planner-orchestrator | behavioural |
| L4 | **`analytics` orchestrator narrates KPIs in persona** | analytics-orchestrator | behavioural |
| L5 | **`project` orchestrator narrates progress** | project-orchestrator | behavioural |
| L6 | `voice-action` routes + slot-fills (✅ A) | voice-action-router | route |
| L7 | Agent isolation — `voice-journal` must NOT see episodic bank | gateway opt-in sets | structural (negative) |

### M. Model-chain resilience (fault injection) → dim `cost`/ops
| # | Probe | Wire | Method |
|---|---|---|---|
| M1 | Primary provider 429 → next provider, answer still lands | ai-chain fallback | fault-injection |
| M2 | All-providers-down → graceful degrade, conversation survives (I1) | ai-chain | fault-injection |
| M3 | Sticky session keeps a thread on one model | sessionKey | structural |
| M4 | 413 (prompt too large) → skip, not fatal | ai-chain | fault-injection |
| M5 | Token/latency budget — no runaway (I4) | context-budget | behavioural |

### N. Persona-contract wiring (the persona IS the spec) → dim `persona`
| # | Probe | Wire | Method |
|---|---|---|---|
| N1 | Each mode builds the right block (conversational/companion/narrated/signature/silent) | persona.ts buildPersonaBlock | structural |
| N2 | CANONICAL_ANCHOR + WORKHIVE_DOCTRINE + CONVERSATION_RECALL present in conversational+companion | persona.ts | structural (L9 guards this) |
| N3 | DOMAIN_LENS bridge present per persona | persona.ts | structural (L8) |
| N4 | Account/hive persona hydration flows profile→ctx→prompt | gateway P4/P5 | behavioural |
| N5 | Client mirror parity (wh-persona.js == persona.ts keys) | persona contract L7 | structural |

### O. Persona-Knowledge Layer (L08) wiring → dim `rag`/`persona`/`memory`
The NEW 8th memory layer (added 2026-06-12, see §8). A per-persona curated DOMAIN knowledge base — the
personas' SKILL.md sources + free external authoritative standards, contextually chunked and embedded, retrieved
**persona-scoped** at inference. Closes the gap that `DOMAIN_LENS` only *names* the wells but never RETRIEVES
them. Built entirely from existing infra (`skill_knowledge`/`knowledge_graph_facts` pgvector, `embedding-chain`
Voyage→Jina 384-dim, `day5_extract_kg_facts.py` + `ingest_user_pdfs.py` ingestion, `skill-library.ts` retrieval
pattern). Ingestion probes are db-effect/offline; retrieval probes drive the launcher LIVE.

| # | Probe | Wire | Method |
|---|---|---|---|
| O1 | Skill.md ingestion — maintenance-expert SKILL.md → technical-scope chunks persisted w/ embeddings | ingest_persona_knowledge | db-effect |
| O2 | Contextual chunking — each chunk carries a prepended context header BEFORE embedding (Anthropic CR) | ingest contextual-chunk | structural + db-effect |
| O3 | External standards ingest — a free authoritative standard → shared-scope chunks | ingest external | db-effect |
| O4 | Embedding-dim consistency — chunks 384-dim, match the vector column (no dim drift) | embedding-chain | contract |
| O5 | Idempotent refresh — re-ingest unchanged = no dup; a CHANGED skill.md supersedes (Memento refresh loop) | ingest refresh | db-effect |
| O6 | **Persona-scoped retrieval — the SAME question yields a DIFFERENT corpus for Hezekiah (technical) vs Zaniah (strategic)** | persona-knowledge.ts scope | structural |
| O7 | **Domain grounding — a corpus-only fact (not in the user's data) surfaces + grounds in the persona answer** | gateway conversational wire | behavioural |
| O8 | Retrieval threshold — an off-domain Q retrieves nothing (below sim) → no block injected, no fabrication | retrieve threshold | behavioural (neg) |
| O9 | Token-budget cap — the injected DOMAIN KNOWLEDGE block respects the cap; no small-model window blowout | context-budget | structural/contract |
| O10 | **Persona isolation (neg) — Zaniah must NOT inject Hezekiah's technical-scope chunks (scope leak)** | scope filter | structural (neg)/security |
| O11 | **Conversational-path firing — the domain block fires on the FLOATING LAUNCHER (voice-journal), not only specialists (the actual gap)** | gateway opt-in | structural |
| O12 | Graceful degrade — embed provider down → no block, conversation still answers (best-effort, same as skill-library) | persona-knowledge best-effort | fault-injection |

---

## 3. Coverage gap map (wiring axis)

| Family | Wired functions | Probed today | Gap |
|---|---|---|---|
| J Pipeline | 26 stages | J5/J6 (rate-limit, unwrap) | **24 stages** — PII, gibberish, cache, cost, passthrough, hydrate |
| K Memory layers | 7 + persist/summary/isolation | L01, L03 (partial) | **L02/L04/L05/L07 entirely; K9/K10/K11** |
| L Cross-agent | ~7 agent paths | voice-journal, voice-action, asset-brain | **assistant/shift/analytics/project** |
| M Model chain | 5 | none (I-family never live) | **whole family** (needs fault injection) |
| N Persona wiring | 5 | N2/N3 (static L8/L9) | N1/N4 live, N5 |
| **O Persona-Knowledge (L08)** | **12 (NEW layer)** | **0 (un-built)** | **whole family — layer built in W6–W7, probed live in W8** |

**Bottom line:** the behaviour battery (A–H) is strong. The **wiring battery went from ~13% to ~92% in one build
session (2026-06-12): wiring 8 → 57 of 62 — the roadmap target, HIT EXACTLY** (W0–W9, all driven LIVE via Playwright
MCP + superuser psql, mega green throughout). **Every family is lit; every named gap is CLOSED.** All 58 probe rows
are have/partial. The final 4 "documented" gaps were all closed live: **K6 cold-archive** (registered temporal-rag
as a gateway route + seeded a >18mo period summary → retrieved live), **L4 analytics** (gateway phase-adapter +
analytics prose-surface + edge /etc/hosts patch for python-api → grounded KPI narrative), **L5 project** (gateway
forwardExtras supplies phase+project_id → grounded progress narrative), **M3 sticky-session** (full wire verified
structurally end-to-end). The producer-less gap was CLOSED too (gateway memory distillation feeds K2/K9). The 5
uncovered of 62 are pipeline-census stages without a dedicated probe row (all functionally exercised), not breaks.
**13 real wiring fixes shipped + the entire L08 persona-knowledge layer built, all proven live.**

> **⚠ EPHEMERAL INFRA NOTE:** the L4 analytics fix depends on the edge container's `/etc/hosts` patch
> (`172.18.0.250 host.docker.internal`) which **resets on every edge-runtime restart** — re-apply it after each
> restart (see the runtime-restart checklist), or analytics 500s again. A durable fix needs `PYTHON_API_URL` to
> reach the edge env (currently `functions/.env` is ignored by this runtime). 7+ real wiring fixes shipped + proven live, plus the entire L08 layer built.

---

## 4. Build plan (highest-leverage first)

1. **Drive the un-probed agents** (Family L) — extend `__CSURF` with an agent param so the live battery can hit
   `assistant / shift / analytics / project / asset-brain` through the gateway, not just `voice-journal`. This
   single change unlocks L02/L04/L07 (they only fire for those agents) — the biggest coverage jump.
2. **Structural wire-probes (Family J + K3/K5/K8)** — assert the injected memory_block actually CONTAINS the
   episodic/procedural/verified-state section for the right agent (read the forwarded prompt via a debug echo or
   a gateway test-mode that returns the assembled `memory_block`). Deterministic, no LLM variance.
3. **DB-effect probes (K2/K9/K10, J9)** — after a turn, assert the row landed (`agent_episodic_memory`,
   `agent_followups`, `agent_memory` summary, `ai_cost_log`) via superuser psql — the method already proven this
   session (the C5 de-contamination used exactly this).
4. **Fault-injection (Family M)** — a gateway/ai-chain test hook to force a provider 429/down and assert
   fallback. Offline/ops lane, not the live LLM arm.
5. **Make it machine-readable** — extend `companion_probe_taxonomy.json` with the J–N families + an
   `assertion_method` field; the `probes` coverage layer then tracks wiring coverage as a forward-only number
   ("we wire-probe 8 of 50 functions").

---

## 5. Decisions needed (Ian)
- **Scope of family L:** do we drive ALL 5 un-probed agents live, or start with the 2 that wire the most layers
  (`asset-brain` = L02+L04+L07, `shift` = L02+L04+L07)? (Recommend: asset-brain + shift first — they cover 3 layers each.)
- **Test-mode echo:** OK to add a gateway `context.debug_echo_memory_block: true` (auth-gated, local-only) that
  returns the assembled `memory_block` so structural wire-probes are deterministic? (Needed for J1/K3/K5/K8.)
- **Dimension shape:** fold J→`cost`/ops + a new `pipeline` lens, K→`memory`, L→`agent`/`rag`, M→`cost`, N→`persona`;
  or add a first-class `wiring` dimension to the scorecard.

---

## 7. BUILD ROADMAP — sequenced so we don't drift

Ordered by **dependency + leverage**. Each phase is small, ends GREEN, and moves ONE forward-only number:
`wiring coverage = N of ~50 wires`. Rule (same as the behaviour flywheel): a phase isn't done until the probe
runs LIVE, the coverage ratchets up, the gate stays green, and the lesson lands in skills + memory. No phase
starts before the prior phase's acceptance gate passes.

> **Anchor invariants (apply to every phase):** local-only, never push to prod · always drive the REAL surface
> via Playwright MCP (or DB via superuser psql for db-effect) · deterministic-first grading · forward-only
> baseline · `_shared`/specialist edits need an edge restart (stop vector first for the cold compile).

### Phase W0 — Foundation: make wiring coverage measurable  *(no probes yet; prevents drift)*  ✅ DONE 2026-06-12
- **Status:** SHIPPED. `companion_probe_taxonomy.json` gained a top-level `wiring_axis` block (50 J–O probe rows,
  `wire_total: 62`, 8 covered: J5/J6/K1/K4/L1/L6/N2/N3); behaviour `probes[]` (A–I) untouched. `companion_dev.py`
  `probe_coverage()` emits a `wiring` block, `layer_probes()` prints `wiring: 8/62` (+ writes
  `companion_probe_coverage.json`), `status` shows a `Wiring coverage` cockpit line, and `--self-test` asserts the
  wiring SHAPE (not the count — so W1–W9 ratchet freely). **Acceptance verified:** `probes` prints `wiring: 8/62`;
  self-test PASS; mega PASS (8 dims active, delivery L0 PASS). Dark families today: M (model-chain), O (L08 un-built).
- **Do:** extend `companion_probe_taxonomy.json` with families **J/K/L/M/N + O** (O = the new L08 Persona-Knowledge
  layer, registered up front so its 12 wires read as 0-covered from day one — anti-drift). Each probe carries
  `{id, family, dimension, wire_target, assertion_method, agent, example, coverage}`; extend the `probes` coverage
  layer in `companion_dev.py` to count **wiring coverage** separately from behaviour ("wire-probe 8 of ~62").
- **Deliverables:** taxonomy rows (J–O) + a `wiring_coverage` block in `companion_probe_coverage.json` + a cockpit line.
- **Acceptance:** `companion_dev.py probes` prints `wiring: 8/62` (today's honest baseline; the +12 L08 wires are all
  un-built/missing); mega still PASS.
- **Size:** S. **Unlocks:** every later phase has a target to ratchet.

### Phase W1 — Cross-agent reach (Family L)  *(biggest unlock, no gateway code)*  ✅ DONE 2026-06-12
- **Status:** SHIPPED. `__CSURF` v1.4.0 gained an `agent`-mode (`_agentProbe`) — drives ANY gateway specialist
  (asset-brain/shift/analytics/project/assistant) with the body-shape adapter, not just the launcher's
  voice-journal. Driven LIVE via Playwright MCP (signed-in supervisor, Baguio hive). **The "gateway-404" did NOT
  reproduce as a 404** — root-caused live to THREE real adapter gaps, each fixed + re-verified mid-flight:
  1. **asset_tag → asset_id not resolved.** The gateway forwarded `context.asset_tag` (the documented contract) but
     asset-brain-query requires the asset_id UUID → 400 "Missing required fields". Fix: gateway resolves tag→id
     hive-scoped (`ASSET_ID_FORWARD_AGENTS`, `asset_nodes`) before forwarding. Live: tag-only AC-001 400→200 cited:5.
  2. **Unresolvable tag leaked a raw 400** ("Asset not found in this hive" class). Fix: graceful `ok()` not-found
     answer instead of a doomed forward. Live: bad tag → 200 "I couldn't find asset ZZ-999 in this hive…".
  3. **shift 400'd on missing `shift_window`, then returned "[object Object]".** Fix: gateway derives the current
     PHT shift window (`forwardExtras`); shift-planner surfaces the briefing PROSE as a top-level `answer` on the
     single-hive path. Live: shift → 200 grounded briefing ("top risk is AC-003 … 7 carried-forward entries").
     (NOTE: shift-planner is S6-retirement-flagged in STREAMLINE_ROADMAP — this fix migrates to the Action Brief
     engine if that fusion lands.)
- **Acceptance MET:** asset-brain + shift (and bonus: assistant) answer through the gateway live; L7 negative holds
  (source-confirmed voice-journal ∈ SEMANTIC_RECALL only, ∉ EPISODIC/VERIFIED_STATE/PROCEDURAL); **wiring 8→12/62**
  (L2/L3/J7 have, L7 partial); mega PASS. Reusable rule banked → ai-engineer + qa-tester skills.
- **Size:** M. **Unlocks:** L02/L04/L07 fire for asset-brain/shift now reachable — prerequisite for W2 (K2/K9/J9) + W3 (K3/K5/K8).

#### W1 ORIGINAL PLAN (for reference)
- **Do:** add an `agent` param to `__CSURF.runProbe` (default `voice-journal`) so the live battery can drive
  `asset-brain · shift · analytics · project · assistant` through the gateway. Author L1–L7 probes.
- **First target:** the **asset-brain gateway-404** found 2026-06-12 (same asset_id grounds via direct
  `asset-brain-query` but is "not found in this hive" via `agent:'asset-brain'`) — is the gateway passing the
  asset context wrong, or resolving the hive wrong? Fix or document.
- **Acceptance:** asset-brain + shift answer through the gateway live; L7 negative (voice-journal must NOT see
  the episodic bank) holds; wiring coverage +5.

### Phase W2 — DB-effect persistence probes (K2/K9/K10, J9)  *(deterministic, proven method)*  🟡 PARTIAL 2026-06-12
- **Status:** J9 ✅ + 2 findings. Drove asset-brain/shift/assistant via the gateway, asserted rows via superuser psql:
  - **J9 ✅ FIXED + PROVEN.** `ai_cost_log` had ZERO rows for gateway turns — root cause: asset-brain-query /
    ai-orchestrator / shift-planner all *import* `logAICost` but **never call it** (dangling import; only
    voice-journal-agent self-logs). Fix: central per-turn cost-log at the gateway (`logAICost` after
    `recordModelHop`, skip voice-journal to avoid double-count). Proven: a row
    `fn=asset-brain-query model=gateway:asset-brain-query 7/86 tok 4150ms` landed. wiring **12→13/62**.
  - **agent_memory saveTurn (P20) ✅** — shift/asset-brain/assistant turns persisted (the gateway-side persist wire works).
  - **K2/K9 ⛔ PRODUCER-LESS (finding, not yet provable).** The gateway PERSIST/ENQUEUE consumers are ready
    (`EPISODIC_MEMORY_AGENTS`/`FOLLOWUP_AGENTS` + a `…length` gate) but **no routine specialist emits
    `memories[]`/`followups[]`** — only `agentic-rag-loop` conditionally. Driven turns left `agent_episodic_memory`
    + `agent_followups` empty. To prove: enhance a specialist to emit, or drive an agentic-rag-loop path that does.
  - **K10 ⏳ not yet driven** — needs a >12-turn conversation to trigger the summary-collapse row.
- **Acceptance (revised):** J9 proven (+1); K2/K9 reframed as producer-less (a real wiring finding); K10 carried forward.
- **Size:** M. **Depends on:** W1. **Next:** decide K2/K9 producer fix; drive the 12-turn K10 probe.

### Phase W3 — Structural injection probes (J1, K3, K5, K8)  *(the rigorous core; touches the gateway)*  ✅ DONE 2026-06-12
- **Status:** SHIPPED. Added the auth-gated LOCAL-ONLY `context.debug_echo_memory_block` to ai-gateway — returns the
  PII-redacted forwarded message + assembled memory_block + a per-layer `sections` flag map + forward extras, with
  NO LLM call. Local-detection = `SUPABASE_URL` host is `kong/localhost/127.0.0.1` (prod is `*.supabase.co`), since
  this edge runtime does NOT read `functions/.env` (env-only gate couldn't enable locally). Triple-gated
  (local/env + authUid + explicit flag); guarded by `tools/validate_debug_echo_prod_safe.py` (PASS — prod-dead).
  **Proven live (each seed→flip discriminated):** J1 ✅ raw `tester@example.com` → `<email_1>` in the forwarded
  prompt; K8 ✅ seeded a `unified_events` row → `sections.verified_state` false→true + block carried "Verified asset
  state … AC-001 running normally"; K3 ✅ seeded `agent_episodic_memory` → `sections.episodic` false→true + block
  carried "aftercooler fouling". K5 🟡 partial — section-tracker proven, but `matchProcedures` is a pgvector RPC
  needing an EMBEDDED procedural memory (skill_library unseeded) → fold the proof into W6's embed pipeline.
  **Findings:** (a) `unified_events` is EMPTY platform-wide (L07 verified-state layer unseeded); (b) the working-
  memory block REPLAYS prior raw PII (per-turn redaction only covers the CURRENT message — historical turns echo
  unredacted to the LLM). **wiring 14→18/62.**
- **(original) Do:** add an **auth-gated, LOCAL-ONLY** `context.debug_echo_memory_block: true` to `ai-gateway` that returns
  the assembled `memory_block` (and which layer sections it contains) WITHOUT calling the LLM. Then assert: PII
  redacted in the forwarded prompt (J1), episodic section present for asset-brain (K3), procedural section for a
  fix-Q (K5), verified-state section for an asset turn (K8).
- **Guard:** the echo must be a no-op in prod (env-gated) + covered by a static validator so it can't leak.
- **Acceptance:** each layer's section deterministically asserted present/absent for the right agent; wiring +4.
- **Size:** M-L. **Depends on:** W1.

### Phase W4 — Model-chain fault injection (Family M)  *(ops lane, offline)*  ✅ DONE 2026-06-12
- **Status:** SHIPPED. Added a LOCAL-ONLY `faultInject` option to `ai-chain.ts callAI` (simulates a provider
  429/413/down via a no-network `continue`, gated on `_AI_CHAIN_LOCAL` = SUPABASE_URL host kong/localhost) + a
  gateway `context.debug_fault_inject` short-circuit (DEBUG_ECHO_ENABLED + authUid gated) that drives the chain and
  reports whether an answer landed. **Proven live** (local chain = groq→cerebras, the only keyed providers):
  M1 ✅ `{fail:[groq]}` → answer "OK" landed (cerebras served); M4 ✅ `{fail:[groq],mode:413}` → landed (413-skip
  falls through); M2 ✅ `{failAll:true}` → chain returns `{}` → `degraded:true` → gateway returns a graceful "AI
  service unavailable, message saved" (conversation survives). M3 🟡 partial (sticky-session present structurally —
  `setStickyModel`/`reorderChain` — but callAI returns content only, no provider-name observability for a
  deterministic single-model live proof). Guarded by the extended `validate_debug_echo_prod_safe.py` (asserts
  faultInject is `_AI_CHAIN_LOCAL`-gated + the gateway path is `DEBUG_ECHO_ENABLED`-gated). **Family M no longer
  dark; wiring 18→22/62.**
- **(original) Do:** a test hook in `ai-chain.ts` (env-gated) to force a provider 429/down; assert fallback lands an answer
  (M1), all-down degrades gracefully (M2), 413→skip (M4), sticky session holds (M3).
- **Acceptance:** fallback proven without the live free-tier flakiness; wiring +4.
- **Size:** M. **Depends on:** nothing (independent lane) — can run parallel to W2/W3.

### Phase W5 — Remaining pipeline + persona wiring (Family J rest, N, K11)  ✅ DONE 2026-06-12
- **Status:** SHIPPED (live). J3 ✅ gibberish guard ("asdfqwer…" → "couldn't make out… Pakiulit po", code-switched);
  J8 ✅ response-extract fallback (proven across shift/voice-action/voice-journal); K11 ✅ per-identity isolation
  (seeded a Bryan-Garcia episodic memory → Leandro's debug_echo block carried HIS memory, NOT Bryan's — no leak).
  N1 🟡 partial (all 5 buildPersonaBlock modes present; identity proven via D1/N2/N3); N4 🟡 partial (persona
  honored in answers); N5 🟡 partial (identities match + 4/5 modes; `wh-persona.js` lacks the server-only
  `signature` mode — flagged, likely intentional, not fixed). J4 adaptive cache left untested (needs a forced
  rate-limit). **wiring 22→28/62.**
- **(original) Do:** gibberish guard (J3), adaptive cache (J4), structured passthrough already covered (J7), response-extract
  fallback (J8); persona mode-build + hydration live (N1/N4), client-mirror parity (N5); **per-identity memory
  isolation** (K11 — my memory ≠ teammate's, the security wire).
- **Acceptance:** wiring coverage approaches the J–N ceiling; the remaining J–N gaps are documented infra-only.
- **Size:** M. **Depends on:** W0–W3.

### Phases W6–W8 — Persona Knowledge Layer (L08): BUILT + PROVEN  ✅ DONE 2026-06-12
- **W6 curate+ingest ✅** — NEW `persona_knowledge` table (migration `20260612000000`, recorded in schema_migrations)
  + `match_persona_knowledge` RPC (server-side scope filter). **Correction to a locked decision:** `skill_knowledge`
  is a WORKER-SKILL/competency table, NOT a doc store — so a dedicated `persona_knowledge` table was the right call
  (cleaner O10 isolation). `tools/ingest_persona_knowledge.py`: maintenance-expert SKILL.md → Hezekiah (38 technical
  chunks), analytics-engineer → Zaniah (26 strategic), ISO-14224/22400 → 3 shared; Anthropic-CR context header per
  chunk before embedding; idempotent + supersede. **O1–O5 db-proven** (67 chunks, headers present, 384-dim, re-run
  no-dup, hash-change supersedes).
- **W7 retrieve+wire ✅** — `_shared/persona-knowledge.ts` (mirrors skill-library): `scopesForPersona`
  (Hezekiah=technical+shared, Zaniah=strategic+shared, default=shared = the O6/O10 wire), token-capped block (O9),
  best-effort (O12). Wired into the gateway conversational path for `PERSONA_KNOWLEDGE_AGENTS` (voice-journal =
  the launcher = **the O11 gap**). `tools/validate_persona_knowledge_wiring.py` PASS (17 checks).
  **★ EMBEDDING-SPACE GOTCHA (cost me a debug cycle):** the first wire-up retrieved NOTHING — I ingested with Jina
  but the edge `generateEmbedding` queries with **Voyage** (its primary). Same 384 DIM, DIFFERENT model = meaningless
  cosine. Fix: the ingester must mirror `embedding-chain.ts` EXACTLY (Voyage `voyage-3.5-lite` `output_dimension:512`
  →slice 384, `input_type:document`); re-ingested, retrieval lit up. **Dim parity is necessary but NOT sufficient —
  the MODEL must match end-to-end.**
- **W8 live Family-O ✅** — driven via Playwright + the debug echo: **O6** (Hezekiah→maintenance-expert vs
  Zaniah→analytics-engineer, same Q different corpus); **O7** (real answer grounded in the ISO-22400 OEE corpus
  fact); **O8** (off-domain "weather" → no block); **O9** (block 469ch ≤ 950 cap); **O10** (Zaniah on a technical Q
  → NO technical-chunk leak, scope enforced in the RPC); **O11** (block FIRES on the floating launcher). O12
  structural (best-effort contract). **Family O: 11 have + 1 partial; wiring 28→40/62.**
- **(original) Do:** (a) **CURATE** the corpus — map SKILL.md files to personas (Hezekiah ← maintenance-expert + technical
  skills; Zaniah ← analytics-engineer + strategist skills) + pick free external authoritative standards
  (license-checked); (b) **SCHEMA** — add `persona_scope` (`technical|strategic|shared`) + `source_type` to
  `skill_knowledge` (reuse), or a focused `persona_knowledge` table if cleaner isolation is wanted; (c) build
  `tools/ingest_persona_knowledge.py` mirroring `day5_extract_kg_facts.py` / `ingest_user_pdfs.py` with **Anthropic
  Contextual Retrieval chunking** (prepend a one-line context header per chunk BEFORE embedding; 384-dim
  Voyage→Jina); (d) ingest.
- **Acceptance:** O1–O5 proven by superuser psql — technical/strategic/shared chunks land, contextual headers
  present, dims consistent, re-ingest idempotent + supersede on change. Wiring coverage **+5**.
- **Size:** M-L. **Depends on:** W0 (taxonomy registers O). **PARALLEL-OK** with W2–W4 (independent of the probe-wire work).

### Phase W7 — Persona Knowledge Layer (L08): Retrieve + Wire  *(build part 2; touches the gateway)*
- **Do:** `_shared/persona-knowledge.ts` (mirror `skill-library.ts`): embed the question, fetch top-k
  **persona-scoped** chunks above a similarity threshold; wire into ai-gateway's conversational/companion path as a
  **token-capped** `DOMAIN KNOWLEDGE` block — respect the ~2,081-token static-prompt budget, only inject when sim
  clears threshold. The persona scope filter is HARD (Zaniah cannot read technical-scope chunks). Edge restart
  (stop vector first). Add `validate_persona_knowledge_wiring.py` (mirror `validate_skill_library_wiring.py`).
- **Acceptance:** block injects on the launcher for the right persona, scope-filtered, capped; validator green;
  mega PASS. (Sets up O6–O12 to run live.)
- **Size:** M-L. **Depends on:** W6.

### Phase W8 — Persona Knowledge Layer: live probe Family O (Playwright MCP)
- **Do:** drive the REAL launcher live — O6 persona-scoped retrieval (Hezekiah vs Zaniah, same Q → different
  corpus), O7 domain grounding, O8 threshold/no-noise, O9 token cap, O10 isolation-negative (no scope leak), O11
  conversational-path firing (fires on the floating launcher, not only specialists), O12 graceful degrade.
- **Acceptance:** O6–O12 green live (O1–O5 already db-proven in W6); wiring coverage **+7**. L08 fully probed.
- **Size:** M. **Depends on:** W7 (and W1 if scope reuse needs the cross-agent param).

### Phase W9 — Full live battery sweep  *(the capstone Ian asked for)*  ✅ WIRING SWEPT TO 55/62 — 2026-06-12
- **Status:** The WIRING axis (J–O) was swept LIVE across W1–W9 (every family driven via Playwright MCP + superuser
  psql) — **wiring 8 → 55/62**, mega green throughout, no dark families. W9 closed: J2 PII-hydrate, J3 gibberish,
  J4 adaptive-cache (forced rate-limit → served_from:adaptive_cache), J11–J18 pipeline stages (CORS/auth/worker+
  persona-resolve/forward/turn-persist/journal-persist/model-hop), K2+K9 (the producer-less gap — wired a
  best-effort gateway memory-distillation that persists durable facts + queues follow-ups), K5/K7 (procedural +
  followup-surface by seed→flip), K11/L7 (isolation), M5 (budget), N1/N4/N5 (persona), O12. The behaviour axis
  (A–I) holds from the prior A–H live walk (118 probes, 3 bugs fixed) + the green mega graders.
- **Remaining 7 (documented, not wiring breaks):** K6 cold-archive (unbuilt + not gatewayed), L4 analytics
  (python-api infra), L5 project (needs project_id context), M3 sticky (no provider-name observability) — all
  recorded with evidence in `companion_probe_taxonomy.json`. **Deploy + commit gate on Ian.**
- **(original) Do:** run the ENTIRE battery in one pass via Playwright MCP through the real launcher (+ superuser psql for the
  db-effect persistence wires) — behaviour **A–I** + wiring **J–N** + persona-knowledge **O**. "After building the
  layer, run all of it."
- **Acceptance:** wiring coverage ratcheted to **~57 of ~62**; remaining gaps documented infra-only; gate green;
  skills + memory updated.
- **Size:** M. **Depends on:** W5 + W8.

---

## Phases W10–W13 — PERSONA KNOWLEDGE: ENRICH + KEEP FRESH (un-bind the personas from the platform)  📋 PLANNED 2026-06-12
> **The continuation Ian folded in (anti-drift), re-sequenced after the architecture Q&A.** L08 (W6–W9) proved the
> engine; today it's fed a thin starter diet (2 SKILL.md + 3 ISO defs = 67 chunks). W10–W13 make Hezekiah (technical
> expert) and Zaniah (strategist) genuinely deeper — **YOUR OWN content first**, kept **auto-fresh by CI**, then
> external sources **second (lower priority)**. **No retraining — it's retrieval.** Registers **Family O probes
> O13–O17** (denominator 62 → 67). See §8a (External-Corpus architecture) for the full design.
>
> **★ TWO LOCKED PRINCIPLES (from the 2026-06-12 architecture Q&A — apply to every phase below):**
> 1. **Two planes, never mixed.** `persona_knowledge` has NO `hive_id` → it is GLOBAL/cross-tenant. So ONLY the
>    persona's general BRAIN goes in: your skills + platform METHODOLOGY/doctrine (canonical OEE/MTBF/PM *definitions*,
>    maturity-stairs) + external references. **EXCLUDED:** ① live tenant data (a hive's logbook/assets — that is the
>    per-tenant plane L01–L07 + asset-brain, RLS-isolated; ingesting it = a multi-tenancy breach) and ② raw
>    code/architecture (implementation, not expertise). The persona FUSES brain + private context at inference.
> 2. **Own content first, external second.** Your 37 articles + 29 features + engineering guides + formula
>    definitions (already inventoried in `platform_catalog.json`) are the goldmine — zero license risk, on-brand,
>    already written. External standards are the *second* layer.

### Phase W10 — CHANNELS + drop-folder  *(the loaders — make the pipe accept anything, CI-ready)*  ✅ DONE 2026-06-12
- **Do:** extend `tools/ingest_persona_knowledge.py` so the SAME contextual-chunk → embed(384) → scope-tag →
  upsert pipeline accepts 3 inputs beyond SKILL.md: (1) **drop-folder** `persona_corpus/{hezekiah|zaniah|shared}/`
  where the FOLDER sets scope (O15); (2) **PDF** — pdfplumber extraction into THIS pipeline, not ingest_user_pdfs'
  industry_standards chain (O13); (3) **URL** — requests+bs4 default (CI-safe, no chromium), `--crawl4ai` opt-in (O14).
  Keep the Anthropic-CR header, idempotency + supersede, `source_type` (`skill_md|external_standard|pdf|url|platform_doc`,
  migration `20260612000001`). **An in-repo `persona_corpus/` is what makes W12's CI trigger possible.**
- **Acceptance:** ✅ O13/O14/O15 db-proven AND LIVE-proven through the real edge (debug_echo) — drop-folder vibration
  chunk top citation 84%/73%, PDF top 78%, URL (Wikipedia/RCM) 67%, shared LOTO 75%; re-ingest idempotent; scope
  isolation held. Wiring **+3 → 60/67**. **Size:** M.
- **★ Embedding-chain REVAMP (surfaced + fixed mid-phase, Ian-driven):** db-proof exposed that the edge
  `generateEmbedding` was a FLIP-PRONE fallback chain (Voyage→Jina→Gemini) and Voyage (no payment method) is
  throttled to **3 RPM** — so ingest and query landed in DIFFERENT vector spaces (cosine = noise, retrieval silently
  empty; LOTO/Zaniah missed live). **Fix (§8c):** per-corpus **pinned primary** (the embedding MODEL is a property of
  the CORPUS) — global stays Voyage (no platform-RAG regression), `persona_knowledge` pinned to **Gemini** (free, no
  card, 1,500 req/day, 384-dim, **batch-capable** = the "so many to embed" fix). Ingest revamped to batch all 5
  providers (gemini/voyage/jina + Cloudflare bge-small & self-host bge-local **wired-ready** for the durable upgrade);
  Mistral excluded (1024-dim). Corpus re-embedded to one Gemini space (80 rows); `validate_embedding_chain_consistency.py`
  guards it. All 4 live queries now retrieve deterministically (no flip).

### Phase W11 — CURATE YOUR OWN content  *(★ the goldmine, driven off `platform_catalog.json`)*  ✅ DONE 2026-06-12
- **W11b — Your published content (BUILT):** `ingest_platform_catalog()` reads `platform_catalog.json` → for each of
  the **37 learn articles** reads `learn/<slug>/index.html` (block-based `_html_text` extraction), and each feature's
  capability prose, → chunk → embed(gemini) → upsert as `source_type='platform_doc'`, scoped by a deterministic topic
  classifier (`classify_scope`: reliability/engineering → Hezekiah `technical`; ROI/KPI/strategy → Zaniah `strategic`;
  safety/onboarding/definitions → `shared`; PH-context is a flavour, NOT a scope). `--source platform` (folded into `all`).
- **Acceptance:** ✅ **corpus 80 → 381 (301 platform_doc chunks)**, one Gemini space, 0 NULL-embeddings. **O6/O7/O10
  re-proven LIVE** (debug_echo): Hezekiah "vibration on a budget" → `learn/vibration-analysis-on-a-phone-budget` 77%;
  "improve OEE" → Hezekiah gets `learn/what-is-oee-how-to-calculate` (technical) while Zaniah gets ISO-22400 + analytics
  SKILL (strategic) = **same Q, different corpus (O6)**; Zaniah never received a technical chunk (**O10**). The
  **②-exclusion** is a gate check in `validate_embedding_chain_consistency.py` (0 tenant UUIDs in the global brain).
- **3 bugs caught by the dry-preview + ingest (fixed):** (1) `_split_len` **truncated** any >1500-char single-paragraph
  block (HTML extraction yields one big block) → silently dropped ~80% of each article → fixed with `_hard_wrap`
  (sentence-split, never truncate); (2) scope classifier over-assigned `shared` (PH-context keywords) → rebalanced;
  (3) **Gemini free tier is ALSO request-rate-limited** (429 'exceeded quota' on a burst) → fixed with **big batches**
  (`EMBED_BATCH=96` → ~4 requests for the whole corpus) + 429 throttle/retry + the upsert backfills any row a 429 left
  un-embedded (and `_ingest_chunks` no longer persists dead rows). **Size:** M.
- **Note:** W11a (a separate curated METHODOLOGY set) is effectively covered — the maintenance/analytics SKILL.md
  (skill_md) + the articles already carry the canonical OEE/MTBF/PM definitions; no separate methodology corpus needed.

### Phase W12 — FRESHNESS engine  *(★ HIGH PRIORITY — the anti-staleness Ian asked about)*
- **Do:** (a) `reconcile_persona_corpus.py` — **add / update / SWEEP-orphans** against `platform_catalog.json` as the
  source of truth: catalog-has/corpus-lacks → INGEST; hash-changed → SUPERSEDE; **corpus-has/catalog-dropped → SWEEP**
  (the missing DELETE — retire a page, its chunks vanish; **O17**). (b) `validate_persona_corpus.py` — the gate (no
  ghost chunks, no gaps, dim/scope consistent, license-tag present) = a "persona-corpus grounding gate", mirroring the
  content-grounding-gate. (c) **GitHub Action** — on-merge to content paths (`learn/**`, `*.html`, `persona_corpus/**`)
  + a nightly cron safety net → auto reconcile + verify. (d) **Gap-harvest (O16):** an off-corpus question (O8 fired,
  nothing retrieved) → logged curation candidate → demand-driven growth (the Memento flywheel).
- **Acceptance:** O16 + O17 db-proven (a retired source's chunks are swept; an off-corpus Q becomes a candidate);
  validator green; the Action runs the reconcile on a merge. Wiring **+2**. **Size:** M. **Depends on:** W10–W11.

### Phase W13 — EXTERNAL sources  *(⬜ LOWER PRIORITY, per Ian — the second layer, ongoing)*
- **Do:** hand-pick **license-clean** (public-domain / CC / Ian-licensed) sources into the drop-folders via the W10 channels:
  - **Hezekiah `technical`** — ISO 14224/55001 + NFPA/API/IEEE excerpts (extend `day6_more_free_standards.py`),
    public-domain field manuals (US Army TM, NASA reliability practices), FMEA/RCM libraries, vibration/lubrication.
  - **Zaniah `strategic`** — RCM-strategy + maturity models, reliability ECONOMICS (cost-of-downtime, LCC), TPM/Lean,
    world-class OEE/MTBF benchmarks, KPI-design + prioritization.
  - **`shared`** — authoritative MTBF/MTTR/OEE definitions, safety/LOTO basics.
- **Acceptance:** reuses O13/O14 (more chunks via the same channels); O6/O7 stay strong; O10 isolation holds.
  **Guardrail:** license-clean ONLY; quality over volume; same-embedding-model (Voyage). **Size:** M (curation-bound, ongoing).

### Sequencing summary
```
W0 (foundation: J–O registered) ─┬─> W1 (cross-agent) ─┬─> W2 (db-effect)
                                  │                     └─> W3 (structural echo) ─> W5 ──────────┐
                                  ├─> W4 (fault-injection, parallel)                            ├─> W9 (full sweep) ✅
                                  └─> W6 (L08 curate+ingest) ─> W7 (retrieve+wire) ─> W8 (live probe) ─┘
                                                                                          │
   W10 (CHANNELS: drop-folder/PDF/URL, CI-ready)
        └─> W11 (CURATE YOUR OWN content: methodology + 37 articles/guides)  ◄── HIGH
               └─> W12 (FRESHNESS: reconcile/sweep + validator + GitHub Action + gap-harvest)  ◄── HIGH
                      └─> W13 (EXTERNAL standards/handbooks)  ◄── LOWER, ongoing
```
**W0–W9 DONE = wiring 8 → 57 of 62 (target hit).** W10–W13 grow the denominator to **67**, ratcheting back toward
**~65/67**: own content FIRST (W11), kept auto-fresh by CI (W12), external SECOND (W13). Tenant data + raw code stay
out by design (the two-planes principle). Deploy stays local; prod push gates on Ian.

---

## 6. Changelog
- **2026-06-12** — Study authored. Wiring inventory grounded in `ai-gateway/index.ts` + the 27 `_shared` modules +
  58 specialists. Headline: the live battery exercises ~2 of 7 memory layers + 3 of ~7 agent paths; J–N families
  defined to close the wiring gap. Builds on COMPANION_PROBE_TAXONOMY.md (behaviour axis).
- **2026-06-12 (build session)** — **W0–W9 EXECUTED + ROADMAP TARGET HIT: wiring 8 → 57/62**, every family lit,
  mega green throughout, all driven LIVE via Playwright MCP + psql. 13 gateway/chain fixes + the L08 layer built +
  the producer-less gap closed. See phase markers (W0–W9 all ✅) + the §3 bottom line. ALL LOCAL, deploy gates on Ian.
- **2026-06-12 (external-corpus fold)** — **W10–W12 + Family O probes O13–O16 folded in** (Ian: "how to supercharge
  the knowledge & skills of my personas from outside sources… I don't want them bound only to my platform"). The
  L08 engine is source-agnostic, so external sources = feeding the same pipe, not a new subsystem. Added the 4
  ingestion channels (drop-folder / PDF / URL / SKILL.md), the per-persona source map, the gap-harvest refresh loop,
  and §8a (External-Corpus architecture). Denominator 62 → **66**; target ~64/66. PLANNED, not yet built — anti-drift.
- **2026-06-12 (re-sequence after architecture Q&A)** — **W10–W12 → W10–W13, + probe O17 (reconcile-sweep); denom
  66 → 67.** Three clarifications locked from Ian's questions: (1) **TWO PLANES** — `persona_knowledge` is global/no-
  hive_id, so ONLY the persona BRAIN (skills + platform methodology/doctrine + external) goes in; live tenant data
  (L01–L07 + asset-brain, RLS) and raw code are EXCLUDED (multi-tenancy + noise). (2) **OWN CONTENT FIRST** — the 37
  articles + 29 features + guides + formula definitions (already in `platform_catalog.json`, currently UNUSED by the
  personas) are W11 (HIGH); external standards demoted to W13 (LOWER). (3) **FRESHNESS = reconcile + verify + CI** —
  the current ingester does ADD+UPDATE but not DELETE; W12 adds `reconcile_persona_corpus.py` (mark-and-**sweep**
  orphans against `platform_catalog.json`) + `validate_persona_corpus.py` + a **GitHub Action** (on-merge + nightly),
  i.e. the content-grounding-gate pattern pointed at the persona brain. Still PLANNED, not built — anti-drift.
- **2026-06-12 (W10 BUILT + EMBEDDING-CHAIN REVAMP)** — **W10 channels built + LIVE-proven** (O13 pdf / O14 url /
  O15 drop-folder → wiring 57→60/67). The db-proof surfaced a latent platform issue: the edge embedding chain was a
  flip-prone fallback (Voyage→Jina→Gemini) and Voyage with no payment method is throttled to **3 RPM**, so ingest and
  query diverged across vector spaces → silent-empty retrieval. **Revamp (§8c, Ian-driven "revamp our
  embedding-chain"):** per-corpus pinned primary (`EMBEDDING_PRIMARY` global=voyage unchanged;
  `PERSONA_KNOWLEDGE_EMBED_MODEL`=gemini for this corpus), **batched** multi-provider ingest (gemini/voyage/jina
  active; Cloudflare bge-small + self-host bge-local wired-ready; Mistral excluded = 1024-dim), corpus re-embedded to
  ONE Gemini space (80 rows), `validate_embedding_chain_consistency.py` added. All 4 live persona queries now retrieve
  deterministically (LOTO + Zaniah, which flipped before, now solid). LOCAL/uncommitted.
- **2026-06-12 (W11 BUILT — own content)** — `ingest_platform_catalog()` ingests the **37 learn articles + feature
  capabilities** from `platform_catalog.json` as `platform_doc`, topic-scoped. **Corpus 80 → 381** (301 platform_doc),
  one Gemini space, 0 NULL. O6/O7/O10 re-proven live (Hezekiah cites your own articles 64–77%; same-Q→different-corpus;
  isolation held). Dry-preview caught 3 bugs (a chunker truncation that dropped ~80% of each article, scope
  over-sharing, Gemini free-tier 429) — all fixed (hard-wrap, rebalanced classifier, big-batch+throttle+backfill). The
  two-planes ②-exclusion is now a gate check (0 tenant UUIDs). LOCAL/uncommitted. **NEXT: W12 freshness** (reconcile/
  sweep O17 + validator + GitHub Action) — now that own content is in, staleness is the risk to close.
- **2026-06-12 (same session)** — **L08 Persona-Knowledge Layer folded in** (Ian: "since we will have a new layer,
  extend the live test probe on this one, not just 2–5 tests… fold this to our roadmap first, then plan the test…
  after building this layer we will run the Playwright MCP all of it"). Added **Family O** (12 probes, equal weight
  to J–N), build+probe phases **W6–W9**, and §8 (the layer architecture). Wiring denominator 50 → 62. External
  grounding: Anthropic Contextual Retrieval (chunk-context before embed, −35–67% retrieval failures), Hermes Agent
  / Zep / Letta / Mem0 landscape (validate the existing stack; borrow framing not code). Reframe honored: this is a
  RAG knowledge-base build, NOT fine-tuning (ai-engineer SKILL.md §816). Builds on the existing ingestion infra
  (`day5_extract_kg_facts.py`, `ingest_user_pdfs.py`, `skill_knowledge`/`knowledge_graph_facts` pgvector,
  `embedding-chain` Voyage→Jina 384-dim, `skill-library.ts`).

---

## 8. L08 — the Persona Knowledge Layer (architecture)

**The gap it closes:** `persona.ts` `DOMAIN_LENS` *names* each persona's knowledge wells ("Hezekiah's depth pulls
from maintenance-expert SKILL.md…") but that is **prompt-level pointing, not retrieval** — the SKILL.md content is
never embedded or fetched, and the conversational personas on the floating launcher retrieve only the worker's own
data, no authoritative domain corpus. L08 makes the wells real: a curated, persona-scoped, embedded knowledge base
the personas actually retrieve from at inference. It is the **Memento pattern pointed at domain expertise**:
curate → contextual-chunk → embed → deterministic persona-scoped retrieval → refresh on source change.

**Built from existing parts (≈70% already in place):** `knowledge_graph_facts` (platform + hive KG),
`fault_knowledge`/`skill_knowledge`/`pm_knowledge` (pgvector 384-dim), `day5_extract_kg_facts.py` +
`day6_more_free_standards.py` (external-standards ingestion), `tools/ingest_user_pdfs.py` (PDF ingestion),
`embedding-chain.ts` (Voyage→Jina), `skill-library.ts` + `match_procedural_memories` (semantic retrieval pattern),
`validate_kg_scope_split.py` / `validate_pgvector_consistency.py` (scope + dim gates).

**The 3 genuinely-new pieces:**
1. **Persona-scoped routing** — a `persona_scope` (`technical|strategic|shared`) tag so Hezekiah pulls technical
   chunks, Zaniah pulls strategic, both pull shared. Today nothing is persona-tagged.
2. **SKILL.md as a source** — `day5` ingests standards, never your skills. maintenance-expert ↔ Hezekiah and
   analytics-engineer ↔ Zaniah map 1:1; ingesting them is the richest, most on-brand corpus available.
3. **Conversational-path wiring** — domain RAG today serves specialists (asset-brain), NOT the floating launcher
   where the personas live. L08 wires a token-capped `DOMAIN KNOWLEDGE` block into the conversational/companion path.

**Pipeline:**
```
CURATE → CONTEXTUAL-CHUNK → EMBED → PERSONA-SCOPED RETRIEVE → tight prompt block
 skills/*.md   (Anthropic-CR     (Voyage→Jina   (persona_scope          (token-capped,
 + free         context header    384-dim)       technical|strategic|    threshold-gated;
 standards      per chunk)                        shared filter)          respects ~2,081-tok budget)
 + PDFs
```

**Hard constraints (from accumulated lessons):**
- **NOT fine-tuning** — deterministic RAG assets only (ai-engineer §816).
- **Token budget** — the static prompt is already ~2,081 tok (≈101% of the small fallback model's window); the
  domain block is tightly capped and only fires above a similarity threshold (ai-engineer prompt-budget lesson).
- **384-dim only** — match the embedding column or Postgres throws on insert (pgvector dimension lesson).
- **Best-effort** — embed/RPC miss returns "" so the gateway proceeds without the block (same contract as
  `skill-library.ts` / episodic recall / verified-state).
- **Scope isolation is a security wire** — a strategist must never receive technical-scope chunks (O10).

**External grounding (what we borrowed):** Anthropic Contextual Retrieval (prepend chunk context before embedding,
the O2 wire) · Hermes Agent / Zep / Letta / Mem0 surveyed — they validate the existing 7-layer stack; we borrow
*framing* ("skills as first-class retrievable knowledge"), not their code, since the native infra already exists.

---

### 8a. External-Corpus extension (W10–W12) — un-binding the personas from the platform
> Ian (2026-06-12): *"how to supercharge the knowledge & skills of my personas from outside sources… I don't want
> them bound only to what I have in my platform — Zaniah as a strategist, Hezekiah as an expert."* Folded as W10–W12.

**Key insight:** the L08 engine (W6–W9) is source-agnostic. A persona's expertise = *whatever is in its scope*. So
"un-bind from the platform" is NOT a new subsystem — it's **feeding the same pipe richer external sources.** Drop a
reliability handbook into `technical` → Hezekiah is deeper; drop a strategy framework into `strategic` → Zaniah is
sharper. No retraining; retrieval.

**Mental model — 3 inputs → 1 scoped brain per persona:**
```
  YOUR SKILLS (.md)  ─┐
  EXTERNAL SOURCES   ─┼─► contextual-chunk ─► embed(Voyage 384) ─► persona_knowledge
  YOUR PLATFORM DATA ─┘         (scope: technical / strategic / shared)
                                         │
                 Hezekiah ◄── technical + shared ──┤  (server-side scope filter = the O10 isolation wire)
                 Zaniah   ◄── strategic + shared ──┘
```

**The 4 ingestion channels (all flow through the SAME chunk→embed→scope pipeline; only the loader differs):**
| Channel | Source | `source_type` | Status |
|---|---|---|---|
| SKILL.md | your accumulated skills | `skill_md` | ✅ W6 |
| Drop-folder (.md/.txt) | curated standards/frameworks/notes; FOLDER = scope | `external_standard` | 🔨 W10 (O15) |
| PDF | handbooks / manuals / standards (reuse `ingest_user_pdfs.py`) | `pdf` | 🔨 W10 (O13) |
| URL | open docs/articles (`crawl4ai` → clean markdown) | `url` | 🔨 W10 (O14) |

**The drop-folder UX (the "Memento" instinct made concrete):**
```
persona_corpus/
  hezekiah/   (→ technical)   *.md  *.pdf
  zaniah/     (→ strategic)   *.md  *.pdf
  shared/                     *.md  *.pdf
```
Drop a file → `ingest_persona_knowledge.py` → live for that persona. Idempotent + supersede-on-change already built,
so editing a source just refreshes its chunks. **W12 gap-harvest** closes the loop: an off-corpus question (O8 fired,
nothing retrieved) is logged as a curation candidate → real demand tells you which external source to add next.

**The source map (the CURATE step — the real value, per persona):**
- **Hezekiah `technical`:** authoritative standards (ISO 14224/55001, NFPA/API/IEEE excerpts), public-domain field
  manuals & reliability handbooks (US Army TM, NASA practices), FMEA/RCM failure libraries, vibration/lubrication.
- **Zaniah `strategic`:** maintenance-strategy frameworks (RCM logic, maturity models), reliability ECONOMICS
  (cost-of-downtime, LCC), TPM/Lean pillars, world-class OEE/MTBF benchmarks, KPI-design & prioritization.
- **`shared`:** MTBF/MTTR/OEE vocabulary, safety/LOTO basics, **Philippine context (PEC 2017, DOLE OSH)** = the moat.

**Guardrails (non-negotiable):** license-clean ONLY (public-domain / CC / Ian-licensed / Ian's own — curate excerpts,
never bulk-ingest copyrighted books) · scope isolation is the O10 security wire · the existing token-cap + similarity
threshold keep a fat corpus from blowing the prompt or injecting noise · **embed with the same model (Voyage)
end-to-end** (the W7 trap). Quality over volume: a 40-chunk hand-picked set beats 4,000 scraped ones.

**New probes (Family O extension): O13** PDF→scoped chunks (db) · **O14** URL→scoped chunks (db) · **O15** drop-folder
scope-routing (struct) · **O16** gap-harvest candidate (db, the self-improving loop) · **O17** reconcile-sweep (db,
retired source → chunks removed). Denominator 62 → 67.

### 8b. Two planes (the multi-tenancy guardrail) + the freshness engine *(locked 2026-06-12)*

**TWO PLANES — never mixed.** `persona_knowledge` has **no `hive_id`** → it is GLOBAL, shared across every
customer/hive. That single fact governs what may enter:
```
  GLOBAL  BRAIN  (persona_knowledge, no hive_id)        PER-TENANT CONTEXT (RLS-isolated)
  ├─ your SKILL.md                                       ├─ this hive's logbook / assets / PM
  ├─ platform METHODOLOGY/doctrine (OEE/MTBF defs)       ├─ this worker's history
  └─ external references                                 └─ served by L01–L07 + asset-brain RAG
        │ same for every customer                              │ different per customer
        └──────────────── fused at inference ─────────────────┘
```
- ✅ **In:** skills + platform **methodology** (canonical *definitions/formulas*, doctrine, maturity-stairs) + external.
- ❌ **Out:** ① **live tenant data** (ingesting a hive's numbers into a global table = one customer's data leaking
  into another's persona answers = a multi-tenancy breach) · ② **raw code/architecture** (implementation, not expertise).
- A **W11 static check** asserts no ingested chunk is tenant-keyed; the O10 scope filter remains the security wire.

**OWN CONTENT IS THE GOLDMINE (currently UNUSED).** As of 2026-06-12 the personas run on 67 chunks (2 SKILL.md +
3 ISO). Your **37 learn articles + 29 feature pages + engineering guides + formula definitions** are *already written,
already inventoried in `platform_catalog.json`*, and **not fed to the personas at all** (the catalog is used for
content-drift detection + the analytics engine uses formulas to COMPUTE, but the personas never RETRIEVE any of it).
W11 ingests your own content FIRST (zero license risk, on-brand); W13 external is the second layer.

**FRESHNESS = reconcile + verify + CI (the anti-staleness engine).** Today's ingester does ADD + UPDATE
(hash-supersede) but **not DELETE** → a retired page leaves ghost chunks. The fix mirrors the existing
content-grounding-gate, pointed at the persona brain:
```
  live platform ──(content-gate regenerates)──► platform_catalog.json  (SOURCE OF TRUTH manifest)
                                                        │
                          reconcile_persona_corpus.py:  catalog⊃corpus → INGEST · hash≠ → SUPERSEDE
                                                        ·  corpus⊃catalog → SWEEP (O17, the missing DELETE)
                                                        │
                          validate_persona_corpus.py  (gate: no ghosts, no gaps, dim/scope/ license-tag)
                                                        │
                          GitHub Action: on-merge(learn/**, *.html, persona_corpus/**) + nightly cron
```
Retire a page → it drops from the catalog → next reconcile **sweeps** its chunks → the persona can never cite a dead
page. The in-repo `persona_corpus/` (W10) makes the Action trigger on a commit; the nightly cron is the safety net.

### 8c. The embedding-chain revamp — per-corpus pinned model + batch ingest *(built 2026-06-12)*
> Surfaced by W10's db-proof, fixed on Ian's "revamp our embedding-chain." The single most important correctness
> property for any pgvector retrieval, made structural.

**The bug class (proven live):** `_shared/embedding-chain.ts` was a *flip-prone fallback chain*
(`generateEmbedding` tried Voyage→Jina→Gemini, first success wins). Two independent facts combined into silent
failure: (1) **Voyage with no payment method is throttled to 3 RPM** (its 429 says so), and (2) the gateway fires
**~2 embeds per turn** (semantic-recall + persona-knowledge). So a rapid ingest *or* a busy turn exhausts Voyage and
**fails over to a different provider = a different vector space**. A corpus embedded with model A but queried with
model B makes cosine similarity noise → retrieval returns nothing, with **no error** (LOTO + Zaniah missed live).
This is the W7 trap as a *systemic* property of a shared fallback chain, not a one-off.

**The fix — the embedding MODEL is a property of the CORPUS, pinned, never inferred:**
```
  generateEmbedding(text, pin?)   pin overrides EMBEDDING_PRIMARY for THIS call
  ────────────────────────────────────────────────────────────────────────────
  global default     EMBEDDING_PRIMARY = 'voyage'   → every EXISTING corpus
                     (fault/pm/asset-brain/semantic-search) unchanged, no regression
  persona_knowledge  PK_EMBED_MODEL    = 'gemini'   → loadPersonaKnowledge pins gemini,
                     and tools/ingest_persona_knowledge.py --embed-model gemini ingests gemini
                     → ingest & query in ONE space, in lock-step
  fallback still happens (no 500 on outage) but logs a loud SPACE-DIVERGENCE warning
```
- **Why Gemini for persona_knowledge:** only generous free tier with a key already on hand — 1,500 req/day, 10M
  tok/min, **no credit card**, 384-dim, and **batch-capable**. Batching (`EMBED_BATCH` texts per API call) is what
  makes "so many to embed" practical: the 38-chunk maintenance skill embeds in ~2 calls, not 38.
- **All providers included, one excluded:** the ingest tool batches **gemini / voyage / jina** (active) plus
  **Cloudflare bge-small** + **self-host bge-local** (`fastembed`/sentence-transformers) — both the SAME
  `bge-small-en-v1.5` model (384-dim native) so local-ingest and edge-query share a space. **Mistral is excluded** —
  `mistral-embed` is 1024-dim, incompatible with `vector(384)`.
- **The durable upgrade path (Ian's pick, wired-ready):** add a Cloudflare token → set `EMBEDDING_PRIMARY`/
  `PERSONA_KNOWLEDGE_EMBED_MODEL=cloudflare` → re-ingest `--embed-model bge-local` (unlimited free, no RPM) → the
  edge queries the same model via Cloudflare. One coherent bge-small space, fully free, no card, decoupled from Voyage.
- **Guard:** `tools/validate_embedding_chain_consistency.py` asserts the ingest default == the edge pin, the chain is
  pinned + warns on divergence, Mistral is absent, and (live) `persona_knowledge` sits in exactly ONE embedding space.
- **Deploy note:** prod edge currently runs Voyage+Jina secrets; pinning persona to gemini in prod needs
  `GEMINI_API_KEY` (and optionally `PERSONA_KNOWLEDGE_EMBED_MODEL`) as deployed edge secrets, else it fails over.
