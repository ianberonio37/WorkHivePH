---
name: external-coga-cognitive-accessibility-design-objectives
type: reference
source: https://www.w3.org/TR/coga-usable/
source_sha: w3c-coga-usable-2026
fetched_at: 2026-07-22
last_verified: 2026-07-22
ttl_days: 180
distilled_by: night-crawler-v1
supersedes: null
topic: W3C COGA — making content usable for people with cognitive & learning disabilities; clear language, minimize load/steps, findable, error-recovery, NO time pressure on tasks, keep oriented, reduce memory/calculation — the measurable core of rubric dim Y2 (stress-case / real-life resilience) + persistence for X2
---

## reference · W3C COGA design objectives (stress-case / real-life resilience)

The measurable core of UFAI **Y2 · Stress-case / real-life resilience** — the design must hold up for a
tired / rushed / distracted / low-literacy / stressed field worker, not only the ideal user. Also grounds
**X2** persistence. W3C "Making Content Usable for People with Cognitive and Learning Disabilities":

* **Clear language** — simple words, short sentences, active voice; no jargon/metaphor/double-negatives
  (≤ Flesch-Kincaid grade 6-8; pairs rubric B3). 1-2 clauses/sentence.
* **Minimize cognitive load** — few actionable items per screen (3-5); single-task focus; primary task in
  ≤3 steps, no deep scroll-hunt.
* **Findable** — critical info/functions identified quickly (key info located in ~10s; critical feature ≤2
  clicks; primary action above the fold). Pairs X3.
* **Error prevention & recovery** — confirm destructive actions (pairs J3); single-step undo/back;
  validation prevents obviously-broken submits. Reverse an accidental action in ≤1 click.
* **★NO time pressure (the safety-task rule)** — remove session timeouts or make them ≥1 hour; if a timeout
  is needed, warn ≥5 min ahead + one-click extend. A SAFETY task must never carry a countdown / auto-dismiss.
  **User work saves automatically or persists across sessions** (this is the measurable spine of **X2**
  interruption resilience — a refresh/interruption must not lose in-progress input).
* **Maintain orientation** — breadcrumbs, page titles, progress indicators for multi-step; the user can tell
  where they are + prior steps after a 2-minute distraction (a real field interruption).
* **Reduce memory/calculation** — don't make users memorize or compute; show previously-entered data;
  autocomplete/pre-fill known fields (pairs Z1 autofill + G5 system memory).

**Testable rule (Y2):** run each canonical task as a stressed persona (tired/rushed/gloved/low-literacy);
FAIL on any: countdown/auto-dismiss on a safety task, >3 steps for the primary action, jargon sentence
(grade > 8), no undo, lost orientation, or lost in-progress input on interruption.

Sources: https://www.w3.org/TR/coga-usable/
