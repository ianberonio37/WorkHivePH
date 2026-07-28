# Project Manager — Deepwalk Expansion Arc

**Opened 2026-07-28.** Successor to `PROJECT_MANAGER_DEEP_ARC.md` (the older, shallower pass).
Same framework as the PM Scheduler and Asset Hub arcs: journeys × personas × states, plus NEW
dimension classes, both denominators measured from state and never asserted.

---

## §1 · WHY THIS PAGE

Chosen on measurement, not preference. `project-manager.html` is **the write-heaviest surface on
the platform** — 21 client writes (9 insert / 10 update / 2 delete) across **7 tables**, 68
interactive elements, 96 top-level functions, 6 truth views and 3 edge functions — and it has never
had an expansion arc.

It is also where the platform handles **money and commitments**: a change order is a contract
amendment, an Earned Value status is a health claim to a client, and a critical path decides which
work is allowed to slip.

### The GROUND findings (measured 2026-07-28, before any journey)

| # | Finding | The measurement |
|---|---|---|
| **G1** | **Six of seven project tables have NO `auth_uid` column at all.** Only `projects` has one. | `project_items`, `project_change_orders`, `project_progress_logs`, `project_roles`, `project_links`, `project_knowledge` — no attribution column exists, so **approving a change order is attributable to nobody**. AHK1's class over a whole domain. |
| **G2** | **`projects` writes NOTHING to `hive_audit_log`.** | `target_type` in `hive_audit_log`: `assets`, `logbook`, `inventory_items`, `marketplace_listings`, `marketplace_sellers`, `worker_profiles`, `amc_briefings` — **no `projects`**. The write-heaviest domain has no tamper-evident trail. |
| **G3** | **Every child table validates its OWN `hive_id` and never the parent project's.** | All 7 policies are a single `PERMISSIVE ... FOR ALL` with `WITH CHECK (auth.uid() IS NOT NULL AND hive_id IN (SELECT user_hive_ids()))`. Nothing joins `projects`. This is exactly PM13 / AHK4, un-probed here. |
| **G4** | ~~One permissive `ALL` policy per table = any active member can approve a change order.~~ **CORRECTED 2026-07-28 by the PJ4 walk — the approval ACT is guarded; the pending REQUEST is not.** | I asserted this from the policy layer alone and it was WRONG: `wh_guard_supervisor_approval()` is a TRIGGER on six tables and `project_change_orders` is one of them. Probed live as a worker: approve -> BLOCKED, reject -> BLOCKED, edit an APPROVED CO's cost -> BLOCKED. What IS open is the pending request itself. A worker rewrote **another worker's** pending CO from PHP 500,000 to PHP 9,999,999 and widened its scope text, and the row still reads `requested_by: Wilfredo Malabanan`; a worker can also DELETE a pending CO outright. With G1 (no `auth_uid` on the table) and G2 (no audit trigger) there is no way to tell it changed, or who changed it — the supervisor approves what they are shown. |
| **G4b** | **A worker can edit or delete a PENDING change order, including one they did not raise.** | The guard protects the approval act and signed-off work; nothing protects the CONTENT or EXISTENCE of a request awaiting review. Proven live in a rolled-back probe. |
| **G5** | **`project_change_orders` = 0 rows. `project_roles` = 0 rows.** | Two tables with policies, triggers and a full UI (`openNewCO`, `approveCO`, `rejectCO`, `cancelCO`, `openAddRole`, `removeRole`) and **no data has ever existed**. AHK3: the CO approve/reject path has never once run. |
| **G6** | **Budget visibility is a UI-only gate.** | `renderBudget()` returns "Budget visibility is restricted to supervisors" when `!isSupervisor()` — a client check, while `projects_hive_rw` grants every member read. The number is one `db.from('projects')` away. |

Row counts at ground: `projects` 12 · `project_items` 90 · `project_progress_logs` 58 ·
`project_links` 54 · `project_change_orders` **0** · `project_roles` **0**.

---

## §2 · EXPANSION 1 — JOURNEYS (grow the JOURNEY denominator)

18 journeys × 5 phases (**G**round · **W**alk · **O**racle · **H**arden · **R**atchet).
**Shallow-W guard:** `W = done` requires ≥ 2 personas AND ≥ 2 states.

| # | Journey | Type | Personas that matter |
|---|---|---|---|
| PJ1 | First run — a hive with no projects at all | T1-onboarding | new, supervisor |
| PJ2 | Create a project — code generation, dates, budget | T4-transition | supervisor |
| PJ3 | **Scope items: add, sequence, set predecessors** | T2-core | supervisor, engineer |
| PJ4 | **Change order: raise → approve / reject / cancel (G5 — never walked)** | T3-collab | supervisor, worker |
| PJ5 | **Who approved this change order? (G1 — no `auth_uid` exists)** | T7-governance | supervisor, auditor |
| PJ6 | Progress log: submit, acknowledge, dispute | T3-collab | worker, supervisor |
| PJ7 | **Earned Value — is green/amber/red defensible? (EVM / PMBOK)** | T5-insight | supervisor |
| PJ8 | **Critical path — what decides that a task may slip?** | T5-insight | engineer, supervisor |
| PJ9 | **Budget: can a non-supervisor read it anyway? (G6)** | T7-governance | worker |
| PJ10 | Roles: assign, remove, and what a role actually gates (G5) | T4-transition | supervisor |
| PJ11 | Links to logbook / inventory / marketplace — do they survive deletion? | T6-fabric | supervisor |
| PJ12 | Delete a project — what goes with it, and is it recorded? (G2) | T4-transition | supervisor |
| PJ13 | **Cross-hive: a foreign project's items / COs cannot leak or be written (G3)** | T7-tenancy | multi |
| PJ14 | AI: draft lessons + intent modal — grounded and attributable? | T5-insight | supervisor |
| PJ15 | Project embeddings — what reaches the RAG, and whose? | T6-fabric | supervisor |
| PJ16 | Client rollup — the number a customer is shown | T5-insight | supervisor |
| PJ17 | Offline / queued project writes | T2-core | worker |
| PJ18 | Mobile 390px — approve a CO from the field | T2-core | supervisor, worker |

