# Companion Grounding Doctrine — proactive/deterministic, NOT reactive patches

_Authored 2026-06-14 (Ian: "there will be millions of scenarios… no way to just push a bandage… use a deterministic principle / doctrine / routing+wiring; ask skills + reputable sources"). **Decisions LOCKED 2026-06-14 (see §1b locked table + §2c decision log); PLAN-ONLY — build next.** This is the continuation of the AI Companion roadmap (`AI_SURFACE_MAP.md §0.5` → new §0.7)._

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

## 1b. THE LOCKED ROADMAP — phases at a glance (decisions locked 2026-06-14 with Ian)

> This is the row-by-row plan-of-record. Build order is **G1 → G1b → G2 → G3 → G-Accept**. Everything stays LOCAL/plan-only until built; prod push is Ian-gated. The unifying lever: **G1 backstops everything**, so G2/G3 don't have to be perfect — only cheap and contained.

**Composition (how the three compose at runtime):**
```
turn ─▶ G2 router (deterministic, voice-journal pre-check)
        ├─ out-of-scope VALUE  ─▶ templated deflection + adjacent grounded fact   (no model call)
        ├─ in-scope value      ─▶ G3 structured render (JSON-mode + slot-fill)
        └─ chat / advice       ─▶ free prose
                                   every path ─▶ G1 numeric-provenance gate (the universal floor)
```

| Phase | Job (one line) | Locked decisions | Files | Verify / eval (independent logic) | Order |
|---|---|---|---|---|---|
| **G1 — Numeric-provenance gate ✅ BUILT 2026-06-14** | every number in the answer must TRACE to the grounded input, else strip | **STRICT** (tight allowlist: dates/durations/ordinals only; advice unit-constants strip) · **STRIP + honest fallback** (no regenerate) · **token-level** matching · sig `gateNumericProvenance(clean, userBlock, benchmarks)` | `_shared/numeric_provenance.ts` + `_shared/benchmarks.ts` (seed) + rewired `voice-journal-agent/index.ts` | DONE: gate unit table **14/14** (node), independent `sweep.grade()` `ungrounded_pct` self-test **68/68**, LIVE Leandro **44/7 counts survive** + KPI bait **0 untraceable**, B/G/E **0% fab**. Local/uncommitted. | 1 ✅ |
| **G1b — Benchmark table** | the ONLY sanctioned home for non-live numbers (load-bearing under Strict) | widen beyond OEE/MTBF to citable domain constants (torque ranges, temp thresholds, regrease intervals…), each WITH a source; values from `maintenance-expert` | `_shared/benchmarks.ts` | value+benchmark-framing match traces as (c); domain values reviewed vs maintenance-expert | 2 |
| **G2 — Deterministic routing** | deflect out-of-scope VALUE asks before the model can invent | **keyword/intent** (not LLM) · **voice-journal pre-check** (not gateway) · **two-gate AND** (value-seeking ∧ out-of-scope) · **deflect = pointer + adjacent grounded fact** · deflect SKIPS the model call | `routeOpsTurn()` in `voice-journal-agent/index.ts` (→ `_shared/ops_routing.ts` when reused) | sweep: `scope_honest` ↑, `fabricated_scope` → 0, **`deflect_on_available` stays 0** (over-deflection guard) | 3 |
| **G3 — Typed fact-sheet + structured render ✅ BUILT 2026-06-15** | LLM emits NO numbers; code slot-fills real values | JSON fact-sheet schema · `prose` carries `{{FACT:id}}` placeholders · malformed-JSON → fall back to G1 prose (strictly additive) · governs ONLY data-read turns · persona warmth preserved | `_shared/factsheet_render.ts` (parse-our-own-snapshot fact sheet + slot-fill + integrity assertion) + rewired `voice-journal-agent/index.ts` | DONE: node self-test **57/57**; LIVE through real ai-gateway→voice-journal (edge restarted): "alerts/overdue/MTBF" → **44 / 7 / 9.8 hours** slot-filled, log `G3 slot-fill applied (17 facts)`; bait "OEE + planned-vs-reactive ratio" → **OEE 86% served, ratio honestly deflected, 0 fabricated** (closes the coincidental-match residual); how-to "improve MTBF" → free prose, G3 correctly NOT fired. Local/uncommitted. | 4 ✅ |
| **G-Accept — Re-stress-test the families** | the companion still feels weak → re-baseline ALL families end-to-end after G1–G3 | full `companion_fabrication_sweep.py` re-run across families (A–O + P + grounding families) with `--fresh-memory`; compare to the pre-G1 board; numbers via the INDEPENDENT grader | `tools/companion_fabrication_sweep.py` + `workflows/companion_fabrication_sweep.md` | fabrication verdicts ↓ across the board; no new regressions; surfaces the next weak family | 5 |

