# WorkHive Platform Glossary

A new supervisor's reference. Every term below shows up somewhere in the UI; if you ever see a badge, button, or score and wonder *what does that mean*, this doc is the canonical answer.

The full machine-readable version lives in the `canonical_sources` table — `wh-help.js` reads from it to power the inline `data-help="..."` tooltips on hover. This Markdown copy is for offline reference, new-hire onboarding, and the assistant's PLATFORM TOOLS context.

---

## Maturity Stack

WorkHive groups every hive into one of five maturity stairs. Higher stairs unlock more tools because the data supports them. We never run predictive analytics on a hive that hasn't earned them — that would lie.

| Stair | Name | Entry signal | Tools that unlock |
|---|---|---|---|
| **0** | Paper | Just signed up | Hive board, Asset Hub (browse), Voice Journal, AI Assistant |
| **1** | Digital Logbook | 10 assets registered, 1 SOP documented | Logbook, PM Scheduler, Inventory, Visual Defect Capture, Skill Matrix, Day Planner |
| **2** | Disciplined | 5 active workers writing, top-5 PM templates registered | AMC daily brief, Reliability Workbench, **AI Quality + ROI**, Alert Hub, Community, Report Sender, **Knowledge Pipeline tile** |
| **3** | Predictive-Ready | PM compliance ≥70%, logbook hygiene ≥80%, 5 supervisor actions/week, 90+ days history OR live sensors | Predictive Analytics, **Anomaly Engine 2.0**, Live Telemetry, parts-staging-recommender, PH Intelligence, Audit Log |
| **4** | Industry Leader | Sensor pipeline live + 10+ RCM strategies + audit compliant + federated benchmarks opted-in | Hive Risk → Insurance Bridge, Synthetic Twins, GraphRAG agent, Standards Auto-Update, Federated benchmarks |

The Maturity Stairway card on `hive.html` is always visible. Tap **Why?** to see the evidence behind the score.

---

## Hive Readiness Score (HRS)

The composite 0..100 score on the Maturity Stairway card. Computed daily across **5 dimensions** from canonical sources:

| Dimension | Weight | What raises it |
|---|---|---|
| Process maturity | 25% | Asset registry depth, PM templates, SOPs documented, FMEA modes approved |
| Data quality | 20% | Logbook hygiene (problem + root cause + action filled), PM compliance, write rate |
| Infrastructure resilience | 15% | Sensor pipeline live, offline-queue use, voice journal participation |
| Leadership engagement | 25% | Supervisor approvals/week, audit log activity, role coverage |
| Cultural adoption | 15% | Active-worker ratio, daily-use rate |

Stair derivation is **epistemic, not technical**. We don't say "you can't use predictive analytics until you pay." We say "predictive analytics on 30 days of data lies — and we won't lie."

---

## Adoption Risk Score

The Supervisor Engagement Card on `hive.html` (supervisor-only). 0..100, **higher = more risk**. Inverse of HRS.

| Tier | Score | Meaning |
|---|---|---|
| 🟢 Healthy | < 35 | Workers active, supervisor engaged, hive moving |
| 🟠 At Risk | 35–64 | One or two signals slipping. Tap **Why?** to see which. |
| 🔴 Critical | ≥ 65 | Multiple signals show momentum loss. Act this week. |

Five risk components: active worker ratio, week-over-week momentum, supervisor decay, stair-stall, new-member silence.

---

## Anomaly Engine 2.0 (alert-hub.html)

Stair 3+ only. Fuses 5 sources daily into a composite anomaly score per machine:

| Source | Weight | Fires when |
|---|---|---|
| Logbook cluster | 30% | 3+ logbook entries for the same machine within 14 days |
| Sensor z-score | 25% | Sensor readings drift >2.5σ in last 7 days |
| PM drift | 20% | PM is overdue past category default |
| Parts spend | 15% | Inventory transactions spike for an asset (stubbed pending schema FK) |
| Failure signature | 10% | An active failure_signature_alerts row exists |

