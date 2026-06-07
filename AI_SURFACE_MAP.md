# AI Surface Map + Companion Unification Roadmap

_Audit date: 2026-06-07. Status: MAP ONLY — no code changed. Author: AI Engineer pass._

> **Why this exists:** "Pages that use AI" feel scattered and confusing. This document
> is the single source of truth for **every AI touchpoint on the platform**, why they
> feel fragmented, and the migration order to unify them under one **AI Companion**
> (Hezekiah / Zaniah) without collapsing real tools into a chat box.

---

## TL;DR

There are **three tiers** of AI surface. Tier 1 is already unified. Tiers 2 and 3 are the confusion.

| Tier | What | Count | State |
|---|---|---|---|
| **1. Floating Companion** | `companion-launcher.js` chat bubble + lazy `voice-handler.js` mic | 32 pages | ✅ Already one persona, one backend (`ai-gateway`) |
| **2. Dedicated companion pages** | `assistant.html`, `voice-journal.html` | 2 pages | ⚠️ Same face, **two different brains** (`ai-orchestrator` vs `ai-gateway`) |
| **3. Inline per-feature AI** | bespoke buttons/panels per page | ~14 features | 🔴 No persona, no shared memory, each its own edge fn |

**The fix is NOT "put everything in the chat bubble."** It's: **one brain + one persona + one memory** that can *chat* AND *invoke the specialist tools*. Tools keep their pages.

---

## The Companion today — it's 4 scripts, not 1

| Script | Role | Backend |
|---|---|---|
| [companion-launcher.js](companion-launcher.js) | Floating text chat widget (the bubble). Page-context hints, cross-page localStorage history, RAG-light `setContext`, bridge button to `assistant.html` | `ai-gateway` (agent `voice-journal`) |
| [voice-handler.js](voice-handler.js) | 7,800-line voice runtime: dialog state, intent routing, clarification ceiling, persona contract, `_LONG_HORIZON_RE` opt-in | `ai-gateway` → and `agentic-rag-loop` for long-horizon |
| [wh-persona.js](wh-persona.js) | Persona definitions (Hezekiah / Zaniah), `getCompanionBlock()`, `getCurrentPersona()` | — |
| [nav-hub.js](nav-hub.js) | Nav FAB; reveals the widget (`body.wh-hub-open`) and **lazy-loads `voice-handler.js`** on first voice use | — |

These four already cooperate well. The persona is consistent across them. **This tier is done.**

---

## Tier 1 — Floating Companion coverage (32 product pages)

`companion-launcher.js` is present on every real page **except** `index.html` (home) and `assistant.html` (which IS the full assistant):

```
hive, resume, inventory, logbook, marketplace, public-feed, report-sender,
pm-scheduler, engineering-design, audit-log, analytics-report, skillmatrix,
predictive, marketplace-seller-profile, marketplace-seller, marketplace-admin,
dayplanner, community, analytics, alert-hub, achievements, ph-intelligence,
asset-hub, project-manager, project-report, shift-brain, integrations,
voice-journal, platform-health, plant-connections, ai-quality, architecture
```

- Backend: `ai-gateway` agent `voice-journal` (free-tier Groq chain, PII redaction, rate-limit, cost log, agent_memory).
- Memory: `localStorage` global history key (carries chat page→page) — see "Memory split" below.
- Persona: `getCompanionBlock()` prepended; falls back to `zaniah`.

---

## Tier 2 — Dedicated companion pages (the split brain)

Same persona face, **different minds behind it**:

