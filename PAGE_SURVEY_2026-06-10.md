# WorkHive — Full Page Survey (2026-06-10)
_Inventory of all 40 app pages: what each shows, what data it reads, how heavy it is to load,
and where it overlaps with others. This is the map that drives the detailed roadmap._

**Compute weight legend:**
- 🟢 **Light** — reads a view/table directly; cheap; fine as-is.
- 🟡 **Snapshot** — reads a pre-computed daily result (already cached).
- 🔴 **Heavy** — recomputes on every load (calls an AI/Python engine). Candidate for "compute-on-view + cache + Refresh".

**Verified legend:** ✅ live-walked this session · ⬜ survey-from-code (walk pending in Phase 6).

---

## Group A — Core operational (daily work)
| Page | Purpose | Reads | Weight | Verified | Overlap / notes |
|---|---|---|---|---|---|
| `index.html` | Marketing landing + signed-in 4-tile glance | `get_hive_dashboard` RPC | 🟢 | ✅ | 4 tiles duplicate the hive board headline |
| `hive.html` | **Hive Live Board — THE dashboard** | `get_hive_board_dashboard`, readiness, adoption, AMC, pattern, benchmarks, `ai-orchestrator` | 🟡+🟢 | ✅ | The hub; everything else is a slice of this |
| `logbook.html` | Digital repair logbook | `v_logbook_truth`; edge: voice/visual/OCR/cmms-push | 🟢 | ✅ | worker-scoped pills (by design) |
| `inventory.html` | Spare-parts monitor | `inventory_items` + `inventory_transactions` | 🟢 | ✅ | low-stock dup on alert-hub + hive |
| `pm-scheduler.html` | PM tracking + compliance | `pm_assets/scope/completions` + `get_pm_compliance_smrp` | 🟢 | ✅ | compliance now canonical (fixed) |
| `dayplanner.html` | DILO day planner | `schedule_items` + `v_logbook_truth` | 🟢 | ✅ | "today's jobs" overlaps hive + shift-brain |
| `asset-hub.html` | Per-asset 360 (risk/history/reliability) | `v_asset+risk+logbook+fmea+weibull`; edge: fmea/weibull/pf/brain | 🟡+🔴* | ✅ | *edge calcs on-demand per asset; risk = per-asset view of v_risk_truth |
| `shift-brain.html` | Shift plan + handover | `shift_plans + v_risk_truth + pm_scope_items`; edge: `shift-planner-orchestrator` | 🔴 | ✅ | "what's happening" overlaps hive + dayplanner; **Phase 2 target** |

## Group B — Intelligence / analytics (the "smart" pages → reconcile to one engine)
| Page | Purpose | Reads | Weight | Verified | Overlap / notes |
|---|---|---|---|---|---|
| `analytics.html` | 4-phase analytics engine | **fetch `analytics-orchestrator`** (live) + batch-risk | 🔴 | ✅ | **recomputes every load — Phase 1 target** |
| `predictive.html` | Risk ranking table | `v_risk_truth`; edge: batch-risk + analytics-orchestrator | 🟡 | ✅ | **half-retired — "centralized in Asset Hub"; Phase 4 retire** |
| `alert-hub.html` | Unified alert feed | `v_risk_truth` + `compute_anomaly_signals`; composes risk+PM+stock+pattern | 🟢 | ✅ | composes same signals as hive board → **R1 one composer** |
| `ai-quality.html` | AI answer quality | `ai_cost_log` | 🟢 | ⬜ | overlaps llm-observability |
| `llm-observability.html` | LLM cost/latency | cost logs | 🟢 | ⬜ | overlaps ai-quality + agentic-rag-obs |
| `agentic-rag-observability.html` | RAG pipeline metrics | RAG logs | 🟢 | ⬜ | 3rd "AI observability" page — consolidation candidate |
| `ph-intelligence.html` | PH industry benchmarks | edge: `intelligence-report` | 🔴 | ⬜ | heavy report; cache+refresh candidate |
| `analytics-report.html` | Analytics PDF/report view | (report) | 🟡 | ⬜ | overlaps analytics + report-sender |

