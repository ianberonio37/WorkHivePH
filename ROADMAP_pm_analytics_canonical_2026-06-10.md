# WorkHive Roadmap — One source of truth, open-fast pages
_Crystallized 2026-06-10. Plain language, scoped to specific pages (see `PAGE_SURVEY_2026-06-10.md`)._

## The big idea (one sentence)
Every number is **calculated once, in one place, shown the same everywhere**; heavy pages show a
**saved result + a Refresh button** instead of recalculating every time you open them.

## The compute rule — NO pg_cron (Ian, 2026-06-10)
- **A page a person opens** → first view of the day computes + **saves**, everyone else sees the
  saved copy, **Refresh** forces new. No scheduled jobs.
- **In-app alerts** compute on view (already do). **Event-driven** reactions (low-stock-on-change) →
  DB webhook (instant, not a timer) *if/when wanted*. **Scheduled email/push** → deferred.

---

## Phase 0 — DONE ✅ (shipped this session, local, gate-green)
- Fixed PM due-date math — `v_pm_scope_items_truth.frequency_days` ignored Weekly/Semi-annual/Annual
  (treated Weekly as 90 days, not 7). Fixed platform-wide. `ac67feb`
- Fixed PM compliance — PM Scheduler showed 0%/60% (on-track ratio) vs the real 88.5% (SMRP). Now one
  shared `get_pm_compliance_smrp` RPC used by **both** PM Scheduler and Analytics. `ca98f8a`
- Added a gate check (`validate_frequency_map_consistency.py`) so the math bug can't return. `328539c`
- Survey + roadmap. `c21fa24`

---

## Phase 1 — Heavy pages open-fast (compute-on-open + Save + Refresh)
**Scope (only the report-style heavy pages):**
- **Analytics** (`analytics.html`) — flagship. Add `analytics_snapshots` table; first open/day computes
  + saves; later opens instant; **Refresh** recomputes. Also removes its dependency on the Python API
  being up at view-time.
- **PH Intelligence** (`ph-intelligence.html`) — same treatment.
- **Project Report** (`project-report.html`) — same.

**Leave live on purpose** (input/chat-driven — you *want* fresh): Assistant, Voice Journal,
Engineering Design. Asset Hub's per-asset calcs → optional cache-per-asset later.

**Done when:** Analytics/PH-Intelligence open instantly after the first daily view, show "Computed Xh
ago," and only Refresh recomputes.

---

