# UX Persona Walkthrough — Phase 3 (does the redundancy confuse a real user?)

> **Simulated, deterministic, SURFACE-only.** Personas (role × experience) attempt real jobs-to-be-done; the rubric flags the confusion their path crosses, grounded in the nav-hub.js role model + the Phase-1 redundancy map. It PRIORITIZES Phase 2's proposals (each finding cites the matching `sweep:ia:*` key); it changes nothing.

## Nav choice-load per role (Hick's Law)

_Primary-nav items a role sees (hidden tools excluded). More choices = slower decisions, worst for a novice._

| Role | Primary-nav tools |
|---|---|
| field | 11 |
| supervisor | 17 |
| engineer | 11 |

## Novice verdict matrix

_The novice is where confusion bites. CLEAR = single obvious source; MILD = a secondary-source risk; CONFUSING = multiple authoritative-looking answers or an unreachable source of truth._

| Job-to-be-done | Role | Canonical home | Reachable? | Surfaces in nav | Verdict |
|---|---|---|---|---|---|
| Find what maintenance is due or overdue | field | pm-scheduler | yes | dayplanner, pm-scheduler | **CONFUSING** |
| Find what maintenance is due or overdue | supervisor | pm-scheduler | yes | dayplanner, pm-scheduler, project-manager | **CONFUSING** |
| Find the highest-risk asset right now | engineer | predictive | **NO** | asset-hub | **CONFUSING** |
| Find the highest-risk asset right now | supervisor | predictive | **NO** | alert-hub, asset-hub | **CONFUSING** |
| See what is waiting for my approval | supervisor | — (ambiguous) | **NO** | asset-hub, inventory | **CONFUSING** |
| Check which parts are low or out of stock | field | inventory | yes | inventory | CLEAR |
| Check which parts are low or out of stock | supervisor | inventory | yes | inventory | CLEAR |
| Check the team's skills / readiness | supervisor | skillmatrix | yes | pm-scheduler, skillmatrix | CLEAR |

## Confusion findings, ranked (novice first)

