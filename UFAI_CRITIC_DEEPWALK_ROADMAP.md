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
**CRITIC PROGRAM: 31.9% overall · 9749 in-scope trajectories · pending 5790 · critiqued 1670 · improving 2289 — registry critic_registry.json (updated 2026-09-11, rubric 975123b63769).**
Findings: 9986 total (S4 820, S3 2141, S2 6493, S1 532) · open Major+ 2961.
Per-wave: A 74% · B 84% · C 82% · D 81% · E 76% · F 80% · G 75% · H 73% · I 70% · J 70% · K 70% · L 70% · M 70% · N 70% · O 70% · P 72% · Q 70% · R 70% · S 70% · T 70% · U 70% · V 70% · W 70% · X 70% · Y 70% · Z 70% · AA 70% · AC 70% · AD 70% · AE 70% · VD 70% · VM 70% · VP 71% · W4 0% · P-A 82% · P-B 81% · P-C 81% · P-D 83% · P-E 78% · P-F 85% · P-G 81% · P-H 81% · P-I 80% · P-J 81% · P-K 79% · P-L 81% · P-M 82% · LX-H 82% · LX-L 83% · LX-S 82% · EX-AT 79% · EX-AX 82% · EX-HP 82% · EX-PF 81% · EX-PX 82% · EX-RV 84% · EX-SB 82% · EX-TL 81% · LX-CI 83% · LX-FN 85% · LX-LB 83% · LX-RL 81% · W3-AR 81% · W3-CL 70% · W3-DF 81% · W3-FN 85% · W3-JN 81% · W3-LC 83% · W3-LN 70% · W3-PG 79% · W3-SC 70%
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

## §6 · Wave 3 — the 148 pages graded on ONE dimension, and the 1,502 rows that arrived with it (2026-09-07)

The wave-3 determination measured the critic bank the same way it measured the trajectory registry, and
found the same shape: **31 root pages carry the full rubric (>60 dimensions), 26 more carry 21-60, and 146
pages carry exactly ONE** — `CV1`, anon call-to-action activation. Those 146 are **53 learn articles, 47
calculators and 48 edge-function files**: every page a stranger meets before they meet a hive, graded once
on whether its button did something.

That single dimension is not a small sample of the rubric — it is a different question from all the others.
The one article driven onto the full rubric this week surfaced **68 findings** before it read 100%, and
thirteen of the fourteen dimensions the calculators failed had already been fixed in the generator and were
waiting on promotion. A page graded on one dimension is a page nobody has looked at.

**So wave 3 puts all 148 on the full rubric**, and the sweeps ride the same visits the W3-LN and W3-CL walks
already make (`tools/prove_content_ufai.mjs` opens each content page once and asks it F, A and I; the rubric
sweep grades it in the same visit), with `tools/close_critic_findings.py --apply` writing the receipt only
when every finding on the page is clean.

**The bank grew with the registry, from one place.** `tools/seed_expansion_wave3.py` calls
`critic_seed_missing.py` at the end of its write, so all 1,502 new trajectories entered the critic bank as
`pending` in the same change — 2,437 rows to **3,939**, statuses `critiqued 1,030 · improving 1,407 ·
pending 1,502`. The preservation rule held on both sides: not one existing critique or improvement reference
was rewritten (the P-M lesson, where a paired write reset 500 critiques and the headline fell 73.5% -> 36.4%
while the number being watched moved exactly as expected).

## §8 · THE FIRST EIGHT IN-MOTION WALKS, AND WHAT THEY SAY TO FIX (2026-09-10)

Eight journeys walked step by step through the chrome-devtools MCP as the person — 57 rows settled,
**40 distinct findings**. The deliverable of this extension is an improvement plan traced to walk
evidence, so here it is, ranked by where the pain actually concentrates rather than by page count.

| page | findings | who meets it |
|---|---|---|
| **index.html** | **14** | only the SIGNED-OUT visitor |
| analytics.html | 6 | everyone, at the end of the day |
| hive.html | 5 | everyone, constantly |
| audit-log.html | 5 | a worker, who is refused |
| shift-brain.html | 4 | a supervisor (fixed this session) |
| report-sender.html | 3 | a supervisor, sending outward |
| logbook.html · alert-hub.html | 1 each | everyone |

**FINDING 1 — 35% of everything is on one screen, and it is the one that greets strangers.**
`index.html` signed OUT carries 14 of the 40; signed IN the same file grades a clean **90/90 with zero**.
The two sets do not overlap by a single dim. Marketese ("SMRP world-class benchmarks", B2 0%), leaked
system jargon (G2 0%), no source chip (E3 0%), 59 controls against 3 primary CTAs (G3 0%) and 32 tap
targets under 44px (F1 46%) are all in the view seen **only by people who do not yet trust the product**.
This is the highest-leverage cluster on the platform and it is one file's marketing half.

