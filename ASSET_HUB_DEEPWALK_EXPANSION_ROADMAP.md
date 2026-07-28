# Asset Hub Deepwalk — EXPANSION Arc (journeys × personas × states, + new asset dimension classes)

> **Ian, 2026-07-28:** *"what's next page we should do next?"* → Asset Hub, chosen after measuring the
> candidates (§0). Then: *"use the usual framework with anti-drift and momentum drive."*
> Same canonical flow as the marketplace / hive / logbook / **PM Scheduler** expansion arcs (the last
> just closed at 100.0% on every axis): GROUND → roadmap → state+scoreboard → register the gate →
> drive Phase 1, with Engine A (live walk) seeding Engine B (night-crawler harvest) at spoke ⑤.

---

## §0 · WHY THIS ARC EXISTS — the honest depth gap (measured, not asserted)

Asset Hub was chosen on evidence, not vibe. It carries the **widest truth-view surface on the
platform** — 11 views (`v_asset_truth`, `v_fmea_truth`, `v_rcm_truth`, `v_risk_truth`, `v_pf_truth`,
`v_weibull_truth`, `v_sensor_truth`, `v_sensor_recent`, `v_logbook_truth`, `v_external_sync_truth`,
`v_marketplace_listings_truth`) — 11 DB writes, 5 edge invokes, and it owns the **asset identity
spine** every other page reads. The PM arc implicated it **twice, independently**, which is direct
evidence it is under-walked:

- `_intervalToFrequencyLabel` rounded a 300-day RCM interval to **Annual (365)** — 65 days rarer than
  the strategy specified (fixed in the PM arc, PMK4).
- `resolvePmAssetId` created `pm_assets` rows straight from the client with **no role gate**, which
  is what blocked the PM INSERT guard until it was moved server-side (PMK6).

`ASSET_ALERT_SHIFT_DEEP_ARC.md` closed its 6-phase PDDA and left a **named backlog** — F18 (dead
external-ids card), F20 (silent 200-row fleet cap), **F21 (a worker's Pending-assets tile always
reads 0)**, F41/F43 (opaque brain citations; `expires_at` selected but never enforced), Ext-2 (reuse
follow-ups). Those are inherited, not re-discovered.

### THE MEASURED GAP: the governance surface has never been walkable

| Measured (2026-07-28) | Value | What it means |
|---|---|---|
| `asset_nodes` total | 95 | the fleet |
| ...with `auth_uid` set | **0** | every row is seeder-created; **nobody authored any of them** |
| ...authored by a worker / supervisor | **0 / 0** | no persona owns a row |
| ...`status='pending'` / `'rejected'` | **0 / 0** | **only the terminal state exists** |
| ...with `submitted_by` (TEXT) | 90 | the submitter is a NAME, with no identity FK behind it |
| `rcm_strategies` approved / unapproved | **172 / 0** | the strategy approval gate is equally unwalkable |
| audit triggers on `asset_nodes`, `rcm_strategies`, `rcm_fmea_modes` | **0 / 0 / 0** | 567 rows, no tamper-evidence |

So the page's entire **submit → review → approve / reject → restore** workflow — its governance, the
thing `approveAssetNode` / `rejectAssetNode` / `restoreAssetNode` / `approveFmeaMode` /
`approveStrategy` exist for — has **no data in any state but the terminal one**. That is why F21 sat
in the backlog undiagnosed: *there has never been a pending asset to see.*

This is the logbook arc's lesson in a new place — **the seeder decides what can be tested, and
under-generating a STATE is the quiet failure because nothing looks broken.** The fixture, not the
walker, is the binding constraint again (LB13/LB17), and building it is Phase 1, recorded as a
finding rather than hidden as setup.

### The second spine: numbers that decide when a machine is opened up