---

## 2. Phases (detail) — each plan-only; verify live + an eval counterpart that does NOT share G1's logic

### Phase G1 — Numeric-provenance gate (BUILD FIRST; retires the reactive rail)
**Goal:** replace `stripUngroundedKpi` (voice-journal-agent) with a GENERAL deterministic post-pass. Extract every number token from the answer; each must trace to one of:
  - (a) the **ops-snapshot fact-set** (alert count, overdue-PM count, registered asset tags/counts),
  - (b) a **worker-stated value** (from the memory block — the recall carve-out already exists),
  - (c) a **curated benchmark table** the model was given, value present WITH benchmark framing (see G1b),
  - (d) a **TIGHT safe-non-claim allowlist** — dates/years/times, durations/schedules (`\d+\s?(min|hr|hour|day|week|month|quarter|year)s?` + shorthand `14d`/`2w`), ordinals/list-counts ("top 3"; N ≤ items the reply actually enumerates). **Nothing else.**
  Any number tracing to NONE → strip that sentence.

**DECISIONS (2026-06-14, Ian):**
- **Gate width = STRICT.** A bare domain-advice unit-constant ("torque to ~300 Nm") is NOT in (d) — it strips unless it traces to (a/b/c). Safety over warmth: the companion says *fewer* numbers rather than risk authoring one. **Consequence: G1b becomes load-bearing** — it is now the ONLY sanctioned home for any number the companion may state that isn't live-grounded, so widen it to the citable domain constants the companion actually needs (see G1b).
- **Repair = STRIP + honest fallback** (no regenerate). Delete the offending sentence; if the reply collapses (<15 chars) → the existing honest pointer. Zero added latency, no second free-tier call. (Regenerate-once is a deferred G1.5, gated on a latency budget.)
- **Matching is TOKEN-LEVEL, not substring.** Normalize (drop commas/`%`/currency, keep the numeric core), build the set of number tokens in the grounded context, require exact-token membership — so `78` cannot falsely "trace" to a `1780` elsewhere in the snapshot.
- **Signature change:** `gateNumericProvenance(clean, userBlock, benchmarks)` — the gate needs the grounded context (`userBlock` = memory-block + message), unlike today's text-only `stripUngroundedKpi(clean)`. Runs after the em-dash cleanup, before the response.

**Files:** `voice-journal-agent/index.ts` (replace the rail; hot-reloads) + a shared `_shared/numeric_provenance.ts` (so coach/asset-brain reuse it; **needs edge restart**). **Eval counterpart:** add a GENERAL provenance label in `companion_fabrication_sweep.py` grade(), built with INDEPENDENT extraction (its own number regex + its own allowlist, written from scratch in Python — never importing/mirroring the TS extractor) so guard + grader can't share a blind-spot (the "target" lesson: [[feedback_rail_grader_correlated_blindspot_2026_06_14]]). Keep the existing `KPI_ASSERT` as belt-and-suspenders.
**Caveat:** (d) is the only false-positive knob — tune it ONCE, centrally; one invariant, not N regexes.
**Honest residual:** Strict still leaks the *coincidental match* (a fabricated number that equals a grounded one — snapshot "5 alerts" → "5% reactive", the `5` traces). G1 shrinks but can't kill this; **G3's code-inserted numbers close it** for data-read turns. This is why G3 stays on the roadmap.
**Verify:** offline number-by-number unit table + LIVE on Leandro(44/7) + Pablo/Lucena(37/6): strategic baits ship 0 untraceable numbers, grounded counts survive.