**FINDING 2 — the product is strongest exactly where the work happens.** `asset-hub`, `pm-scheduler`,
`inventory`, `skillmatrix`, `achievements`, `community`, `assistant`, `voice-journal`, `dayplanner` and
`ph-intelligence` each graded **90/90 with zero sub-100 dims** in at least one walk. The surfaces a
technician touches with dirty hands are clean; the pain is at the front door and in the reporting tail.

**FINDING 3 — four dims cut across three pages each, so they are conventions, not page bugs:**
`B3` readability (analytics, audit-log, index) · `F1` tap targets (index, report-sender, shift-brain) ·
`K2` glanceable KPI + target size (same three) · `N1` bilingual label coverage (analytics, hive, index).
`N1` was read as the sharpest and **that reading was wrong, corrected the same session**: analytics'
"1 of 6 labels (17%)" is a MECHANISM census counting `data-i`, the static swapper's marker. The five
uncovered labels ARE the whole sample and they are the "Show all N assets" controls, built through the
platform's other bilingual mechanism, `_t(en, fil)`; switched to FIL the page renders "Ipakita lahat ng
30 asset", "Ipakita lahat ng 85 pares", "Ipakita lahat ng 24 piyesa". No Filipino reader meets an
English page there. The dim now names that blind spot at the measurement, and the retraction is
appended to all 32 rows that carried the claim. **The remaining three cross-cutting dims stand.**

**FINDING 4 — a page's score is a claim about ONE persona in ONE auth state.** `hive.html` fails A2+N1
for a worker and G3+A3+X1 for a fleet supervisor; `shift-brain`'s two dead ends existed only for the
supervisor; `audit-log`'s permission gate is a state only a worker can reach. An at-rest board grades
whichever screen it happened to load, and the defects concentrate in the one it did not.

**Already fixed and verified this session:** `shift-brain` X1 50→100 (two good-news dead ends rewritten
in the house style) and `audit-log` F1 0→100 / K2 50→100 (a 142x41 escape control for someone already
told no, now 142x44). Both were invisible to any at-rest sweep.

## §7b · RE-MEASURED, AND THE DEFECT BACKLOG IS ZERO (2026-09-10)

§7 named re-measuring the backlog as its next unit. Done, and the answer is that there is no backlog —
the 5,897 findings are **receipted, not open**:

| bucket | rows |
|---|---|
| pending (never walked) | **1,522** |
| improving, carrying `improvement_refs` (**resolved**) | 1,407 |
| critiqued with no findings (clean) | 1,030 |
| **critiqued, with findings, no refs — the only OPEN state** | **0** |

Asked of the closer itself rather than derived by hand, which is what makes this a measurement:

    python tools/close_critic_findings.py
    open rows examined: 0 · closable: 0 · partial (stay open): 0 · skipped: 0

`close_critic_findings.py:88` is the definition — it considers a row only when it is `critiqued` or
`improving`, HAS findings, and does **not** already carry `improvement_refs`; and its header says a row
reaches `improving` "ONLY when EVERY one of its findings is clean". So a finding sitting under an
`improving` row has already been re-checked against the page and found repaired.

**This is the second time the same number has invited the same wrong plan.** On 2026-09-07 a whole phase
was written around "513 improving rows / 2,454 unresolved findings" before the closer's one-line rule
showed the real backlog was 46 rows. The count has since grown to 5,897 and is no more open than it was
then — a large number nobody has checked is the probe, not the program
([[feedback_improving_means_the_fix_landed]]).

**AND 243 OF THOSE PENDING ROWS WERE ANSWERABLE WITHOUT A BROWSER — but only 243 of them.**
`critic_from_board.py` writes the family rubric board's verdicts onto pending rows, and its dry-run
offered **933**. Taking all 933 would have been wrong, and the tool says why in one line: `pg =
r["pages"][0]`. That is exactly right for a row whose subject IS one page, and wrong for a JOURNEY —
W31 crosses index, hive, asset-hub, logbook, pm-scheduler and alert-hub, and grading it from
`index.html` alone, at rest, is the shallowness this extension exists to answer.

Split by page count: **536 single-page rows** (learn articles, calculators, page × layer cells, the
persona/device cells) of which **243** have their page on the board and carry a full 90-dim grade, and
**724 multi-page rows — every one a W3-JN journey**, of which 690 would have been credited from their
first page. The tool now **skips multi-page rows by default** and counts them in its own line
(`--include-multipage` exists for a caller who decides otherwise and has to say so out loud). Applied:
243 moved, registry validated, **critic program 48.4% → 52.7%**.

