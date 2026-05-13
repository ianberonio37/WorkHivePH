# WorkHive — The Operational Readiness Roadmap

Version: 2026-05-13. Author: Ian Beronio (with Claude Code).
Supersedes the prior "free industrial intelligence platform" positioning. Captures the maturity-stacking strategy that reframes WorkHive as the **Operational Readiness Layer** for Filipino industrial plants, not another CMMS.

This document is the strategic spine the validator catalog, the roadmap phases, and the product UX align to. Update in place; do not branch.

---

## 0. The reframe in one paragraph

The CMMS / ERP literature is unambiguous: technology becomes the answer to problems that aren't technological. Globally, $97M of every $1B in technology spend ties to failed digital transformations, and SMEs are the most vulnerable. The maintenance-maturity literature (DREAMY, Elecosoft 2026) has converged on the same conclusion: in 2026, maturity is judged by how reliably maintenance activity translates into business outcomes, not by how much software has been deployed. WorkHive cannot win by being a better CMMS. It wins by being the **Operational Readiness Layer** that makes any digital tool — including itself — actually work in a Filipino plant. That is a different category, a different sales motion, a different roadmap.

The old roadmap was a feature-stacking plan. This revised roadmap is a **maturity-stacking** plan.

---

## 1. What the research and the skills converge on

| Signal | Source | What it says |
|---|---|---|
| Maintenance maturity 2026 is outcome-judged | Elecosoft, DREAMY framework | "Asset data is trusted and actively used in decision-making; technicians follow consistent digital workflows; compliance evidence generated as part of everyday work." |
| Top 3 ERP success factors | Multiple academic + practitioner sources | Top management support, strategic focus, employee training. **Software is not in the top 3.** |
| Culture eats process | Athens Journal, Culture Partners | Existing culture is "pivotal" to readiness. Cultures that value adaptability and learning succeed; rigid ones fail. |
| Readiness assessment is a precondition | Prosci, NetSuite | A readiness assessment must happen **before** deployment. WorkHive can build this *into* the product. |
| Brownfield reality | Hilscher, ZedIoT | "Most brownfield plants use a mix of protocols" — flexibility is required, not optional. |
| Maintenance-expert skill (Filipino context) | Internal | PSME / PEC / ASHRAE-tropical / typhoon-season patterns. Local realities are non-trivial. |
| Designer Home Stack pattern | Internal | "Today's One Thing → Stack → Tools drawer." Overwhelm = failure. Maturity-aware UI extends this. |
| Community gamification rule | Internal | "Reward real work, not gaming." Apply same rule to maturity tracking. |

**The convergence:** WorkHive's edge is not the AI, the validators, or the gateway. The edge is that the framework discipline can be turned outward — productised as **maturity-aware adoption tooling** that imported CMMS will not build because they're optimised for plants where these problems are smaller.

---

## 2. What WorkHive is NOT (the doctrine)

The platform's marketing, sales narrative, AI assistant, and product UX must defend these. The doctrine is hard-coded into `assistant.html` and `floating-ai.js`.

1. **WorkHive will not replace your ERP/CMMS.** It is the field-worker interface that makes the ERP/CMMS actually used. We integrate; we don't displace.
2. **WorkHive will not promise predictive analytics on 30 days of data.** We surface the gap, not the dream. If a hive has insufficient history, the predictive tile says so honestly.
3. **WorkHive will not enforce rigid workflows.** Every state machine is opt-in. Every approval is configurable. The Filipino reality is flexible; the product must be too.
4. **WorkHive will not require enterprise infrastructure.** Brownouts, 2G, shared devices, intermittent power are first-class operating conditions, not edge cases.
5. **WorkHive will not bill on seats.** Free at the worker tier forever. Paid tier triggers on capability (AI, integrations, compliance), not headcount.
6. **WorkHive will not deploy without a Readiness Score.** Every new hive sees its starting score within 30 minutes of signup. We don't pretend.

---

## 3. What WorkHive IS (the positioning)

> **WorkHive is the Operational Readiness Layer for Filipino industrial plants.**
> We don't replace your ERP, CMMS, or SCADA. We make them work.
> We start with paper-and-spreadsheet chaos and build forward in five maturity stairs.
> Every stair is measurable. Every stair has tools. Every stair is honest about the gap.

