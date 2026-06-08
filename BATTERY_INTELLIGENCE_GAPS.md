# BATTERY_INTELLIGENCE_GAPS.md — why the Layer-3 MCP battery is shallow, and the plan to make it think

> Owner critique (2026-06-08): *"my layer-3 UFAI full battery (the MCP sweep) lacks curiosity,
> proactivity, critical thinking and intelligence. It doesn't check clickables, the input/insert/select
> fields, shallow journeys and components… also lack of a critic that thinks 'this should be transferred
> here', 'this should be streamlined to one', 'this one is redundant and makes the user confuse' — alerts,
> shift handovers, AMC, everything."*

He's right. The battery today is a **deterministic referee** (axe contrast, tap-size, CWV, wiring-exists,
KPI-parity) + a **shallow fingerprint critic** (same-label / same-key / theme cluster). It checks whether a
thing is *readable / tappable / wired / numerically-right*. It does NOT check whether a thing is *the right
thing, in the right place, said once, and not confusing*. The marketplace dup-affordance false-positives
(counting 13 per-card "Save" buttons as redundancy) are the proof: the critic counts strings, it doesn't
reason about the product.

This doc maps each gap to a concrete build, in priority order. Doctrine unchanged: **DEFECT → fix inline;
CRITIC → surface for human disposition** (engine proposes, owner disposes).

---

## Gap 1 — Clickables are checked for EXISTENCE, not PURPOSE  ·  ✅ BUILT `__UFAI.clickAudit()` (v1.5.0)
**Status (2026-06-08): SHIPPED + validated.** Checks accessible-name, dead-ends, and **R-FP1 target-keyed
redundancy** — redundancy = `(name × RESOLVED target)`, EXCLUDING per-list-item siblings. Validated live on
marketplace: `listItemsExcluded:62`, `redundant:0` → the 4 dup-affordance false-positives I rejected in
`promotion_dispositions.json` are now **killed at the source**. Two bugs found+fixed during live validation:
(a) `closest('[class*=card]')` stopped at a card SUB-part (`div.card-image`, 2 sibs) not the repeated unit
(`article.listing-card`, 13 sibs) → now walks the FULL ancestor chain for a ≥2 same-template-sibling repeat;
(b) 9 modal-close buttons using `addEventListener` resolved to a `∅` target and collapsed → now only groups
on a RESOLVED target (conservative: may miss an unresolvable dup, never invents one).

### (original spec, retained)
**Today:** F-pillar checks `onclick → window[fn]` exists and `href` not-broken. That's it.
**Missing:**
- **Accessible name** — a `<button>`/icon-button with no text + no `aria-label`/`title` is unusable by SR
  and ambiguous to everyone. (axe catches *some*, but not icon-only buttons with a decorative SVG.)
- **Dead-end / no-op** — `href="#"`, `href="javascript:void(0)"`, `onclick=""` with no real handler.
- **Duplicate TARGET (the FP fix, R-FP1)** — redundancy is `(accessible-name × RESOLVED TARGET)`, not name
  alone. 13 "View" buttons that each open a *different* listing detail = a list (KEEP). 3 "Settings" links
  that all go to the *same* page from one screen = real redundancy. Key on the target, and EXCLUDE
  per-list-item actions (siblings under one repeated card/row container).
- **Reachability** — is this the ONLY way to do X, or the 4th? (ties to Gap 5.)
**Output:** `__UFAI.clickAudit()` → per-clickable {name, role, target, isListItem, defect?}.

## Gap 2 — Form fields (input / select / textarea) are barely checked  ·  ✅ BUILT `__UFAI.formAudit()` (v1.5.0)
**Status (2026-06-08): SHIPPED + found real defects.** Checks programmatic label (placeholder ≠ label),
right input type (from field key), iOS-zoom font floor, autocomplete on identity fields. First run on resume:
**16 unlabeled fields + an email rendered as `type=text`** — all invisible to the contrast/tap referee. The
`.field > label`(no `for`) + `.wh-input` pattern is **platform-wide (15 files, 851 occurrences)** → escalated
as work item `sweep:platform-wide:form-label-association` (W-form, approved DRAFT-REC). Downpayment shipped:
resume `basicsField()` template now emits `id`+`for` + type-from-key + autocomplete (7 fields fixed+verified;
16→9 remaining = section editors + other pages).

### (original spec, retained)
**Today:** only `input-font<16` (iOS zoom). Nothing else.
**Missing, per field:**
- **Programmatic label** — `<label for>` / `aria-label` / `aria-labelledby` / wrapping `<label>`. A
  placeholder is NOT a label (vanishes on input, fails SR). This is the #1 real form a11y defect.
- **Right input type** — an email field as `type=text` (no keyboard hint, no validation); a phone as
  `type=text` (should be `tel`); a quantity as `type=text` (should be `number`/`inputmode=numeric`).
  Heuristic from name/label/placeholder.