**AND 186 MORE WERE ANSWERABLE WITHOUT A BROWSER, BY FIXING THE PRODUCT FIRST.** The W3-FN rows carry
a `no_ui_basis` that says it plainly — *"critiqued against the AI/API dimensions via its contract, not a
browser walk"* — and `critic_edge_fn_copy.py` is the instrument for exactly that: it grades every string
a function returns, because a client renders those verbatim. Run today it reported **59 of 63 clean**,
and the four failures were real user-facing copy, one of them written earlier the same day:

| function | what the person was told | what they are told now |
|---|---|---|
| `pdf-ingest` | `could not open a kb_documents row: <driver text>` | This document could not be filed, so nothing was indexed. Upload it again, or tell your supervisor. |
| `voice-model-call` | All models failed (rate limited or down) | The voice service is busy. Wait a moment and try again, or type your entry instead. |
| `supervisor-reset-password` | That person is not an active member of this hive, so their password cannot be reset here. | This person is not active in this hive. Re-activate them first, then reset the password. |
| `sensor-readings-ingest` | No reading passed validation: all N were rejected. See errors[] … (24 words) | No readings stored: all N rows failed validation. Check each row's reason in errors, then send the batch again. |

`See errors[]` names a field in the reply, not a step a person can take; the cause is not lost in any of
these, it moved to the log or stayed in the `errors` array beside the message. **63/63 now pass**, and
the 186 rows banked to `improving` with receipts. Two things were repaired in the tool on the way: its
receipts were dated by a hardcoded `2026-09-06` and claimed a hardcoded `62/62`, so every later run
banked evidence four days stale against a denominator that had already moved — both derived from the run
now.

**The 76 W3-SC component rows are NOT answerable this way, and that is a decision rather than an
oversight.** Their trajectories ask whether a shared piece *"does its job on every page that carries
it"* — a property of the component ACROSS its hosts, which only a walk on three host pages can answer.
Grading their copy statically would answer a different question than the row asks, which is the same
error as crediting a journey from `pages[0]`.

So the remaining critic work is **1,093 pending: 724 journeys owing an in-motion deepwalk, 293 whose
page the board has never graded, and the rest**. Not defects to fix —

**So the critic program's remaining work is PENDING WALKS** — browser work
through `family_rubric_sweep.mjs`, not a repair queue. Any plan that reads the percentage as
"52% of the UI is broken" is reading pending walks as open defects.

## §7 · The backlog is STALE, and re-measuring it is the next unit (measured 2026-09-10)

`critic_registry.json` reports **1,311 rows carrying unresolved findings** (5,897 findings in all), and
that number cannot be used as a work queue yet. A finding written by `family_rubric_sweep` on
2026-09-04 quotes the exact sentence it failed on, which makes it checkable against the page as it
stands today. Of the 21 unresolved findings that quote a sentence, **18 quote text that no longer
exists in the page source** — and at least one was verified by eye as genuinely repaired:

    community.html B3, worst(22w): "Matched on earned skill badges: hive-mates holding a badge a…"
    today:  "Matched on earned skill badges. These hive-mates hold a Practitioner badge or higher in
             one of your trades. A teammate doing the same work without that badge will not appear here."

One 22-word sentence, already split into three. `alert-hub.html`'s worst sentence ("2 parts recommended
(72% confidence) for Bearing failure: Ri…") is not in the source at all because it is BUILT at runtime
from data — a different reason for the same "gone", and one that means no source edit could ever
resolve it.

**So the open count is measuring the age of the last sweep, not the state of the platform** — the same
shape as the calculators in §6, where thirteen of fourteen failed dimensions were already fixed in the
generator and waiting on promotion, and the same shape as
[[feedback_improving_means_the_fix_landed]]: a row is only `improving` while the fix has NOT landed.

**NEXT for this program, in order:**

1. **Re-run `node tools/family_rubric_sweep.mjs` (all 32 pages) and `tools/close_critic_findings.py
   --apply`** before any further fixing. It needs the browser, so it is sequenced behind the W3-JN walk
   chain rather than run against it — two Playwright jobs on this 8 GB host is the contention rule, not
   a preference. Everything that re-measures clean closes itself; what survives is the real backlog.
2. Only then cluster what remains into `UFAI_UIUX_IMPROVEMENT_PLAN.md` (§4's deliverable). A synthesis
   built on the current numbers would cluster phantoms.
3. Separate the two "gone" reasons in the report, because they need opposite actions: **rewritten** =
   close it; **runtime-generated** = the rubric must grade the rendered string, and a source edit will
   never satisfy it.