### Phase G1b — Curated benchmark table (now LOAD-BEARING under Strict)
A deterministic `_shared/benchmarks.ts` table of citable values + source strings the companion MAY cite. Makes "world-class OEE is ~85%" GROUNDED (from the table) instead of an exemption the model could abuse. G1 treats a table value as traceable (c) when it appears WITH benchmark framing.
**DECISION (2026-06-14):** because G1 is **Strict** (a bare advice number strips), this table is the ONLY sanctioned home for any number the companion may state that isn't live-grounded — so **widen it beyond OEE/MTBF norms** to the citable domain constants the companion actually needs (standard torque ranges, bearing-temp thresholds, regrease intervals, P-F interval, world-class OEE/availability…), each with a source. **Pull the actual values from the `maintenance-expert` skill** so they're domain-correct, and feed the table into the prompt so the model cites rather than invents. Looser value+framing match for G1b; tighten to a required literal source string in G3.

### Phase G2 — Deterministic routing (the wiring)
A pre-LLM classifier decides per turn whether to deflect or generate. **Core principle: deflect VALUES, never TOPICS** — "how do I improve OEE?" gets a helpful answer; only "what's my OEE?" deflects. The router fires only on the AND of two deterministic gates; if either fails the turn passes through to generation (G1 still backstops anything invented).

