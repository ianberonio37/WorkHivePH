# Workflow: Audit → Synthesis — discover the work, then judge it

**Objective.** Find what static checks can't, *measure* it, and end with the **synthesis** — the
opinionated design judgment that clusters findings by job-to-be-done. An audit that stops at a
findings register is half-done. This is the *evaluator half* of an evaluator-optimizer over the
whole platform: each finding it produces becomes a Change (`make_a_change.md`).

**Entered from.** `FRAMEWORK.md` Step 0 (Triage) when the request is discovery ("is X right?",
"walk X", "find problems in X").

---

## 1. Pick an instrument (measure, don't vibe)

| Instrument | What it's for | Reuse |
|---|---|---|
| **Deep MCP walk** | *Operate* the feature live (exercise scanners, pickers, forms) — don't just eyeball it | `workflows/grounded_mcp_sweep.md`, `ufai_battery.js` |
| **UFAI battery** | Score a page **Usability / Functionality / Adaptability / Internal-Control**, measured % | `ufai_battery.js` (+ axe-core live-inject) |
| **Cross-page sweep** | Grep one finding's pattern platform-wide to find every sibling instance | grep + the sibling-sweep reflex |

Rules: walk **every** surface (scroll to the last element, expand every section); measure axe /
tap-targets / labels / i18n-coverage — never score them by eye; verify the **row, not the toast**.

## 2. Register findings

One line per finding: page · what · severity · the evidence that proves it (the row, the axe node,
the measured %). Evidence, not assertion.

## 3. SYNTHESIZE — the actual deliverable

Cluster the findings by **job-to-be-done** and give opinionated verdicts, strongest fusion first:
- *"These N surfaces do the same job → fuse into ONE"* (name the owner, what gets deleted, the blast
  radius), **or**
- *"Keep distinct because X."*

Maps and bug lists are instruments; the design judgment is the deliverable. Lead with the strongest
fusion case. **The dominant fusion verdict is P5's:** N surfaces sharing a defect = ONE unadopted
canonical component → name the component, its adoption %, and the family-wide adoption plan (the lever
ladder), not N per-page tickets. This is what keeps the platform a harmonious family.

## 4. Feed the Flywheel

Each surviving finding enters `make_a_change.md` (usually Fix or Redesign mode) and runs the
Flywheel to lock + teach + persist. The audit doesn't "end" — it *routes*.

## Grounding

- Anthropic *Building Effective Agents* — Evaluator-Optimizer.
- `substrate/` — `feedback_synthesis_not_just_audit`, `feedback_deep_mcp_walk_every_page`,
  `feedback_ufai_per_dim_measurement_drive`, `reference_ufai_battery`, `GROUNDED_SWEEP_ROADMAP.md`.
