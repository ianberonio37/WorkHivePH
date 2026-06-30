# Arc V — Engine A: the Playwright-MCP "Demanding-User" Persona Walk

**Purpose.** The DISCOVERY engine of the EFFORTLESS program (`EFFORTLESS_UX_ROADMAP.md`). Where the Node harness
(`tools/effortless_sweep.mjs`) *measures* friction deterministically, this playbook drives a **Playwright-MCP
session as a demanding, impatient real user** to *discover* friction the counters can't see on their own —
confusion, dead-ends, "why is this buried," "I'd have given up here." It is the **UXAgent pattern** (CHI 2025):
an LLM persona operating a real browser to surface usability pain *before* a human study.

> **Hard rule — discovery is HYPOTHESES ONLY, never a gate.** UXAgent's own finding is that simulated user
> behavior is *not fully realistic*. So nothing a persona walk reports is allowed to move a baseline or pass/fail
> a sub-arc. Every pain it finds must be **reproduced and counted by Engine B** (a seeded `ideal`, a Load/Clarity
> detector, a click-count delta) before it ratchets. Discovery → CODIFY → GATE → VERIFY → RATCHET.

---

## The 3 personas (start set — V-D4)

Drive each goal *in character*. Narrate the inner monologue ("I expected X here… I don't see how to…"), and the
moment you'd realistically abandon, STOP and log it — that abandonment point is the highest-value finding.

### P1 — Marielle, impatient field technician
- **Context:** plant floor, gloves, one-handed on a mid-range Android in sunlight, 30 seconds between tasks.
- **Mindset:** "Just let me log this and get back to the machine." Zero patience for menus, reading, or hunting.
- **Frustrates her:** small/buried controls, more than ~2 taps to start a log, any wall of text, a spinner with no sign it's working, a form that loses what she typed.
- **Primary goals:** log a fault (logbook); check a part's stock (inventory); see today's jobs (dayplanner).

### P2 — Boyet, first-day supervisor (low familiarity — Jakob's Law stress test)
- **Context:** promoted yesterday, never trained on the tool, desktop + phone.
- **Mindset:** "Where do I even… is this the right page? What does this number mean?" Relies entirely on labels and visual hierarchy to self-orient.
- **Frustrates him:** unlabeled icons, two buttons that look equally primary, jargon, a KPI with no definition, having to visit 3 pages to answer one question.
- **Primary goals:** approve a pending member (hive); read what's at risk this shift (alert-hub / shift-brain); supervise + audit (hive→audit-log).

### P3 — Engr. Cruz, power engineer (speed-seeker, Tesler's Law stress test)
- **Context:** experienced, does the same calcs/projects weekly, wants the shortest expert path.
- **Mindset:** "I know exactly what I want — stop making me click through the beginner flow every time."
- **Frustrates him:** no recents/defaults/shortcuts, re-entering the same inputs, decision-paralysis pickers (12+ options, no search), no keyboard path.
- **Primary goals:** run a known calc (engineering-design); plan/track a project (project-manager→report).

---

## The walk protocol (per page / per family)

Run via the `mcp__playwright__browser_*` tools (this is interactive MCP — distinct from the Node sweep).

1. **Sign in** as the persona's role at `http://127.0.0.1:5000/workhive/<page>.html` (worker = `bryangarcia@auth.workhiveph.com`; supervisor/engineer = `leandromarquez@auth.workhiveph.com`; both `test1234`; hive `9b4eaeac-59b0-4b0e-9b0b-0947b45ad1e7`). Seed `wh_*` localStorage identity as the Node harness does (see `signIn` in `tools/live_page_journeys.mjs`).
2. **State the goal** in the persona's words. Then operate the page toward it — `browser_snapshot` to read affordances, `browser_click`/`browser_type` to act, narrating each decision as the persona.
3. **Count + time as you go** (mirrors Engine B): taps to reach the goal, page-hops, any action that stalls with no busy affordance, any control you misread or had to hunt for.
4. **Log the abandonment point** if the persona would give up — and *why*.
5. **Emit one pain report per goal** (schema below).

### Pain-report schema (one JSON object per goal)
```json
{
  "page": "engineering-design.html",
  "family": "V6 Build & Project",
  "persona": "P3 power engineer",
  "goal": "run my usual HVAC load calc",
  "observed_path": ["FAB", "Eng Design tile", "HVAC pill", "scroll calc list", "...", "Calculate", "Print"],
  "clicks": 9,
  "hops": 2,
  "dead_ends": ["no search in the 12-item calc picker", "no 'recent calcs'"],
  "confusion_points": ["two buttons look equally primary on the result card"],
  "wished_for": ["recents row", "type-to-filter the calc list", "smart defaults from last run"],
  "abandon_point": null,
  "severity": 2
}
```
Write reports to `arc_v_persona_findings.json` (array). Severity 1 minor · 2 major · 3 blocker (would abandon).

---

## Discovery → CODIFY (how a persona finding becomes a gated number)

| Persona found | Engine B codification | Becomes |
|---|---|---|
| "too many taps to do X" | seed `IDEAL['<JTBD id>'] = {clicks, hops}` in `tools/live_page_journeys.effort.mjs` | excess-click **debt** (ratchets → 0) |
| "12-option picker, no search → paralysis" | add a Load detector (choice-count > Miller 7) to the Critic pass | **L-lens** Miller-violation (→ 0) |
| "two equal primary buttons" | promote `H-single-primary-cta` heuristic to a counted metric | **C-lens** competing-primaries (→ 0) |
| "spinner with no sign it's working" | F-lens: slow action (>400ms net) lacking `.wh-skeleton`/`aria-busy` | **F-lens** slow-silent (→ 0) |
| "lost what I typed on error" | extend the Recoverable check (form state preserved) | **C-lens** unhelpful-error (→ 0) |

Then re-run `node tools/effortless_sweep.mjs --page <page>.html` to confirm the number moved, fix, and
re-walk with the persona to confirm the abandonment is gone (the human-felt VERIFY).

---

## VERIFY (per sub-arc — pairs the number with the suffering reduced)
1. Engine B before/after: click-hops + density delta on the page (the number).
2. Engine A re-walk: the same persona, same goal, **no longer abandons / no longer hits the dead-end**.
3. No regression: Arc K `live_pct` ≥ baseline; UFAI floor stays 0 (didn't break completion or a11y to cut clicks).