The 133+ validators are no longer just internal quality gates — they become the **empirical backbone** of the maturity score the hive sees.

---

## 4. The Maturity Stack

A 5-stair model that doubles as the product's strategic spine and the hive's user-visible progress ladder. Every stair has a defined **entry signal**, **exit signal**, **tools enabled**, and **honest limit**.

| Stair | Entry signal | Exit signal | Tools enabled | Honest limit |
|---|---|---|---|---|
| **0 — Paper** | Hive joined | 10 assets registered, 1 SOP documented | Hive board, Asset Hub (browse only), Voice Journal, AI Assistant | Predictive analytics suppressed; AMC suppressed; cross-hive benchmarks suppressed |
| **1 — Digital Logbook** | Stair 0 exit | 5 active workers writing entries 5+ days/week; PM templates registered for top 5 assets | Logbook, PM Scheduler, Inventory, Visual Defect Capture, Skill Matrix, Day Planner | Predictive analytics suppressed; cross-hive benchmarks suppressed |
| **2 — Disciplined** | Stair 1 exit | PM compliance ≥70% for 30 days; logbook hygiene ≥80%; supervisor approving ≥5 actions/week | AMC daily brief, Reliability Workbench (FMEA + RCM), AI Quality Dashboard, Alert Hub, Community, Report Sender | Sensor-based prediction suppressed; insurance bridge suppressed |
| **3 — Predictive-Ready** | Stair 2 exit | 90+ days logbook history OR live `sensor_readings` for 30+ days; Z-score anomaly engine active | Predictive Analytics, Anomaly Engine 2.0, Live Telemetry, parts-staging-recommender, Phase 5b composite risk, PH Intelligence, Audit Log | Multi-hive enterprise dashboards suppressed |
| **4 — Industry Leader** | Stair 3 exit | All four of: sensor pipeline live, RCM strategy on 10+ assets, audit trail compliant, federated PH-Intelligence opted-in | Hive Risk Score → Insurance Bridge, Synthetic Twins, GraphRAG agent, Standards Auto-Update, Federated benchmark export, Engineering Design Calculator, Project Manager, CMMS Integrations, Marketplace | — (top of stack) |

**The gating is epistemic, not technical.** We're not saying "you can't use predictive analytics until you pay." We're saying "predictive analytics on 30 days of data lies to you, and we won't lie to you." That honesty is the moat.

---

## 5. Five strategic principles

### Principle 1 — DISCIPLINE before AUTOMATION
Don't automate chaos. Every new automation surface ships paired with a "discipline gate": the surface unlocks only when the prerequisite signals are green. AMC unlocks at Stair 2, not Stair 0. Anomaly Engine 2.0 unlocks at Stair 3.

### Principle 2 — READINESS before RICHNESS
Don't add a feature until existing ones are adopted. The Hive Readiness Score becomes a first-class metric. New builds must justify themselves against adoption, not just functionality. A page with 0 daily-active users gets sunset, not extended.

### Principle 3 — RESILIENCE first, then richness
The Filipino industrial reality is the design target, not an accommodation. Every page must pass a "Manila brownfield" test: throttled to 200kbps with 3 random network drops in 5 minutes.

### Principle 4 — LEADERSHIP signal must be visible
The supervisor is the linchpin. The platform surfaces supervisor engagement as a metric the supervisor themselves can see. Without this, supervisors fade out and adoption collapses.

### Principle 5 — CULTURE flexibility is a product feature
Workflow rigidity is a failure mode. Every state machine is opt-in. Every approval threshold is configurable per hive. Every required field has a "log anyway" path with a flag. The product bends to the plant; the plant doesn't bend to the product.

---

## 6. The six-phase roadmap

### Phase 0 — The Reframe (1-2 weeks, ~3 sessions)

**Goal:** Embed the maturity stack and honesty layer into the product before anything else ships.