Asset Hub does not just display data — it **computes engineering values that set inspection timing**:
Weibull β/η fits, P-F intervals, FMEA RPN, RCM strategy intervals. A wrong Weibull shape or a wrong
P-F interval does not misreport history; it decides *when a plant next looks at a machine*. The PM
arc's discipline (a number is a claim; a claim needs a falsifiable oracle) applies here at its
sharpest, and the consequence of being wrong is physical rather than cosmetic.

---

## §1 · FRAMEWORK (reused, not reinvented — anti-drift)

- **The 5 phases** `G → W → O → H → R` (Ground, Walk, Observe, Harvest, Resolve).
- **The two-engine loop** — Engine A (live Playwright-MCP walk) drives Engine B
  (`tools/night_crawler.py`) at spoke ⑤. **Retrieve-first stays the rule** (`--query` / `--ensure`
  cost 0 crawl tokens on a hit); crawl only on a genuine bag miss.
- **The measured %-board** — `tools/asset_hub_deepwalk_scoreboard.py` computes from
  `asset_hub_deepwalk_state.json`. No number is asserted in prose.
- **Forward-only ratchet** — registered gate; a walked cell cannot silently revert.
- **The shallow-W guard** — `W=done` requires **≥2 personas AND ≥2 states**. It earned its keep in
  both prior arcs by refusing credit until a fixture could express a second persona; §0 says it will
  refuse most of this arc until the governance fixture exists.
- **Evidence classification** — a cell moves only on cited live evidence.

### Surfaces in scope
`asset-hub.html` (fleet list · detail with FMEA / RCM / P-F / Weibull / telemetry / timeline / risk ·
the pending-approval queue · the parts-staging panel). In scope where a journey crosses:
`pm-scheduler.html` (the RCM→PM push, now via `ensure_pm_asset_for_node`), `hive.html` (the same
approval queue), `logbook.html` (asset identity + the rename propagation via
`sync_pm_asset_identity`), `alert-hub.html` and `shift-brain.html` (risk consumers), and the five
edge functions (`ai-gateway`, `asset-brain-query`, `fmea-populator`, `pf-calculator`,
`weibull-fitter`).

---

## §2 · EXPANSION 1 — THE JOURNEY MATRIX (grow the JOURNEY denominator)

### Persona axis (5)
`P-worker` (submits an asset from the floor) · `P-supervisor` (reviews the queue, approves/rejects) ·
`P-reliability` (builds FMEA / RCM strategy / Weibull / P-F) · `P-multi` (member of ≥2 hives) ·
`P-new` (a hive with assets but no reliability work yet).

### State axis (7)
`S-pending` · `S-approved` · `S-rejected` · `S-restored` · `S-no-history` (an asset with no failures —
Weibull cannot fit) · `S-no-telemetry` (no sensor rows) · `S-error` (RLS refusal / edge fn down).

### The journeys (AH1–AH18)

| # | Journey | Type | Personas that matter |
|---|---|---|---|
| AH1 | First run — a hive with assets but no reliability work | T1-onboarding | new, reliability |
| AH2 | **Worker submits an asset → it enters the pending queue** | T4-transition | worker |
| AH3 | **Supervisor approves / rejects — and the rejection must SAY WHY** | T3-collab | supervisor, worker |
| AH4 | **Restore a rejected asset — can the submitter see what happened?** | T4-transition | worker, supervisor |
| AH5 | Fleet list: search, 200-row cap, QR scan (inherited **F20**) | T2-core | supervisor, worker |
| AH6 | Asset detail — the 11-view roll-up renders honestly per state | T2-core | reliability, worker |
| AH7 | **FMEA: add a failure mode, RPN is computed and defensible** | T5-insight | reliability |
| AH8 | **RCM strategy → interval → push to PM Scheduler** | T6-fabric | reliability, supervisor |
| AH9 | **Weibull fit — with too few failures, does it refuse or guess?** | T5-insight | reliability |
| AH10 | **P-F interval — the number that sets inspection frequency** | T5-insight | reliability |
| AH11 | Asset identity: rename propagates to PM + logbook (via the new RPC) | T6-fabric | supervisor |
| AH12 | Delete / retire an asset — what happens to its FMEA, RCM, history | T4-transition | supervisor |
| AH13 | Cross-hive: a foreign asset's reliability data cannot leak or be written | T7-tenancy | multi |
| AH14 | Parts staging: accept / dismiss a recommendation (inherited **F43** `expires_at`) | T3-collab | supervisor |
| AH15 | Asset Brain Q&A — citations are checkable (inherited **F41**) | T5-insight | reliability, worker |
| AH16 | Telemetry / sensor panel with and without data | T2-core | reliability |
| AH17 | External CMMS ids — the dead card (inherited **F18**) | T6-fabric | supervisor |
| AH18 | Mobile 390px at-the-asset lookup (QR → detail) | T2-core | worker |

