# BATTERY_ROADMAP.md — using the full UFAI battery family

> **Status:** rollout plan (2026-06-08). `BATTERY_ARCHITECTURE.md` is the MODEL
> (what the battery family is); this is the USAGE plan (how we run it across the
> whole product, in what order, at what cadence, and how findings get fixed or
> disposed). Sibling of `AI_SURFACE_MAP.md`, `AGENTIC_RAG_ROADMAP.md`.
>
> **The goal:** every `(page × altitude × role)` cell of WorkHive gets audited by
> the right battery, DEFECTs fixed inline, TASTE/IA surfaced for disposition — and
> then it becomes a recurring discipline, not a one-off.

---

## 0. The operating loop (how the battery is used EVERY time)

The same loop at every altitude — this is the doctrine the waves below execute:

```
 boot kernel ─▶ run the altitude ─▶ REFEREE defects ─▶ fix INLINE (DEFECT)
                                   └▶ CRITIC candidates ─▶ ufai_ingest.py
                                                          ─▶ sweep_critiques.json
                                                          ─▶ flywheel_orchestrator
                                                          ─▶ promotion_queue.md
                                                          ─▶ you DISPOSE
                                                             (promotion_dispositions.json)
```

- **Two halves.** *Headless* (deterministic, run anytime, no browser):
  `run_battery_family.py` + the per-altitude Python spines. *Live* (Playwright
  MCP, rendered values + real interaction): `__UFAI.run` / `__UFAI.component` /
  `__JOURNEY` / `__CSB`.
- **Referee fixes, critic surfaces.** A measured DEFECT (28px tap, axe violation,
  missing component sub-part, a number that disagrees with its oracle) is fixed
  INLINE. Opinionated TASTE/IA (redundancy, choice overload, a one-off variant) is
  queued — never auto-applied.
- **Coverage honesty.** A single run is never "the page is clean." Track what was
  NOT seen (other states, other roles, the live half) in the coverage ledger (§7).

### Definition of Done — per altitude

| Altitude | A cell is DONE when… |
|---|---|
| **① Component** | static `survey_component_consistency.py` clean + `__UFAI.component()` live-confirms modal shape, 0 missing-required, on a representative page per nav section |
| **② Page** | `__UFAI.run` referee **0 Major** across all states (`sweepAll`) for every applicable **role × experience**; critics ingested |
| **③ Journey** | each planned journey executed live; continuity verdict recorded; result attached to its `sweep:ia:*` candidate |
| **④ Platform** | `run_battery_family.py` 🟢 all-ran; candidate ledger fully **dispositioned** (accept/defer/reject) |

---

## 1. Wave plan