| # | Build | Sessions | Why now |
|---|---|---|---|
| 0.1 | Hive Readiness Score (HRS) + `hive_readiness` table + Python compute handler + RPC | 2 | The empirical foundation of the entire reframe |
| 0.2 | Maturity Stairway UI on `hive.html` | 1 | Visible to every hive member. Shows current stair, exit criteria, blocked tools |
| 0.3 | Honest empty-state rewrites (predictive, analytics, ph-intelligence) | 0.5 | When below threshold, show the gap, not a chart of garbage |
| 0.4 | "What WorkHive isn't" doctrine in assistant + floating-ai + landing page | 0.2 | The platform must say no to things it can't do |
| 0.5 | `validate_maturity_gating.py` | 0.5 | Every advanced tool surface must check the hive's stair before rendering |

**Exit criterion:** Every hive sees a Readiness Score within 30 minutes of signup. Validator green.

### Phase 1 — Defensive Closure (2-4 weeks, ~6 sessions)

Same as the prior roadmap's Phase 1. The 9 items are unchanged because they were correct on their own terms — they just become preconditions for the readiness story rather than the story itself.

1. Lock down knowledge-base RLS (fault_knowledge, skill_knowledge, pm_knowledge)
2. Audit-log completion (hive.html member_joined + performLeave)
3. Asset lifecycle field + state machine
4. Asset FK on knowledge tables
5. External fetch timeout wrapper
6. AI cost log retrofit (amc-orchestrator, voice-journal-agent, visual-defect-capture)
7. Voice-journal PII redaction through shared redactor
8. Context-window auto-compressor
9. 5 missing validators (`validate_amc`, `validate_visual_defect`, `validate_sensor_pipeline`, `validate_achievements`, `validate_dayplanner`)

**Plus** one addition triggered by the reframe: `validate_resilience.py` — checks every page for offline queue, error-state UI, network-loss fallback, and shared-device safety.

### Phase 2 — Resilience Hardening (4-6 weeks, ~8 sessions)

**Goal:** Make the platform actually survive a Filipino industrial plant.

| # | Build | Sessions |
|---|---|---|
| 2.1 | Offline-first parity audit (extend IndexedDB queue to inventory, PM, photo-defect drafts, asset edits, FMEA inserts) | 2 |
| 2.2 | Bandwidth-aware mode (detect 2G/3G, degrade gracefully) | 1 |
| 2.3 | Brownout-safe state (auto-persist every 5s, recover without prompts) | 1 |
| 2.4 | Shared device pattern (quick-switch profile pill, session timeout) | 1 |
| 2.5 | Connectivity weather report (visible network strength + queue size) | 0.5 |
| 2.6 | `validate_resilience.py` expansion (Manila brownfield test: 200kbps + 3 drops) | 0.5 |
| 2.7 | Cybersecurity baseline for SME PH context (2FA, anomalous-login, supervisor card) | 2 |

**Exit criterion:** Platform passes deliberate-sabotage test — pulled cable, dropped Wi-Fi, mid-form power-off, mid-photo crash, fresh-device login — and data integrity holds.

### Phase 3 — Adoption Observability + Change Management (4-6 weeks, ~7 sessions)

**Goal:** Build the change-management layer into the product. What enterprises pay outside consultants $50K-$200K to do, we make a free in-product capability.

| # | Build | Sessions |
|---|---|---|
| 3.1 | Adoption Risk Score per hive (companion to asset risk score) | 2 |
| 3.2 | Supervisor Engagement Card (direct feedback loop on approvals + dropped readiness) | 1 |
| 3.3 | In-product onboarding paths per role (5-step worker, 7-step supervisor) | 2 |
| 3.4 | Champion Program tracker (one worker per hive as power user) | 1 |
| 3.5 | "Why are you here?" intent capture at hive signup | 0.5 |
| 3.6 | `validate_adoption_observability.py` | 0.5 |

**Exit criterion:** A new hive signs up, sees Readiness Score within 30 min, hits Stair 1 within 14 days, supervisor receives weekly engagement card. This loop is what no imported CMMS will build.

### Phase 4 — Revenue Surfaces (6-10 weeks, ~10 sessions)

The three builds from the prior roadmap survive, but each gets **maturity-gated** so it only enables when the hive is ready.

| Build | Maturity gate | Notes |
|---|---|---|
| AI Quality + ROI Dashboard | Stair 2+ | Honest ROI: "Predicted savings at your maturity (Stair 3) carry 78% confidence. Historical accuracy: 82%." |
| Anomaly Engine 2.0 | Stair 3+ | 5-source fusion (logbook clusters, sensor Z-score, PM drift, parts-spend spikes, failure-signature matches) |
| Knowledge Pipeline Health Tile | Stair 2+ | RAG freshness KPI |