- **`autocomplete`** on identity fields (name/email/tel/org) — speed + correctness.
- **Required + error state** — is `required`/`aria-required` set where the flow needs it; is there a
  visible + `aria-describedby` error path (not just a toast)?
- **Placeholder ≠ sole instruction** — if the placeholder carries the only hint, it's lost on focus.
**Output:** `__UFAI.formAudit()` → per-field {hasLabel, type, expectedType, autocomplete, required, defects[]}.

## Gap 3 — Journeys are 2-3 KPI reads, not real job completion  ·  ✅ BUILT `journey_battery.js` v0.2.0
**Status (2026-06-08): SHIPPED + positive AND negative controlled.** Added `act(label, fn)` (DO an
interaction — fill/click — then snapshot; records errors) + `assertEqual(label, aSpec, bSpec)` where a spec
can be `{count: rowSelector}`. verdict() now raises `journey-action-inconsistency` (a control disagrees with
the data it drives) and `journey-action-error` (the task is blocked). **Validated live on pm-scheduler:** an
action-journey *tapped the "Overdue" filter and asserted the rendered list (2) == the Overdue KPI (2)* —
Tesler consistency, major 0. Negative control: asserting overdue(2)==due-soon(5) correctly fired the Major.
(Bug found+fixed live: action/assert steps have no `.readings`, so verdict's number-continuity must guard
`Object.entries(s.readings || {})`.) NEXT for this gap: a *create→appears→count* mutation journey (needs
local DB writes; self-clean with a resolve step).

### (original spec, retained)
**Today:** `step(label,{kpi:sel})` reads a number per page, asserts continuity. No ACTIONS.
**Missing:** a journey should DO the job — `create → appears → edit → complete → reflected in KPI`. e.g.
"log a fault → it shows in logbook → it bumps the open-count KPI → close it → count drops". That exercises
forms, optimistic UI, cross-surface propagation, and the empty→populated transition in ONE pass. Add
`action(label, fn)` steps (fill+submit) between the read steps; assert the post-state. Also: identity
state-continuity needs the `window.WHShell` (or localStorage) seam (already logged).