Ordered cheapest-first (headless before live) and highest-traffic-first (the
field worker's core path before the long tail).

### Phase A — Platform baseline (④, headless) — **start here, ~0 cost**
1. `python tools/run_battery_family.py` → `battery_family_report.md` (done:
   🟢 all-ran, **11 IA + 0 component** candidates).
2. Queue + **dispose the existing backlog**:
   `python ufai_ingest.py ia_streamlining_candidates.json` (done — 11 in queue) →
   work `promotion_queue.md`, decide each via `promotion_dispositions.json`. The
   Phase-3 walkthrough already ranks the 4 on a CONFUSING novice path first.
3. **Exit:** family report green + every candidate has a disposition.

### Phase B — Page sweep (②, live MCP) — **the bulk of the work**
Drive `__UFAI` live per page; for each: `boot()` → `run({pageId,role,experience})`
→ `sweepAll()` for multi-state → fix DEFECTs inline → `ingest` critics → re-run the
role×experience matrix. Tiered by who hits it and how often:

| Wave | Pages | Roles to matrix |
|---|---|---|
| **B1 — Field core** | index · logbook · inventory · dayplanner · pm-scheduler | field, supervisor × novice/exp |
| **B2 — Supervisor intelligence** | hive · analytics · predictive · asset-hub · alert-hub · shift-brain | supervisor, engineer × novice/exp |
| **B3 — Build & Grow & Connect** | engineering-design · project-manager · skillmatrix · resume · achievements · marketplace · integrations · community · ph-intelligence | role per nav-gate |
| **B4 — Long tail / hidden** | assistant · voice-journal · ai-quality · audit-log · plant-connections · report-sender · analytics-report · project-report | supervisor (most are hidden/supervisor) |

- **Per-page exit:** referee 0 Major across states; role×experience covered; critics ingested. Log the cell in §7.
- Reuse the existing L2 `tests/journey-*.spec.ts` as the regression backstop — the battery ADDS the 5 live things specs lack (axe/CWV/focus/prod-path/dpr), it doesn't replace them.

### Phase C — Component confirm (①, live)
Run `__UFAI.component()` on the design-system primitives (`.simple-card`,
`.sum-card`, chips/tabs) on **one representative page per nav section**; reconcile
against `component_consistency_report.md`. Fix any DOM-only drift the static scan
can't see (e.g. a tag applied by JS). **Exit:** live component verdict clean on the
representative set; static report still 0 missing-required.

### Phase D — Journey execution (③, live)
Drive the 3 grounded journeys in `journey_battery_plan.md` with `__JOURNEY`:
- `overdue-continuity` (expect **agree**) — a drift here is the live proof of the
  overdue-KPI derivation drift → evidence onto `sweep:ia:theme:late-overdue`.
- `risk-continuity` (expect **agree**) — confirm one number vs three lenses.
- `approvals-distinct` (expect **drift-confirms-distinct**) — a drift CONFIRMS the
  RELABEL; agreement would be coincidence.
Then expand the registry with more JTBDs (resume build, marketplace list→offer,
PM complete→logbook). **Exit:** journeys executed, continuity results dispositioned.

### Phase E — The other two SUBJECTS (behaviour + data)
- **AI-behaviour:** `__CSB` companion-stack sweep (Agent·Memory·RAG·Safety) across
  the companion surfaces; `validate_companion_stack.py` G0 stays green.
- **Data/truth:** `analytics_correctness.js` per-tile parity on every source-of-
  truth page (analytics + the pages that read it); wire both into
  `run_battery_family.py` so the platform run covers all three subjects, not just
  interface. **Exit:** all 3 subjects covered at page + platform altitude.

### Phase F — Make it recurring (the discipline, not a one-off) — **wired ✅**
- **Mega Gate G3 (DONE):** `python tools/run_battery_family.py --gate` is registered
  in `UNIFIED_MEGA_GATE.md` as gate layer **G3**, slotted into the pre-commit
  sequence after G2. Forward-only ratchet (Rule B) vs `battery_family_baseline.json`
  — exit 1 if a component missing-required DEFECT appears or surfaced candidates rise
  above baseline; auto-tightens on reduction; `--update-baseline` to accept. Proven:
  regression → exit 1, at-baseline → exit 0.
- **Harden-down bridge (GH):** a stable G3 DEFECT → a G0 validator; a G3 journey-
  continuity check → a committed G2 spec (see `BATTERY_ARCHITECTURE.md` §7b).
- **Flywheel cadence** (§6).
- **Coverage ledger** ratchets toward 100% of the matrix (§7).

---

## 2. Cadence — when each altitude runs

| Trigger | What runs |
|---|---|
| **Every commit** | `run_battery_family.py` (headless) — fast, gates the candidate ledger |
| **Every feature / touched page** | `__UFAI.run` page kernel live on the changed page(s) + the L2 spec |
| **Weekly** | one live Page-sweep wave (B1→B4 rotation) + component confirm |
| **Every release** | the 3 journeys + the full platform family + companion stack |

---

## 3. Deploy & commit gating

Everything from this build is **LOCAL/uncommitted** (HEAD `8a904c4`). The roadmap's
first housekeeping step:
1. **Commit the battery family tooling** (the 4 tools + `journey_battery.js` +
   `ufai_battery.js` v1.4.0 + the two doctrine docs) — it's test/audit
   infrastructure, no product/runtime risk.
2. **Per-page fixes** found in Phase B ship through the normal deploy pipeline
   (the standing deploy decision still applies to the product edits).
3. The **family verdict becomes a pre-deploy check** (Phase F) so quality can't
   regress silently between releases.

---

## 4. The dispositioned backlog (already on the queue)

11 IA candidates are in `sweep_critiques.json` now. Phase-3 flags these 4 as
highest-priority (they sit on a CONFUSING novice path):
`sweep:ia:theme:late-overdue` · `sweep:ia:theme:due-soon-upcoming` ·
`sweep:ia:theme:risk-hot-critical` · `sweep:ia:relabel:pending-approval`.
The other 7 (affordance extra-paths + healthy/on-track theme) are Minor. Work them
through `promotion_dispositions.json`; accepted CONSOLIDATE/RELABEL items become
Architect/Frontend tickets that must keep `validate_user_facing_kpi_canonical.py`
green (0 math-drift).

---

## 5. What "fully used" looks like (success criteria)

- Every page in the matrix has a ② page-sweep with referee 0 Major for its roles.
- ① component verdict clean across the nav-section representatives.
- ③ all registered journeys executed; continuity drift either fixed or explained.
- ④ platform family green + candidate ledger fully dispositioned.
- ⑤ behaviour + data subjects wired into the platform run.
- ⑥ the family runs in CI and the coverage ledger ratchets — the battery is now a
  standing discipline.

---

## 6. Flywheel integration

The battery feeds the SAME engine as every other finding: critic candidates →
`sweep_critiques.json` → `flywheel_orchestrator` → `promotion_queue.md` →
`promotion_dispositions.json`. So "using the battery" is not a parallel process —
it's more fuel for the existing improvement flywheel. Each disposed item that
teaches a rule also gets a skill writeback (qa-tester / frontend / the domain
skill) per the project's self-improvement loop.

---

## 7. Coverage ledger (the honesty matrix — fill as you go)

> Mark each cell: `—` not started · `R` referee-clean · `S` swept-all-states ·
> `✓` role-matrix complete. A blank is an admission, not a pass.

| Page | ② Page (field) | ② Page (sup) | ② Page (eng) | ① Comp | ③ Journey |
|---|---|---|---|---|---|
| index | — | — | n/a | — | — |
| logbook | — | — | n/a | — | — |
| inventory | — | — | n/a | — | overdue?/stock |
| dayplanner | — | — | n/a | — | overdue |
| pm-scheduler | — | — | n/a | — | overdue |
| hive | n/a | — | n/a | — | — |
| analytics | n/a | — | — | — | — |
| predictive | n/a | — | — | — | risk |
| asset-hub | n/a | — | — | — | risk/approvals |
| alert-hub | n/a | — | n/a | — | risk |
| shift-brain | n/a | — | — | — | — |
| skillmatrix | ✓all | ✓all | ✓all | — | — |
| _…remaining 16 pages…_ | — | — | — | — | — |

(Seed the table from `ia_inventory_corpus.json.pagesSurveyed`; `skillmatrix` row
shown as the format example — set real marks as waves complete.)

---

## 8. First action

```
# headless, right now — re-baseline + see the queue:
python tools/run_battery_family.py
python ufai_ingest.py ia_streamlining_candidates.json   # (already done; idempotent)

# then Phase B1 live (per page), e.g. index:
#   browser_navigate → boot ufai_battery.js → __UFAI.run({pageId:'index',role:'field',experience:'novice'})
#   fix DEFECTs inline → ingest critics → repeat for supervisor × novice/exp
```