---

## §3 · EXPANSION 2 — NEW DIMENSION CLASSES `AHK*` (grow the DIMENSION denominator)

Seeded **small and only where evidence already exists**, the discipline both prior arcs proved. Two
open on measured evidence; the rest must be *earned* by a walk.

| Class | The rule | Measure | Distinct from existing | Gate |
|---|---|---|---|---|
| **AHK1 · A governance decision needs an IDENTITY, not a name** (OPEN) | Approve / reject / submit must be attributable to an auth identity that cannot be typed, and recorded where it cannot be bypassed. | `asset_nodes`: 0 of 95 rows carry `auth_uid`; 90 carry a TEXT `submitted_by`; `approved_by` is TEXT; **0 audit triggers**. | PMK3 covered *completion* tamper-evidence; this is the **approval decision** itself, and the forgeable-name half. | new |
| **AHK2 · A number that sets inspection timing must be FALSIFIABLE** (OPEN) | Weibull β/η, P-F interval and RPN each need a stated method, a refusal path when the data cannot support them, and an oracle. | 172 RCM strategies, 300 FMEA modes, all approved; Weibull/P-F run in edge fns with no in-repo oracle found at ground. | PMK1 was a metric *flattering what was done*; this is a computed value **deciding future action**. | new |
| **AHK3 · The fixture must contain every state the workflow can be in** (CANDIDATE) | A state with no rows is a state nobody has walked; the seeder is part of the test surface. | 0 pending, 0 rejected, 0 unapproved strategies. | Sharpens LB13/LB17 from *relationships* to *workflow states*. | earn it |
| **AHK4 · Reliability data is hive-private** (CANDIDATE) | FMEA/RCM/Weibull are competitive plant knowledge; cross-hive read or write is a leak. | `rcm_*` policies are member-scoped ALL; unprobed. | Extends PMK6/PM13 to the reliability tables. | earn it |

---

## §4 · THE %-BOARD (measured from state, never asserted)

`asset_hub_deepwalk_state.json` + `tools/asset_hub_deepwalk_scoreboard.py`, registered as
`asset-hub-deepwalk-ratchet`. Two axes, both must reach 100%:

- **journeys** = 18 × 5 phases, with the shallow-W guard naming every cell credited on one persona.
- **classes** = the `AHK*` denominator × 6 stages (harvest / define / detect / sweep / fix / gate).

---

## §5 · DRIVE ORDER (risk-first)

1. **AH2 + AH3 + AHK3** — build the governance fixture, then walk submit → approve/reject. Nothing
   else in the workflow is walkable until this exists, and §0 says the guard will refuse credit.
2. **AHK1** — probe self-approval, name-vs-identity attribution, and the missing audit trail.
3. **AH9 + AH10 + AHK2** — the numbers that set inspection timing: does a Weibull fit refuse when the
   failure count cannot support it, and where does the P-F interval come from?
4. **AH8 + AH11** — the RCM→PM push and identity propagation (both touched by the PM arc).
5. **AH13 + AHK4** — cross-hive reliability isolation.
6. Then §2 order downward; every ⑤-harvest that earns a class refills the §7 queue.