### Severity bands
| Badge | Composite | What to do |
|---|---|---|
| ℹ️ INFO | < 25 | Background noise. Watch. |
| 👁 WATCH | 25–49 | Worth a glance; not urgent. |
| ⚠️ WARNING | 50–74 | Plan corrective work this shift. |
| 🔴 CRITICAL | ≥ 75 | Stage parts, brief crew, intervene before next shift. |

### Lifecycle (supervisor actions)
| Status | Meaning |
|---|---|
| `active` | The fuser raised this and no one has touched it |
| `acknowledged` | A supervisor saw it and is on it. Coordination signal, not a fix. |
| `resolved` | Supervisor closed it. Fix shipped, or false positive. |
| `expired` | Auto-aged out (planned cron). |

Acknowledge and Resolve both write to `hive_audit_log` so compliance + the insurance-bridge view can read the trail.

---

## AMC Daily Brief

Generated once per hive per shift_date at **06:00 PHT**. Five sub-agents run via `Promise.allSettled`:
1. Failure-Predictor — top-3 highest-risk assets from `v_risk_truth`
2. PM-Planner — top-5 PMs due, criticality-ranked
3. Parts-Stager — pending parts staging recommendations
4. Crew-Builder — per-asset worker match from `v_worker_skill_truth`
5. Briefing-Composer — narrative paragraph via `callAI`

The supervisor reviews on `alert-hub.html` and clicks **Approve** or **Reject**. Both decisions write to `hive_audit_log`.

---

## Audit Log Actions

Every supervisor power action lands in `hive_audit_log`. The viewer (`audit-log.html`) renders each action with its own icon + label, defined in `hive.html`'s `ACTION_ICON` map. The new validator `validate_audit_trail_coverage.py` enforces both: every lifecycle update writes to the audit log, and every action name has a rendering entry.

| Action | Icon | What happened |
|---|---|---|
| `member_joined` | + | Worker joined the hive |
| `member_left` | ↩ | Worker left the hive |
| `kick_member` | ⊘ | Supervisor removed a worker |
| `new_device` | ⚠ | Worker signed in from a new device fingerprint |
| `approve_item` / `reject_item` | ✓ / ✗ | Pending asset or inventory approved/rejected |
| `register_asset` / `edit_asset` / `delete_asset` | ＋ / ✎ / ⊘ | Asset registry changes |
| `anomaly_acknowledged` / `anomaly_resolved` | 👁 / ✓ | Anomaly Engine 2.0 lifecycle |
| `approve_amc_brief` / `reject_amc_brief` | ✓ / ✗ | AMC daily brief decision |
| `complete_pm` | ✓ | PM task completed |
| `export_hive_data` | ⤓ | PDPA right-to-access export (Phase 5) |
| `open_dispute` / `resolve_dispute_order` | ⚠ / ✓ | Marketplace dispute lifecycle |
| `submit_review` | ★ | Marketplace review submitted |

---

## Doctrine — what WorkHive is NOT

These are hard-coded into `assistant.html` and `floating-ai.js` and surfaced on the landing page. Bind everything you build to them.

1. **We do not replace your ERP/CMMS.** WorkHive is the field-worker interface that makes the ERP/CMMS actually used.
2. **We do not promise predictive analytics on 30 days of data.** We surface the gap honestly.
3. **We do not enforce rigid workflows.** Every state machine is opt-in. Every approval threshold is configurable.
4. **We do not require enterprise infrastructure.** Brownouts, 2G, shared tablets are first-class operating conditions.
5. **We do not bill on seats.** Free at the worker tier forever. Paid tier triggers on capability (AI, integrations, compliance), not headcount.
6. **We do not deploy without a Readiness Score.** Every new hive sees its starting HRS within 30 minutes of signup.

---

## Where the truth lives

If this glossary contradicts the database, the database wins. The canonical sources are:

- `canonical_sources` table — every domain has a row with `description`. The source of truth for tooltips.
- `STRATEGIC_ROADMAP.md` — the strategic spine. Phase 0 (Reframe) through Phase 6 (Industry-Defining).
- `validate_*.py` — 150+ architectural gates that enforce the doctrine in code.

Last refresh: 2026-05-13.