**Honesty as a sales asset, not a liability.**

### Phase 5 — Enterprise Unlock (3-6 months, ~20 sessions across parallel tracks)

Same as the prior roadmap's Phase 3.

- **Track A — Compliance certification:** PDPA full compliance, soft-delete + 30-day hard delete, data export, vendor DPA review, SOC 2 Type II readiness (8-12 month audit window), ISO 27001 readiness (parallel for 20-30% bundle savings)
- **Track B — Enterprise auth:** Complete Supabase Auth migration Phase F, SSO/SAML readiness, MFA for supervisor + manager roles, session audit
- **Track C — Plant Connections Console:** Unified supervisor view of CMMS sync + broker config + topic mappings + gateway audit

**One addition triggered by the reframe:** `hive_readiness_audit` log — every score change persisted and queryable. Auditors love this. Insurance partners love this. Banks love this.

### Phase 6 — Industry-Defining (6-24 months)

Same as the prior roadmap's Phase 4.

| # | Build | Sessions |
|---|---|---|
| 6A | Per-hive Industrial Knowledge Graph (Digital Twin tier) | 6-10 |
| 6B | Synthetic Training Twin Generator (solve cold-start) | 4 |
| 6C | Hive Risk Score → Insurance Bridge (financial infrastructure play) | 6 |
| 6D | Federated PH Industry Benchmarks (national data product) | 4 |
| 6E | Drone Inspection Pipeline | 4-6 |
| 6F | Standards Auto-Update Agent | 3 |
| 6G | Spec-to-Drawing Generator (productise as SKU) | 3-4 |
| 6H | Edge AI on phones (deferred until B1 has 30+ days of data) | 6-8 + research |

**One addition triggered by the reframe:** **Maturity-as-a-Service consulting wedge.** Once the Readiness Score is proven and refined across 50+ hives, productise the methodology as a paid consulting offering ("we'll get you to Stair 3 in 90 days"). The asymmetric play the failure-mode passage hints at — "transformation requires preparation" — and you can be the brand that owns that preparation in PH industrial.

---

## 7. What was killed from the prior roadmap

| Killed / deferred | Why |
|---|---|
| Default-on AMC for every hive at signup | Re-gate to Stair 2. Stair 0 hives get a "log 10 things first" empty state |
| Anomaly Engine 2.0 as a Phase 2 build | Pushed to Phase 4 / Stair 3 gating. It would lie at lower maturity |
| Generic ML / predictive at Stair 0 | Suppressed at Stair 0-1 entirely. Replaced with "what to do next to unlock prediction" |
| Per-asset risk score as primary alert source | Stays, but de-emphasised at low maturity |
| "Free industrial intelligence platform" tagline | Replaced with "Operational Readiness Layer for PH industrial plants" |
| Marketplace as near-term priority | Stays gated behind DTI registration AND demoted relative to readiness/resilience work |
| Stage Popout tools Architecture + Symbol Gallery | Removed; both retired as admin-only archival pages (2026-05-13) |

---

## 8. Resourcing reality check

| Phase | Sessions | Calendar |
|---|---|---|
| Phase 0 — The Reframe | ~3 | 1-2 weeks |
| Phase 1 — Defensive Closure | ~6 | 2-4 weeks |
| Phase 2 — Resilience Hardening | ~8 | 4-6 weeks |
| Phase 3 — Adoption Observability + Change Management | ~7 | 4-6 weeks |
| Phase 4 — Revenue Surfaces | ~10 | 6-10 weeks |
| Phase 5 — Enterprise Unlock | ~20 across tracks | 3-6 months |
| Phase 6 — Industry-Defining | ~40+ | 6-24 months |

**To "honest about its gaps" maturity-aware product:** ~3 sessions / ~2 weeks.
**To enterprise-ready state:** ~24 sessions / ~3-5 months focused work.
**To industry-defining position:** ~80+ sessions / ~12-18 months at current cadence.

The capital intensity is low — you've already built the hard parts (gateways, canonical views, multi-agent scaffolding, validator framework). The remaining work is **wiring + dashboards + audit artefacts + compliance docs + epistemic honesty**, not architectural lift.