## Phase 2 — Shift Handover: auto each shift + carry-forward (`shift-brain.html`)
First open in a new shift generates the handover (seeded from the previous shift's open items) and
saves it for that shift. Anything that happens in a shift rolls into the next shift's handover. No
pg_cron; "handover ready" push deferred.

**Done when:** each shift opens to a ready handover that already carries the prior shift's open items.

---

## Phase 3 — One brain: intelligence pages read one engine (stop re-deriving)
This is where the compliance bug came from — two pages, two calculations. Fix the pattern:
- **One alert composer** feeding both **Alert Hub** (`alert-hub.html`) and the Hive Board "Open
  issues" (`hive.html`) — same risk+PM+stock+pattern logic computed once.
- **Dashboards read the engine** — Home (`index.html`) + Hive Board already use `get_hive_dashboard`;
  extend it so they never re-derive (add AMC headline + analytics snapshot KPIs).
- **Asset Hub** (`asset-hub.html`) carries the same risk score the alert feed showed (no recompute).
- **Feedback loop** — supervisor does a PM / dismisses a false risk / thumbs an AI answer → feeds the
  next risk calculation (`batch-risk-scoring`) + `ai_reply_feedback`.

**Done when:** the same number reads identical on every screen, and acting on something updates the
one source.

---

## Phase 4 — Remove duplicate pages
- **Retire `predictive.html`** — it already says "risk is centralized in Asset Hub." Fold its table
  into Asset Hub + the Analytics *Predictive* tab; redirect.
- **Merge the 3 AI-health pages** (`ai-quality` + `llm-observability` + `agentic-rag-observability`)
  → one **AI Health** page.
- **Decide on the other pairs:** integrations ↔ plant-connections · analytics-report ↔ report-sender
  · community ↔ public-feed · project-manager ↔ project-report.
- Delete retired `parts-tracker.html`.

**Done when:** fewer pages, each metric lives in exactly one place.

---

## Phase 5 — Gate checks so it can't drift again
- **KPI source registry** — every metric declares its one official source (view/RPC); a new gate
  check fails any page that invents its own calculation (would've caught the compliance bug).
- Clean up two small leftovers: `spike_factor` contract (F5), em-dash text glitch (F6).

**Done when:** if someone adds a screen that recalculates a number locally, the gate stops it.

---

## Phase 6 — Live-walk the ~14 un-walked pages (IN PROGRESS next)
Operate each like the core ones (not just read code), find + fix real bugs. Priority order:
Shift Brain detail → AI-health trio → PH Intelligence → Project Manager/Report → Integrations/Plant
Connections → Marketplace seller/admin → Skill Matrix → Public Feed → Audit Log → Platform Health.
**Findings from this walk get folded back into Phases 1–5.**

**Done when:** all 40 pages operated and their bugs fixed.

---

## Phase 7 — Deploy to production (your call)
Phase 0's fixes are **local only** — production still has the wrong PM due-dates + compliance number.
This is a **correctness deploy**. Timing is your decision.

---

## Suggested order
Phase 6 walk (now) → Phase 1 (Analytics open-fast) → Phase 5 (registry check) → Phase 3 (one brain)
→ Phase 4 (remove duplicates) → Phase 2 (shift handover). Phase 7 (deploy) whenever you say.

---

<details>
<summary>Appendix — technical detail (for engineers)</summary>

### Findings ledger (this session)
| # | Finding | Status |
|---|---|---|
| F1 | Source-chip captions said retired "30 days since last anchor"; hive chip named wrong source view | ✅ d782b9e |
| F2 | `frequency_days` seeder-vocab drift (Weekly/Semi-annual/Annual → ELSE 90) | ✅ ac67feb |
| F3 | `prescriptive.py FREQ_DAYS` same drift (weekly=30) | ✅ 328539c |
| F4 | pm-scheduler "compliance" = on-track/total, not SMRP 88.5% → canonical RPC | ✅ ca98f8a |
| F5 | `parts_consumption_spike` `spike_factor:null` contract violation | ⬜ Phase 5 |
| F6 | Em-dash double-encoding in generated strings | ⬜ Phase 5 |
| F9 | Flat 14-day due-soon makes weekly PMs always "due soon" | ⬜ design |

### Why the gate missed it (the meta-gaps)
Strong on **structure** (does the column/view/token exist), weak on **semantics** (is the math right;
do duplicate copies agree). 4 meta-gaps → closing via: `validate_frequency_map_consistency.py` (done);
KPI source-parity validator (Phase 5); extend source-chip-truth; contract-violation ratchet.

### Compute model (grounded)
Default = lazy compute-on-first-view + cache + Refresh, **no cron**. Already-snapshot surfaces
(`amc_briefings`, `ai_reports`, `hive_readiness`, `hive_adoption_score`, `v_risk_truth` @ 13:00) can
move to the same model. Only ~8 pages are 🔴 Heavy (recompute on load) — see `PAGE_SURVEY_2026-06-10.md`.

### Reconciliation (Phase 3) data flow
Engine (orchestrator + batch-risk ML + AMC) writes canonical snapshots → alert-hub, asset-hub, home,
hive board, predictive READ them → user actions feed back. Work items R1 one alert composer · R2
asset-brain projection · R3 dashboards read engine · R4 ML feedback signal · R5 KPI source registry.
</details>
