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

---

## 3. Coverage gap map (wiring axis)

| Family | Wired functions | Probed today | Gap |
|---|---|---|---|
| J Pipeline | 26 stages | J5/J6 (rate-limit, unwrap) | **24 stages** — PII, gibberish, cache, cost, passthrough, hydrate |
| K Memory layers | 7 + persist/summary/isolation | L01, L03 (partial) | **L02/L04/L05/L07 entirely; K9/K10/K11** |
| L Cross-agent | ~7 agent paths | voice-journal, voice-action, asset-brain | **assistant/shift/analytics/project** |
| M Model chain | 5 | none (I-family never live) | **whole family** (needs fault injection) |
| N Persona wiring | 5 | N2/N3 (static L8/L9) | N1/N4 live, N5 |

**Bottom line:** the behaviour battery (A–H) is now strong, but the **wiring battery is ~15% covered.** The
companion has ~50 distinct internal wires; we directly probe ~8.

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

### Phase W0 — Foundation: make wiring coverage measurable  *(no probes yet; prevents drift)*
- **Do:** extend `companion_probe_taxonomy.json` with families **J/K/L/M/N** (each probe `{id, family, dimension, wire_target, assertion_method, agent, example, coverage}`); extend the `probes` coverage layer in `companion_dev.py` to count **wiring coverage** separately from behaviour ("wire-probe 8 of ~50").
- **Deliverables:** taxonomy rows + a `wiring_coverage` block in `companion_probe_coverage.json` + a cockpit line.
- **Acceptance:** `companion_dev.py probes` prints `wiring: 8/50` (today's honest baseline); mega still PASS.
- **Size:** S. **Unlocks:** every later phase has a target to ratchet.

### Phase W1 — Cross-agent reach (Family L)  *(biggest unlock, no gateway code)*
- **Do:** add an `agent` param to `__CSURF.runProbe` (default `voice-journal`) so the live battery can drive
  `asset-brain · shift · analytics · project · assistant` through the gateway. Author L1–L7 probes.
- **First target:** the **asset-brain gateway-404** found 2026-06-12 (same asset_id grounds via direct
  `asset-brain-query` but is "not found in this hive" via `agent:'asset-brain'`) — is the gateway passing the
  asset context wrong, or resolving the hive wrong? Fix or document.
- **Acceptance:** asset-brain + shift answer through the gateway live; L7 negative (voice-journal must NOT see
  the episodic bank) holds; wiring coverage +5.
- **Size:** M. **Unlocks:** L02/L04/L07 only fire for these agents — this is the prerequisite for K3/K5/K8.

### Phase W2 — DB-effect persistence probes (K2/K9/K10, J9)  *(deterministic, proven method)*
- **Do:** after a driven turn, assert the row landed via superuser psql — `agent_episodic_memory` (K2),
  `agent_followups` (K9), `agent_memory` summary row at >12 turns (K10), `ai_cost_log` (J9). (Method already
  used this session to de-contaminate C5.)
- **Acceptance:** each persistence wire proven to write; wiring coverage +4. No LLM variance (db truth).
- **Size:** M. **Depends on:** W1 (need to drive the agents that persist episodic/followups).

### Phase W3 — Structural injection probes (J1, K3, K5, K8)  *(the rigorous core; touches the gateway)*
- **Do:** add an **auth-gated, LOCAL-ONLY** `context.debug_echo_memory_block: true` to `ai-gateway` that returns
  the assembled `memory_block` (and which layer sections it contains) WITHOUT calling the LLM. Then assert: PII
  redacted in the forwarded prompt (J1), episodic section present for asset-brain (K3), procedural section for a
  fix-Q (K5), verified-state section for an asset turn (K8).
- **Guard:** the echo must be a no-op in prod (env-gated) + covered by a static validator so it can't leak.
- **Acceptance:** each layer's section deterministically asserted present/absent for the right agent; wiring +4.
- **Size:** M-L. **Depends on:** W1.

### Phase W4 — Model-chain fault injection (Family M)  *(ops lane, offline)*
- **Do:** a test hook in `ai-chain.ts` (env-gated) to force a provider 429/down; assert fallback lands an answer
  (M1), all-down degrades gracefully (M2), 413→skip (M4), sticky session holds (M3).
- **Acceptance:** fallback proven without the live free-tier flakiness; wiring +4.
- **Size:** M. **Depends on:** nothing (independent lane) — can run parallel to W2/W3.

### Phase W5 — Remaining pipeline + persona wiring (Family J rest, N, K11)
- **Do:** gibberish guard (J3), adaptive cache (J4), structured passthrough already covered (J7), response-extract
  fallback (J8); persona mode-build + hydration live (N1/N4), client-mirror parity (N5); **per-identity memory
  isolation** (K11 — my memory ≠ teammate's, the security wire).
- **Acceptance:** wiring coverage approaches ~45/50; the remaining gaps are documented infra-only.
- **Size:** M. **Depends on:** W0–W3.

### Sequencing summary
```
W0 (foundation) ─┬─> W1 (cross-agent) ─┬─> W2 (db-effect)
                 │                      └─> W3 (structural echo) ─> W5 (pipeline+persona)
                 └─> W4 (fault-injection, parallel)
```
**Done = wiring coverage ratcheted from ~8 to ~45 of ~50, every wire probed live or by db-effect, gate green,
skills+memory updated each phase.** Deploy stays local; prod push gates on Ian.

---

## 6. Changelog
- **2026-06-12** — Study authored. Wiring inventory grounded in `ai-gateway/index.ts` + the 27 `_shared` modules +
  58 specialists. Headline: the live battery exercises ~2 of 7 memory layers + 3 of ~7 agent paths; J–N families
  defined to close the wiring gap. Builds on COMPANION_PROBE_TAXONOMY.md (behaviour axis).
