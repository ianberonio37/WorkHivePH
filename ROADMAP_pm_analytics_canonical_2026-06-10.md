# WorkHive Roadmap — One source of truth, open-fast, one coherent web
_Crystallized 2026-06-10. Updated after the Phase-6 deep walk + 49-item drift triage + the "walk the web / consolidate as a critic" refinement. Plain language, scoped to specific pages (see `PAGE_SURVEY_2026-06-10.md`)._

## The big idea (one sentence)
Every number is **calculated once, in one place, shown the same everywhere**; heavy pages show a
**saved result + a Refresh button**; and the platform is **one coherent web of tools**, not 40 islands —
so we walk the connections, fuse what's redundant, and keep outward content grounded in the real pages.

## The compute rule — NO pg_cron (Ian, 2026-06-10)
- **A page a person opens** → first view of the day computes + **saves**; everyone else sees the saved
  copy; **Refresh** forces new. No scheduled jobs.
- **In-app alerts** compute on view. **Event-driven** reactions → DB webhook (instant, not a timer) if wanted.
  **Scheduled email/push** → deferred.

---

## WHERE WE ARE (2026-06-10)
- **Phase 0** ✅ committed-not-pushed (prior session): PM frequency math, PM compliance RPC, freq-map gate.
- **Phase 6a** ✅ this session: live-walked 14 un-walked pages → 7 fixes (PROJ-DRIFT ×5, agentic-rag verdict, skillmatrix badges, shift-brain risk threshold).
- **Phase 5** 🟡 this session: built + registered `validate_truth_view_consumer_columns.py` (the gate that catches PROJ-DRIFT-class drift).
- **DRIFT track** ✅ **DONE**: validator found the drift is **platform-wide (49 items)**; **all 49 fixed → backlog 0** (baseline auto-tightened). The final 15 (the "Pattern-E/FP" tail) resolved: marketplace `reviewed_at` was view-exposure drift (base col existed; new migration); adoption `active_workers_week/adoption_score` had no source → repointed to `risk_tier`; asset `state`→`status` + honest operational-vocab silence (no op-state telemetry exists); voice asset category/description/PM-dates slimmed to real cols; the COUNT items were real `.execute()`/`.group_by()` bugs (not supabase-js v2) → rewrote the whole voice + platform-scraper digest; dayplanner `.open` was a validator parser FP → bounded the query window at `;`. Live-triaged via the app's real anon client. _(see `.tmp/proj_drift_triage_2026-06-10.md` CLOSURE)._
- **Phase 4** 🟡 this session: retired `platform-health.html` (delisted + links repointed).
- **EVERYTHING this session is LOCAL/UNCOMMITTED** (Ian: hold; he reviews the diff). Production still has none of it (Phase 0 is committed-not-pushed). → the deploy (Phase 7) is the biggest open item and now bundles a large correctness ship.

---

## Phase 0 — DONE ✅ (committed, not pushed)
PM due-date math (`frequency_days` Weekly/Semi-annual/Annual → 90d bug) `ac67feb`; PM compliance unified to `get_pm_compliance_smrp` `ca98f8a`; freq-map gate `328539c`; survey + roadmap `c21fa24`.

## Phase 6 — Live-walk the whole platform (nodes + the WEB)
**6a — DONE ✅** the 14 un-walked pages, operated in isolation.
**6b — STARTED 🟡 (deep-link contracts walked, 2 edge bugs found+fixed)** — the param-carrying edges are verified:
| Edge | Contract | Result |
|---|---|---|
| project-manager → project-report `?project_id=` | base `projects.id` (page reads base table, not v_project_truth — deferred by design L13) | ✅ live: 47% · 3/7 · no error |
| index (QR-scan + Top-At-Risk) → asset-hub `?tag=` | **was DEAD — asset-hub only read `?node_id=`** → scan→360 loop broken | ✅ **FIXED**: asset-hub now resolves `?tag=` by tag OR name (case-insens); verified M-001 opens |
| predictive → asset-hub `?node_id=` | `v_risk_truth.asset_id` = asset_nodes id-space (proven live) | ✅ sound |
| asset-hub → marketplace `?listing=` | **was DEAD — marketplace had no `?listing=` reader** | ✅ **FIXED**: deep-link opens detail sheet incl cross-section fallback fetch; verified jobs listing opens from parts default |
| marketplace → seller-profile `?worker=` | `urlParams.get('worker')` | ✅ live: profile renders |

