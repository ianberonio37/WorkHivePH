# WorkHive Roadmap — Fix the numbers, then one brain for all screens
_2026-06-10. Plain-language plan. Each phase is a small, shippable step._

## The big idea (one sentence)
Every number should be **calculated once in one place** and **shown the same everywhere** —
heavy screens should show a **saved result + a Refresh button** instead of recalculating every
time you open them.

---

## Phase 0 — DONE this session ✅
What we found and fixed already (all local, gate green, not deployed):

- **PM due-date math was wrong.** Weekly PMs were treated as if they were due every 90 days
  instead of every 7. This made "next due" dates and overdue/due-soon wrong on **every** PM
  screen. → Fixed.
- **PM compliance number was wrong on the PM Scheduler.** It showed 0% (then 60%) when the real
  number is **89%** — so the page said you were failing the maturity gate when you were passing.
  → Fixed by making **one shared calculation** that both PM Scheduler and Analytics now use.
- **Added a gate check** so this kind of math bug can't silently come back.
- Wrote this roadmap.

---

## Phase 1 — Analytics: show saved result + Refresh (stop recalculating every visit)
**Problem:** Analytics recalculates all 4 tabs every time you open the page (slow, and it depends
on a server being up). Everything else (AMC brief, risk, readiness) already saves a daily result —
Analytics is the only one that doesn't.

**Do:**
1. Save each Analytics result to a table when it runs.
2. Page opens → show the **last saved result instantly** with a "Computed 6h ago" label.
3. The **Refresh button** is the only thing that recalculates.
4. A nightly job refreshes it automatically, so mornings are fresh without a click.

**Done when:** Opening Analytics is instant, shows when it was last computed, and only Refresh
recomputes. (This is the first thing you'll actually *see* change.)

---

## Phase 2 — Shift Handover: auto each shift + carry over to the next
**Problem:** Handover should be a daily routine, not something recalculated on page load.

**Do:**
1. Generate the handover **once per shift** automatically (06:00 / 14:00 / 22:00).
2. **Carry forward:** anything that happens during a shift (new job, PM done, new risk) rolls
   into the **next** shift's handover automatically.

**Done when:** Each shift opens to a ready handover that already includes the previous shift's
open items — nothing dropped at handoff.

---

## Phase 3 — One brain, many screens
**Problem:** AMC brief, Alert Hub, Asset 360, Home, Hive board, and Predictive each do their own
math today. That's how the compliance bug (Phase 0) happened — two screens, two calculations.

**Do:**
1. One "analytics engine" calculates the numbers and **saves** them.
2. All the screens above **read** those saved numbers — they never recalculate.
3. **Feedback loop:** when a supervisor acts (does a PM, dismisses a false risk, thumbs an AI
   answer), that feeds back into the engine so the next calculation reflects it.

**Done when:** The same number shows the same on every screen, and acting on something updates
the source everyone reads from.

---

## Phase 4 — Remove the duplicate Predictive page
`predictive.html` is already half-retired — the page itself says *"risk is now centralized in
Asset Hub."* Fold its one table into Analytics + Asset Hub and remove the page (with a redirect).

**Done when:** One less page to maintain; risk lives in Asset Hub + Analytics only.

---

## Phase 5 — Add gate checks so it can't drift again
**Do:** Add automated checks that enforce the "one brain" rule — e.g. *"every screen reads the
official number, it doesn't invent its own."* Plus small clean-ups (a couple of cosmetic display
bugs found this session).

**Done when:** If someone adds a screen that recalculates a number locally, the gate stops it.

---

## Phase 6 — Keep checking the rest of the pages
Walk the remaining pages the same careful way we did Analytics (Community, Marketplace, Resume,
Skill Matrix, Achievements, Voice Journal, Assistant, Audit Log, etc.), find and fix what's wrong.

---

## Phase 7 — Deploy to production (your call)
The Phase 0 fixes are **local only**. Production still has the wrong PM due-date math and the wrong
compliance number until we deploy. This is a **correctness deploy** (it fixes real wrong numbers),
not just a feature — so it's worth doing, but the timing is your decision.

---

## Suggested order
Phase 1 first (you'll see it immediately), then Phase 5's "one official number" check, then Phase 3
(one brain), then Phase 4 (remove duplicate), then Phase 2 (shift handover). Phase 6 and Phase 7 run
alongside whenever you want.

---

## Two questions for you
1. **Where do I start building — Phase 1 (Analytics save+refresh, visible win) or the Phase 5
   check first (locks everything after it)?**
2. **Alert Hub refreshes every 60 seconds today.** Keep it live like that (it's the "act now"
   screen), or switch it to saved + manual Refresh like Analytics?

---

<details>
<summary>Appendix — technical detail (for engineers)</summary>

### Findings ledger
| # | Finding | Status |
|---|---|---|
| F1 | Source-chip captions said retired "30 days since last anchor" rule; hive chip named wrong source view | ✅ d782b9e |
| F2 | `v_pm_scope_items_truth.frequency_days` seeder-vocab drift (Weekly/Semi-annual/Annual → ELSE 90) | ✅ ac67feb |
| F3 | `prescriptive.py FREQ_DAYS` same drift (weekly=30) | ✅ 328539c |
| F4 | pm-scheduler "compliance" = on-track/total, not SMRP 88.5% → canonical RPC `get_pm_compliance_smrp` | ✅ ca98f8a |
| F5 | `parts_consumption_spike` `spike_factor:null` contract violation | ⬜ Phase 5 |
| F6 | Em-dash double-encoding in generated strings | ⬜ Phase 5 |
| F9 | Flat 14-day due-soon makes weekly PMs always "due soon" | ⬜ design |

### Why the gate missed it
Strong on **structure** (does the column/view exist), weak on **semantics** (is the math right;
do duplicate copies agree). 4 meta-gaps → closed/closing via: `validate_frequency_map_consistency.py`
(done), a KPI source-parity validator (Phase 5), extend source-chip-truth, contract-violation ratchet.

### Compute model (Phase 1/2) — grounded
Already snapshot: `amc_briefings`, `ai_reports`, `hive_readiness`, `hive_adoption_score`,
`v_risk_truth` (daily 13:00 PHT). Outlier: analytics-orchestrator recomputes on every load → give it
an `analytics_snapshots` table + Refresh + nightly cron. Shift handover → `shift_handovers` snapshot
at shift boundaries with carry-forward.

### Reconciliation (Phase 3) — data flow
Engine (orchestrator + batch-risk ML + AMC) writes canonical snapshots → alert-hub, asset-hub,
home, hive board, predictive all READ them → user actions (completions, dismiss-risk, thumbs) feed
back. Work items R1 (one alert composer) · R2 (asset-brain projection) · R3 (dashboards read engine)
· R4 (ML feedback signal) · R5 (KPI source registry + gate check).
</details>
