# FRAMEWORK — the reusable operating system for building WorkHive

**What this is.** The small set of workflows we actually repeat, fused from a flat list of 22
recurring motions into **3 core workflows + a reflex layer + a content track**, governed by 4
principles and entered through one router. Use this as the map; each workflow has its own SOP in
`workflows/`.

**Where it came from.** Synthesized from `CLAUDE.md` (standing rules), the `substrate/`
(WORKHIVE_PLATFORM_BOOK, GROUNDED_SWEEP_ROADMAP, the self-improvement-loop docs), and Memento
feedback memories — then upgraded against two external sources distilled into the bag via the
Night Crawler:
- Anthropic, *Building Effective Agents* → `substrate/external/external-building-effective-agents-workflow-patterns.md`
- *12-Factor Agents* (humanlayer) → `substrate/external/external-12-factor-agents-reliability-principles.md`

---

## The whole thing on one line

> **TRIAGE** the request → route to **MAKE-A-CHANGE** (build) · **AUDIT→SYNTHESIS** (discover) ·
> or a **CONTENT SOP** → all of which run on **THE FLYWHEEL** spine → governed by the **PRINCIPLES**
> and interrupted by the **REFLEXES**.

```
  incoming request
        │
   ┌────▼─────────────────────┐
   │ STEP 0 · TRIAGE / ROUTER  │   ← classify, then route (Anthropic "Routing")
   └────┬───────────┬─────────┬┘
        │           │         │
   change?      discovery?  content?
        │           │         │
        ▼           ▼         ▼
  MAKE-A-CHANGE  AUDIT→     CONTENT SOPs
  (3 modes)      SYNTHESIS  (article / video)
        │           │         │
        └─────┬─────┘         │
              ▼               │
        THE FLYWHEEL  ◄────────┘   ← the spine every unit of work runs on
   skill-first → work → verify → lock → teach → persist → next
              ▲
        governed by PRINCIPLES P1–P4  +  REFLEXES (check-the-bag / recall-the-move / canonical / whole-artifact)
```

---

## Principles (P1–P5) — the governing header

- **P1 · Simplest thing first; escalate only when it pays.** Default to an inline, single-pass
  solution. Add steps, agents, or structure only when a concrete need justifies the added latency
  and token cost. *(Anthropic: "start simple, increase complexity only when it improves outcomes.")*
- **P2 · WAT is the split.** Workflows (deterministic SOPs) decide *what*; the Agent decides
  *which/when*; Tools (`tools/*.py`) execute. This is exactly Anthropic's own "workflows for
  predictable tasks, agents for flexibility" distinction — external validation that the
  architecture is right. Probabilistic reasoning orchestrates; deterministic code executes.
- **P3 · Parallelize by sectioning + adversarial verify — INLINE, never agent fan-out.** Anthropic's
  Parallelization pattern is real, but on this project the `Workflow` fan-out tool is permanently
  disabled and tokens are Ian's cost. So we get parallelism's benefit the token-safe way: **section**
  the work-list (one page / one surface at a time) and **verify** with a single adversarial pass —
  we do not spawn agent fleets. *(See `WORKFLOW_TOKEN_GOVERNANCE.md` + retrieve-first.)*
