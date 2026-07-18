# Workflow: Make-a-Change — one workflow, three modes, one shared tail

**Objective.** Take a triaged "change" request and ship it. All three modes share the **same
back-half** (the Flywheel tail: verify → lock → teach → persist). They differ only in the
**front-half** — how you ground and build. Pick the mode, do its front-half, then hand to
`flywheel.md` from spoke 3 (Verify).

**Entered from.** `FRAMEWORK.md` Step 0 (Triage) when the request changes product code.

---

## Pick the mode

| Mode | Use when | Front-half (before the Flywheel tail) |
|---|---|---|
| **Feature** | adding a new page / edge fn / capability | skill-first → build → **registration checklist** (nav registry, validators, assistant context, catalog tables) |
| **Fix** | correcting a bug | **ripple-map first** (what else touches this?) → skill-first → fix at root cause → verify the **row, not the toast** |
| **Redesign** | reworking a whole page/layout | **evaluator-optimizer loop** (below) + **whole-page disposition map** |

---

## Feature mode — registration is part of "done"

A new surface isn't done when it renders; it's done when it's **registered**. Before Verify:
- nav registry / two-tier hub updated
- a `validate_*.py` covers it (or an existing one extended) and is registered in `run_platform_checks`
- the AI assistant's platform-context list names the new page
- any catalog tables are excluded from `RESET_TABLES`
- deep-link params it emits have a **reader** in the destination page

## Fix mode — ripple before repair, via the lever ladder (P5)

- **Ripple-map first:** grep the fix's pattern platform-wide; a bug in one renderer is usually in its
  siblings.
- **The lever ladder (P5 — component-library-first, the harmonious-family north star):** a repeat
  across siblings is **ONE unadopted canonical component, not N bugs**. Fix it at the HIGHEST rung that
  covers all instances — **token → shared component → shared script → per-page (LAST resort)**. The
  instant you're about to hand-edit surface 2, STOP, lift it up a layer, and adopt it family-wide
  (check `component_adoption_report.md` / the layer `*_component_registry.json` first). Per-page edits
  are the symptom, never the cure; they're what make pages read as "different personalities."
- **Root cause, not symptom.** Then verify the DB row + FK, not the success toast.

## Redesign mode — an explicit evaluator-optimizer

This is Anthropic's **Evaluator-Optimizer** pattern, and it's Ian's preferred loop:

1. **Generate** — crawl the current page → grade against the rubric → build a **standalone
   before/after mockup** to the Desktop.
2. **Evaluate** — Ian reviews the mockup (the SOFT/vision judge is *his* eye; do the Playwright
   legwork yourself first).
3. **Optimize** — refine against the feedback; re-present until approved.
4. **Only then implement** — and implement the **whole page**: build the CURRENT→TARGET
   **disposition map** (every element = KEEP / MOVE / MERGE / DELETE — a new element that surfaces
   data X makes every old X-surface redundant; delete/merge them in the *same* change), then verify
   with a **full-page screenshot diff**, never viewport-only.

---

## Then: the shared Flywheel tail

Regardless of mode, hand to `flywheel.md` at spoke 3:
**Verify → Lock (validator + gate + sentinel) → Teach (all relevant skills) → Persist (Memento) → Next.**

## Grounding

- Anthropic *Building Effective Agents* — Evaluator-Optimizer, Orchestrator-Workers.
- `substrate/` — `feedback_redesign_scope_whole_page_not_component`,
  `feedback_new_feature_registration`, `feedback_cross_page_sibling_sweep_and_registration`,
  `feedback_proposal_first_ux_mockup_loop`, `feedback_soft_judge_do_it_yourself`.