| # | Persona | Job | Confusion | Sev | UX-law | Why | Prioritizes |
|---|---|---|---|---|---|---|---|
| 1 | supervisor/novice | See what is waiting for my approval | **Relabel collision** | High | Nielsen #2 (real world) | "Pending approval" appears on asset-hub, inventory meaning different subjects (assets vs parts) under one label. | `sweep:ia:relabel:pending-approval` |
| 2 | field/novice | Find what maintenance is due or overdue | **Ambiguity of source** | High | Jakob + Nielsen #4 | 2 pages in this field's nav answer the same job (dayplanner, pm-scheduler). the overdue count is derived two ways (per-asset v_pm_compliance_truth vs per-scope-item v_pm_scope_items_truth) → the surfaces CAN disagree. | `sweep:ia:theme:late-overdue`, `sweep:ia:theme:due-soon-upcoming` |
| 3 | supervisor/novice | Find what maintenance is due or overdue | **Ambiguity of source** | High | Jakob + Nielsen #4 | 3 pages in this supervisor's nav answer the same job (dayplanner, pm-scheduler, project-manager). the overdue count is derived two ways (per-asset v_pm_compliance_truth vs per-scope-item v_pm_scope_items_truth) → the surfaces CAN disagree. | `sweep:ia:theme:late-overdue`, `sweep:ia:theme:due-soon-upcoming` |
| 4 | engineer/novice | Find the highest-risk asset right now | **Canonical unreachable** | High | Nielsen #6 (recognition) | The source of truth (predictive) is hidden from primary nav → this engineer lands on a secondary surface and takes it as authoritative. | `sweep:ia:theme:risk-hot-critical` |
| 5 | supervisor/novice | Find the highest-risk asset right now | **Ambiguity of source** | High | Jakob + Nielsen #4 | 2 pages in this supervisor's nav answer the same job (alert-hub, asset-hub). risk is shown as alerts (alert-hub), critical assets (asset-hub), and the risk ranking (predictive) — three lenses, one underlying question. | `sweep:ia:theme:risk-hot-critical` |
| 6 | supervisor/novice | Find the highest-risk asset right now | **Canonical unreachable** | High | Nielsen #6 (recognition) | The source of truth (predictive) is hidden from primary nav → this supervisor lands on a secondary surface and takes it as authoritative. | `sweep:ia:theme:risk-hot-critical` |
| 7 | supervisor/novice | See what is waiting for my approval | **Ambiguity (weak / cross-subject)** | Low | Jakob | 2 pages in this supervisor's nav answer the same job (asset-hub, inventory). BUT these surface different subjects (assets, parts) → likely distinct jobs sharing a word, not one drifting number. | `sweep:ia:relabel:pending-approval` |
| 8 | supervisor/novice | Check the team's skills / readiness | **Ambiguity (weak / cross-subject)** | Low | Jakob | 2 pages in this supervisor's nav answer the same job (pm-scheduler, skillmatrix). BUT these surface different subjects (PM tasks, skills) → likely distinct jobs sharing a word, not one drifting number. | `sweep:ia:theme:healthy-on-track` |
| 9 | field/experienced | Find what maintenance is due or overdue | **Ambiguity of source** | High | Jakob + Nielsen #4 | 2 pages in this field's nav answer the same job (dayplanner, pm-scheduler). the overdue count is derived two ways (per-asset v_pm_compliance_truth vs per-scope-item v_pm_scope_items_truth) → the surfaces CAN disagree. | `sweep:ia:theme:late-overdue`, `sweep:ia:theme:due-soon-upcoming` |
| 10 | supervisor/experienced | Find what maintenance is due or overdue | **Ambiguity of source** | High | Jakob + Nielsen #4 | 3 pages in this supervisor's nav answer the same job (dayplanner, pm-scheduler, project-manager). the overdue count is derived two ways (per-asset v_pm_compliance_truth vs per-scope-item v_pm_scope_items_truth) → the surfaces CAN disagree. | `sweep:ia:theme:late-overdue`, `sweep:ia:theme:due-soon-upcoming` |
| 11 | supervisor/experienced | Find the highest-risk asset right now | **Ambiguity of source** | High | Jakob + Nielsen #4 | 2 pages in this supervisor's nav answer the same job (alert-hub, asset-hub). risk is shown as alerts (alert-hub), critical assets (asset-hub), and the risk ranking (predictive) — three lenses, one underlying question. | `sweep:ia:theme:risk-hot-critical` |
| 12 | supervisor/experienced | See what is waiting for my approval | **Relabel collision** | Med | Nielsen #2 (real world) | "Pending approval" appears on asset-hub, inventory meaning different subjects (assets vs parts) under one label. | `sweep:ia:relabel:pending-approval` |
| 13 | engineer/experienced | Find the highest-risk asset right now | **Canonical unreachable** | Med | Nielsen #6 (recognition) | The source of truth (predictive) is hidden from primary nav → this engineer lands on a secondary surface and takes it as authoritative. | `sweep:ia:theme:risk-hot-critical` |
| 14 | supervisor/experienced | Find the highest-risk asset right now | **Canonical unreachable** | Med | Nielsen #6 (recognition) | The source of truth (predictive) is hidden from primary nav → this supervisor lands on a secondary surface and takes it as authoritative. | `sweep:ia:theme:risk-hot-critical` |
| 15 | supervisor/experienced | See what is waiting for my approval | **Ambiguity (weak / cross-subject)** | Low | Jakob | 2 pages in this supervisor's nav answer the same job (asset-hub, inventory). BUT these surface different subjects (assets, parts) → likely distinct jobs sharing a word, not one drifting number. | `sweep:ia:relabel:pending-approval` |
| 16 | supervisor/experienced | Check the team's skills / readiness | **Ambiguity (weak / cross-subject)** | Low | Jakob | 2 pages in this supervisor's nav answer the same job (pm-scheduler, skillmatrix). BUT these surface different subjects (PM tasks, skills) → likely distinct jobs sharing a word, not one drifting number. | `sweep:ia:theme:healthy-on-track` |

### Positive control (came back CLEAR — proves the rubric isn't crying wolf)

- **Check which parts are low or out of stock** (field novice): single source `inventory`, reachable — no ambiguity.
- **Check which parts are low or out of stock** (supervisor novice): single source `inventory`, reachable — no ambiguity.
- **Check the team's skills / readiness** (supervisor novice): single source `skillmatrix`, reachable — no ambiguity.

## How this re-prioritizes Phase 2

These Phase-2 candidates sit on a **CONFUSING novice path** → treat as the highest-priority dispositions (not just Minor TASTE):

- `sweep:ia:relabel:pending-approval`
- `sweep:ia:theme:due-soon-upcoming`
- `sweep:ia:theme:late-overdue`
- `sweep:ia:theme:risk-hot-critical`

---
### Phase 3 — the heavier LIVE tier (optional)
This deterministic pass says WHERE a new user gets confused. To CONFIRM it with a real agent: drive each CONFUSING row live in Playwright MCP as the persona — sign in, set the role mode, attempt the job, and have the model report (a) could it find the answer, (b) did two surfaces show different numbers, (c) did it trust the wrong one. Feed disagreements back as evidence on the cited `sweep:ia:*` candidate. The seam already exists: `__UFAI.inventory()` (Layer A) dumps the per-page units the agent reads. **Still SURFACE-only — the human disposes.**