---

## 9. The single biggest strategic shift

The prior roadmap aimed at *"better CMMS / more features."* This revised roadmap aims at *"the only platform that's honest about what it can and can't do, and makes operational readiness measurable."*

The validator catalogue gives you the receipts. The maturity stack gives you the narrative. The Filipino industrial reality gives you the moat that imported platforms cannot copy. **The reframe is not a feature addition — it's a category move.**

Imported ERPs solve for the C-suite. WorkHive solves for the plant floor. Imported CMMS sell speed. WorkHive sells truth about your own plant. That's a defensible position.

---

## Status

| Phase | Status | Shipped | Notes |
|---|---|---|---|
| Phase 0 | **Closed (scaffolded)** | 2026-05-13 `70314ba` | Doctrine + HRS schema + Maturity Stairway. 138 PASS |
| Phase 1 | **Closed** | 2026-05-13 `e899baa` | Knowledge-base RLS + lifecycle + audit log + fetchWithTimeout + cost log + PII + compressor + 6 validators. 144 PASS |
| Phase 2 | **Closed** | 2026-05-13 `2324f07` | 5 resilience helpers (offline-queue + connectivity + autosave + session-timeout + device-fingerprint) + validate_resilience grew 4→7 layers. 144 PASS |
| Phase 3 | **Closed** | 2026-05-13 `679d921` | Adoption risk score + supervisor engagement card + onboarding stepper + intent capture + validate_adoption_observability. 145 PASS |
| Phase 4 | **Closed (maturity-gated)** | 2026-05-13 `20e8d61` | ai-quality.html (Stair 2+) + Anomaly Engine 2.0 on alert-hub (Stair 3+) + Knowledge Pipeline tile (Stair 2+) + validate_revenue_surfaces. 147 PASS |
| Phase 5 | **Closed (scaffolding)** | 2026-05-13 `b738240` | hive_retention + soft-delete cron + PDPA export + auth_session_events + MFA scaffold + SSO scaffold + Plant Connections Console + validate_enterprise_unlock. 148 PASS. Audits + DPAs + MFA UI + SSO IdP intentionally out-of-scope |
| Phase 6 | **Closed (scaffolding)** | 2026-05-13 *(this batch)* | knowledge_graph_facts + drone_inspections + industry_standards seed + federated opt-in + v_insurance_bridge_truth + consulting_engagements + validate_industry_defining. ML pipelines + drone hardware + insurer integrations + edge AI runtime intentionally out-of-scope |

---

## Source references

- [What Maintenance Maturity Means in 2026 — Elecosoft](https://elecosoft.com/news/maintenance-maturity-2026/)
- [DREAMY framework — Taylor & Francis](https://www.tandfonline.com/doi/full/10.1080/00207543.2025.2455476)
- [ERP Implementation Failure Statistics: 2025 Research — Godlan](https://godlan.com/erp-implementation-failure-statistics/)
- [The Importance of Culture in ERP Adoption — Athens Journal](https://www.athensjournals.gr/business/2018-4-3-2-Skoumpopoulou.pdf)
- [How to Use a Readiness Assessment For Change Management — Prosci](https://www.prosci.com/blog/when-should-you-use-a-change-management-readiness-assessment)
- [Future of Maintenance 2026 — Oxmaint](https://oxmaint.com/article/future-maintenance-trends-2026-ai-cmms)
- [Philippines PDPA — OneTrust](https://www.onetrust.com/blog/philippines-pdpa-compliance-made-simple-what-privacy-teams-need-to-know/)
- [How Much Does SOC 2 Cost in 2026 — SecureLeap](https://www.secureleap.tech/blog/soc-2-certification-cost)
- [Supervisor Agent Architecture — Databricks](https://www.databricks.com/blog/multi-agent-supervisor-architecture-orchestrating-enterprise-ai-scale)
- [OPC UA FX 2026 — ZedIoT](https://zediot.com/blog/opc-ua-fx-industrial-interoperability/)

---

*This roadmap is the strategic spine for WorkHive 2026 onward. The validators, the canonical sources, the maturity stack, and the doctrine are mutually reinforcing. Change one, you must change the others.*