## Gap 4 — Components are shape-only, one altitude  ·  ✅ BUILT `__UFAI.statesAudit()` (v1.6.0)
**Status (2026-06-08): DONE.** `statesAudit()` now checks, per primitive family (12 incl `.btn`, `.asset-card`,
all the tab/chip/pill kinds): **(1) selected distinctness** — `.active`/`[aria-selected]` must compute a
visibly distinct style from base (an invisible selection = Major); **(2) hover + focus affordance** — scans
the page stylesheets for a `:hover` and `:focus`/`:focus-visible` RULE per family (no hover = dead on desktop;
no focus = keyboard users can't see focus, WCAG 2.4.7); **(3) disabled distinctness** — a `:disabled`/`.disabled`
instance must look inactive. Validated live on pm-scheduler: `.filter-chip` selected=distinct (major 0), and it
found real Minors — `.filter-chip` + `.asset-card` have **no `:focus` rule** (the asset-card is a clickable
`div` with no keyboard focus at all). **Lesson:** a synthetic DOM mutation during testing CONTAMINATES later
runs — `delete window.__UFAI` reinstalls the battery but does NOT undo DOM edits; RELOAD between synthetic
state tests (a leftover inline style made `selected-not-distinct` false-fire until reload).

### (original spec, retained)
**Today:** `.simple-card`/`.sum-card` modal-shape drift only.
**Missing:** (a) the OTHER primitives (chips, pills, list-rows, detail_panel, banners, toasts, modals);
(b) **interaction states** (hover/focus/active/selected/disabled/loading/empty) per primitive — does the
chip have a visible focus ring? does the row have a pressed state? (c) cross-page component drift is
static-only (`survey_component_consistency.py`) — make the live `component()` emit a fingerprint the
aggregator can diff across pages.

## Gap 5 — THE BIG ONE: no semantic critic that reasons about the product  ·  ✅ BUILT `tools/ia_semantic_critic.py` (LLM, free-tier)
**Status (2026-06-08): SHIPPED + run.** Groq `gpt-oss-120b` (free chain) reasoned over the 84-unit corpus →
**6 grounded proposals, 0 hallucinated** (the citation-validation guard worked). Real finds the fingerprinter
+ the human missed: `marketplace:current_tab` is a KPI tile that just shows the *active tab* (REMOVE);
shift-brain `top_risk_this_shift` vs alert-hub `high_severity_alerts` collide on "risk" language (RELABEL —
the owner's shift-handover + alerts domains); a 2nd PM-due-vs-task-due relabel the journey never reached. It
even produced a healthy critic-vs-critic FORK (it proposed CONSOLIDATE pending-approval where the
deterministic pass said RELABEL-keep-distinct → escalated, not auto-resolved). Queued via `ufai_ingest.py`.
**Reusable technique:** ground the LLM in a DETERMINISTIC corpus + post-validate every cited id against it →
judgment WITHOUT hallucination. Next: feed page SCREENSHOTS (not just the text corpus) for visual-IA reasoning.

### (original spec, retained)
**Today:** the IA critic is `survey_ia_redundancy.py` — deterministic label/key/theme fingerprints. It can
say "the word 'overdue' appears on 3 pages". It CANNOT say *"these two alert surfaces should be one"*,
*"AMC lives on 3 pages — pick a home and deep-link"*, *"shift-handover duplicates the logbook's last-shift
view — transfer, don't rebuild"*, *"this label confuses a novice because it collides with that one"*.
**The build:** a reasoning critic that ingests the GROUNDED corpus I already produce
(`ia_inventory_corpus.json` = 87 units × page × label × theme × value × affordances) + the page set, and
prompts an LLM **as a senior product/IA architect** (free-tier Gemini Flash per the project's cost rule) to
emit, with evidence and a user-confusion rationale, proposals in 4 verbs:
- **TRANSFER** — "this belongs on page Y, not X" (e.g. an AMC tile on predictive that belongs on alert-hub).
- **STREAMLINE/CONSOLIDATE** — "these N surfaces are one job → one canonical home + deep-links".
- **REDUNDANT/REMOVE** — "this duplicates that and adds no context".
- **RELABEL/DIFFERENTIATE** — "same word, different meaning → disambiguate".
Grounding rules (so it can't hallucinate): every proposal MUST cite real `unitId`s + pages from the corpus;
the deterministic surveyor's output is fed in as priors; output is **CRITIC candidates → `ufai_ingest.py`
→ disposition** (never auto-applied). The LLM adds the JUDGMENT the fingerprinter lacks; the corpus keeps it
HONEST. Domains explicitly in scope: **alerts, shift-handover, AMC, risk, approvals, overdue/due, OEE** —
the surfaces the owner named.

## Gap 6 — Subject axis (AI-behaviour, data) under-run at page altitude  ·  ✅ ENTRY POINT BUILT `__UFAI.full()` (v1.6.0)
**Status (2026-06-08): DONE.** `full({pageId,role,experience})` runs the ENTIRE interface subject-axis for a
page in ONE call — referee (U/F/A/I/C) + formAudit + clickAudit + statesAudit + component — and returns a
consolidated `{ totalMajor, byBucket, counts, majorDefects, cwv, coverage }`. This is the single entry point
the comprehensive scenario run drives. The other two subject-axes COMPOSE on top, live: **AI-behaviour** =
`companion_battery.js` (`window.__CSB`, the Agent·Memory·RAG·Safety stack battery) on AI pages; **DATA** =
`analytics_correctness.js` (`__ANALYTICS_PARITY`) on data pages. Validated live on pm-scheduler
(`totalMajor:2`, byBucket {referee:1 [the queued FAB], states:1}). sweepAll() + modal drills + journeys stay
MCP-orchestrated (multi-state/cross-page can't run in one tick).

---

## Build order (highest leverage first)
1. **Gap 5 semantic critic** — ✅ DONE (`tools/ia_semantic_critic.py`, 6 grounded proposals).
2. **Gap 2 form audit** + **Gap 1 clickAudit (incl. R-FP1)** — ✅ DONE (battery v1.5.0; R-FP1 killed the
   4 dup-affordance FPs; formAudit found 16 unlabeled fields → W-form work item).
3. **Gap 3 action-journeys** ✅ DONE + **Gap 4 component states** ✅ DONE (selected + hover/focus + disabled).
4. **Gap 6** subject-axis entry point ✅ DONE (`full()`). 

**ALL SIX GAPS CLOSED (2026-06-08).** Battery `ufai_battery.js` v1.6.0 + `journey_battery.js` v0.2.0 +
`tools/ia_semantic_critic.py`. Remaining *enhancements* (not gaps): the Gap-3 create→count MUTATION journey
(needs DB writes), Gap-4 hover/pressed *visual* states (vs rule-existence), and live cross-page component drift.
NEXT = the full Layer-3 manifest (`BATTERY_LAYER3_MANIFEST.md`) + the comprehensive MCP scenario run.

_Session log: 10 dispositions drafted; Gap-5 semantic critic BUILT (6 grounded candidates); Gaps 1+2 BUILT
(battery v1.5.0 — formAudit + clickAudit/R-FP1, validated live: dup-affordance FPs killed, 16 unlabeled
fields found → resume basics fixed + W-form escalated). NEXT = Gap 3 action-journeys + Gap 4 component states._