| Surface | Backend | Brain type | Memory |
|---|---|---|---|
| Floating widget (32 pages) | `ai-gateway` → voice-journal agent | conversational | localStorage history |
| [voice-journal.html](voice-journal.html#L1002) | `ai-gateway` → voice-journal agent + `voice-transcribe` + `tts-speak` | conversational | `agent_memory` (server) |
| [assistant.html](assistant.html#L856) | **`ai-orchestrator`** (7-agent fan-out) + `semantic-search` | analytical | none persisted client-side |

**Problem:** A worker chatting in the bubble gets "I don't have access to your records here," but the Assistant page *does*. Same avatar, contradictory capability. The bubble even has a **bridge button** that punts to `assistant.html` precisely because it can't answer data questions — a UX seam that exposes the split.

---

## Tier 3 — Inline per-feature AI (the real fragmentation)

Each is its own button/panel, its own edge function, **no persona, no shared memory**. Two sub-kinds:

### 3a. Conversational surfaces → SHOULD become the Companion in-context
| Page | Feature | Edge fn | Note |
|---|---|---|---|
| [asset-hub.html](asset-hub.html#L3487) | Asset Brain Q&A | `asset-brain-query` | Reinvents the widget's `setContext({key:'asset:<uuid>'})` |
| [hive.html](hive.html#L3702) | Reliability Coach / board AI | `ai-orchestrator` | This is exactly the widget's coach mode |

### 3b. Deterministic / structured tools → STAY tools, Companion can *invoke*
| Page | Feature | Edge fn(s) | Why it's a tool not a chat |
|---|---|---|---|
| [logbook.html](logbook.html#L4175) | Speak-to-Fill, Photo Defect, Tag OCR | `voice-logbook-entry`, `visual-defect-capture`, `equipment-label-ocr` | Fills form fields / OCR; WAT tool layer |
| [engineering-design.html](engineering-design.html#L10729) | Calc narrative, BOM/SOW | `engineering-calc-agent`, `engineering-bom-sow` | Deterministic math + structured doc |
| [asset-hub.html](asset-hub.html#L2693) | Weibull, P-F | `weibull-fitter`, `pf-calculator` | Pure math (not LLM) |
| [predictive.html](predictive.html#L431) / [analytics.html](analytics.html#L742) / [analytics-report.html](analytics-report.html#L588) | Risk + Action Plan | `analytics-orchestrator` | Structured analytics narrative |
| [shift-brain.html](shift-brain.html#L608) | Shift plan | `shift-planner-orchestrator` | Scheduled multi-agent doc |
| [alert-hub.html](alert-hub.html) | AMC daily brief | `amc-orchestrator` (5 sub-agents) | Scheduled brief |
| [project-manager.html](project-manager.html#L1716) / [project-report.html](project-report.html#L312) | Project AI | `project-orchestrator` | Structured project doc |
| [ph-intelligence.html](ph-intelligence.html#L502) | Benchmark report + API | `intelligence-report`, `intelligence-api` | Structured report |
| [resume.html](resume.html#L1032) | Resume extract / polish | `resume-extract`, `resume-polish` | Structured extraction; separate product |
| [report-sender.html](report-sender.html#L1513) | Voice report intent | `voice-report-intent`, `voice-transcribe`, `scheduled-agents` | Intent → report |

### Infra (not user-facing AI, listed for completeness)
`embed-entry`, `voice-embeddings`, `semantic-search`, `tts-speak`, `voice-transcribe`, `hierarchical-summarizer`, `semantic-fact-extractor`, `temporal-rag-orchestrator`, `data-fabric-normalizer`, `cold-archive-query`, `agent-memory-store`, `batch-risk-scoring`, `sensor-readings-ingest`.

---

## The three root causes of "it's confusing"

1. **Split brain (Tier 2):** the same persona answers from two different backends with different capabilities (`ai-gateway` vs `ai-orchestrator`).
2. **Memory split:** three stores that don't share — widget `localStorage`, voice-journal `agent_memory`, assistant nothing. A conversation doesn't follow the worker across surfaces.
3. **Persona-less Tier 3:** 14 inline features each speak in their own un-personalized voice, with their own UI affordance, so they don't read as "the Companion" at all.

> Good news: the **routing intelligence to fix #1 already exists** — `ai-gateway` can delegate, `ai-orchestrator` already function-call-routes to 7 agents, and `agentic-rag-loop` already classifies query context. The pieces are built; they're just entered from different doors.

---

## Target end-state

```
                         ┌──────────────────────────────┐
   Floating bubble ─────►│                              │
   Voice mic       ─────►│   ai-gateway  (ONE FRONT     │
   assistant.html  ─────►│   DOOR · ONE PERSONA ·       │
   Asset Hub Q&A   ─────►│   ONE MEMORY)                │
   Hive Coach      ─────►│                              │
                         │   internal router decides:   │
                         │   ├─ simple chat (callAI)     │
                         │   ├─ ai-orchestrator (7-agent)│
                         │   ├─ agentic-rag-loop (temporal)
                         │   └─ asset-brain-query (scoped)
                         └───────────────┬──────────────┘
                                         │ can INVOKE (function-calling)
                ┌────────────────────────┼───────────────────────────┐
                ▼                        ▼                           ▼
        engineering-calc /        voice-logbook-entry /        analytics /
        bom-sow / fmea            visual-defect / OCR          project / shift tools
        (stay as inline tools, Companion can trigger + narrate in persona)
```

**Principle:** Companion = the single conversational **front door**. Deterministic tools stay as inline features but become **invocable** by the Companion and **narrate in persona**. Nothing real gets deleted; the seams disappear.

---

## Migration roadmap (lowest blast radius first)

| Step | Change | Touches | Risk | Unlocks |
|---|---|---|---|---|
| **0** | _This map_ | — | none | Shared understanding |
| **1. Converge the brain** | Route `assistant.html` through `ai-gateway`; gateway internally delegates to `ai-orchestrator`/`agentic-rag-loop` by its existing router (instead of the client picking the door) | `assistant.html`, `ai-gateway` | Med | Kills Tier 2 split brain |
| **2. Unify memory** | One memory contract (`agent_memory` + episodic) shared by widget + voice + assistant; localStorage becomes a cache, not the source | `companion-launcher.js`, `ai-gateway`, `agent-memory-store` | Med | Conversation follows the worker everywhere |
| **3. Fold conversational Tier-3 in** | `asset-hub` Asset Brain Q&A → Companion `setContext('asset:<uuid>')`; `hive` Coach → Companion coach mode. Retire the two bespoke chat UIs | `asset-hub.html`, `hive.html`, launcher | Med | -2 redundant chat UIs |
| **4. Expose tools as Companion functions** | Register eng-calc, BOM/SOW, FMEA, Weibull, OCR, Speak-to-Fill as function-call tools the Companion can invoke. Pages keep their buttons | `ai-gateway`/`ai-orchestrator` tool registry + 6 edge fns | Med-High | "Run the HVAC calc for me" works from the bubble |
| **5. Persona + standards consistency pass** | Every remaining AI narrative (analytics action plan, project AI, intelligence report) prepends `getCompanionBlock()` + Tier-S standards anchors | analytics/project/intelligence fns | Low | Every AI output *sounds* like the Companion |

Each step ships independently, gate-green, and is reversible. Steps 1–2 are invisible to users (pure convergence); 3–5 are the visible "it's all one Companion now" payoff.

---

## Synthesis & Triage — skills + external research (2026-06-07)

_Cross-checked the roadmap above against the `ai-engineer` skill (internal doctrine) and four reputable external sources. The map's direction held; the research re-ordered it and added one critical step._

### What the sources said
- **`ai-engineer` skill:** one `callAI` shared module; **`ai-gateway` is already a router that fetches specialists** (the supervisor exists); **WAT split** (math deterministic, AI narrates); sticky-key `${hive_id}:${worker_name}:${agent}`; **never auto-apply AI output — gate it**; the **7-layer memory stack** is already built; free-tier 8B models are weak → `voice-action-router` already does **deterministic intent→tool mapping**.
- **Anthropic — Building Effective Agents:** "Start simple… add agentic complexity *only when it demonstrably improves outcomes*." Routing = classify→specialist; orchestrator-workers = unpredictable subtasks; **reduce abstraction layers, don't hide prompts behind a framework**.
- **Microsoft — Copilot Super App:** same problem at scale → **"a single front door… the central front door, not the only door"** (per-app copilots still exist); goal = "less dependent on the user restating context every five minutes."
- **LangGraph Supervisor / LangChain benchmarking:** "If a single agent with all tools hits **≥85% on eval** and tasks are homogeneous, **stay single**; move to supervisor only when task types are distinct and accuracy plateaus."
- **mem0 / MemOS:** universal memory layer keyed by **user_id + session**, cross-session; MemOS reports **~35% token savings from cross-task skill reuse** (= our procedural skill library).

### Convergent verdict (all sources agree)
1. **Central front door, NOT the only door** — Companion = one conversational entry; deterministic tools keep their pages. (Triple-validated: Microsoft + Anthropic + WAT.)
2. **Don't build a new framework** — `ai-gateway`/`ai-orchestrator`/`agentic-rag-loop` ARE the router + orchestrator-workers patterns. Reuse, don't rebuild.
3. **Memory unification is the highest-leverage lever** — point the *existing* 7-layer stack at **one identity key**; no mem0 dependency needed.

### Re-ranked triage (leverage × 1/effort × 1/risk)

| Rank | Step | Leverage | Effort | Research verdict |
|---|---|---|---|---|
| **0 (NEW)** | **Eval-gate the rollout** — freeze the companion's safety/grounding score (`ai_eval_gate.py` C2); block any regressing step | 🔴 critical | Low | **Added by research.** Establish BEFORE touching anything — proves convergence didn't break the 214-turn companion. |
| **1** | **Unify memory** (was Step 2) | 🔴 high | Med | **Promoted** — external sources call this *the* win. 7-layer stack on one `${hive_id}:${worker_name}` key; localStorage→cache. |
| **2** | **Converge the brain** (was Step 1) | 🟠 high | Med | Route `assistant.html` *through* `ai-gateway` (thin router delegates); don't merge `ai-orchestrator` in. |
| **3** | **Fold conversational Tier-3 in** (Asset Brain, hive Coach) | 🟠 med | Med | Unchanged — retire 2 bespoke chat UIs → Companion in-context. |
| **4** | **Tool invocation** | 🟡 med | Med-High | **Refined:** use the proven `voice-action-router` intent→tool map, NOT model-native function-calling. |
| **5** | **Persona/standards consistency pass** | 🟢 low | Low | Unchanged, do last. |
| **6 (later)** | **Proactive companion** | — | — | Microsoft "remember goals, report back" = our `agent_followups` (prospective layer) + `scheduled-agents`. Already half-built. |
| **7 (capstone)** | **Comprehensive AI Playwright MCP** — agentic E2E critic that drives the unified Companion across all 32 surfaces and grades it against the 3 reference stacks (Agent / Memory / RAG). Full design in the appendix. | 🔴 high (proof) | Med | **Added 2026-06-07.** Verifies every ✅ in the rubric tables end-to-end; only meaningful AFTER Phases 1–5 wire the Companion. Test-only, no product change. |

### What research added beyond the original map
- **Step 0 eval-gate** — the single most important addition; don't converge blind.
- **A thin safety-screen** at the front door (Anthropic's parallel guardrail) — formalize the existing PII-redaction + rigorous-grader into one screen.
- **Loud caution:** every source warns against over-engineering. You are **not** under-built — you're **fragmented at the front door**. The work is *wiring + retiring duplicates*, NOT a new agent framework.

### Revised one-line sequence
> **0.** Freeze eval baseline → **1.** Unify memory on one identity key → **2.** Converge entry points behind `ai-gateway` → **3.** Fold Asset Brain + Coach into the in-context Companion → **4.** Wire tools via `voice-action-router` → **5.** Persona/standards pass → *(6. proactive layer, later)* → **7.** Comprehensive AI Playwright MCP (grade the whole stack against the 3 rubrics). Each step gate-green, reversible, **eval-gated**.

### Sources
[Anthropic — Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents) · [Microsoft Copilot Super App (Fortune)](https://fortune.com/2026/05/29/microsoft-working-on-super-app/) · [Windows Forum analysis](https://windowsforum.com/threads/microsoft-copilot-super-app-one-ai-workspace-to-end-fragmentation.420844/) · [LangGraph Supervisor (GitHub)](https://github.com/langchain-ai/langgraph-supervisor-py) · [LangChain multi-agent benchmarking](https://blog.langchain.com/benchmarking-multi-agent-architectures/) · [mem0 (GitHub)](https://github.com/mem0ai/mem0) · [MemOS (GitHub)](https://github.com/MemTensor/MemOS)

---

## Guardrails carried from prior work

- **Free-tier-only chain** — every delegate must use a `taskProfile` on the free-tier allow-list (`validate_groq_fallback.py`). No paid-model escalation.
- **Fail-open** — if a delegate (orchestrator / rag-loop / tool) fails, fall back to plain `ai-gateway` chat. Never dead-end the worker.
- **Hive isolation** — every delegated query keeps `.eq('hive_id', hiveId)`; solo flows use the per-identity rate gate (`checkSoloRateLimit`).
- **Rate limit first** — gateway enforces before any model call.
- **Don't break the 214-turn voice handler** — `voice-handler.js` opt-in stays additive; convergence happens behind `ai-gateway`, not by rewriting the voice brain.
- **WAT split intact** — math stays deterministic (Weibull, P-F, eng-calc compute); the Companion only narrates.

---

## Open decisions for next session

1. **Step 1 entry point** — fold `ai-orchestrator` logic *into* `ai-gateway`, or keep `ai-gateway` as a thin router that delegates? (Leaning: thin router — less churn, preserves the 7-agent fn.)
2. **Memory model** — promote `agent_memory` to the single store, or add a unification view over the three? (Leaning: single store, localStorage as cache.)
3. **Tool invocation** — function-calling via the model, or an explicit intent → tool map like `voice-action-router` already does? (Leaning: reuse `voice-action-router` pattern; it's proven.)
4. **Scope cut** — is `resume.html` in or out? (It's a distinct product with its own builder; suggest OUT of Companion unification for now.)

_End of map. Build starts only on your go, step by step._

---

# Detailed Execution Designs (grounded in code, 2026-06-07)

_Written during the autonomous run after reading `ai-gateway/index.ts`, `companion-launcher.js`, `voice-action-router/index.ts`. These are **ready-to-execute** — each names exact files, the change, the eval-gated verification, blast radius, and the revert. NOT executed autonomously (cross-page blast radius needs your eyes)._

## 🔑 The keystone finding that reshapes everything

`ai-gateway` is **already** the single front door + unified memory hub:
- `AGENT_ROUTES` registry maps agent → specialist fn (asset-brain, analytics, project, shift, logbook-voice, report-voice, voice-journal).
- Rate gate ONCE (hive + user) · PII redact · **persona injected** (`accountPersona`) · **sticky `session_key = ${hive_id}:${agent}:${authUid}`** already built.
- **Full memory stack already wired**, all keyed by `{hive_id, worker_name, auth_uid, agent_id}`: agent_memory (10 turns + summary) + episodic + verified-state + procedural + followups + journal-recall.

**Consequence:** memory is *already unified* for anything entering through the gateway. **Steps 1 and 2 therefore MERGE** — the real gap is just callers that *bypass* the gateway (`assistant.html` → `ai-orchestrator` directly; there is no `orchestrator`/`assistant` route in `AGENT_ROUTES`). Route them through the gateway and memory/persona/rate-limit/sticky-session unify *for free*.

---

## Step 1+2 (MERGED) — Converge the brain = unify the memory
**Goal:** every conversational surface enters through `ai-gateway` with the same `${hive_id}:${agent}:${authUid}` identity, so they share one memory + persona + rate-limit.

**Grounded current state:**
- Floating widget (`companion-launcher.js`) → `ai-gateway` agent `voice-journal` ✅ (already; when signed in, the supabase client attaches the JWT, gateway resolves `authUid`, persists to agent_memory). Its `localStorage` history is **client display cache only** — server agent_memory is authoritative.
- `voice-journal.html` → `ai-gateway` voice-journal ✅.
- `assistant.html` → **`ai-orchestrator` DIRECT** ❌ (bypasses gateway → no shared memory, no persona injection, no unified rate-limit). [assistant.html:856](assistant.html#L856)

**Exact change:**
1. `ai-gateway/index.ts` `AGENT_ROUTES`: add
   ```ts
   "assistant": { fn: "ai-orchestrator", description: "Full multi-agent fan-out (failure/PM/inventory/...) over the worker's data" },
   ```
   (Decision confirmed earlier: thin router delegates; do NOT merge orchestrator code in.)
2. Add `"assistant"` to `EPISODIC_MEMORY_AGENTS` (it benefits from durable recall).
3. `ai-orchestrator/index.ts`: accept the gateway's forwarded body shape (`message`, `memory`, `context`, `session_key`, `gateway:true`) — it currently takes `{question, hive_id, worker_name, mode}`. Add a thin adapter: `const question = body.question ?? body.message;` and forward `session_key` into its `callGroq`/`callAI` calls (so assistant conversations get sticky-session continuity).
4. `assistant.html`: change the fetch from `/functions/v1/ai-orchestrator` to `WH_DB.functions.invoke('ai-gateway', { body: { agent:'assistant', message, hive_id, context:{persona, source:'assistant-page'} } })`. Keep the `getCompanionBlock()` prepend OR drop it (gateway now injects persona — avoid double-injection; prefer gateway's).
5. `validate_gateway_routing.py`: register the new `assistant` route so the L0 gate stays green.

**Verification (eval-gated):** re-run companion flywheel 1 clean turn → `ai_eval_gate.py gate` must stay within tolerance on 🔒test. Plus a manual curl: `assistant.html` question now shows in `agent_memory` for that `auth_uid` AND continues in the floating widget (cross-surface memory proof).

**Blast radius:** medium — assistant.html + 2 edge fns + 1 validator. **Revert:** git restore the 4 files (no migration, no schema).

**⚠️ Pre-flight:** `ai-orchestrator` is NOT in `ANON_OK_AGENTS`, so the gateway will hard-require auth for `assistant` — correct (the Work Assistant needs the worker's records). Confirm assistant.html is behind sign-in (it is).

---

## Step 3 — Fold conversational Tier-3 into the in-context Companion
**Goal:** retire the two bespoke chat UIs (asset-hub Asset Brain Q&A, hive Coach) → make them the Companion bound to that context.

**Grounded current state:**
- asset-hub calls `asset-brain-query` directly ([asset-hub.html:3487](asset-hub.html#L3487)). But the gateway's `asset-brain` agent **already** injects verified-state + episodic + procedural when `context.asset_tag` is present (gateway lines 454–488).
- The widget already supports `WHAssistant.setContext({key:'asset:<uuid>', summary, badge})` (companion-launcher `_setContext`).

**Exact change:**
1. asset-hub: replace the bespoke Asset Brain Q&A box with `WHAssistant.setContext({key:'asset:'+tag, summary:<asset facts>, badge:tag})` + open the widget, OR route its existing box through `ai-gateway` agent `asset-brain` with `context.asset_tag`. Retire the direct `asset-brain-query` invoke from the page.
2. hive Coach (`hive.html:3702` → `ai-orchestrator`): point at `ai-gateway` agent `assistant` with `context.mode:'coach'` (gateway forwards; ai-orchestrator already supports `mode:'coach'`).

**Verification:** Asset Brain answers still ground in that asset's verified-state (curl with `asset_tag`); the conversation now persists to agent_memory and continues in the widget. Page journey specs (`journey-asset-hub`, `journey-hive`) stay green.

**Blast radius:** medium (2 pages). **Revert:** git restore the 2 HTML files.

> ### ⚠️ GROUNDED RE-SCOPE (2026-06-07) — Step 3 is NOT a clean "route through the gateway" swap
> Reading the actual code revealed both surfaces return **rich, structured payloads that the gateway's `{ answer }` response contract DROPS**:
> - **hive Coach** ([hive.html:3767](hive.html#L3767)) returns `{ actions: [{priority, urgency, machine, action, why}] }` rendered as urgency-colored cards — NOT prose. The gateway flattens every specialist response to `answer` (ai-gateway:579), so routing it through would render nothing.
> - **asset-hub Asset Brain** ([asset-hub.html:3506-3522](asset-hub.html#L3506)) reads `data.answer` **+ `data.narration`** (TTS) **+ `data.cited`** (source chips) **+ `data.remaining`** (rate display). The gateway returns only `answer` → loses TTS, citations, and the rate counter.
>
> **So Step 3 needs a DESIGN DECISION (your call), not an autonomous swap:**
> - **Option A — additive `data` passthrough on the gateway:** have ai-gateway include the specialist's full parsed payload as a new `data` field (backward-compatible — existing `.answer` callers unaffected), then point Coach at `resp.data.actions` and Asset Brain at `resp.data.{answer,narration,cited,remaining}`. **Caveat:** the gateway's `hydratePII` only runs on `answer`; structured fields would bypass PII restoration — needs a redaction pass over the passthrough.
> - **Option B — treat them as secured Tier-3 STRUCTURED tools:** they aren't really chats. Keep them calling their fns directly, but secured by in-fn membership gates (Coach: ✅ done via the ai-orchestrator gate; Asset Brain: needs the same audit on `asset-brain-query`). Achieve the "Companion feel" via persona consistency (Step 5) + the widget's `setContext`, not by funneling structured tools through the chat gateway.
>
> **The security half of Step 3 is already delivered** for the Coach: the ai-orchestrator membership gate (commit after c4843ce) closes its cross-hive IDOR regardless of which option is chosen. The remaining decision is purely about the conversational-folding UX. Recommendation: **Option B for the Coach** (it's a structured tool), **Option A or `setContext` for Asset Brain** (it's genuinely conversational). See [[project_companion_unification]].

---

## Step 4 — Tool invocation via the proven `voice-action-router` intent map
**Goal:** the Companion can DO things (log an entry, deduct a part, complete a PM, look up an asset), not just chat — without model-native function-calling (free-tier 8B is unreliable at it).

**Grounded current state:** `voice-action-router/index.ts` already classifies a transcript into structured intents — `logbook.create | inventory.deduct | pm.complete | asset.lookup | query.ask | unknown` — each with `confidence` + `params` + a persona `narration`, and resolves asset names against `v_asset_truth`. The calling page APPLIES intents (with a confirmation chip on ambiguity). `query.ask` falls through to the general assistant.

**Exact change:**
1. Add gateway route `"action": { fn: "voice-action-router", ... }` so the Companion mic/text can hit it through the one front door (gets rate-limit + persona + PII for free).
2. companion-launcher mic flow: send transcript → `ai-gateway` agent `action` → render the returned `narration` + show **confirm chips** for actionable intents (apply via the existing page action handlers); `query.ask` → re-send as agent `voice-journal`/`assistant` (chat).
3. **Internal-control rule (non-negotiable):** NOTHING applies without a confirm chip (the "never auto-apply AI output — gate it" doctrine). Asset resolution ambiguity → chip. Undo on every applied intent.

**Verification:** `journey-ai-assisted` + a new probe in the companion bank ("I replaced the V-belt on P-5" → expects `logbook.create` intent + confirm chip, NOT auto-applied). Eval gate stays green.

**Blast radius:** medium-high (touches the widget action layer). **Revert:** git restore companion-launcher.js + 1 gateway line.

---

## Step 5 — Persona/standards consistency pass
**Goal:** every AI narrative *sounds* like the Companion (Hezekiah/Zaniah) + cites the right standard.

**Grounded current state:** `_shared/persona.ts` `buildPersonaBlock()` exists; voice-action-router + the gateway already inject persona. Gaps = inline tool narratives that DON'T prepend it: `engineering-calc-agent`, `engineering-bom-sow`, `analytics-orchestrator` action plan, `project-orchestrator`, `intelligence-report`.

**Exact change:** for each, prepend `buildPersonaBlock(clampPersona(persona))` to the narrative-generation system prompt (NOT the deterministic calc — WAT split intact: math stays bare). Pass `persona` through from the page → gateway/fn.

**Verification:** `validate_persona_contract.py` (the gate that reads `WORKHIVE_PERSONA_CONTRACT.md`) stays green; spot-check one narrative reads in-voice. **Blast radius:** low (additive prompt prefix). **Revert:** trivial.

---

## Cross-cutting follow-up surfaced by the flywheel (Step 0)
**The eval gate's locked-test split is n=1** (only ~2 companion probes mapped to `test`). Before relying on the gate as a hard blocker, enlarge `companion_probe_bank.json` and/or aggregate multiple clean turns so 🔒test has ≥10 functionality + ≥10 safety probes. Until then, treat a gate FAIL as advisory + eyeball the per-probe diff. _This is the #1 infra task before the unification steps lean on the gate._

> ✅ **RESOLVED 2026-06-07 (Step 0 done + committed):** bank enlarged 18→58, split rebuilt → 🔒test split is now **functionality 100% (n=6) / safety 100% (n=3)** (was n=1), baseline re-frozen v2. The "4% adversarial" scare was a grader false-negative (English-only refusal detector missed code-switched + varied refusals) — companion refuses all 25 adversarial probes with 0 leaks. The gate is now a meaningful hard blocker for Phases 1–7. See [[feedback_eval_refusal_detection_multilingual]].

---

## Coverage completeness — pages with NO AI surface (intentional, audited 2026-06-07)

_Filesystem-verified: **39 root product pages + 39 static subpages**. Every page is classified. The pages below have ZERO AI surface (no `companion-launcher.js`, no AI edge-fn invoke — confirmed by grep) and are correctly OUT of Companion unification scope. Listed here so coverage is closed-loop, not implied — this closes the "did you cover all my pages?" audit gap._

**Root pages with no AI surface (5) — observability / admin / internal:**
| Page | What it is | Why no AI surface |
|---|---|---|
| `agentic-rag-observability.html` | RAG pipeline telemetry dashboard | Read-only; *observes* the AI, isn't itself an AI surface |
| `llm-observability.html` | LLM cost / latency / token dashboard | Read-only telemetry |
| `founder-console.html` | Founder admin console | Internal ops; no worker-facing AI |
| `validator-catalog.html` | Gate validator catalog | Internal reference |
| `parts-tracker.html` | Lightweight parts view | Structured CRUD; the AI for parts lives in `inventory.html` |

**Home / marketing (1):** `index.html` — AI named in copy only; no chat bubble (deliberate, marketing page).

**Static subpages (39) — SEO / legal / info, no AI:** `learn/` (34 articles + `index`), `about/`, `privacy-policy/`, `terms-of-service/`, `feedback/` (the feedback FAB is a form, not a chat).

> **Coverage math:** 32 Tier-1 (floating Companion) + `assistant` (Tier 2) + `index` (home) + 5 no-AI = **39 root ✓**. Nothing unclassified. (`voice-journal` is counted in the 32 — it is both Tier 1 and a Tier 2 dedicated page.)

---

## Industry-rubric alignment — 3 reference stacks (added 2026-06-07)

_Cross-checked WorkHive's AI architecture against three widely-circulated reference stacks (Rakesh Gohel: AI Agent Stack, AI Agent Memory Stack, RAG Architecture). Used as a **grading rubric**, not a build target — most layers already exist. The ✅'s below are asserted from this surface audit; **Phase 7 (below) is what verifies them end-to-end.**_

### Rubric 1 — The AI Agent Stack (6 capability layers)
| Layer | WorkHive today | State |
|---|---|---|
| RAG / Context | `agentic-rag-loop`, `semantic-search`, `temporal-rag-orchestrator`, `voice-embeddings` | ✅ |
| Function Calling / Action | `voice-action-router` (deterministic intent→tool; **not** model-native FC — free-tier 8B unreliable at it) | 🟠 Phase 4 |
| MCP / Access | MCP is **dev-side** only (Playwright/postgres/github/grafana/sentry/crawl4ai); the *product* Companion has no MCP access layer | ⚪ future |
| CLI Tool / Control | N/A to the product (Claude Code's lane, not the worker's Companion) | — out of scope |
| AI Agent / Orchestration | `ai-orchestrator` (7-agent fan-out: goal→plan→reason→choose-tool→execute) | ✅ |
| A2A / Coordination | `ai-orchestrator` + `amc-orchestrator` (5 sub-agents), `shift-planner-orchestrator`, `project-orchestrator` | ✅ internal |

### Rubric 2 — AI Agent Memory Stack (7 layers) — maps 1:1 to our built stack
All keyed `${hive_id}:${worker_name}:${auth_uid}:${agent}`, injected by `ai-gateway`. See [[project_memory_stack_flywheel_2026_05_30]].
| Layer (image) | WorkHive | State |
|---|---|---|
| 01 Working (FIFO window) | gateway 10-turn `agent_memory` window | ✅ |
| 02 Episodic (retrievable) | episodic layer (T1) | ✅ |
| 03 Semantic (distilled facts) | `semantic-fact-extractor` / `semantic-search` (T4) | ✅ |
| 04 Procedural (skill library) | procedural memory (T5) | ✅ |
| 05 Hierarchical (hot/warm/cold) | tiered + `cold-archive-query` (T3) | ✅ |
| 06 Prospective (follow-ups) | `agent_followups` (T6) = the Phase 6 proactive layer | ✅ built, ⚪ unsurfaced |
| 07 Shared (one truth) | verified-state / shared memory (T2) | ✅ |

> **7/7 exist. The gap is access, not capability:** `assistant.html` bypasses the gateway → touches none of this. **Phase 1+2 fixes exactly this** (route it through the gateway → memory unifies for free).

### Rubric 3 — RAG Architecture patterns (8 variants)
| Pattern | WorkHive | State |
|---|---|---|
| Naive RAG | `semantic-search` baseline | ✅ |
| Multimodal RAG | `visual-defect-capture` (photo), `equipment-label-ocr`, `voice-transcribe` | ✅ |
| Graph RAG | `semantic_search_kg_facts` (knowledge-graph facts) | ✅ |
| Hybrid RAG | vector + KG together | ✅ partial |
| Adaptive RAG | `agentic-rag-loop` classifies query-context → routes | ✅ |
| Agentic RAG | `agentic-rag-loop` + `ai-orchestrator` (short/long mem + ReAct/CoT + multi-agent) — **essentially our architecture** | ✅ |
| HyDE | hypothetical-doc embedding | ⚪ not built |
| Corrective RAG | grade-retrieval → web-fallback | 🟠 partial (we grade outputs, not retrievals) |

> **6/8 implemented.** HyDE + Corrective are optional refinements, not missing foundations.

**Net rubric read:** WorkHive is *not under-built* — Memory **7/7**, Agent-stack **4/6** (the 2 open = our Phase 4 + a future product-MCP layer), RAG **6/8**. The remaining work is **convergence + verification**, exactly the map's thesis. Don't build a new framework.

---

## Phase 7 (capstone) — Comprehensive AI Playwright MCP

> ### ✅ BUILT 2026-06-07 — the "Companion Stack Battery" (sibling of the UFAI battery)
> Shipped (LOCAL/uncommitted-pending-commit): **`companion_battery.js`** (`window.__CSB`, v0.4.0 — boot + `agentStack`/`memoryStack`/`ragStack`/`safety` + `critic` + cache-awareness), **`tests/journey-companion-comprehensive.spec.ts`** (durable driver: rate-limit `beforeAll`, self-skip-till-live, cached-tolerant), **`companion_stack_rubric.json`** (scorecard), **`validate_companion_stack.py`** (G0 `companion-stack`, forward-only on `max_major_defects`, registered in `run_platform_checks.py`). CRITIC candidates flow through the existing `ufai_ingest.py` → `sweep_critiques.json`.
> **Live-verified via the Playwright MCP** (signed in, hive b0c619…): Agent (tool→`voice-action-router`, fanout→`ai-orchestrator`, model_chain-grounded) · Memory (persist hard-proof + cross-surface identity-keyed; recall soft) · RAG (asset-brain Graph/Hybrid `cited:4` + semantic-search Naive) · Safety (0 leaks) → **verdict major:0**.
> **3 findings the capstone surfaced + fixed:** ai-orchestrator now honors the gateway-injected memory window (recall); the gateway `asset-brain` route never worked (body-shape) → adapter + `STRUCTURED_PASSTHROUGH_AGENTS` so `cited[]` survives; per-agent memory buckets dispositioned accept-by-design. See [[project_companion_unification]] + ai-engineer "Companion Stack Battery".
> Note on "all 32 surfaces": the durable spec + battery parametrize by surface; memory/agent behavior is identity+agent-keyed (not page-keyed) so the proven distinct-brain results generalize to the widget surfaces that share the `voice-journal` agent. A literal 32-surface live MCP sweep is rate-limited to a few clean runs per reset — run in waves.

**Goal:** an **AI-driven** Playwright-MCP harness that drives the *real* unified Companion across all 32 surfaces and grades it against the 3 rubrics above with **grounded** assertions (observable side-effects, not vibes). This is the agentic evolution of the per-element Grounded Sweep critic ([[reference_holistic_critic_tooling]]), which is blind to whole-system behavior (it checks tap-targets + modal a11y, not "does the Companion deliver all 7 memory layers?").

**Why capstone, not earlier:** it can only grade the *unified* Companion once Phases 1–5 wire it. Run before, and it merely re-documents the fragmentation already mapped.

**Probe classes — every assertion checks an observable:**
- **Agent-stack** — a tool-needing query actually hits `voice-action-router` (Action); a fan-out question reaches `ai-orchestrator` (Orchestration/A2A). Assert via the network request to the right edge fn.
- **Memory-stack (the headline test)** — cross-surface memory proof: a statement made on `assistant.html` resurfaces in the floating widget on `logbook` (working→episodic→shared). Assert the `agent_memory` row exists for that `auth_uid` + same `session_key`. A follow-up fires (prospective).
- **RAG-pattern** — an asset question grounds in `asset-brain` verified-state (Graph/Hybrid); a doc question hits `semantic-search` (Naive); a photo hits multimodal. Assert the *retrieved context*, not just the answer text.
- **Safety carry-over** — re-run the frozen Step-0 companion eval probes through the unified front door; the 🔒test split must hold (no regression from convergence).

**Grounding doctrine (carried from the Grounded Sweep):** Playwright MCP as a grounded observer; every claim tied to a DB row / edge-fn invoke / `session_key`; self-detects deploy + skips till live (like `journey-definer-rpc-hive-isolation.spec.ts`); blast-radius aware; findings → disposition queue, not auto-applied.

**Deliverables:** `tests/journey-companion-comprehensive.spec.ts` (the agentic E2E critic) + `companion_stack_rubric.json` (the 3-rubric scorecard, G0-ratcheted like the sweep) + skill writeback (ai-engineer / qa-tester / realtime-engineer / multitenant-engineer).

**Blast radius:** test-only (no product change). **Revert:** delete the spec + rubric file.

---

# Phase 8 — Companion Eval & Optimization Harness ("fine-tuning/training across dimensions")

**Added 2026-06-07** after Ian asked for "fine-tuning and training of all of these, for different dimensions, for the whole companion roadmap." **Ian's fork decisions:** approach = **eval-driven optimization** (NOT weight-training); dimensions = **all four** (Agent/tool-routing, RAG grounding+citations, Memory recall, Persona+Safety). Planned via skills + external GitHub/research synthesis (Ian's directive). **PLAN ONLY — nothing built yet.**

## The reality that shapes everything
The companion runs entirely on **free-tier Groq** models (llama-4-scout, qwen3-32b, llama-3.1-8b…). We don't own the weights and free-tier offers no custom fine-tuning, so "fine-tuning" cannot mean weight-training today. The achievable, high-leverage interpretation: **systematically improve the companion along each dimension by measuring against golden sets, optimizing the controllable surface (prompts / few-shot exemplars / RAG retrieval / model-chain order), and ratcheting wins** — "training the system, not the weights." This ALSO harvests the labeled corpus that real fine-tuning (deferred Option B) would later need, so it is the on-ramp, not a detour.

## Reuse, don't rebuild (we are ~40% there)
| Existing asset | Role in Phase 8 |
|---|---|
| `tools/ai_eval_gate.py` | per-(split×dimension) regression gate; exits 1 on a **locked-test** regression. Generalize from {functionality,safety,cost} to all 6 dims. |
| `tools/gate_eval_splits.py` | train / validation / **locked-test** anti-overfit partition + tamper `test_seal`. The anti-overfit spine of the optimization loop. |
| `tools/companion_rigorous_grader.py` | independent, no-LLM, rule-based grader (shares no code with the companion — the trust property). Extend per dimension. |
| `tools/companion_probe_bank.json` | probes with `expected_route` + `expected_keywords` + `must_not_contain`. Extend to golden sets. |
| `companion_battery.js` / `companion_stack_rubric.json` | live Agent/Memory/RAG **observables** (model_chain, agent_memory rows, cited[]). The grounded signal source. |
| `ai-quality.html` + `ai_quality_log` + worker thumbs | production signal → corpus harvest (8.5) + the eval dashboard surface (8.6). |

## External patterns adopted (skills + GitHub/research synthesis)
- **DSPy / GEPA** ([stanfordnlp/dspy](https://github.com/stanfordnlp/dspy), [gepa-ai/gepa](https://github.com/gepa-ai/gepa), [dspy.GEPA](https://dspy.ai/api/optimizers/GEPA/overview/)) — **reflective prompt evolution via natural-language feedback on the trajectory**, black-box (no weights), Pareto selection; beats RL (GRPO) and MIPROv2 with ~35× fewer rollouts → **the optimization engine**, and "fewer rollouts" is exactly what makes it viable on free-tier. (Pattern, not necessarily the dep — a lightweight GEPA-inspired propose→A/B→ratchet loop fits our stack.)
- **Ragas** ([explodinggradients/ragas](https://github.com/explodinggradients/ragas), [arXiv 2309.15217](https://arxiv.org/pdf/2309.15217)) — the 4 RAG metrics: **faithfulness, answer relevancy, context precision, context recall** → the RAG-dimension scorecard.
- **BFCL / τ-bench / Agent-as-a-Judge** ([arXiv survey 2503.16416](https://arxiv.org/html/2503.16416v2), [arXiv 2508.02994]) — **deterministic Tool Correctness** (exact route + required params, NO judge) + multi-step **task completion** + 3-axis agent judging (completion / tool-selection rationale / planning) → the Agent-dimension grader. Research line: "deterministic checks are better for exact tool names, required params, expected outputs" — validates our rule-based-first approach.
- **LongMemEval** ([xiaowu0162/LongMemEval](https://github.com/xiaowu0162/LongMemEval), [arXiv 2410.10813](https://arxiv.org/abs/2410.10813)) — **5 memory abilities**: information extraction, multi-session reasoning, temporal reasoning, knowledge updates, **abstention**. Even GPT-4o scores 30–70% → memory is the hardest dim; our golden set must probe all 5, especially cross-session recall + abstention (don't fabricate) → the Memory-dimension scorecard.
- **promptfoo / DeepEval / Inspect AI** ([promptfoo](https://github.com/promptfoo/promptfoo), [DeepEval](https://github.com/confident-ai/deepeval), [Inspect](https://github.com/UKGovernmentBEIS/inspect_ai)) — harness shape: **deterministic assertions run FREE first; LLM-as-judge only where unavoidable** (it costs tokens). Standard production pattern = a red-team CI gate + a metric CI gate. We already have the CI-gate spine (`run_platform_checks.py` G0).

## The roadmap (8.0 → 8.6 — each gate-green, reversible, $0-first)
| # | Step | What | Reuse / new |
|---|---|---|---|
| **8.0 ✅ BUILT (2026-06-08)** | Dimension taxonomy + scorecard | Extend the `{domain,dimension}` tags to **6 dims** (agent, rag, memory, persona, safety, cost). One `companion_eval_scorecard.json` row per dim: metric · grader · golden-set ref · baseline · tolerance · gate. | extend `gate_eval_splits.py` + `ai_eval_gate.py` |
| **8.1 ✅ Agent BUILT (2026-06-08)** | Golden datasets per dimension | Agent: `expected_route` + `expected_params` (BFCL) + multi-step chains (τ-bench). RAG: question + ground-truth answer + ground-truth chunk ids. Memory: multi-session scripts (LongMemEval 5 abilities) + abstention probes. Persona: utterance + voice markers / anti-markers. Safety: extend frozen set. | extend `companion_probe_bank.json` + new golden files |
| **8.2 ✅ Agent BUILT (2026-06-08)** | Graders (deterministic-first, judge w/ backstop) | Agent = Tool Correctness (route+params, no judge). RAG = Ragas-4 (context precision/recall deterministic from `cited[]` vs truth; faithfulness/relevancy = free-tier judge + claim-overlap backstop). Memory = persist (agent_memory row) + recall (fact match) + abstention. Persona = voice-marker regex + judge. Safety = existing leak/refusal grader. All **independent + negative-controlled**. | extend `companion_rigorous_grader.py` |
| **8.3 ✅ Agent BUILT (2026-06-08)** | Per-dimension regression gates | Generalize `ai_eval_gate` to all 6 dims; each a **G0 forward-only ratchet on the locked-test split** (degrade-to-SKIP without data). Baselines frozen only from clean runs. | `ai_eval_gate.py` + register in `run_platform_checks.py` |
| **8.4** | Optimization loop (the "training") | GEPA-style: run dim → grader emits per-failure NL feedback → reflective proposal of prompt/few-shot/RAG/chain variants → **A/B on the VALIDATION split** → accept iff val improves AND locked-test holds → ratchet. Anti-overfit by construction. | new `tools/companion_optimize.py` |
| **8.5** | Continuous harvest | Wire `ai_quality_log` + worker thumbs → auto-grow golden corpus. **This is the labeled-data on-ramp to deferred Option B (real fine-tuning).** | new |
| **8.6** | (capstone) Eval dashboard | Surface the 6-dim scorecard + trend in `ai-quality.html` / founder-console (per-hive AI quality already lives there). Closes the loop visibly. | extend `ai-quality.html` |

**Recommended sequencing:** 8.0 → **Agent first** (8.1+8.2 — most deterministic, fastest win, reuses `expected_route`) as the reusable template → RAG → Memory → Persona/Safety → 8.4 optimize → 8.5 harvest → 8.6 dashboard.

**Guardrails:** $0 free-tier (deterministic graders first; judge sparingly + always a deterministic backstop); graders import no companion code (trust property); anti-overfit via the existing locked-test split + seal; forward-only gates; reversible per step; **Option B (real weight fine-tuning/distillation) stays explicitly deferred** until harvested data volume + budget justify it.

## Build log

### 8.0 — Dimension taxonomy + scorecard registry ✅ (2026-06-08)
**What shipped (additive only — the frozen functionality/safety baselines + `test_seal` were preserved):**
- **`tools/gate_efficacy_ledger.py`** — added `COMPANION_DIMENSIONS = (agent, rag, memory, persona, safety, cost)` + `classify_companion_dimension(entry)` on a **separate axis** from the validator `DIMENSIONS` (so no validator tag reshuffles and the eval-split seal — keyed on unit id — never moves). `reclassify` confirmed **0 of 362 validators changed**. The "safety" companion dim = ADVERSARIAL ROBUSTNESS only (`adversarial` section); domain-safety queries (`safety_intent`, `held_out_safety`: "what PPE/permit do I need") are route-selection → **agent**, so companion `eval_dimension=safety` is byte-identical to the frozen baseline's safety set (train 17 / val 5 / test 3, verified per split).
- **`tools/gate_eval_splits.py`** — tags every companion-probe + canonical-question unit with an additive `eval_dimension` field (specs stay on the validator axis). Split assignment + `test_seal` unchanged. New "companion dimension × split" coverage report.
- **`companion_eval_scorecard.json`** (NEW registry — the single source of truth) — one row per dim: metric · grader · golden-set ref · baseline_ref · tolerance · gate · **status** (`active` = frozen baseline exists → gated; `pending` = degrade-to-SKIP until 8.1+8.3). Today: **safety + cost active; agent/rag/memory/persona pending.**
- **`tools/companion_eval_scorecard.py`** (NEW) — `report` / `verify` (well-formedness + active-baseline resolvability; exit 1 on a malformed registry, degrade-to-SKIP if absent) / `sync` (live coverage into the registry).
- **`tools/ai_eval_gate.py`** — `score_results` parametrized by `dim_field` / `score_dims` (default = the FROZEN `dimension` axis, so `gate`/`baseline`/`report` are byte-identical — verified all deltas `+0.0pp`, exit 0). New **informational** `companion-report` subcommand scores the `eval_dimension` axis with per-dim registry status; pending dims SKIP. The enforcing per-dim gate is 8.3.

**Coverage snapshot (the map 8.1 builds against):** agent 49 (8 locked-test) · safety 25 (3) · rag 1 · memory 1 · **persona 0**. Confirms the **Agent-first** sequencing: agent is the most-covered + most-deterministic dim. RAG / Memory / Persona golden sets are 8.1's job.

**Shipped standalone (not yet a G0 validator)** — mirrors how P1's ledger + P6's split shipped before their gates; the G0 registration of the per-dim regression gate lands in 8.3. **Blast radius:** 2 new files + 3 additive tool edits + 1 registry; reversible via `git restore`. No product/runtime change.

### 8.1 + 8.2 — Agent dimension golden set + Tool-Correctness grader ✅ (2026-06-08)
The Agent dimension, built first as the **reusable template** for RAG / Memory / Persona.
- **`companion_agent_golden.json`** (NEW, 8.1) — the BFCL/τ-bench golden set, grounded in the REAL `voice-action-router` contract (intent kinds `logbook.create | inventory.deduct | pm.complete | asset.lookup | query.ask | unknown` + their param shapes): **12 single-turn** (`expected_route` + `expected_params` + per-key `param_match` modes), **3 multi-step chains** (τ-bench, pass iff all steps pass), **4 negative controls** (off-topic / vague / ambiguous / bulk-destructive — must abstain).
- **`tools/companion_rigorous_grader.py`** (extended, 8.2) — added pure, importable `grade_agent_*` functions: route exact-match (intent kind) + param match modes (`exact`/`contains`/`eq`/`parts_subset`) + negative-control abstention (confident write = route ∈ write-intents with confidence ≥ floor). DETERMINISTIC, no judge, no companion imports (the trust property holds).
- **`tools/companion_agent_eval.py`** (NEW, 8.2) — harness. `--self-test` proves the grader is **negative-controlled with no live companion**: an ORACLE observation passes all 19 units; a BLIND observation (always a confident `logbook.create`) fails every negative control and scores strictly lower (verified: oracle 19/19, blind 0/19, 4/4 negatives failed). `--observed F` grades a real route_result map → eval-results shape for 8.3.
- **splits**: new `agent_golden` kind; corpus 200→**219** units, seal `041272→b5c9028` (legitimate golden growth, committed). Agent coverage now **train 40 / val 18 / locked-test 10** — enough to baseline + gate in 8.3.
- **registry**: `agent` row points at the real golden set + grader; **status stays `pending`** until 8.3 freezes a clean Agent baseline from a live flywheel run (degrade-to-SKIP holds). Frozen functionality/safety gate re-verified **byte-identical (Δ+0.0pp, exit 0)**.

### 8.3 — Agent live capture + per-dimension gate ✅ (2026-06-08)
The Agent dimension is now proven end-to-end (golden → grader → live capture → freeze → gate → registered G0). First Phase-8 step with a runtime dependency; runtime-verified LOCALLY (no deploy).
- **`tests/agent-golden-capture.spec.ts`** (NEW) — drives the 19 golden units (22 gateway calls incl. chain steps) through the LIVE `ai-gateway` `voice-action` route, reusing the flywheel's in-browser-fetch + localStorage-JWT sign-in. Captures `route_result.intents[0]` → normalized `{route, params, confidence, answer}` into `.tmp/agent_golden_observed.json`. Clean run: rate-limit counters + `ai_cache` reset first; **22/22 calls ok**.
- **`tools/ai_eval_gate.py`** (extended) — `companion-baseline --dim <d>` (freeze a per-dimension locked-test floor into `companion_dim_baselines.json`) + `companion-gate` (score each active dim's latest results vs its floor; exit 1 only on a *blocking* regression; degrade-to-SKIP without baseline/results). Reuses `score_results(dim_field="eval_dimension")`. The frozen functionality/safety `gate` is untouched (re-verified byte-identical).
- **`validate_companion_dim_gate.py`** (NEW) + registered **G0 `companion-dim-gate`** in `run_platform_checks.py` (auto-discovery: 333/333 validators registered).
- **Result: the companion routes 19/19 correctly** (after one fix below). Agent baseline frozen at **locked-test 100% (n=2)**, clean run. Registry `agent` → **active**, but **blocking=false (forward-only WARN)**: n=2 locked-test is too small to block on (one LLM-router flake = 50pp); flips to blocking after the golden set is expanded.

**Two real findings the live run surfaced:**
1. **Gateway wraps its payload under `.data`** (`{ok, data:{answer, route_result,...}, model_chain,...}`) — a raw-fetch capture must unwrap `.data` first. First pass read top-level → all routes `None`. Re-derived from the captured RAW dump (no expensive re-run). Spec fixed for future runs.
2. **Golden label error (AG-02)** — "did the scheduled preventive lubrication... no issues" is `pm.complete` (a completed scheduled PM per the router contract), not `logbook.create`. The router was right; my 8.1 label was wrong. Corrected **pre-baseline-freeze** (legitimate first-validation curation, not overfitting — id kept stable, documented with domain rationale independent of the model output).

### RAG dimension — full 8.1+8.2+8.3 ✅ (2026-06-08)
The Agent template replicated for RAG in one pass — and **no new validator was needed** (the generalized `companion-dim-gate` G0 covers every dimension once it has a baseline; that's the template paying off).
- **`companion_rag_golden.json`** (NEW, 8.1) — 7 grounded questions + 2 abstention controls, scoped to a REAL seeded asset (HPU-001, verified to have logbook 243 / pm 1 / fmea 3 / weibull 1 / rcm 2 / pf 1 and **no risk** — the missing lane is the built-in abstention control). Ground-truth = expected citation **kinds** (asset-brain cites `{kind, index}`, not text chunks).
- **`tools/companion_rigorous_grader.py`** (extended, 8.2) — `grade_rag_*`: context recall/precision **deterministic** from `cited[]` kinds vs expected; answer-relevancy + faithfulness **deterministic backstops** (judge optional); abstention controls pass iff the answer says "no data"/clarifies AND doesn't fabricate a forbidden-kind citation. Negative-controlled self-test (oracle 9/9, blind 0/9, 2/2 abstentions fail).
- **`tools/companion_rag_eval.py`** (NEW) + **`tests/rag-golden-capture.spec.ts`** (NEW) — live capture through the gateway `asset-brain` route (9/9 calls ok), graded **8/9**. RAG baseline frozen at locked-test **100% (n=1)**; registry `rag` → **active**, blocking=false (n=1, same expand-first caveat as Agent). Frozen + agent gates re-verified intact; scorecard now **4 active** (agent/rag/safety/cost).

**Two findings from the RAG live run:**
1. **RG-02 = a real RAG gap** — asset-brain answered "PM compliance is 0%..." correctly but emitted **no `pm` citation** (grounded-but-uncited). On the VAL split (informational), so it doesn't move the locked-test baseline. A concrete 8.4 optimization target (improve citation emission).
2. **RG-04 = grader calibration** — my faithfulness backstop wrongly required the asset name in the answer prose; a correct, cited Weibull answer ("beta is 1...") that didn't restate "HPU-001" false-failed. Fixed pre-freeze: faithfulness = cited-something + no-forbidden-content (retrieval is asset-scoped, so cited evidence is on-asset by construction).

**NEXT: Memory** (LongMemEval 5 abilities + abstention; `agent_memory` rows are the live observable) → **Persona** (voice markers from the registered narrated-specialists) → **8.4 GEPA-style optimization** (RG-02 is a ready first target). **Follow-up for Agent + RAG:** expand both golden sets (more locked-test units) so `blocking` can flip true.