## Group C — Growth / people
| Page | Purpose | Reads | Weight | Verified | Overlap / notes |
|---|---|---|---|---|---|
| `skillmatrix.html` | Skill matrix | `skill_profiles + skill_badges` | 🟢 | ⬜ | feeds resume |
| `resume.html` | Resume builder | pulls Skill Matrix / Logbook / typed | 🟢 | ✅ (earlier) | dedupe across sources |
| `achievements.html` | XP / gamification | `worker_achievements + achievement_xp_log` | 🟢 | ✅ | — |
| `community.html` | Forum | `community_posts + replies + reactions` | 🟢 | ✅ (earlier) | public-feed overlaps |
| `public-feed.html` | Public activity feed | community feed | 🟢 | ⬜ | overlaps community |
| `voice-journal.html` | Voice journal companion | edge: `ai-gateway` | 🔴 | ✅ | AI; per-entry compute |
| `assistant.html` | AI assistant chat | edge: `ai-gateway` | 🔴 | ✅ (earlier) | floating companion appears platform-wide too |

## Group D — Marketplace
| Page | Purpose | Reads | Weight | Verified | Overlap / notes |
|---|---|---|---|---|---|
| `marketplace.html` | Listings | `marketplace_listings + v_marketplace_sellers_truth` | 🟢 | ✅ (earlier) | vestigial Stripe (free platform) |
| `marketplace-seller.html` | Seller dashboard | seller tables | 🟢 | ⬜ | — |
| `marketplace-seller-profile.html` | Seller profile | seller tables | 🟢 | ⬜ | — |
| `marketplace-admin.html` | Marketplace admin | admin tables | 🟢 | ⬜ | admin-only |

## Group E — Integrations / connections / reports
| Page | Purpose | Reads | Weight | Verified | Overlap / notes |
|---|---|---|---|---|---|
| `integrations.html` | CMMS/SAP connectors | `integration_configs + external_sync`; edge: `cmms-sync` | 🟢 | ⬜ | overlaps plant-connections |
| `plant-connections.html` | Plant data connections + retention | `integration_configs`, `hive_retention_config` | 🟢 | ⬜ | overlaps integrations |
| `report-sender.html` | Send AI reports to contacts | `v_ai_reports_truth + report_contacts` | 🟢 | ⬜ | overlaps analytics-report |

## Group F — Projects / engineering
| Page | Purpose | Reads | Weight | Verified | Overlap / notes |
|---|---|---|---|---|---|
| `project-manager.html` | Maintenance project planner | `projects + project_items`; edge: project-orchestrator/progress/embed | 🔴 | ⬜ | heavy orchestrator |
| `project-report.html` | Project report/handover | edge: `project-orchestrator` | 🔴 | ⬜ | overlaps project-manager |
| `engineering-design.html` | Engineering calcs + BOM/SOW | edge: `engineering-calc-agent`, `engineering-bom-sow` | 🔴 | ✅ (earlier) | per-calc compute |

## Group G — Admin / dev / meta (not end-user-facing)
| Page | Purpose | Reads | Weight | Verified | Overlap / notes |
|---|---|---|---|---|---|
| `founder-console.html` | Platform owner console | platform_health, analytics_events, readiness, orders, ai_cost, audit | 🟡 | ✅ | owner-only; localhost bypass |
| `platform-health.html` | Platform health board | `platform_health.json` | 🟢 | ⬜ | overlaps founder-console |
| `audit-log.html` | Hive audit log | `hive_audit_log` | 🟢 | ⬜ | — |
| `architecture.html` | Architecture diagram | static | 🟢 | ⬜ | reference |
| `validator-catalog.html` | Gate validator catalog | validators | 🟢 | ⬜ | dev tool |
| `symbol-gallery.html` | P&ID symbol gallery | static | 🟢 | ⬜ | design reference |
| `parts-tracker.html` | (legacy) | — | — | — | **RETIRED — remove** |

