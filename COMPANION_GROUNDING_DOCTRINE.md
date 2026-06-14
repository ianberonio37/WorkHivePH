# Companion Grounding Doctrine — proactive/deterministic, NOT reactive patches

_Authored 2026-06-14 (Ian: "there will be millions of scenarios… no way to just push a bandage… use a deterministic principle / doctrine / routing+wiring; ask skills + reputable sources"). **PLAN-ONLY — build in the next window.** This is the continuation of the AI Companion roadmap (`AI_SURFACE_MAP.md §0.5` → new §0.7)._

> **Open this when starting the Grounding arc.** It supersedes the reactive `stripUngroundedKpi` regex rail (the "target"-hole bandage that shipped a fabricated "41%" to Ian's screen).

---

## 0. The principle (one invariant, fixes the whole class)

**The LLM PHRASES facts it is given; it never AUTHORS numbers.** Every number / KPI / status in a companion answer must trace to the deterministic fact-sheet — or it is, by construction, a fabrication.

This is not new doctrine — it is WorkHive's own WAT rule the companion broke:
- ai-engineer SKILL.md **L769**: *"Never ask the AI to compute numbers… LLMs hallucinate numbers. JS is deterministic. Keep them separate."*
- **L798**: *"Code builds a FACT SHEET deterministically; the model only phrases it."*
- **L822**: *"This is the answer to 'we can't do unending flywheels': move the recurring failure out of the probabilistic prompt into deterministic code that fixes the whole CLASS at once."*
- **L1526**: *"Use the PROMPT for judgement, CODE for rules (WAT)."*

The conversational companion violated this: `ai-gateway buildOpsSnapshot` hands the model FREE TEXT and lets it GENERATE PROSE WITH NUMBERS → it invents "your planned-vs-reactive ratio is 41%". The reactive rail tried to catch known patterns and failed on the first unknown framing ("…from a target of 80%"). **We stop matching bad patterns and start enforcing the invariant.**

---

## 1. The architecture — 3 deterministic layers (defense by CONSTRUCTION)

| Layer | What | Removes |
|---|---|---|
| **G1 Numeric-provenance gate** | every number in the output must trace to the fact-set; else strip/regenerate. The UNIVERSAL backstop. | the whole fabricated-number class, in one rule |
| **G2 Deterministic routing** | pre-LLM classifier: out-of-fact-sheet value queries → templated honest deflection, never free-generated | the OPPORTUNITY to fabricate for the biggest class |
| **G3 Typed fact-sheet + structured render** | LLM returns structured output (which facts to surface + prose); CODE inserts the real numbers | the LLM's ability to emit a number AT ALL |

**Why three, not one:** G3 is the strongest (fabrication impossible by construction) but the biggest change; G1 is immediate + universal + retires the regex rail; G2 is the cheap high-leverage routing win. Build G1 → G2 → G3.

---

## 2. Phases (each plan-only; verify live + add an eval counterpart that does NOT share G1's logic)

### Phase G1 — Numeric-provenance gate (BUILD FIRST; retires the reactive rail)
**Goal:** replace `stripUngroundedKpi` (voice-journal-agent) with a GENERAL deterministic post-pass. Extract every number token from the answer; each must trace to one of:
  - (a) the **ops-snapshot fact-set** (alert count, overdue-PM count, registered asset tags/counts),
  - (b) a **worker-stated value** (from the memory block — the recall carve-out already exists),
  - (c) a **curated benchmark table** the model was given, emitted WITH its citation (see G1b),
  - (d) a **safe non-claim allowlist**: dates / times / years, ordinals ("top 3"), list-counts (N items it actually listed), and domain-advice constants in non-current-state advice ("regrease every 2 weeks").
  Any number tracing to NONE → it's a current-state fabrication → strip that sentence (or, better, regenerate once with the offending claim named).
**Files:** `voice-journal-agent/index.ts` (replace the rail) + a shared `_shared/numeric_provenance.ts` (so coach/asset-brain reuse it). **Eval counterpart:** mirror the SAME invariant in `companion_fabrication_sweep.py` grade(), but with INDEPENDENT extraction logic — a guard and the grader that validates it MUST NOT share a word-list/blind-spot (the "target" lesson: [[feedback_rail_grader_correlated_blindspot_2026_06_14]]).
**Caveat:** (d) the safe-non-claim set is where false-positives live — tune it ONCE, centrally; it's one invariant, not N regexes.
**Verify:** offline number-by-number unit table + LIVE on Leandro(44/7) + Pablo/Lucena(37/6): strategic baits ship 0 untraceable numbers, grounded counts survive.

### Phase G1b — Curated benchmark table (small, enables honest benchmark talk)
A deterministic `_shared/benchmarks.ts` table of citable values (world-class OEE ~85% (ISO 22400), P-F curve, MTBF norms…) the companion MAY cite **with the source string**. Makes "world-class OEE is ~85%" GROUNDED (from the table) instead of an exemption the model could abuse. G1 treats table values as traceable (c).

### Phase G2 — Deterministic routing (the wiring)
A pre-LLM classifier (cheap: keyword/intent or a tiny routed call) decides per turn: does the query ask for a value the fact-sheet HOLDS (alerts/PM/asset existence) or one it does NOT (OEE/MTBF/ratio/%/project/inventory/skill detail)? Out-of-fact-sheet → a **templated** honest answer + page pointer (no free generation, no chance to invent). In-scope → grounded generation. Folds the current prompt-based OUT-OF-SCOPE DOMAINS clause into deterministic code (NeMo Guardrails dialog-rail pattern). **Files:** `ai-gateway/index.ts` (route before forwarding) or voice-journal-agent pre-check.

### Phase G3 — Typed fact-sheet + structured-output rendering (the deepest)
`buildOpsSnapshot` → a STRUCTURED JSON fact-sheet (not free text). The agent runs in JSON-mode/function-calling and RETURNS structured output: `{facts_to_surface:[ids], tone, advice_prose}` — it picks WHICH grounded facts + the prose framing, but emits NO raw numbers. Deterministic code renders the final text, inserting the real values from the fact-sheet (LLM picks the slot, CODE fills the value). This is the resume FACT-SHEET pattern (SKILL.md L798) + Guardrails-AI structured output. After G3, G1 becomes a cheap assertion (numbers are inserted by code, so they're traceable by construction). **Biggest change; gated on G1+G2 proving the model + UX hold.**

---

## 3. Honest constraints (so this is real, not hype)
- **Free-tier API providers can't do true grammar-constrained decoding** (Outlines/XGrammar need local model control; Groq/Cerebras/etc. are API-only). But **JSON-mode + function-calling ARE available** (the chain already passes `jsonMode`) → G3's structured output + G1's post-verification are both implementable on our stack. The strongest token-level constraint is off the table until a self-hosted model; the fact-sheet+verify hybrid gets ~all the benefit.
- **Constrained output has an "alignment tax"** — rigid formats dull conversational warmth/reasoning (arXiv 2604.06066). Mitigation: **prose framing stays free; only NUMBERS are slot-filled/verified.** The companion still sounds human; it just can't author a figure.
- **G1's false-positive surface = the safe-non-claim set (d).** A date or "top 3" must not be stripped. This is the one thing to tune carefully — but it's ONE central allowlist, the opposite of the per-scenario regex treadmill.

---

## 4. Sources (skills-first, then reputable; per the standing method)
- WorkHive skills: **ai-engineer** (WAT FACT-SHEET doctrine L769/798/822/1526), **maintenance-expert** (benchmark values for G1b), **security** (excessive-agency / no-free-generation routing).
- [NeMo Guardrails — fact-checking & dialog rails](https://docs.nvidia.com/nemo/guardrails/latest/configure-rails/guardrail-catalog/fact-checking.html) · [NeMo Guardrails (arXiv 2310.10501)](https://arxiv.org/pdf/2310.10501)
- [Guardrails AI — structured output / RAIL](https://guardrailsai.com/blog/nemoguardrails-integration)
- [RAG hallucination mitigation survey (MDPI)](https://www.mdpi.com/2227-7390/13/5/856) · [Detect RAG hallucinations (AWS)](https://aws.amazon.com/blogs/machine-learning/detect-hallucinations-for-rag-based-systems/)
- [Constrained decoding guide](https://www.aidancooper.co.uk/constrained-decoding/) · [Alignment tax of constrained decoding (arXiv 2604.06066)](https://arxiv.org/pdf/2604.06066) · [VeriFact — verify facts against records (arXiv 2501.16672)](https://arxiv.org/pdf/2501.16672)

---

## 5. Roadmap placement & start point
This is **§0.7 of `AI_SURFACE_MAP.md`** (the canonical companion spine), the continuation after §0.5 (P/T/R/V/Q/S/U + faithfulness rail, all DONE). **The faithfulness rail (§0.5 Pri 2) is now SUPERSEDED — G1 retires it.**
**NEXT WINDOW START = Phase G1.** Ground in: `voice-journal-agent/index.ts` (current `stripUngroundedKpi` to replace), `ai-gateway buildOpsSnapshot` (the fact-set source), `companion_fabrication_sweep.py` grade() (the eval counterpart). Local edge hot-reloads voice-journal-agent; `_shared/*` needs an edge restart. Everything LOCAL/uncommitted; prod push Ian-gated.
