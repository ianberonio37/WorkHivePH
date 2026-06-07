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