---

## §3 · EXPANSION 2 — NEW DIMENSION CLASSES `PJK*` (grow the DIMENSION denominator)

| Class | Claim | Ground evidence | Distinct from | Status |
|---|---|---|---|---|
| **PJK1 · A money decision needs an identity and a trail** | Raising, approving or rejecting a change order must be attributable to an auth identity and recorded where it cannot be bypassed. | G1 + G2: no `auth_uid` on 6/7 tables; `projects` absent from `hive_audit_log`. | AHK1 covered an *approval*; this is a **financial commitment**, and the trail is missing entirely rather than merely forgeable. | OPEN |
| **PJK2 · A schedule/health number must be falsifiable** | Earned Value status and the critical path each need a stated method, a refusal path when inputs are missing, and an oracle. | G-scan: `renderCpm` reads `_progress.critical_path`, `renderBudget` reads `_progress.earned_value` — both computed in the `project-progress` edge fn with no in-repo oracle found at ground. | AHK2 governed *inspection timing*; this decides **what may slip and what a client is told**. | OPEN |
| **PJK3 · Authority must be enforced where the data is** | A supervisor-only surface must be supervisor-only at the DATABASE, not in the renderer. | G4 + G6: one permissive `ALL` policy per table; budget hidden client-side only. | Sharpens `feedback_ui_only_approval_gate_is_bypassable` from a button to a **whole pane**. | OPEN |
| **PJK4 · A child row's parent must live in its own hive** | Items, COs, logs and links must not point at another hive's project. | G3: no policy joins `projects`. | Direct re-use of AHK4 in a new domain — **earn it by probing, not by assuming the analogy**. | CANDIDATE |

---

## §4 · THE %-BOARD (measured from state, never asserted)

State: `project_manager_deepwalk_state.json` · Scoreboard: `tools/pm_manager_deepwalk_scoreboard.py`
· Gate: registered in `run_platform_checks.py` in the SAME change as the state file.

```
journeys : 18 × 5 phases
classes  : PJK1–PJK4 × 6 stages (harvest · define · detect · sweep · fix · gate)
OVERALL  : the lower of the two, forward-only ratcheted
```

**AHK4's lesson is pre-applied here:** PJK4 is in the denominator from day one as a CANDIDATE. The
Asset Hub board read 100% while its fourth class sat untracked — a green headline over a missing
axis produces no red anywhere. A CANDIDATE that gets earned is promoted **with its gate in the same
change**, never promoted alone.

---

## §5 · DRIVE ORDER (risk-first)

1. **PJ4 + PJ5 + PJK1** — build the change-order fixture (G5: zero rows), then walk raise →
   approve/reject. Nothing else can be judged until the money path has data.
2. **PJ9 + PJK3** — probe the budget as a worker. A UI-only gate is one query from open.
3. **PJ13 + PJK4** — cross-hive probe on all six child tables. **Verify WHAT blocks a write, not
   merely THAT something did** (the 23514-vs-42501 error from AH13).
4. **PJ7 + PJ8 + PJK2** — the numbers that decide slip and client-facing health.
5. **PJ12 + G2** — deletion blast radius and the missing audit trail.
6. PJ1–PJ3, PJ6, PJ10, PJ11, PJ14–PJ18.

---

## §6 · SEED EVIDENCE (so it is not re-litigated)

- The six GROUND findings above are **measured**, not inferred: policy definitions, `pg_attribute`
  for `auth_uid`, `hive_audit_log.target_type` DISTINCT, and live row counts.
- `_shared` edge code and the `project-progress` / `project-orchestrator` functions were deployed to
  prod on 2026-07-28 unchanged by this arc — the arc starts from a known-deployed baseline.

---

## §7 · NEXT (the standing queue — drive top-down)

1. Build `project_manager_deepwalk_state.json` + scoreboard + gate **in one change**.
2. Seed the change-order and role fixtures (G5) — including a REJECTED CO with a reason, per the
   AH3 lesson that a refusal must say why.
3. PJ4/PJ5 walk.

---

## §8 · THE TWO DISCIPLINES (non-negotiable)

**1. ANTI-DRIFT.** The board is MEASURED from state. A cell moves only on cited live evidence. When
a gate fires on correct code, **teach the gate** — never bend the code. A gate must have TEETH:
slice the artifact into the units the rule is about, never count occurrences (the Asset Hub identity
gate passed with the bug reintroduced because it counted).

**2. MOMENTUM.** Authoring a `NEXT:` line is *executing its first item*. An Ian-gated outward step
is never a stop — pivot to remaining local work. Only these end a turn: (a) a fork Ian must decide,
(b) a hard external ceiling, (c) an irreversible action that is the SOLE remaining item, (d) the
local queue genuinely EMPTY, (e) Ian says wrap in THIS message.