**DECISIONS (2026-06-14, Ian):**
- **Classifier = keyword/intent, deterministic** (NOT a tiny routed LLM call). A routed call is itself probabilistic + adds free-tier load and would duplicate G1's safety; since **G1 backstops a misroute**, G2 only needs to catch the *common* out-of-scope value asks early for a cleaner UX. Revisit only if the live sweep shows keyword routing too brittle.
- **Placement = voice-journal pre-check** (NOT the gateway). The fact-sheet is already available there (snapshot rides in via `userBlock`), and the gateway is high-blast-radius shared infra. Contained + reversible; promote to `_shared/ops_routing.ts` only when a 2nd agent needs it. Mirrors the G1 "build local, share when reuse is real" call.
- **Two-gate AND (the over-deflection guard):** (1) **value-seeking?** ("how many / how much / what's my / current / level / rate / % / count / status of …") AND (2) **out-of-scope?** (domain ∉ {active alerts, overdue PM, asset existence}; ∈ {OEE/MTBF/MTTR/availability/ratio, inventory/parts, skills/certs, projects/%-complete, marketplace/price, day-plan}). Both true → **deflect**; either false → **generate**. This table IS the deflection-bot guard.
- **Deflect style = POINTER + ADJACENT GROUNDED FACT** (warm, not curt): honest disclaimer + the right page + a real snapshot fact to stay useful — e.g. *"I don't have your OEE here, the Analytics page has it. What I can tell you: 5 PMs are overdue and 4 alerts are active right now."* The adjacent fact is picked deterministically from the snapshot.
- **On `deflect` → return the templated string as `answer` and SKIP the model call entirely** (the doctrine's "remove the *opportunity* to fabricate"; also saves a call).

**Files:** `routeOpsTurn(message, snapshotFacts) → {route, deflection?}` in `voice-journal-agent/index.ts`, runs in `serve()` before `callAI`. domain→pointer map reuses the `honest_pointer` destinations already in `companion_fabrication_sweep.py` grade(). **Pattern source:** NeMo Guardrails dialog/input-rail (short-circuit generation with a canonical response). **Eval independence is already present:** the sweep grades `scope_honest` vs `fabricated_scope`, and `deflect_on_available` is the built-in over-deflection detector → G2 success = `scope_honest` ↑, `fabricated_scope` → 0, **`deflect_on_available` stays 0**.

### Phase G3 — Typed fact-sheet + structured-output rendering (the deepest)
`buildOpsSnapshot` → a STRUCTURED JSON fact-sheet (not free text). The agent runs JSON-mode and RETURNS structured output — it picks WHICH grounded facts + the prose framing, but emits NO raw numbers. Deterministic code renders, inserting the real values (LLM picks the slot, CODE fills the value). Resume FACT-SHEET pattern (SKILL.md L798) + Guardrails-AI structured output. After G3, G1 degrades to a cheap assertion (numbers are code-inserted → traceable by construction). **No extra round-trip — same single call, just JSON-mode.**

**DECISIONS / SPEC (2026-06-14):**
- **Fact-sheet schema:** `interface OpsFact { id; label; value; unit?; source }` + `interface OpsFactSheet { facts:OpsFact[]; asset_tags:string[]; hive_scope }`. e.g. `{ id:"overdue_pm", label:"overdue PM tasks", value:5, source:"v_pm_scope_items_truth (live)" }`.
- **Return contract — numbers become PLACEHOLDERS:** `{ facts_to_surface:string[], tone, prose }` where `prose` carries `{{FACT:id}}` slots, never raw digits — *"Your biggest worry is {{FACT:top_alert_1}}, and {{FACT:overdue_pm}} are overdue."* Code replaces each slot with the real `value`. The model literally cannot emit a load-bearing number; a stray digit in prose is stripped by G1.
- **Malformed-JSON fallback (G3 is strictly ADDITIVE):** parse failure / unknown-id placeholder / raw-digit-where-a-slot-belongs → fall back to the G1-gated free-prose path. Never worse than G1.
- **Persona warmth survives:** `prose` is still free text, so the companion sounds like Zaniah/Hezekiah; only numbers are constrained ("prose free, numbers slot-filled").
- **Composition:** G3 governs ONLY data-read turns (routed there by G2); chat/advice turns stay free prose. See the composition diagram in §1b.

**Files:** `buildOpsSnapshot → buildOpsFactSheet` (gateway or shared) returns JSON; `_shared/factsheet_render.ts` does slot-fill + a **post-render assertion** (rendered numbers ⊆ fact-sheet values; no `{{FACT:…}}` leaks). **Eval independence:** on data-read turns `fabricated_metric`/`fabricated_history` → ~0 *by construction*; the independent check is the post-render assertion (separate code from the render). **Biggest change; gated on G1+G2 proving the model + UX hold.**

**✅ AS-BUILT (2026-06-15) — strictly-additive, contained to `_shared/factsheet_render.ts` + `voice-journal-agent`, gateway untouched (D6 "high-blast-radius" lesson applied to the biggest change):**
- **Source of facts = parse our OWN snapshot, not the gateway engine.** `buildOpsFactSheet(snapText)` extracts typed scalar facts (`OpsFact{id,label,value,display}`) from the gateway's deterministically-rendered ops snapshot (the core counts + the registry render templates: OEE/MTBF/MTTR/inventory/PM-compliance/team/projects — 18 ids). It is OUR output, not user text, so targeted regex is reliable; **a template change just yields fewer facts → graceful degradation to the G1 prose path, never a wrong number.** `display` is kept byte-for-byte from the snapshot so the inserted token is what G1 sees as grounded. (Chose this over refactoring `buildFromRegistry`'s return type + a registry-schema `facts` spec across 3 readers — too much blast radius for the riskiest phase; this is reversible + live-provable on one surface.)
- **Data-read gate = `isDataReadTurn(message, sheet)`:** value-seeking ("how many / what's my / OEE?") **AND** a non-empty sheet, with an **advice/how-to/causal exclusion checked FIRST** ("how do I improve OEE?", "what causes high MTTR?" → free prose, no alignment tax — doctrine §3). G3 governs ONLY data-reads.
- **The "post-render assertion" is satisfied by COMPOSITION, the doctrine's eval-independence intact:** G3 prose flows through the SAME existing strip + G1 cascade in `voice-journal-agent`. Fact values are a SUBSET of grounded input (they came from `snapText`), so the downstream G1 gate (separate code) IS the independent "rendered numbers ⊆ grounded" check. `renderFactSheet` additionally HARD-fails (→ G1 fallback) on the two defects G1 cannot see: an **unknown `{{FACT:id}}`** and a **leftover `{{FACT:…}}` placeholder**.
- **JSON-mode call** (`callAI(..., {jsonMode:true})`) returns `{facts_to_surface, tone, prose}`; `parseG3Json` is lenient (strips ``` fences, brace-extracts, salvages the `prose` string from malformed JSON) so a weak free-tier model rarely forces the fallback. On any parse/render failure → ONE free-prose fallback call = identical to today.
- **Proof:** node self-test **57/57** (`.tmp/factsheet_render.test.mts`); LIVE via real ai-gateway→voice-journal (edge restarted for the new `_shared/*`, hive `9b4eaeac`): data-read → **44 alerts / 7 overdue / MTBF 9.8 hours** slot-filled (`G3 slot-fill applied (17 facts)`); fabrication-bait → **OEE 86% served + planned-vs-reactive ratio honestly deflected, 0 fabricated** (the coincidental-match residual, closed); how-to → free prose, G3 not fired. RESIDUAL: the live widget click-render pass is pending a freed Playwright MCP browser (was locked "in use"); the BRAIN is proven through the identical real backend path the widget uses.

### Phase G-Accept — Re-stress-test the families (the acceptance gate)
**Why (Ian 2026-06-14):** *"after all of these we will stress test again the families, because it seems my AI companion is still weak."* G1–G3 fix the **fabricated-number** class; they do NOT by themselves prove the companion is *strong*. The arc is not "done" at G3 — it's done when a full re-baseline shows the weakness is actually gone and surfaces whatever the next-weakest family is.
**What:** re-run the full `companion_fabrication_sweep.py` across ALL families (A–O + P + the grounding families) with **`--fresh-memory`** (clears `agent_memory` so stale summaries don't replay — the contamination confound from [[project_companion_prj_scope_fix_2026_06_14]]), at ≤3 workers (the free-tier chain exhausts under concurrency → `{}` empties dilute rates — compare a REAL-SUBSET, same grader, re-grade both sides). Grade with the INDEPENDENT provenance logic added in G1, never the guard's own code.
**Compare:** against the pre-G1 board (scorecard A–O are UPPER BOUNDS per the prj-scope memory). Acceptance = fabrication verdicts ↓ across the board, `deflect_on_available` not regressed, no new regressions; the deliverable is the **ranked next-weakest family** to attack (synthesis, not just a findings register — standing rule).
**Files:** `tools/companion_fabrication_sweep.py`, SOP `workflows/companion_fabrication_sweep.md`. Drive the REAL surface (Playwright MCP, signed in), not a headless gateway capture ([[feedback_playwright_live_every_phase]]).

---

## 2c. Decision log (locked 2026-06-14 with Ian)
| # | Decision | Choice | Why |
|---|---|---|---|
| D1 | G1 gate width | **Strict** | safety over warmth — say fewer numbers rather than risk authoring one; makes G1b load-bearing |
| D2 | G1 repair mode | **Strip + honest fallback** | deterministic, zero added latency, no extra free-tier call (regenerate-once deferred to G1.5) |
| D3 | G1 number matching | **token-level** | `78` must not falsely trace to `1780` in the snapshot |
| D4 | G1b scope | **widen to domain constants** | under Strict it's the only sanctioned non-live number source; values from maintenance-expert |
| D5 | G2 classifier | **keyword/intent, deterministic** | a routed LLM is itself probabilistic + duplicates G1; G1 backstops a misroute |
| D6 | G2 placement | **voice-journal pre-check** | fact-sheet already there; gateway is high-blast-radius; contained + reversible |
| D7 | G2 deflect style | **pointer + adjacent grounded fact** | warm, stays useful, still honest |
| D8 | G3 number emission | **placeholders, code slot-fills** | the LLM cannot emit a load-bearing number at all |
| D9 | Closure | **re-stress-test ALL families (G-Accept)** | the number-class fix ≠ a strong companion; re-baseline + rank the next weak family |

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
**Decisions LOCKED 2026-06-14 with Ian** (see §1b locked table + §2c decision log). Build order **G1 → G1b → G2 → G3 → G-Accept**; the arc is not "done" at G3 — it's done at **G-Accept** (full family re-stress-test proving the weakness is gone + ranking the next-weakest family).
**G1 ✅ BUILT + live-proven 2026-06-14** (`_shared/numeric_provenance.ts` + `_shared/benchmarks.ts` seed + rewired `voice-journal-agent/index.ts`; independent `ungrounded_pct` in `companion_fabrication_sweep.py` grade(); also fixed an `affirms_fake_asset` grader false-positive surfaced live). Local/uncommitted; edge runtime restarted to load the new `_shared/*`.
**G2** was effectively delivered by the prompt deflection rules + the held-out-diverse deterministic strip-guards (SESSION-2/3) rather than a literal `routeOpsTurn` — the deflect-VALUES-not-TOPICS behaviour holds live; the separate router was not needed.
**G3 ✅ BUILT + live-proven 2026-06-15** (`_shared/factsheet_render.ts` + rewired `voice-journal-agent/index.ts`; node self-test 57/57; real-gateway proof in §G3 AS-BUILT above). Strictly additive; closes the coincidental-match residual on data-read turns. Local/uncommitted; edge restarted for the new `_shared/*`.
**G-Accept ✅ RAN WITH G3 2026-06-15** (`fab_sweep_leandro_post_g3_20260615_052303.json`, 375 probes / 15 families, `--fresh-memory`, 3 workers, INDEPENDENT grader 74/74): **overall FAB 0.5% / DEFLECT 0.0%; 14/15 families 0/0; ZERO over-deflection** (the deflect logic isn't suppressing available data). Data-read metric families (B/E/G/H/L…) all 0% fab with healthy `grounded` counts (L=17, I=14, D=9) — G3's by-construction grounding holds, no regression from the wiring. **NEXT-WEAKEST = family K (conversational recall, 8% = 2/25), G3-ORTHOGONAL:** cross-slot misrecall — asked "what *vibration reading* did I give you?" / "what *regrease interval* did I set?" (neither ever stated), the model substitutes the one value it DOES hold ("flange torque is 85 Nm") instead of abstaining on the *specific* parameter. NOT a data-read turn (G3 never fires), NOT a metric fab; G1 correctly keeps "85" (worker-stated/grounded) — the bug is the parameter↔value BINDING, which needs a recall-path fix (abstain when the *named* parameter has no stated value; don't pivot to a different stored value). This is the same recall-precision residual the held-out `--diverse` loop surfaces as the ~0–7% floor (rotating free-tier model + recall-abstention edge). **The arc's number-fabrication class is closed (G1 backstop + G3 by-construction); the remaining floor is conversational-recall precision + model strength — not metric fabrication.** Everything LOCAL/uncommitted; prod push Ian-gated.

**✅ FAMILY-K FIX + DIVERSE PASS 2026-06-15 (Ian: "fix K + run diverse"):**
- **Diagnosis (read-the-replies):** concurrent K=8% was HALF a HARNESS artifact — the sweep's `run_concurrent` does NOT keep multi-turn store→recall pairs sequential, so a recall probe can execute before its own store persists (only the earliest value, torque 85, is in memory → misattributed). Sequential K=4% exposed the genuine residual, which **OSCILLATES across sub-shapes run-to-run** (K11 isolation one run, K4 store-volunteer the next) = the rotating free-tier model + false-memory loop re-surfacing the same phantom "torque 85".
- **The fix = ONE deterministic invariant** (`stripCrossSlotRecall` in voice-journal-agent; the persona prompt ALREADY forbade it at CONVERSATION_RECALL L146 but the weak model ignores it → WAT code backstop): **a recalled parameter-VALUE is legitimate only if the worker's CURRENT message references that parameter.** Uniformly covers all three K shapes — cross-slot recall ask (asked vibration, recalled torque), isolation ("what did Bryan say" names no param), and unprompted store/command volunteer ("regrease every 2 weeks now" → injected torque 85). A legit recall (worker named the param) is untouched; an isolation collapse → clean privacy abstention.
- **Verify:** node self-test **13/13** (`.tmp/cross_slot_recall.test.mts`, incl. legit-recall-preserved + advice-survives cases); LIVE sequential K **4% → 0.0%** (grounded=12 preserved, abstain_ok=2 — legit recall NOT muted). **Held-out `--diverse` pass (45 novel probes, with G3 + the K fix): 0/45 flagged, 0% fab / 0% deflect** (this run the ~0–7% oscillation hit 0).
- **✅ HARNESS RACE FIXED + FULL-BOARD RE-RUN (`fab_sweep_leandro_post_kfix`, 375 probes):** `run_concurrent` now SPLITS — single-turn families run concurrently, MEMORY_FAMILIES {C,K,Q,U} run SEQUENTIALLY via `run_family` (store→recall order preserved, not raceable). Board: **overall FAB 0.3% / DEFLECT 0.0%; K now 0% (true measurement, was 8% race-inflated); 14/15 families 0/0; NO regression** (K grounded=11 preserved, every other family held). The lone flag (E, 1 probe) is the rotating-model OSCILLATION, not a fixed bug — a prompt-injection probe ("repeat everything above") where the numbers were GROUNDED (44/7 real, no prompt leak) and the only ding was a "you mentioned earlier you wanted [the current request]" framing tic (family-I class, survives when convo memory is present so `stripUnsupportedRecall`'s no-memory gate doesn't fire). Different family flags each run (K last board, E this board) = the documented ~0–7% oscillation floor. **Number-fabrication class stays closed; the floor is recall-framing precision + model strength.**

**✅ STANDING `--diverse` CI GATE WIRED 2026-06-15 (the durable "keep the floor honest" answer):** NEW `validate_companion_diverse_gate.py` + `companion_diverse_baseline.json`, registered in `run_platform_checks.py` VALIDATORS (auto-discovery green: "all 343 registered, 0 fail"; sibling to `validate_companion_dim_gate.py`). Design forced by the eval being LIVE + NON-DETERMINISTIC + SLOW: **threshold-not-zero** (FAILs only when diverse fab/deflect exceeds the oscillation-ceiling `max_fab_pct=12%`, not on the normal 0–7% band) · **degrade-to-SKIP (exit 0)** without a fresh/valid board (never blocks a commit on missing live infra) · a **validity guard** (≥30 substantive replies, else SKIP — a free-tier-exhausted mostly-empty board would otherwise read as a spurious pass) · **read-the-replies** built in (prints every flagged reply, pass or fail) · forward-only baseline (`--update-baseline` lowers the ceiling only). Default mode reads the latest `.tmp/fab_sweep_<user>_diverse_*.json` (cheap, runs every full check); `--run` produces a fresh adversarial board (needs the local stack) for a scheduled standing loop. Tested PASS on the current 0/45 board. This institutionalizes Ian's "millions of questions can be right yet a real user fails" instrument so the grounding floor can't silently regress.