---

## What the survey tells us (feeds the detailed roadmap)

**1. There is ONE dashboard (hive board) + satellites.** Home, alert-hub, predictive, shift-brain,
dayplanner all re-show slices of the hive board's signals. → consolidation + "read one engine."

**2. Only ~8 pages are actually 🔴 Heavy** (recompute on load): `analytics`, `shift-brain`,
`ph-intelligence`, `project-manager`, `project-report`, `engineering-design`, `voice-journal`,
`assistant`, plus asset-hub's per-asset edge calcs. **These are the only "compute-on-view + cache +
Refresh" candidates.** Everything else is 🟢 light direct-view reads that are already fine — no change
needed. (So Phase 1's scope is small and targeted, not "every page.")

**3. Three observability pages overlap** (`ai-quality`, `llm-observability`,
`agentic-rag-observability`) — merge into one "AI Health" page.

**4. Other redundancy clusters to debate:** integrations ↔ plant-connections · analytics-report ↔
report-sender · community ↔ public-feed · project-manager ↔ project-report · predictive (retire).

**5. ~14 pages still need the live deep-walk** (⬜ above) — the Phase 6 execution list, in priority:
shift-brain detail, ai-quality/llm-obs/rag-obs, ph-intelligence, project-manager/report,
integrations/plant-connections, marketplace-seller/admin, skillmatrix, public-feed, audit-log,
platform-health.

**6. Compute model is mixed today** — confirms the Phase 1 direction (make the 🔴 pages
compute-on-view + cache + Refresh; no pg_cron). The 🟡 snapshot pages (predictive, hive AMC/readiness)
already behave this way.

> Next: turn this into the **detailed roadmap** — each phase now scoped to the *specific* pages above,
> not vague "screens."

---

## Local data-state (walk grounding, 2026-06-10) — which pages have data to show
Checked the tables these pages read. **Empty locally** (page renders an empty/placeholder state):
| Table (rows) | Page(s) | Is it a bug? |
|---|---|---|
| `ai_cost_log` 0 · `ai_quality_log` 0 · `ai_audit_log` 0 · `ai_reply_feedback` 0 | ai-quality, llm-observability, agentic-rag-observability | **No AI usage is logged locally** — not a wrong-table bug; the seeder seeds no AI logs. These pages can't be walked/demoed until sample logs exist. → seed AI logs OR treat as prod-only. |
| `amc_briefings` 0 | hive board "AMC daily brief" | Shows "None today" gracefully. Under the no-cron model, AMC should **generate on first view** (Phase 3). |
| `shift_plans` 0 | shift-brain | No-plan state (where the prior stuck-loader bug lived). Phase 2 generates-on-view. |
| `integration_configs` 0 | integrations, plant-connections | Empty connectors view — by design until a CMMS is linked. |
| `ph_intelligence_reports` 0 | ph-intelligence | Generates on demand (heavy). |
| `hive_audit_log` 1 | audit-log | Sparse (1 row). |

**Have data:** community 49 · marketplace 27 · projects 12 · skill_profiles 15 · skill_badges 134.

**Implication for the roadmap:** (1) the AI-health trio (Phase 4 merge) also needs **seeded AI logs** to
be testable; (2) AMC + shift-handover empties confirm the **compute/generate-on-view** direction
(Phases 1–3); (3) integrations/ph-intelligence empties are by-design-until-used.

**NOTE:** live operate-it verification (clicks, render, stuck-loaders) for the ~14 ⬜ pages is **pending**
— the Playwright MCP browser is holding a stale handle this session (needs an MCP restart). The findings
above are from DB + code grounding (the method that caught this session's headline bug).