- **P4 · Every tool has a documented interface + a self-test.** A tool the Agent can't understand or
  trust is a liability. Each `tools/*.py` states its inputs/outputs and ships a self-test (most
  validators already do). *(Anthropic's "Agent-Computer Interface"; 12-Factor "tools as structured
  outputs".)*
- **P5 · Unified design = centralized component libraries; the platform is a harmonious FAMILY, not
  different personalities.** ★ THE north star for this platform (Ian, 2026-07-16: *"a centralized
  design component library for my family pages… not like different personalities but a harmonious
  family"*). A defect that repeats on N surfaces is **never N bugs — it is ONE unadopted canonical
  component** (the FAMILY_UFAI §10 METHOD LAW). The **lever ladder** governs every fix, in order:
  **token → shared component → shared script → per-page (LAST resort).** Per-surface hand-edits are
  the *symptom*, never the cure — the instant you catch yourself editing the same pattern on surface
  2, STOP and lift it up a layer. Retrieve-first applies to **components**, not just knowledge: before
  building any shared affordance, grep the adoption of the component that already satisfies it (a
  0%-adopted component is indistinguishable from one that doesn't exist — except it already cost the
  build). Canonical spines: **`FULLSTACK_COMPONENT_LIBRARY_ROADMAP.md`** (per-layer adoption %) +
  **`FAMILY_UFAI_ROADMAP.md`** (cross-page rubric score). See
  [[feedback_family_resemblance_cross_page_lens]] + [[feedback_universal_a11y_shared_component]].

---

## Step 0 · TRIAGE / ROUTER — pick the path before doing the work

The one motion our old list was missing: an explicit classifier. Before touching anything, route:

| The request is… | Route to | Because |
|---|---|---|
| "build / add / fix / redesign X" | **`workflows/make_a_change.md`** (pick a mode) | it changes product code |
| "is X right? / audit / walk / find problems in X" | **`workflows/audit_to_synthesis.md`** | it discovers work; each finding then re-enters Make-a-Change |
| "write the article / render the video" | **content SOP** (`workflows/video_marketing.md`, /learn article SOP) | separate track, own cadence |
| "we're blocked / it needs data / it's external" | **REFLEXES first** (recall-the-move) before accepting the blocker | a ceiling is usually a move we already have |

Routing is a decision, not a build step — cheap, always first.

---

## The 3 core workflows

1. **THE FLYWHEEL** — `workflows/flywheel.md`
   The spine. Every unit of work is a **prompt-chain with an exit-gate between spokes**:
   `skill-first → do the work → verify → lock (validator + gate + sentinel) → teach (skills) →
   persist (Memento) → next`. You do not advance a spoke until its gate is green.

2. **MAKE-A-CHANGE** — `workflows/make_a_change.md`
   One workflow, three entry **modes** (Feature / Fix / Redesign) that share the *same* Flywheel
   tail and differ only in the front-half. **Redesign runs as an explicit evaluator-optimizer**
   (proposal-first mockup → Ian evaluates → refine) with a whole-page disposition map.

3. **AUDIT → SYNTHESIS** — `workflows/audit_to_synthesis.md`
   The discovery workflow and the *evaluator half* over the whole platform: pick an instrument
   (deep MCP walk / UFAI battery / cross-page sweep), measure, then **synthesize** (cluster by
   job-to-be-done, opinionated fuse-or-keep verdicts). Synthesis is the deliverable, not the
   findings list. Each finding becomes a Change.

---

## Reflexes — fire *inside* every workflow (not standalone SOPs)

- **Check-the-bag first.** Before building or crawling, retrieve: `memento_retrieve.py "<topic>"`,
  a `SKILL.md`, the substrate, or `night_crawler.py --query`. Never re-derive known knowledge.
- **Recall-the-move before declaring a ceiling.** A "blocker" is usually a move we already have:
  **reseed** (`seeders/`), **start a stopped container** (`docker start <svc>`), **install a local
  tool**, **run a local substitute**, or **reuse an existing harness**. Only after that comes up
  empty is it a genuine external ceiling — and if it needs *structure* to be provable, build the
  structure.
- **Canonical audit.** Check what already exists before building anything new.
- **Component-library-first (the lever ladder — P5).** Before ANY per-page fix, check the canonical
  component's adoption (`component_adoption_report.md`, the layer `*_component_registry.json`). Fix the
  canonical component + adopt it family-wide; never hand-patch surface-by-surface. A repeated defect =
  ONE unadopted component — this is how the platform stays a harmonious family, not different
  personalities.
- **Whole-artifact discipline.** A redesign transforms the *whole* page — build the
  CURRENT→TARGET disposition map (KEEP/MOVE/MERGE/DELETE) and verify with a full-page diff, never
  just the component you touched.
- **★ Point to the roadmap-%-board when in doubt (the anti-drift compass — Ian, 2026-07-17).** The
  measured-%-per-phase roadmap is the compass. **(1)** UPDATE its %-cell the moment you move a phase —
  it's part of the Flywheel's Persist spoke; a stale board is worse than none. **(2)** At ANY "what
  next / should I stop / is this worth it / which item" doubt — *especially* as a session lengthens and
  the pull toward smaller tangents grows — re-read the CURRENT %-board and drive its **LOWEST-scoring
  in-scope cell**. When in doubt, the roadmap decides, not the tangent in front of you. See
  `workflows/flywheel.md` (Persist+ratchet / Next-via-compass / the anti-drift rule) +
  [[feedback_roadmap_percent_is_the_anti_drift_compass]].

---

## Content track (separate cadence)

- **/learn article build** — tool-aligned, full-audience-spectrum SEO content.
- **Video pipeline** — `workflows/video_marketing.md` (Remotion / clean-screen capture).

These are genuine standalone SOPs, not part of the platform Flywheel.

---

## How the framework improves itself

The Flywheel's **teach** + **persist** spokes are what make this compounding: every fix writes a
lesson back to all relevant `SKILL.md` files and a `NEXT:` trajectory to Memento. The AUDIT
workflow feeds the Flywheel; the Flywheel feeds the skills; the skills make the next AUDIT sharper.
That loop — not any single workflow — is the point.