**6b — DONE ✅ (2026-06-10):** all remaining nodes walked (founder-console clean · analytics-report generate operated · report-sender clean · architecture/validator-catalog/symbol-gallery load). **Shared-state sweep CLEAN** — hive-id readers uniformly `wh_active_hive_id||wh_hive_id` (0 drift suspects); `wh_worker_name`'s 39 reads are a documented fallback chain behind `wh_last_worker`, not drift.

**IA map — the tier classification (input to Phase 4):**
- **FOUNDER/INTERNAL tier (Ian's personal pages, NOT for public):** founder-console, architecture, validator-catalog, symbol-gallery, marketplace-admin. All now gated: loopback = founder dev bypass; public hosts require `isPlatformAdmin` (fail-closed) + `noindex,nofollow`. Deliberately NOT in robots.txt (don't advertise the URLs). Excluded from product-IA consolidation pressure.
- **PRODUCT tier:** everything else — the Phase-4 critic operates on these only.

**ANALYTICS ENV BLOCKER KILLED (2026-06-10):** edge fn → python-api now works locally. Root causes (3 stacked): `host.docker.internal`→unroutable IPv6; all IPv4 routes dead; Windows Firewall PUBLIC profile blocks container→host. Fix: python-api runs AS a container (`workhive_python_api`, static `--ip 172.18.0.250` on `supabase_network_workhive`) + `/etc/hosts` in-place patch on the live runtime + durable `PYTHON_API_URL=http://172.18.0.250:8000` in `supabase/functions/.env` (env is baked at container create — takes effect on next `supabase stop/start`). **All 4 analytics phases verified live** (descriptive/diagnostic/predictive/prescriptive = real postgres_rpc data). Phase 1 (analytics open-fast) is now unblocked for real e2e work.
- **Deep-link contracts** — every tile/button that links elsewhere (`project-manager → project-report?project_id=`, dashboard tile → pm-scheduler, alert-hub → asset-hub) carries the right param AND the destination shows the **same number at the same granularity** (we saw "9 overdue items" link to "6 overdue assets").
- **Shared state** — every page reads the same `hive_id`/role/worker from localStorage; one unguarded reader cascades.
- **Data handoffs** — page A writes, page B reads (PROJ-DRIFT was this within the data layer).
- **Remaining nodes** still un-walked: founder-console, marketplace-seller-profile, analytics-report, report-sender, architecture, validator-catalog, symbol-gallery, + re-walk any fused candidates.

**Output of 6b = an interconnection / IA map** (who links to whom, with what param, sharing what state/view). **That map is the input to Phase 4.**
**Done when:** every page operated AND every cross-page edge has a verified contract; the IA map exists.