---

## §6 · SEED EVIDENCE (what is already proven, so it is not re-litigated)

- The RCM interval→frequency rounding is FIXED and gated (`whFreqFromDays`, PMK4) — AH8 inherits a
  green floor and must not re-open it.
- `resolvePmAssetId` now routes through `ensure_pm_asset_for_node` (SECURITY DEFINER, membership
  checked, idempotent, cross-hive-refusing) — AH8/AH11 build on that, not around it.
- Asset renames propagate via `sync_pm_asset_identity`; `pm_assets` INSERT/UPDATE/DELETE are all
  supervisor-gated at the DB (PMK6) — AH11/AH12 inherit those guarantees.

---

## §7 · NEXT (the standing queue — drive top-down)

1. ~~Ground: measure the depth gap, read the inherited PDDA backlog, choose the spine.~~ (this turn)
2. **Build** `asset_hub_deepwalk_state.json` + `tools/asset_hub_deepwalk_scoreboard.py` with
   `--selftest` and the shallow-W guard, and register the gate + the `validate_asset_hub_deepwalk.py`
   flywheel shim **in the same change**.
3. **AH2/AH3/AHK3 — the governance fixture.** Seed worker-submitted `pending` and `rejected`
   asset_nodes with real `auth_uid` attribution, and at least one unapproved RCM strategy; co-land it
   in `test-data-seeder/` so a reseed cannot reopen the gap. Then walk submit → approve → reject.
4. **AHK1** — self-approval probe, name-vs-identity attribution, audit trail.
5. **AH9/AH10/AHK2** — the inspection-timing numbers and their refusal paths.
6. Then §5 order downward.

---

## §8 · THE FLYWHEEL (standing SOP — one turn advances a journey)

① pick the lowest cell (§5 order) → ② **Engine A** live walk (≥2 personas × ≥2 states) → ③ observe
with evidence (a clean walk is a real result; record it) → ④ fix → ⑤ **Engine B** harvest a citable
standard *for the friction just observed* (`--query`/`--ensure` first; crawl on a genuine bag miss)
→ ⑥ lock with a gate → ⑦ ratchet → next cell.

Method lessons carried in from the PM arc, which cost real time to learn:

- **Measure the legitimate callers BEFORE tightening a write.** Twice the obvious guard would have
  broken more than the bug (all 90 asset renames; every worker's RCM push). The fix both times: move
  the system-owned write into a SECURITY DEFINER RPC, *then* gate the table.
- **Verify the instrument before the page.** `browser_resize(390)` gave `innerWidth` 585 (dpr 0.667);
  a literal grep missed a branch matching on the complement; a probe picked a node the worker did not
  author and "proved" a guard that was not there.
- **SQL through `subprocess` must be pure ASCII** — an em dash silenced a whole probe and reported
  five failures that were one encoding error.
- **Measure the WORKED state**, not the landing state (dashboard 0 defects, detail 10).
- **A ratchet must stay re-baselineable** — keep `--accept` in front of the checks.
- **Restore what a walk consumes**, and never label a bare `UPDATE` as rolled back.

---

## §9 · THE TWO DISCIPLINES (non-negotiable)

**1. ANTI-DRIFT.** The board is MEASURED from state, never asserted. A cell moves only on cited live
evidence. The scoreboard is a REGISTERED, forward-only gate. When a gate fires on correct code,
**teach the gate** — never bend the code — and pin the false-positive shape as a named self-test. New
DB functions, validators, RPCs and write tables need their registration **in the same change**.

**2. MOMENTUM.** Authoring a `NEXT:` line is *executing its first item*. An Ian-gated outward step
(commit / push / deploy) is never a stop — pivot to the remaining local work. Only these end a turn:
(a) a fork Ian must decide, (b) a hard external ceiling, (c) an irreversible action that is the SOLE
remaining item, (d) the local queue genuinely EMPTY and tested, (e) Ian says wrap in THIS message.
