# UFAI CRITIC DEEPWALK — the UI/UX Improvement Extension

**Mandate (Ian, 2026-09-01):** *"we have to make a proper extension of this roadmap, the UI and UX
improvement. all you are sharing are so shallow, you have to deepwalk live mcps each trajectories to
compare it with the critics for UFAI UI UX, from there we can have a proper improvement UI UX plan."*

The 500-trajectory program built and locked the platform's CORRECTNESS. This extension walks each
trajectory again — live, via MCP, as its persona on its device through its entry path — and holds the
EXPERIENCE against the UFAI UI/UX critic rubric (33 classes / 102 dims, `ufai-rubric-spec.json`).
No instrument has ever produced `trajectory × rubric` evidence: `family_rubric_sweep` grades pages
AT REST; Arc K graded page-scoped JTBDs. The in-motion critique grid is the missing instrument.
The deliverable is `UFAI_UIUX_IMPROVEMENT_PLAN.md` — every improvement cluster traced to walk
evidence — then fix waves that land and LOCK each improvement.

<!-- critic-scoreboard:begin (GENERATED - edit critic_registry.json, not this block) -->
**CRITIC PROGRAM: 71.0% overall · 705 in-scope trajectories · critiqued 657 · improving 48 — registry critic_registry.json (updated 2026-09-03, rubric 975123b63769).**
Findings: 9 total (S2 5, S1 4) · open Major+ 0.
Per-wave: A 74% · B 84% · C 82% · D 81% · E 76% · F 80% · G 75% · H 73% · I 70% · J 70% · K 70% · L 70% · M 70% · N 70% · O 70% · P 72% · Q 70% · R 70% · S 70% · T 70% · U 70% · V 70% · W 70% · X 70% · Y 70% · Z 70% · AA 70% · AC 70% · AD 70% · AE 70% · VD 70% · VM 70% · VP 71%
<!-- critic-scoreboard:end -->

## §1 · Scope — ALL 500 considered, 480 critiqued, none silently skipped

| bucket | n | treatment |
|---|---|---|
| descoped (org-federation tier) | 20 | out, recorded basis |
| registry-paged (T-wave learn/tools + expansion) | 160 | walk the page set as the cell's persona |
| basis-resolved (T1–T200, pages from walk receipts) | 126 | walk the trajectory's own route |
| surface-resolved (title/story names the surface) | 70 | walk the named surface as the story's persona |
| echo-resolved (machine arcs → human-facing echo) | 87 | walk WHERE THE HUMAN SEES the machine's effect (webhook → audit trail; adversary probe → alert-hub; API write → the rendering page): does the person see, understand, trust it? |
| condition-core (condition/journey arcs) | 37 | walk the core set (hive · logbook · pm-scheduler · inventory) UNDER the arc's condition (interruption, clock skew, unicode names, max-length data…) |

Targets seeded by `tools/backfill_trajectory_pages.py` (self-tested; zero unresolved). Every row
flagged `needs_review` gets its target confirmed at walk time before critiquing — a wrong proposed
target is corrected in the registry row, never walked blindly.

## §2 · The walk protocol (per trajectory — the critique is IN MOTION, not at rest)

1. **Enter by the trajectory's OWN entry path** — search arrival, nav, deep link, notification —
   never a direct URL unless the story says so. Set the row's `walk_viewport_px` FIRST.
2. **Be the persona**: the cell's auth state (anon / worker / supervisor / the echo's viewer), the
   story's intent held in mind — the walk asks "can THIS person do THIS job without pain?"
3. **At each route step**: `browser_evaluate` → `__UFAI.referee()` + `__UFAI.critic()`
   (ufai_battery.js) and, once the worked state renders, `__RUBRIC.survey()` (survey_ufai_rubric.js
   refuses to grade a pre-ready page — a walk that scored nothing is a FAILED WALK, never a clean page).
   Run the battery's `mcp_todo` items by hand.
4. **The in-motion layer (the part no script sees)**: gulf-of-execution moments, context lost
   between steps, hesitation points, copy that reads wrong in the moment, the thing the persona
   would give up on. Recorded as findings `{dim | IN-MOTION, layer: heuristic, severity 0-4,
   evidence, receipt, owner}` — Arc K's severity scale (Polish/Minor/Major/Blocker), the critic
   PROPOSES, Major+ triaged with Ian.
5. **Bank the row**: status pending→walked→critiqued, dims_graded / findings / clean_note into
   `critic_registry.json`; scoreboard regenerates (`tools/update_critic_scoreboard.py`);
   `tools/validate_critic_registry.py` holds it honest (hollow critiques, invented dims, silent
   drops all redden — teeth proven).

## §3 · Waves (~20 trajectories/session, inline live-MCP, NO fan-out, browser reaped pre-session)

| wave | trajectories | leading lenses |
|---|---|---|
| CW1 field work, phone-first | wave B (T9–T18) | K glanceability · Y context · Z modality · T native-feel |
| CW2 supervisor ops, PC | wave C (T19–T28) | DD density · G heuristics · E data-state |
| CW3 cross-page chains | wave D + X-class arcs | X journey · W wayfinding · S family |
| CW4 degraded & hostile | wave E + refusal-legibility targets | Y1 offline · PP perceived perf · J recovery |
| CW5 personas & identity | waves F/G/Y | A comprehension · B language · O onboarding · TR trust |
| CW6 AI experience | wave I (T79–T92) | AI1–AI6 · PP · TR |
| CW7 a11y spectrum | wave X (T385–T402) | Q · F3 · the assistive-tech cell walks |
| CW8 economy & marketplace | waves J/AA | DP deception-absence · TR · M forms |
| CW9 echo surfaces (machine arcs) | waves V/W/AE echoes | E4 refusal legibility · K · TR |
| CW10 funnel families | waves T/U (template-sampled: one deep walk per template + variance spot-checks, never 113 identical walks) | JA arrival · CV conversion · B |
| CW11 conditions & lifecycle | waves L/M/N/R/S/Z/AC condition arcs | X2 resumability · Y · PP |

Per-wave close: findings clustered by ROOT (synthesis is the deliverable) → Major+ triage with Ian →
fix batch (A15 one-way-green) → redesign-class findings proposal-first with a CURRENT→TARGET
disposition map (Whole-Artifact Discipline) → resurrection-proved detector per closed class →
scoreboard regen → skills writeback + Memento checkpoint. New rubric dims discovered by walking are
added to the spec with citations (the JA/CV/Q2/Q3 precedent — walk → dim is the established pattern).

## §4 · The improvement plan (the deliverable)

After CW1–CW3: synthesize `UFAI_UIUX_IMPROVEMENT_PLAN.md` — every confirmed finding clustered by
root cause, ranked severity × breadth, each cluster carrying its fix/redesign proposal, owner, and
the gate that will lock it. The document then GOVERNS the remaining fix waves. It is a LIVING
artifact: later waves append clusters; resolved clusters link their locks.

## §5 · Sequencing

Behind the in-flight endgame: full board → promote → bank restamp → post-board batch (sw.js bump ·
revoke migration · 0x08 repairs · dup-migration renumber · T113/T114 re-runs · census recal) →
land Phase-0 artifacts from `.tmp/` staging (this doc, `critic_registry.json`,
`tools/backfill_trajectory_pages.py` --apply, `tools/update_critic_scoreboard.py`,
`tools/validate_critic_registry.py` + its registration) → CW1 begins. Live walks NEVER share the
machine with a full board (the load-flake law); every walk session pre-flights
`tools/browser_gate_health.py --reap`.