## Phase 4 — Consolidation & IA rationalization (you-as-critic) ⭐ (broadened)
Was "remove duplicate pages"; now a **principled IA pass** fed by 6b's map. Decide **fuse / merge / keep / cut** with a rubric, not vibes:
- **Fuse only when: same data source + same user job + same audience.** (Table-overlap alone is a trap — marketplace's 3 pages overlap heavily but serve buyer/seller/admin → keep; logbook↔pm-scheduler share tables but are different jobs → keep.)
- **Every merge/retire has blast radius**: update nav-hub TOOLS, `index.html` stageData, `llms.txt`, sitemap, **and learn-article links** (lived this retiring platform-health). Use the retirement checklist.

**CRITIC PASS EXECUTED 2026-06-10** (evidence = live walk of all 14 candidate pages, data-source capture via network sniff, link census). Verdicts per the rubric:

| Candidate | Verdict | Why (data · job · audience) | Status |
|---|---|---|---|
| `parts-tracker.html` | **DELETED** | Zombie: assistant notes already declared it retired; inventory.html is the canonical surface (same v_inventory data, same job, same audience). Removed from sw.js SHELL_FILES (a precached missing file fails the whole SW install). | ✅ `git rm`, 404 verified, link+sitemap gates PASS |
| `predictive.html` | **RETIRED** (file kept, delisted) | Same data (v_risk_truth) + same job as Asset Hub per-asset risk 360; failure-trend/next-failure = Analytics' now-live Predictive phase. Only 1 product link existed. | ✅ analytics.html link → asset-hub ("Asset Risk"), nav-hub entry removed, assistant retirement note |
| AI-health trio | **NOT a merge — a tier split.** ai-quality stays PRODUCT (hive-scoped, maturity-gated ROI). llm-observability + agentic-rag-observability = **founder tier** (platform-wide ai_cost_log / dev-roadmap traces, ZERO product links in — orphans). | Different data (3 tables) + different audience: hive supervisor vs founder. | ✅ both founder-gated (isPlatformAdmin + noindex) |
| integrations ↔ plant-connections | **MERGE long-term** (config + monitor of the same connections domain, same supervisor audience). Interim: cross-links both ways. | Same domain/audience, adjacent jobs (configure vs monitor) | ✅ back-link added (plant-conn → integrations already existed); merge build = future item |
| community ↔ public-feed | **KEEP both** | Same table, different audience+job: hive participation vs anon read-only discovery funnel | ✅ recorded |
| analytics-report ↔ report-sender | **KEEP both** | Different data (live orchestrator compose vs stored v_ai_reports send) + different job. Phase-3 flow edge: analytics-report should SAVE to ai_reports so report-sender can distribute it | ✅ recorded |
| project-manager ↔ project-report | **KEEP both** | Same data, different job (manage vs print deliverable); report is manager's print-mode, deep-link contract verified | ✅ recorded |
| platform-health.html | retired (prior session) | — | ✅ |

**Done when:** fewer pages, each metric/job lives in exactly one place, no dangling links. **Remaining:** the integrations→plant-connections merge build; Ian's veto window on the trio tier-split.

## Phase 5 — Gate checks so it can't drift again
- ✅ `validate_truth_view_consumer_columns.py` (consumer column vs the v_*_truth view it queries; backlog 49→0).
- ✅ **`validate_deeplink_param_contracts.py` (2026-06-10)** — every emitted `page.html?param=` must have a `.get('param')` reader in the destination. Forward-only ratchet, JS/HTML-comment-stripping, synthetic self-test 4/4, registered (338th validator, auto-discovery green). **Its first live run found 3 MORE dead params beyond the 6b pair — ALL FIXED + Playwright-verified:** companion→assistant `?q=` (the "continue in Assistant" hand-off dropped the question → now prefills+focuses, never auto-sends), search-overlay→logbook `?id=` (now opens the entry's detail modal), search-overlay→inventory `?q=` (now filters the list). Backlog 0.
- ✅ **F5 closed** — `spike_factor: null` is the honest NEW_USAGE value (no baseline → no ratio; UI already renders "New usage"); the CONTRACT was wrong → forward migration `20260610000003` makes it `["number","null"]` + registers signal/interpretation. Applied + verified locally.
- ✅ **F6 closed as not-reproducible** — zero `â€` mojibake in live logbook/shift_plans AND in a fresh 4-phase orchestrator payload (30 clean em-dashes); the original sighting matches the Windows cp1252 *console-rendering* artifact class, not stored data.
- ✅ **KPI source registry (2026-06-10) — PHASE 5 COMPLETE.** `kpi_source_registry.json` (4 audit-established metrics: pm_overdue→`v_pm_scope_items_truth.is_overdue`/`get_hive_dashboard`; pm_compliance→`get_pm_compliance_smrp`; low_stock→`v_inventory_items_truth.is_low_stock`; top_risk_band→`v_risk_truth`+`risk_level` bands) + `validate_kpi_source_registry.py` (339th validator, self-test 3/3, live 3/3 PASS): R1 every consumer references the official source, R2 no consumer matches a documented-wrong derivation (flat `is_due` proxy, `ontrack/` compliance, unbanded top-risk — each encoded as a forbidden regex with its incident), R3 anti-rot (sources must exist in live DB; SKIP offline). This closes the F4 gap the other gates can't see: two pages reading two DIFFERENT canonical views for the same metric while every chip/raw-read gate stays green. New metrics get registered when their derivation is parity-audit-established — never speculatively.
**Done when:** a new screen that recalculates a number locally, or a link that contradicts its destination, is stopped by the gate. ✅ **Both gates exist and are registered.**

## Phase 1 — Heavy pages open-fast (compute-on-view + Save + Refresh) — ✅ COMPLETE (2026-06-10)
- **analytics (flagship) ✅** — `analytics_snapshots` table (migration 20260610000004: UNIQUE(hive,phase,period), RLS member-read, **service-role-only writes** so a client can't poison the shared copy) + orchestrator persists every successful UNFILTERED compute + page hydrates from today's (PHT) snapshots. **Measured: reload ready in 514ms with ZERO orchestrator calls** (one REST GET), "Updated X min ago" honest, Refresh forces recompute (verified orchestrator fires) and re-saves. First view of the day computes; filtered views always live; solo mode always live. validate_analytics.py 34/34.
- **ph-intelligence ✅ already compliant** — zero edge-fn calls on load; reads persisted `ph_intelligence_reports` + `hive_benchmarks` behind the Stair-3 honest gate. (Its "heavy" label predated this audit.)
- **project-report ✅ already compliant** — 4 scoped truth-view reads, renders instantly; the old heaviness was the PROJ-DRIFT breakage, fixed in the DRIFT track.
- **Caveat for the parity harness:** `__ANALYTICS_PARITY` compares rendered DOM to a fresh oracle — on a snapshot-hydrated view run Refresh first (or compare against the snapshot payload) to avoid false intra-day mismatches.
**Done when:** they open instantly after the first daily view, show "Computed Xh ago," and only Refresh recomputes. ✅ all three verified live.

## Phase 3 — One brain: intelligence pages read one engine — ✅ COMPLETE (2026-06-10)
- **One alert composer ✅** — `v_alert_truth` (signature+anomaly UNION, active+acknowledged only) was already the Hive Board's source; **alert-hub's signature read repointed to it** (was raw `failure_signature_alerts` with NO status filter → resolved alerts resurrected in the hub while the board dropped them; the view also normalizes severities into the feed's palette). Verified live: 1 v_alert_truth read / 0 raw reads, "Pattern 1" = DB census. Ack/resolve writes still target base tables (views aren't writable) and now retract the alert from BOTH surfaces.
- **Dashboards read the engine ✅** (pre-existing: `get_hive_dashboard` unified pm_overdue; hive "Open issues" composes pm_overdue + open-WO + low-stock from canonical sources — parity-audited, now KPI-registry-locked).
- **Asset Hub carries the alert's risk score ✅** — verified live: hub alert "AC-003 risk 90%" deep-links via `?tag=` (the 6b reader) → asset-hub 360 shows the same 90% from the same `v_risk_truth`.
- **Feedback loop ✅** — PM done → `pm_completions` → batch-risk-scoring (un-starved by the Pattern-B drift repoint, 547 completions now feed the composite); risk ack/resolve → status update + audit log → drops everywhere via the shared composer; AI thumbs → `ai_reply_feedback` (built 2026-06-09) → companion harvest loop.
**Done when:** the same number reads identical on every screen, and acting on it updates the one source. ✅ verified (canonical_sources 6/6, kpi-registry 3/3, truth-view 0-backlog).

## Phase 2 — Shift Handover auto each shift (`shift-brain.html`) — ✅ COMPLETE (2026-06-11)
- **`maybeAutoGenerate()`** hooked at loadPlan's tail: in a hive + viewing the LIVE window + no plan dated today (**PHT** — shift_plans.shift_date defaults `Asia/Manila`; 22-06 spans midnight so yesterday counts) → calls shift-planner-orchestrator once per page load, fail-soft to the existing empty state + Generate button. Carry-forward comes from the orchestrator's existing sub-agent.
- **The 3 pg_cron jobs RETIRED** — migration `20260610000005` (idempotent unschedule; applied locally, `cron.job` clean). `enable_shift_brain_cron.sql` + Platform Book annotated SUPERSEDED; both stale "wait for the production cron" toasts updated. Retention/purge crons are housekeeping, out of the compute-rule's scope.
- **PROVEN LIVE both paths:** (1) first open of the planless live window → `shift_plans` row `14-22 / 2026-06-11 / draft / generated_by=shift-planner-orchestrator` at 07:41:37, three seconds after page-open, zero crons scheduled; (2) next open → 0 orchestrator calls, renders "Heavy shift — prioritize hot assets and carry-forward" with the carry-forward section, no duplicate rows.
**Done when:** each shift opens to a ready handover carrying the prior shift's open items. ✅

## CONTENT track — outward surfaces grounded in real page flows (parallel)
Learn articles + landing copy + video-marketing scripts must be **grounded in the actual platform flow**, never invented; when pages consolidate (Phase 4), the content follows. **This is already being built in the concurrent session** (`CONTENT_GROUNDING_GATE.md` + `tools/platform_catalog.py`) — do NOT duplicate; align Phase 4 retirements with it so articles never point at fused/retired pages.

## Phase 7 — Deploy to production (your call)
Bundles Phase 0 + the 7 walk fixes + the 34 drift fixes. A **correctness deploy** that un-breaks the entire project vertical and un-starves the AI/ML brains of 547 PM completions in prod. Timing is your decision.

---

## Suggested order
Finish DRIFT (15 left) → **6b (walk the web → IA map)** → **4 (consolidate as critic)** → 5 (lock with gates) → 1 (analytics open-fast) → 3 (one brain) → 2 (shift handover). Phase 7 (deploy) whenever you say. CONTENT track runs in parallel (concurrent session).

---

<details>
<summary>Appendix — technical detail</summary>

### Findings ledger
| # | Finding | Status |
|---|---|---|
| F1 | Source-chip captions stale ("30 days since last anchor") | ✅ d782b9e |
| F2 | `frequency_days` seeder-vocab drift (Weekly/Semi-annual/Annual → 90) | ✅ ac67feb |
| F3 | `prescriptive.py FREQ_DAYS` same drift | ✅ 328539c |
| F4 | pm-scheduler compliance = on-track/total, not SMRP → canonical RPC | ✅ ca98f8a |
| F5 | `parts_consumption_spike` `spike_factor:null` contract | ✅ migration 20260610000003 (contract → `["number","null"]`; null = honest NEW_USAGE) |
| F6 | Em-dash double-encoding in generated strings | ✅ closed not-reproducible (0 mojibake in live data + fresh orchestrator payload; was the cp1252 console-rendering artifact) |
| — | **PROJ-DRIFT** v_project_truth id/end_date/deleted_at (5 consumers) | ✅ fixed (local) |
| — | shift-brain risk threshold (no band filter) | ✅ fixed (local) |
| — | agentic-rag verdict stuck on placeholder | ✅ fixed (local) |
| — | skillmatrix badge denominator hardcoded 30/6 vs 5 | ✅ fixed (local) |
| — | **DRIFT-49** platform-wide v_*_truth consumer-column drift | ✅ 49/49 fixed (local); backlog 0 (see `.tmp/proj_drift_triage_2026-06-10.md` CLOSURE) |
| — | `.execute()`/`.group_by()` not supabase-js v2 → whole voice + platform-scraper digest silently dead | ✅ fixed (local; edge deploy pending) |
| — | `v_asset_truth.status` is approval-state, not operational state; no op-telemetry exists | ✅ honest silence (local) |
| — | marketplace `reviewed_at` view-exposure drift (base col existed, view omitted) | ✅ migration `20260610000002` (local) |

### Drift fix patterns (reusable)
- **A** PostgREST output alias `id:pm_asset_id` / `id:asset_id` (fixes the 400, downstream-safe).
- **B** repoint per-event reads off the rollup view to the **base table** (`v_pm_compliance_truth` → `pm_completions`); a per-asset rollup is NOT a per-event source.
- **C** solo (worker_name) branches → `pm_assets` (the hive view has no worker_name).
- **RLS lesson:** verify base-table data via `psql -U postgres` (superuser), NOT the MCP read conn (RLS makes it report false 0s).

### Why the gate missed it (meta-gaps → closing)
Strong on structure (does the column/view exist), weak on semantics (is the math right; do duplicate copies agree; **does a consumer's columns exist on the VIEW it queries**; do two pages linked together agree). Closing via: freq-map validator (done) · `validate_truth_view_consumer_columns.py` (done) · KPI source registry + cross-page contract validator (Phase 5).

### Compute model (grounded)
Default = lazy compute-on-first-view + cache + Refresh, no cron. Only ~8 pages are 🔴 Heavy — see `PAGE_SURVEY_2026-06-10.md`.
</details>
