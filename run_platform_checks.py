"""
WorkHive Platform Guardian — Master Orchestrator
=================================================
Phase 1: Run every validator, check readiness, compare to baseline.

Usage:
  python run_platform_checks.py             # full run
  python run_platform_checks.py --fast      # skip live API calls (Layer 3)
  python run_platform_checks.py --gate-only # readiness gate only (no validators)

Output:
  platform_health.json   — machine-readable report (feeds future visual dashboard)
  platform_baseline.json — saved when all checks pass (used for regression detection)

Exit codes:
  0 = all pass (safe to deploy / start next feature)
  1 = one or more validators failed
  2 = regression detected (was passing, now failing)
  3 = readiness gate blocked

Loops (Phase 1 implements 1 + 3; Phases 2-4 add the rest):
  Loop 0: Observation    — baseline snapshot comparison
  Loop 1: Retrospection  — run all validators, classify failures
  Loop 3: Readiness Gate — git/deployment/API status
  Loop 2: Self-Learning  — (future: auto-update skill files)
  Loop 4: Improvement    — (future: web search, backlog)

Crash-prevention checks added 2026-04-28 (from production Safari iOS crash):
  validate_mobile.py     +2  — will-change:filter mobile override (FAIL),
                               body{animation} prefers-reduced-motion override (FAIL)
  validate_performance.py +1 — body{animation} animationend safety guard (FAIL),
                               index.html added to LIVE_PAGES scope

Deployment config + live endpoint coverage added 2026-04-29 (from analytics 500):
  validate_edge_config.py    — every supabase/functions/ dir must have config.toml
                               entry with explicit verify_jwt (catches silent JWT default)
  validate_analytics_live.py — calls deployed analytics-orchestrator for all 4 phases
                               (skip_if_fast=True; catches what static checks miss)
"""
import subprocess, sys, os, json, time, datetime
import urllib.request

PYTHON = sys.executable
FAST     = "--fast" in sys.argv
GATE     = "--gate-only" in sys.argv
AUTOFIX  = "--autofix" in sys.argv

BASELINE_FILE = "platform_baseline.json"
HEALTH_FILE   = "platform_health.json"

# ── Colour helpers (Windows-safe ANSI) ────────────────────────────────────────
def green(s):  return f"\033[92m{s}\033[0m"
def red(s):    return f"\033[91m{s}\033[0m"
def yellow(s): return f"\033[93m{s}\033[0m"
def cyan(s):   return f"\033[96m{s}\033[0m"
def bold(s):   return f"\033[1m{s}\033[0m"

# ── Unicode output (Windows UTF-8 fix) ────────────────────────────────────────
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Validator registry ─────────────────────────────────────────────────────────
# Each entry: (id, script, label, group, report_json)
VALIDATORS = [
    # ── Engineering Calc Suite ────────────────────────────────────────────────
    # run_all_checks.py runs 3 layers internally and produces its own reports.
    # We call it with --fast here; the full integration test (Layer 3) is separate.
    {
        "id":      "calc-suite",
        "script":  "run_all_checks.py",
        "args":    ["--fast"],
        "label":   "Engineering Calc Suite (L1+L2a+L2b)",
        "group":   "Engineering Calculator",
        "report":  None,   # run_all_checks.py manages its own reports
        "skip_if_fast": False,
        "severity": "blocker",
    },
    # ── Platform Validators ───────────────────────────────────────────────────
    {
        "id":      "auto-discovery",
        "script":  "validate_auto_discovery.py",
        "args":    [],
        "label":   "Auto-discovery Validator (HTML classified, edge fns in config, validators registered)",
        "group":   "Platform",
        "report":  "auto_discovery_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "gate-observability",
        "script":  "validate_gate_observability.py",
        "args":    [],
        "label":   "Gate Observability (Mega Gate persists a durable log + verdict on every terminal path)",
        "group":   "Platform",
        "report":  "gate_observability_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "seeder-insert-columns",
        "script":  "validate_seeder_insert_columns.py",
        "args":    [],
        "label":   "Seeder Insert-Columns (forward-only: no NEW seeder writes a column absent from the live table)",
        "group":   "Platform",
        "report":  "seeder_insert_columns_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "frequency-map-consistency",
        "script":  "validate_frequency_map_consistency.py",
        "args":    [],
        "label":   "Frequency-Map Consistency (every PM frequency maps to its canonical interval days; live view + code copies agree)",
        "group":   "Platform",
        "report":  "frequency_map_consistency_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "fab-consolidation",
        "script":  "validate_fab_consolidation.py",
        "args":    [],
        "label":   "FAB Consolidation Contract (bottom-right corner stays consolidated into the nav-hub; companion/feedback/connectivity launch from inside the hub, no standalone corner FABs)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "component-purity",
        "script":  "tools/component_purity_census.py",
        "args":    ["--check"],
        "label":   "Component Purity Ratchet (PLATFORM_CENTRALIZATION C-P0/Axis-2: shared-chrome SSOT files must not add RAW brand literals — use var(--wh-*, <fallback>); fallback-aware, forward-only, count may only fall)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "storage-keys",
        "script":  "tools/validate_storage_keys.py",
        "args":    ["--check"],
        "label":   "Storage-Key Registry (PLATFORM_CENTRALIZATION C-P4: every localStorage/sessionStorage key is CANONICAL or a registered ALIAS in storage_key_registry.json; a new UNKNOWN key FAILs until registered — stops the wh_active_hive_id/wh_hive_id drift class)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "role-checks",
        "script":  "validate_role_checks.py",
        "args":    ["--check"],
        "label":   "Client RBAC Ratchet (PLATFORM_CENTRALIZATION +RBAC: raw `role === 'supervisor'` comparisons may only FALL — new client role-gates must use window.WHRoles.isSupervisor()/.can(); wh-roles.js is the SSOT)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "truth-view-consumer-columns",
        "script":  "validate_truth_view_consumer_columns.py",
        "args":    [],
        "label":   "Truth-View Consumer-Columns (forward-only: no NEW consumer reads a column absent from the v_*_truth view it queries — catches PROJ-DRIFT)",
        "group":   "Platform",
        "report":  "truth_view_consumer_columns_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "interactive-lineage",
        "script":  "tools/validate_interactive_lineage.py",
        "args":    [],
        "label":   "Interactive Lineage Axis (forward-only: per-field downstream blast-radius dead-ends, display-anchor resolution, and redundancy verdicts don't regress — INTERACTIVE_LINEAGE_ROADMAP Phase F)",
        "group":   "Platform",
        "skip_if_fast": True,
        # Promoted warn -> fail (2026-07-08, Ian: "drive to 100%"): this D22 deep-interaction ratchet
        # PASSES with real coverage (5 dead-end + 38 cascade fields, 59 anchors resolved, 0 pending) —
        # locking it makes the 40 D22 page cells ✅ and blocks any future regression, per the deepwalk
        # flywheel's forward-only floor. It was advisory only while the axis was still being built.
        "severity": "fail",
    },
    {
        "id":      "causal-cascade-coverage",
        "script":  "tools/validate_causal_cascade_coverage.py",
        "args":    [],
        "label":   "Causal Cascade Coverage (Phase A anti-rot: both legs — every DB-trigger AND every edge-fn cross-table data write is mapped in causal_cascades.json — surfaces a new unmapped cascade for review)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "reactivity-wiring",
        "script":  "tools/validate_reactivity_wiring.py",
        "args":    [],
        "label":   "Reactivity Wiring (Phase D anti-rot: every write surface with cross-page fan-out emits a cross-surface receipt [D1], and every high-blast surface has impact-preview.js + a live save-button anchor [D2] — a new silent write surface FAILs)",
        "group":   "Platform",
        "skip_if_fast": True,
        # Promoted warn -> fail (2026-07-08, Ian: "drive to 100%"): this D3 cross-surface-receipt
        # ratchet PASSES (7/7 write surfaces have a verified receipt, 4/4 high-blast wired, 4/4
        # snapshot-KPI owners fresh) — locking it makes the 40 D3 page cells ✅ and blocks a new
        # silent write surface. Advisory only while the receipt wiring was still being rolled out.
        "severity": "fail",
    },
    {
        "id":      "attribution",
        "script":  "tools/validate_attribution.py",
        "args":    [],
        "label":   "Attribution integrity (every CLIENT insert/upsert into an auth_uid-no-default table must set auth_uid — locks the auth_uid-drop bug class found live 2026-07-06 on inventory_transactions/pm-scheduler/logbook/integrations/marketplace-seller/asset-hub; unresolvable payloads need an attribution-allow marker)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "client-singleton",
        "script":  "tools/validate_client_singleton.py",
        "args":    [],
        "label":   "Client singleton / idle-refresh (every Supabase client routes through getDb() so it inherits the Finding-#6 token auto-refresh + visibilitychange refresh + timeout fetch and does not spawn a 2nd GoTrueClient — locks the raw-createClient idle-401 class found live 2026-07-06 on voice-handler.js/search-overlay.js; standalone public pages carry a singleton-exempt marker; dim-14)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "embed-auth",
        "script":  "tools/validate_embed_auth.py",
        "args":    [],
        "label":   "Embed-auth / tenancy-gated edge-fn JWT forwarding (every browser fetch to embed-entry forwards the user session JWT as Bearer so its Pillar I tenancy check resolves — locks the client-drops-JWT 401 class found live 2026-07-07 on skillmatrix/logbook/pm-scheduler/voice-handler; without it the write lands but the skill/fault/PM embedding is silently dropped from the RAG index; dim-4)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "voice-journal-single-write",
        "script":  "tools/validate_voice_journal_single_write.py",
        "args":    [],
        "label":   "Voice-journal single-write (the companion agent:'voice-journal' gateway call already persists the turn server-side via persistJournalEntry with an embedding — so NO client _saveJournalTurn/insert may run on its success or clarify path; locks the double-write class found+proven-live 2026-07-07 on voice-handler.js where every companion voice turn was journaled twice, one copy embedding-less; client saves belong only on non-gateway paths [shortcuts / RAG short-circuit / offline catch]; dim-4)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "agent-memory-persist-complete",
        "script":  "tools/validate_agent_memory_persist_complete.py",
        "args":    [],
        "label":   "agent_memory persist-complete (the store_memory_turn RPC's INSERT names every NOT NULL column [worker_name/agent_id/kind] + sets kind to a CHECK-allowed literal — locks the class found live 2026-07-07 where the RPC omitted 3 NOT NULL cols and failed 100% silently, killing the companion's session-memory layer [voice-handler _storeTurn -> _fetchRecentMemory]; dim-4/dim-13)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "logbook-asset-linkage",
        "script":  "tools/validate_logbook_asset_linkage.py",
        "args":    [],
        "label":   "Logbook->asset linkage (LIVE: 0 logbook entries whose `machine` EXACTLY matches a registered asset tag may be asset_node_id NULL — locks the asset-history fragmentation class found live 2026-07-08 [deep-walk CL1], where 2700 entries [46% in Baguio] named a real tag yet were unlinked, so v_asset_truth.lifetime_logbook_entries + asset-brain + analytics UNDERCOUNT an asset's history [PB-001: 18 shown vs 37 real]. Backfill migration 20260708000000 fixed existing rows; this is a fix-to-ZERO down-ratchet. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "inventory-ledger-reconciled",
        "script":  "tools/validate_inventory_ledger_reconciled.py",
        "args":    [],
        "label":   "Inventory balance<->ledger reconciliation (LIVE: qty_on_hand must == the ledger's newest qty_after AND the ledger must chain [qty_after = prev + qty_change] — locks the stock-level seesaw found live 2026-07-08 [ARC DI §10.5], where 77/82 items' stored balance drifted from the transaction ledger [seeder wrote an OPENING balance + random-order txns]. Migration 20260708000001 added a reconcile trigger [balance mirrors the ledger on every movement] + backfill; the seeder is now born-consistent; this is a fix-to-ZERO down-ratchet. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "inventory-txn-isolation",
        "script":  "tools/validate_inventory_txn_isolation.py",
        "args":    [],
        "label":   "Inventory ledger-write hive isolation (LIVE two-tenant, rolled-back: simulates a real authenticated member and asserts a hive-A member CANNOT insert an inventory_transaction against a hive-B item [42501] — locks the cross-tenant ledger-tamper hole live-exploited 2026-07-12 [Inventory PDDA], where `inventory_transactions_write` WITH CHECK was only `auth.uid() IS NOT NULL` so a foreign-item txn's bogus qty_after was mirrored onto that item's stored qty_on_hand by the SECURITY DEFINER sync trigger [78->88888 cross-hive]. Migration 20260712000011 scoped the write policy to hive_members membership + item-hive match, hive-guarded the trigger, and added a qty_after>=0 CHECK [negative-stock tamper]. Also asserts a legit in-hive insert still succeeds [no regression]. Actors picked dynamically = reseed-robust. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "pm-write-isolation",
        "script":  "tools/validate_pm_write_isolation.py",
        "args":    [],
        "label":   "PM-write hive isolation (LIVE two-tenant, rolled-back: simulates a real authenticated member and asserts a hive-A member CANNOT [42501] inject a pm_scope_item onto a hive-B asset, a pm_completion into hive B [compliance poisoning of v_pm_compliance_truth -> analytics/shift-planner/hive-health/predictive], nor a phantom pm_asset into hive B — the same child/ledger-table WITH-CHECK class as the inventory ledger tamper, THREE holes live-exploited 2026-07-12 [PM Scheduler PDDA]: pm_scope_items_write WITH CHECK was `auth.uid() IS NOT NULL` only; pm_completions_write + pm_assets_write had WITH CHECK=null so INSERT fell back to a USING with no hive gate [completions] / an `auth_uid=self OR member` OR [assets]. Migration 20260712000012 membership-joins the parent/own-hive in every WITH CHECK. Also asserts a legit in-hive completion still succeeds [no regression]. Actors picked dynamically = reseed-robust. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "display-correctness-fixes",
        "script":  "tools/validate_display_correctness_fixes.py",
        "args":    [],
        "label":   "Display-correctness fix regression gate (STATIC: asserts the 2026-07-13 bug-hunt render-logic fixes are still present — a revert removes the marker and this FAILs, catching what a DB probe can't see. Locks: achievements 'XP this week' summed from a dedicated 7-day query not the .limit(30) list [limit-as-aggregate undercount] + init surfaces whListError on a query error not a fake 'No achievements yet'; asset-hub 'Total assets'/'Critical' via count:'exact' not the .limit(200) list length; ai-quality loadCostLog/loadReplyFeedback throw on {error} instead of swallowing it as [] + dropped the unused user_feedback column; inventory supervisor fetches the full pending approval queue + stock counts exclude non-approved; hive adoption card shows a neutral 'No data yet' tier when there's no snapshot not a green 'Healthy' + PM-overdue count/banner reset on hive-switch. Complements the LIVE validate_hive_write_isolation.py)",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "hive-write-isolation",
        "script":  "tools/validate_hive_write_isolation.py",
        "args":    [],
        "label":   "Hive-write isolation for the sibling tables the 2026-07-12 sweep MISSED (LIVE two-tenant, rolled-back: asserts a hive-A member CANNOT [42501] inject a phantom inventory_items part into hive B, nor a report_contact into hive B [cross-tenant recipient exfil], and a WORKER CANNOT mint an api_key [supervisor-only] — three holes live-exploited 2026-07-13 [platform bug-hunt]: inventory_items_write WITH CHECK owner branch `auth_uid=self` had no hive gate [status<>approved dodges the approval trigger]; report_contacts_write WITH CHECK was `auth.uid() IS NOT NULL` only; api_keys_hive_rw had no role gate [worker minted a hive credential]. Migrations 20260712000019 [hive-gate inventory_items+report_contacts WITH CHECK] + 000020 [supervisor-scope api_keys/project_roles, approval-trigger project_change_orders]. Also asserts a legit in-hive part add + a supervisor api_key mint still succeed [no regression]. Actors picked dynamically = reseed-robust. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "hive-isolation",
        "script":  "tools/validate_hive_isolation.py",
        "args":    [],
        "label":   "Hive cross-tenant READ + MEMBERSHIP + ATTRIBUTION + ROLE isolation (LIVE two-tenant, rolled-back — bug-hunt 2026-07-13/14, migs 20260713000001-012). 25 invariants as a real authenticated member (+engineering_calcs/parts_records/voice_journal authorship pin [mig 012: eng_calc_attr_pin + parts_rec_attr_pin + voice_j_attr_pin — substrate closure-pass siblings; parts_records has no auth_uid so worker_name is its only attribution; project_items.owner_name deliberately NOT pinned = it's an assignment field not authorship] +community_posts + inventory_items attribution [mig 011: comm_post_attr_pin + inv_item_attr_pin — a spoofed author_name/registrant on a community_posts/inventory_items INSERT is server-pinned to the caller via bind_community_post_submitter/bind_inventory_item_submitter; substrate-found siblings of the mig-007/010 sweep], +pm-scheduler attribution [mig 010: pm_asset_attr_pin + pm_completion_attr_pin — a spoofed registrant/completer on a pm_assets/pm_completions INSERT is server-pinned to the caller via bind_pm_*_submitter], +marketplace listing trust-forge sourced from canonical [mig 009], credential/gamification server-mediated forge-block [skill_badges/worker_achievements], logbook owner-scoped edit; 13/14 = community_replies attribution: comm_reply_attr_pin [a spoofed auth_uid/author_name on a reply INSERT is server-pinned to the caller] + comm_reply_hijack_block [a member cannot UPDATE another member's reply; author-or-supervisor-only]; mig 007 bind_community_reply_submitter + author-scoped write policies, closing the within-hive forge + cross-author BOLA on community.html): (1) read_logbook_xhive + (2) read_cxp_xhive — a FOREIGN hive's v_logbook_truth / community_xp return 0 rows [mig 001: v_logbook_truth/v_project_truth/v_marketplace_listings_truth were missing security_invoker so the view ran as superuser and BYPASSED base RLS — a non-member read 1105 rows of another tenant's logbook LIVE; +community_xp_read was auth.uid()-only, leaking every hive's roster/XP/UUIDs]; (3) mem_selfjoin [P5-01: self-join any hive_id] + (4) mem_kickrestore [P5-02: DELETE-then-reINSERT un-bans a kicked worker] — closed by mig 002 (server-verified join_hive_by_code RPC + founder-only INSERT + sticky-kicked DELETE); (5) asset_attr_pin + (6) logbook_attr_pin + (7) projects_attr_pin — a spoofed auth_uid/worker_name on INSERT is server-pinned to the caller [migs 003/004/005 bind_*_submitter triggers]; (8) comm_announce_gate — a WORKER cannot post a category='announcement' [UI-only-gate BOLA closed by mig 006]; (9) audit_actor_bind [P4-03: forged hive_audit_log.actor rebound] + (10) text_caps_present [P4-02: hives/hive_members cap triggers] [mig 003]; (11) join_rpc_ok + (12) founder_create_ok — no-regression. Actors + a data-rich foreign hive chosen dynamically = reseed-robust. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "bughunt-scoreboard",
        "script":  "tools/build_bughunt_scoreboard.py",
        "args":    ["--check"],
        "label":   "per-page bughunt v3 ANTI-DRIFT scoreboard — regenerates PER_PAGE_BUGHUNT_SCOREBOARD.md (every page's 12x6 matrix mapped to its covering gate) and FAILs if any page has an uncovered GAP: a footprint item no standing gate hunts (an edge fn not in the 57-fn edge-auth sweep, a hive_id view not in read-isolation, or a page-battery finding). This is the drift-guard — a NEW page or a new edge fn/view/write that isn't gate-covered trips it. Reads the page-battery + read-isolation reports (so runs in full mode, after those refresh). 2026-07-20: 42 pages · 1 DEEP · 41 COVERED · 0 GAP",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "rate-limit-handling",
        "script":  "tools/validate_rate_limit_handling.py",
        "args":    [],
        "label":   "per-page SaaS-LAYER · Layer RL (Rate Limiting) — METHOD-LAW central-adoption gate. When a page's AI/edge call is rate-limited (server checkAIRateLimit → structured 429), the user must see a SCOPE-CORRECT message, not a raw error. The mapping is ONE central helper `window.whAiError(err, fallback)` in utils.js (429→'you hit the rate limit, wait' · 503→'AI busy' · network→'check connection'). Every page invoking a rate-limited AI fn (ai-gateway/*-orchestrator/*-assist/voice-*/semantic-search/asset-brain) must handle 429 via whAiError OR an inline check. Adopted 2026-07-22 on the 8 that lacked it (analytics/analytics-report/marketplace/project-manager/project-report/report-sender/shift-brain/voice-journal) → 12/12 covered; alert-hub exempt (best-effort empty-catch-allow keeps the stored fallback). Server 429→graceful is separately gated by perf_l5_llm_resilience; companion 429 UX is central in companion-launcher.js. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "sw-shell-membership",
        "script":  "tools/validate_sw_shell_membership.py",
        "args":    [],
        "label":   "CA (Caching/CDN) deep-walk cell — every page in the service-worker OFFLINE SHELL (sw.js SHELL_FILES) must (a) exist on disk (a stale entry 404s the SW precache install → the whole offline shell breaks for every PWA user) and (b) the shell must be cache-VERSIONED (CACHE_NAME), so a shell change re-primes rather than serving stale cached markup. Emits its exact per-page pass-list to deepwalk_layer_pages.json[CA] for the deepwalk flywheel's CA architectural-layer cell (the gate-emitted-pass-list mechanism: the gate publishes its EXACT scope, the flywheel never regex-approximates). 8 shell HTML pages. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "degraded-state-central",
        "script":  "tools/validate_degraded_state_central.py",
        "args":    [],
        "label":   "per-page SaaS-LAYER · Layer AV (Availability & Recovery) — METHOD-LAW central-component adoption gate. The device-offline / degraded warning is ONE shared idempotent component (`offline-banner.js`, __whOfflineBannerLoaded guard), NOT per-page code. Every USER-FACING backend-touching page (getDb/db.from/functions.invoke/rpc) must ADOPT it, so a page that ships stale/failed actions with no offline warning FAILs. Adopted 2026-07-22 on the 4 that lacked it (analytics-report/founder-console/platform-actions/resume) — 31/31 user-facing backend pages now covered. Internal dev/observability consoles + backups exempt (documented). The OTHER AV half (backend-down fail-closed / empty-vs-error) is reused: L-backbone (error-capture) + P12 (page-battery) + read-battery. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "error-capture",
        "script":  "tools/validate_error_capture.py",
        "args":    [],
        "label":   "per-page SaaS-LAYER · Layer L (Error Tracking & Logs) — a catch around a BACKEND op (db.from/db.rpc/db.functions.invoke/fetch) that SURFACES the error to the user (showToast/addBubble/showFormError/textContent/alert) must ALSO CAPTURE it (console.error/warn, logEvent, window.onerror, captureException). A show-but-don't-log catch leaves a backend op that starts failing for users INVISIBLE in the console/aggregator (the L-layer 'ungreppable logs' failure mode). REAL bug locked 2026-07-22: assistant.html sendMessage swallowed the ai-gateway failure from observability (shown, never logged). Best-effort/silent-by-design catches (comment `empty-catch-allow`/`best-effort`/`non-fatal`) + no-user-surface + non-backend catches are excluded. FORWARD-ONLY ratchet on the swallow count (baseline seeds; a NEW swallow FAILs; `--accept` ratchets DOWN as the backlog is fixed to 0). Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "saas-layer-scoreboard",
        "script":  "tools/build_saas_layer_scoreboard.py",
        "args":    ["--check"],
        "label":   "per-page SaaS-LAYER bughunt ANTI-DRIFT scoreboard (PER_PAGE_SAAS_LAYER_BUGHUNT_ROADMAP.md §0) — regenerates PER_PAGE_SAAS_LAYER_SCOREBOARD.md (every page × the 13 SaaS production layers F/A/D/AU/H/C/CI/S/RL/CA/LB/L/AV, each cell COVERED/OPEN/N.A derived from the page's substrate footprint) and holds the count of OPEN operational cells (C/RL/CA/L/AV — the genuine new hunt) as a FORWARD-ONLY CEILING. FAILs if it RISES above baseline: a new page / new edge fn / regressed operational gate that escapes coverage = drift, caught by CI not vigilance. As each per-page operational probe (L error-capture, C LLM-fallback, RL 429-backoff, CA cache-hit, AV degraded) is built + registered, edit COVERAGE in the builder to flip its cells ○→✓ and `--accept` ratchets the baseline down toward 0. Seed 2026-07-22: 42 pages · 138 OPEN ops · 251 COVERED · 157 N/A.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "edge-fn-auth-gate",
        "script":  "tools/validate_edge_fn_auth_gate.py",
        "args":    [],
        "label":   "per-page bughunt v3 L6 — every hive-touching edge fn must gate its caller (STATIC, no DB). A Supabase edge fn runs with SERVICE_ROLE (RLS-bypass); one that reads/writes tenant data keyed by a CLIENT hive_id WITHOUT first proving caller entitlement = cross-tenant write/read injection by any anon caller. The 2026-07-20 sweep of all 57 fns found every one gated (resolveTenancy/resolveIdentity/requireServiceRole/getUser/authenticate/cron-secret, or verify_jwt=true); 4 exempt (login = session-creator; resume-extract/resume-polish IGNORE hive_id [Pillar P back-compat]; voice-journal-agent uses hive_id only as ai_cost_log telemetry). A NEW fn that references hive_id but ships without a caller gate FAILs until reviewed + explicitly allowlisted. Baseline 0 ungated",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "hive-battery",
        "script":  "tools/validate_hive_battery.py",
        "args":    [],
        "label":   "hive.html LIVE per-page battery — PER_PAGE_BUGHUNT_ROADMAP Tier-1 (P1 Smoke / P2 Console+Network / P8 Visual). Headless Playwright signs in as the REAL Baguio supervisor (leandromarquez / hive 636cf7e8) and asserts, on the live board load: P1 — renders REAL data [no undefined/NaN/[object Object]], NOT the no-hive empty state, the primary anchor stats #stat-open == v_logbook_truth open-WO count and #stat-members == hive_members active count [rendered==DB truth], and ZERO console errors; P2 — every Supabase REST/RPC/auth/functions response is <400 [no silent 4xx/5xx / swallowed error]; P8 — no horizontal overflow at 390px [mobile] or 1280px [desktop]. Re-drive: node tools/validate_hive_battery.mjs [--headed]. Skips cleanly if node or the local stack [Flask :5000 / Supabase :54321] is absent; a render-drift / console-error / 4xx-5xx / overflow regression is a FAIL)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "page-battery",
        "script":  "tools/validate_page_battery.py",
        "args":    [],
        "label":   "Platform-wide page battery (LIVE headless Playwright, real Baguio supervisor sign-in) - PER_PAGE_BUGHUNT_ROADMAP section 5 mechanical floor across ALL ~30 interactive pages. Locks the page-agnostic phases so a regression FAILs: P1 Smoke (every page loads signed-in, renders a non-blank body, NO error-state banner ['failed to load'/'unexpected error'], ZERO console errors on load); P2 Console/Network (no 5xx response during load = no silent server error); P4 Inputs (the SAFE reflected-XSS probe: typing an <img src=x onerror> payload into every visible input NEVER executes [window flag stays unset] NOR reflects as a live <img onerror> node - locks the reflected-DOM-XSS invariant across every page's inputs; submit-path P4 stays MCP-interactive per the roadmap); P8 Visual (no horizontal overflow at 390px [mobile-first invariant] on any page). Complements the DEEP per-page truth gate validate_hive_battery.py (asserts rendered==DB for hive.html). Re-drive: WH_TEST_HIVE=636cf7e8-431a-4907-8a9f-43dd4cc216d6 node tools/page_battery.mjs --gate [--headed]. Skips cleanly if node or the local stack (Flask :5000 / Supabase :54321) is absent)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "page-crud",
        "script":  "tools/validate_page_crud.py",
        "args":    [],
        "label":   "Per-page P3 CRUD-at-DB gate (LIVE headless Playwright, real WORKER sign-in via live_page_journeys). Three invariant shapes, because not every entity is a worker's to create or destroy. (1) CREATE-AND-PIN (voice_journal_entries/engineering_calcs/community_posts): INSERT with a FORGED display name -> assert it PERSISTED but the name is PINNED to the caller (bind_*_submitter, migs 010/011/012) -> owner-scoped DELETE -> assert cleaned. (2) REFUSED-by-design (pm_assets): a worker's INSERT must be DENIED — mig 20260728000011 made creating a PM asset supervisor-only, since every added asset moves the hive's PM-compliance denominator; a row coming back means the guard was lost. (3) deleteRefused (projects): a worker MAY create and the name pins, but removal is supervisor-only (guard_and_audit_project_removal), so a worker DELETE that lands is the regression. RETURNING clauses are explicit everywhere: a bare .select() is `select *` and 42501s on a SELECT-revoked column (projects.budget_php) AFTER the row has committed — see the `star-returning` gate. Probe rows use a per-run unique key and are swept by the Python wrapper. Skips cleanly (exit 0) if the local stack/sign-in is absent.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "fixture-hive-exists",
        "script":  "tools/validate_fixture_hive_exists.py",
        "args":    [],
        "label":   "FIXTURE HIVE EXISTENCE — a pinned test hive that no longer exists is a SILENT instrument, and the worst shape a test failure can take. FOUND 2026-07-30 while triaging read-battery, which reported SIX pages failing 'DB empty -> empty-state (no error)'. Every one read db=0, and the cause was not the pages: the hive UUID hardcoded as the battery's fallback (636cf7e8-...) DOES NOT EXIST — a reseed removed it, and every instrument still pinned to it began measuring an empty world. It does not error and it does not skip; it renders plausible, specific, entirely fictional page defects and sends you to read page code that was never wrong. Seventeen REGISTERED instruments were pinned to hives that are gone. Scoped deliberately: only files the suite actually runs (registered scripts, their .mjs helpers, and specs) — an abandoned scratch diagnostic pinning a dead hive is dead code, not a live lie, and including them returned 24 hits of mostly noise. Two exemptions, both principled: the all-zeros UUID is deliberately unresolvable (it proves a NEGATIVE — a caller with no tenancy), and a UUID the file itself INSERTs is self-minted inside a rolled-back probe and is SUPPOSED not to exist (the first cut flagged 37, most of them correct code). The durable fix is dynamic resolution — read-battery now resolves the signed-in supervisor's own most-populated hive with a deterministic tie-break — and this gate makes the rot LOUD in the meantime: one line naming the file instead of an afternoon of phantom triage.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "marketplace-state-inducers",
        "script":  "tools/validate_marketplace_state_inducers.py",
        "args":    [],
        "label":   "MARKETPLACE STATE INDUCERS — the two bank states SQL altitude cannot reach. TB-STATE-inducers induces `empty`, `filtered0` and `edge` in rolled-back SQL and deliberately stops there; `error` (the listings read FAILS, induced by aborting that request at the network layer) and `degraded` (the device is offline, induced at the browser-context level rather than by stubbing navigator.onLine, which would test the stub instead of the guard) are BROWSER facts and live here. WHY THE `error` ONE IS THE POINT: a failed read and an empty result are the same thing to a row count, and this platform has already been bitten by that — read-battery once reported SIX named page failures, all 'DB empty -> empty-state (no error)', and none were real. From the USER's side the ambiguity is worse: a seller whose query merely failed must not be told 'be the first to sell', because that reads as *your listings are gone*. marketplace.html already gets this right — `_loadError` is documented at line 1064 as 'P7: a FAILED listings fetch must render an error state, not the first-run be-the-first-to-sell CTA' — but that behaviour had NO browser test, because a static grep cannot prove which branch renders when the network actually fails. This gate LOCKS the fix rather than re-implementing it, and asserts the CTA is absent as well as the error being present. TWO THINGS THE SPEC HAD TO GET RIGHT, both learned by getting them wrong first: (1) POLL, never sleep-then-assert — the page RETRIES the read (abort count climbs 12 -> 20 -> 32) and declares failure only once retries are exhausted at ~8s, so a 2.5s sleep measured the retry budget and failed while the product was correct; (2) assert INSIDE #listing-grid, never over body.innerText — both the error copy AND the CTA exist elsewhere in the document as other sections' markup, so a whole-page match goes green for the wrong reason, and innerText silently omits anything in an inactive tab. The offline half requires the guard to BOTH refuse and announce, including the sentence that nothing was sent: a guard that refuses in silence is the failure mode this platform found live when a centralised offline guard produced no toast because showToast is page-local. Both assertions are non-vacuous by construction — the error test fails if the request was never intercepted, the offline test fails if whRequireOnline is absent rather than merely permissive. skip_if_fast: browser minutes.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "guard-mutation-score",
        "script":  "tools/validate_guard_mutation_score.py",
        "args":    [],
        "label":   "GUARD MUTATION SCORE — would the marketplace test bank NOTICE if a guard behaved differently? The bank's SQL lane is 130/130 green and the transition board reads 99.6%; both say the cells RAN and agreed with the guards, and neither says anyone would have noticed had a guard changed. The 2026-07-30 triage is why that distinction is not academic: of seven suite failures, FOUR were defects I had just introduced, two were instruments, one was contamination, and ZERO were product defects the suite had found — every genuine defect came from BUILDING a new instrument, not from a gate going red. Mutation testing is the discipline for exactly this, and the research is blunt: a suite with 100% line coverage can score BELOW 50% when assertions are weak. HOW: for each of the four status-machine guards (service_requests / service_credit_topups / marketplace_orders / marketplace_listings) it applies semantically meaningful operators — negate the party gate, drop it entirely, force v_is_party false, force v_is_client/v_is_matched_provider true, make the admin bypass unconditional again, turn a `raise exception` into `return new` (fail OPEN), widen an authorised from-state list — then re-runs ONLY that table's bank cells and requires at least one to go RED. Each mutant carries exactly ONE fault, because two can mask each other. SAFETY: the mutated CREATE OR REPLACE is injected INSIDE each cell's own begin/rollback, so the mutation and the cell that judges it live and die together; DDL is transactional, so a crash cannot leave a weakened guard installed, and no migration is ever written. The run asserts 0 mutated guards persist afterwards. HONESTY: a SURVIVOR is a punch-list item naming a behaviour change no cell objected to; a MALFORMED mutant (will not compile) is an operator bug, discarded and reported rather than inflating the score; an UNREACHABLE mutant is excluded WITH a printed reason, because a silently-excluded mutant is how a mutation score gets flattered — the same no-silent-skip rule this arc applied to the anon/admin partitions. THE FIRST RUN CAUGHT MY OWN INSTRUMENT: it reported guard_service_topup_status at 0% on 1 cell, because authored probes carry no `transition` field and my selection could not see them — while TB-I2 was asserting precisely the top-up self-deal those mutants create and reading the credit ledger back. Probes now declare `covers_tables` explicitly (auditable, cannot drift silently). ★AND THEN IT REPORTED A FABRICATED 100% THREE TIMES RUNNING (27/27, 36/36, 42/42), all of which were recorded as verified before being caught: `pg_get_functiondef()` returns CREATE OR REPLACE with NO trailing semicolon, so the injected definition swallowed each cell's next statement and every mutated run died on a syntax error before one assertion executed — and because the oracle reads an ERROR as a REFUSAL, negative cells passed silently while positive cells failed, so every mutant looked killed by a fixture that had never run. The honest score was 50.0%. It was caught by an operator written EXPECTING a survivor coming back killed on a branch no fixture could reach: a kill that is impossible on the evidence is a report about the instrument, not the code. Three sibling defects had also flattered the number — an `is_party_false` operator injecting a `false or` PREFIX (false OR X is X: an unkillable no-op counted as a SURVIVOR), then `false and` on guards whose party test is a DISJUNCTION ((false and A) or B is B, so it silently collapsed), a duplicate operator under re.IGNORECASE inflating the denominator, and a mutated-guard leak check still grepping for the first draft's mutation text, i.e. a safety check that had silently stopped checking (it now compares each guard's definition byte-for-byte against its pre-mutation capture). THE HONEST MEASUREMENT THEN FOUND THE REAL GAP: guard_service_request_status scored 31.6% — 13 of 19 faults surviving across 107 cells — because every cell in the bank derives from the authorised-TRANSITION set, so every cell is an UPDATE ... SET status, and two whole regions of each guard had never been entered: the TG_OP='INSERT' branch (what state a row may be BORN in — a top-up born `verified` mints credit without ever entering the verification path) and the `status unchanged` branch (field reassignment, ownership transfer, a stranger's edit). TB-BIRTH, TB-FIELD and TB-MINT close those. THE RATCHET IS NOW FORWARD-ONLY ON THREE AXES, because adding operators legitimately lowers the score and a score-only ratchet called that a REGRESSION and failed the gate — which would have pressured me to drop the new operators or fake the baseline: `killed` may never fall (the absolute count of faults the bank catches), `score` may fall only when `viable` GREW (new questions asked), and `fixture_kills` may only fall — a mutant that dies because a cell could not RUN is not a mutant the bank noticed, and a spike in it is the exact signature of the broken injection above, which the score alone could never have seen since the fabricated 100% and the honest 100% are numerically identical. Self-test proves the harness measures CELLS and not scaffolding (one derived cell kills 1, the 103-cell derived grid kills 6, the full 109 kills 18) and discloses that 12 of 18 kills come ONLY from authored probes — the derived grid is broad and shallow, which is the standing punch list. skip_if_fast because it re-runs cells per mutant.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "fetch-retry-contract",
        "script":  "tools/validate_fetch_retry_contract.py",
        "args":    [],
        "label":   "FETCH RETRY CONTRACT - one retry for idempotent READS, never for writes. fetchWithTimeout (utils.js) retries ONCE on a transport failure, because two gates flaked on that exact shape: push-runtime-delivery went red once against four greens, and the Playwright smoke tier carries an intermittent Supabase blip. Neither was a product defect and neither was a timeout - the wrapper's budget is 45s and both failures landed in milliseconds, so they were the network briefly refusing a connection. Widening each spec's budget would have measured network weather instead of the product, so the fix went to the source. THE RETRY IS SCOPED BY HTTP METHOD, NOT BY AN OPT-IN FLAG, deliberately: the helper cannot know whether its caller is safe to repeat, a flag can be forgotten at any of ~20 call sites, and a retried write is how one payment becomes two. GET is idempotent by contract, so every write method is excluded BY CONSTRUCTION rather than by discipline. This gate asserts four properties, and the two that must NOT retry are the ones that license the feature at all: a GET retries once and resolves on the second attempt; a POST is NEVER retried and its error propagates; an AbortError (the timeout path) still returns null on the FIRST attempt, because silently doubling a budget breaks the contract callers reason about - and three callers were just fixed for mis-handling that very null; and a persistently dead endpoint stops at EXACTLY two attempts rather than looping, the recursion guard being the only thing between 'one retry' and an unbounded budget. The assertions run against the SHIPPED text of utils.js - the helper is lifted out of the real file rather than copied into the test - so the gate cannot drift from the code it guards, which is the failure mode of every hand-mirrored fixture this platform has found. Invoked via node directly, never npx, because this repo's path contains an ampersand that npx's own path resolution splits on. Static/fast, no DB, no browser.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "audit-actor-hive-scoped",
        "script":  "tools/validate_audit_actor_hive_scoped.py",
        "args":    [],
        "label":   "AUDIT ACTOR RESOLUTION — every audit trigger must resolve the acting worker IN THE AUDITED ROW'S HIVE. Seven triggers do `SELECT hm.worker_name INTO v_actor FROM hive_members hm WHERE hm.auth_uid = auth.uid() ... LIMIT 1`, and two of them (fixed by mig 20260730000007) did it WITHOUT constraining the hive. `LIMIT 1` with no ORDER BY and no hive predicate picks an ARBITRARY membership, so a member of two hives could have an amendment in hive A logged under the worker_name they use in hive B — the same limit(1)-picked-the-wrong-hive shape this platform has been bitten by before. MEASURED, not assumed: it is LATENT rather than live, because there are 2 multi-hive members today and ZERO use a different worker_name across memberships, so the arbitrary pick currently returns the same string either way; it becomes a real misattribution the first time one person is 'Pablo Aguilar' in one hive and 'P. Aguilar' in another, which needs no code change to happen. WHY THIS IS A STATIC GATE AND NOT A BANK CELL: the fix is correct by construction but NOT verifiable by an outcome test, and I proved that rather than assuming it — a behavioural probe manufactured the missing state (two hives, deliberately different names for one person, an amendment in hive B), then restored the PRE-FIX definition inside the same rolled-back transaction to watch it fail, and it did NOT fail: the arbitrary LIMIT 1 returned the hive-B row anyway, so the probe reported the correct actor in BOTH worlds. A test that passes against the bug is not evidence, and banking it would have been precisely the false-green this platform keeps finding — so the property is locked where it IS deterministic, in the source. The check requires the predicate in the SAME STATEMENT as the lookup, because several of these functions also read hive_members elsewhere for a role check and accepting that would let an unscoped actor lookup hide behind an unrelated scoped query. Self-test strips the predicate from one function THROUGH THE READER (nothing on disk or in the DB is touched) and requires the gate to go red naming it. Static, fast, always runs.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "membership-auth-uid-resolution",
        "script":  "tools/validate_membership_resolved_by_auth_uid.py",
        "args":    [],
        "label":   "MEMBERSHIP RESOLVES BY AUTH_UID, NOT DISPLAY_NAME — a CROSS-TENANT PRIVILEGE ESCALATION a self-rename could drive, found 2026-07-31 while building behavioural teeth on the shared tenancy helper. `v_worker_truth` is the membership anchor `_shared/tenant-context.ts::resolveTenancy` trusts, and through it 30 SERVICE-ROLE edge functions decide which hive a caller belongs to. Its membership join was `LEFT JOIN hive_members hm ON hm.worker_name = wp.display_name` — keyed on a DISPLAY STRING, not an identity. `worker_profiles.display_name` is UPDATE-granted to authenticated/anon, the RLS policy `profiles update own` (USING auth.uid()=auth_uid, no WITH CHECK) lets a user set it to ANY value, and there is NO UNIQUE constraint on it. So a member of hive A renames their own profile to a member of hive B's display name and the view joins their auth_uid to hive B's membership row. PROVEN, rolled back: Pablo Aguilar (a member of Manila Electronics, NOT of Baguio Textile Mills) runs `update worker_profiles set display_name='Leandro Marquez'` as himself under RLS (allowed), then resolveTenancy(<pablo>, <baguio>) run SERVICE-ROLE exactly as the edge functions run it returns {ok:true, role:'supervisor'} for a hive he never joined. The helper itself was correct — it filters v_worker_truth on auth_uid AND hive_id AND active — the VIEW lied to it. Why anon/authenticated did not already leak it: v_worker_truth is security_invoker, so under the caller's own role RLS on hive_members hides other hives; but the edge functions call it on a service-role client (RLS bypassed) scoped only by the client-supplied hive_id, so for them the phantom row is fully visible. FIXED by 20260731000001, which re-keys both the membership join and the active_hive_count subquery on the IMMUTABLE auth_uid — proven behaviour-identical on current data (all 17 active memberships carry a non-null auth_uid; name-keyed and auth_uid-keyed joins return the SAME 17 rows, 0-row delta), so no legitimate resolution changes and only the rename attack is closed. THIS GATE IS A BEHAVIOURAL PROBE, NOT A STATIC ONE, because the escalation is DETERMINISTIC (unlike the audit-actor lookup, whose failure was non-deterministic and had to be locked in source): it discovers an (attacker not in hive H, victim active in H) pair from live data, and inside ONE rolled-back transaction renames the attacker to the victim's name as `authenticated` (proving the rename is actually allowed), asks the REAL view under service_role whether the attacker is now a member of H (MUST be 0), then mutates the view BACK to the name-keyed join and asks again (MUST be >=1 — the teeth: a probe that cannot reproduce the bug proves nothing), then rolls back and re-reads the live definition to confirm no mutant persists. Self-test control: WITHOUT the rename even the name-keyed mutant escalates 0 rows, proving the escalation is caused by the rename and nothing else. Sibling *_truth views that name-key a DECORATION join (skill_badges, achievements, assignment, worker_skill) were triaged: none is on a service-role authz-resolution path (0 of the sensitive ones have any edge-fn consumer; the two used by orchestrators scope by hive_id at query time and carry auth_uid in their base) — recorded as a lower-severity hygiene backlog, not this critical class. skip_if_fast is OFF: it is a fast rolled-back probe, and a tenancy escalation is worth the seconds.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "tenant-context-contract",
        "script":  "tools/validate_tenant_context_contract.py",
        "args":    [],
        "label":   "TENANT-CONTEXT HELPER CONTRACT — behavioural + mutation teeth on `_shared/tenant-context.ts`, the tenancy boundary 30 edge functions trust. It is imported by 42 functions; 30 route their tenancy decision through resolveContext/resolveTenancy. FOUR registered gates already 'cover' it (edge-fn-auth-gate, public-fn-authz, gateway-bypass, public-fn-write-authz) and EVERY ONE is a regex marker over CALLER source — it asserts callers IMPORT the helper — so a weakened isServiceRoleBearer or a dropped 401 guard would pass all four. This gate exercises the helper's ACTUAL branch logic. IT CANNOT DO SO OVER HTTP: the edge runtime serves a CACHED module, proven 2026-07-31 with a sentinel — the message string of resolveTenancy's 403 was changed on disk and the running function kept returning the ORIGINAL over two calls two seconds apart. A mutation harness that edits the file and calls the function over HTTP would therefore score EVERY mutant 'killed' while nothing actually changed — the exact fabricated-100% shape the guard mutation arc already corrected once (a suite that never ran, reading green). So the runner (tenant_context_contract.mjs) loads the REAL helper under Node v24, which strips the TS types natively — only the type-only SupabaseClient import is neutralized to `type SupabaseClient = any`, behaviourally identical after stripping — runs its functions against a stubbed Supabase client that records every .eq() filter, and MUTATES the source text to prove the assertions bite. 16 behavioural assertions: a service-role bearer is accepted on EXACT match only (a prefix, a superstring, and empty are all rejected); with no env key configured ANY bearer is rejected (fail-closed); a service-role bearer resolves isServiceRole with authUid null; a user bearer resolves authUid from the JWT; null authUid is 401; an active member is ok; the membership lookup is filtered by auth_uid AND hive_id AND active status; a non-member is 403; a hiveless caller with a profile is solo-ok and without one is 403. SEVEN mutants, 6 viable all KILLED: exact-match weakened to a prefix; the empty-bearer guard dropped; the null-authUid 401 removed; the non-member 403 removed; the hive_id filter dropped; the active-status filter dropped. ONE is EXCLUDED as equivalent WITH a falsifiable mechanism — dropping the redundant Boolean(key) conjunct cannot change any result (bearer===key with a truthy bearer already implies a truthy key, and a shared '' short-circuits on Boolean(bearer)) — and if that mutant is ever KILLED the run fails as a STALE EXCLUSION, the same discipline the guard arc used for its six exclusions. The DB-level escalation (a self-rename into another hive) is locked SEPARATELY by membership-auth-uid-resolution; this locks the helper's own service-role / null-auth / non-member branches. Node directly, never npx (this repo's path contains an ampersand npx mis-parses). Static/fast, no DB, no browser.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "embedding-space-integrity",
        "script":  "tools/validate_embedding_space_integrity.py",
        "args":    [],
        "label":   "EMBEDDING SPACE INTEGRITY - every corpus must live in exactly ONE vector space, matching its registry pin. Caught live 2026-07-31: fault_knowledge held 534 rows in bge-small-en-v1.5-local while a newly written pm_knowledge row came back nomic-embed-text-v1_5. Both writes SUCCEEDED and nothing errored - but a vector embedded by a different model lives in a DIFFERENT GEOMETRY, so cosine against it is noise: the row is silently unfindable AND can outrank real matches. A row COUNT cannot catch this (every row is present, non-null, correctly shaped); only the model column distinguishes a usable vector from a useless one. Running it immediately found MORE than the row that prompted it: skill_knowledge sits ENTIRELY in nomic space (4 rows), so that corpus is unusable against bge queries, and three different tag strings were in play for the same model. Asserts: one distinct embedding_model per corpus, no NULL model (which would make single-space unprovable), and agreement with the registry pin so ingest and query cannot drift into different spaces. Corpora are DISCOVERED from the catalog, so a new knowledge table is covered the day it appears. FIX is DELETE-first re-embed, never an upsert - a hash-keyed upsert will not replace a vector when only the MODEL changed and the text did not. Self-test proves the detector on synthetic input (split caught, NULL caught, pin-disagreement caught, clean corpus accepted) and main() refuses to report if it fails.",
        "group":   "AI Validation",
        "severity": "fail",
        "skip_if_fast": True,
    },
    {
        "id":      "knowledge-is-retrievable",
        "script":  "tools/validate_knowledge_is_retrievable.py",
        "args":    [],
        "label":   "KNOWLEDGE IS RETRIEVABLE - a logbook entry is the hive's memory of a failure and earns its keep only if someone can FIND it months later, which means reaching fault_knowledge (the embedded, semantically searchable copy keyed logbook_id). A row with no fault_knowledge row is WRITTEN-ONLY: on the board, invisible to every search, RAG answer and 'has this happened before?'. Measured 2026-07-31: 3,811 qualifying entries, 533 retrievable (14.0%), 3,278 written-only. The denominator is honest - embed-entry SKIPS an entry whose composed text is under 50 chars, so this gate composes the SAME text the function does (Equipment/Problem/Root cause/Action taken/Lesson learned/Category) and counts only rows that would actually qualify; on this database ZERO rows are short enough to be skipped, so the 86% gap is real and not an artifact of the filter. Self-test asserts the composition reproduces the function's own 50-char rule on a rich-vs-bare pair, because a denominator that does not match the product invents a backlog. WHY THE BACKLOG EXISTS: the trigger meant to embed these rows POSTed them to a PRODUCTION url (see local-triggers-dont-call-prod), so embeddings landed in production while the local index stayed empty, and that trigger is now DISABLED. Backfilling means 3,278 free-tier embedding calls - a costed decision, not something a gate does behind anyone's back - so this is FORWARD-ONLY: the uncovered count may FALL, never rise. It does not fail on the existing backlog; it fails when a NEW write surface puts knowledge on the board without indexing it.",
        "group":   "AI Validation",
        "severity": "fail",
        "skip_if_fast": True,
    },
    {
        "id":      "credit-economy-simulation",
        "script":  "tools/simulate_credit_economy.py",
        "args":    ["--runs", "400"],
        "label":   "CREDIT ECONOMY SIMULATION - generated job lifecycles driven through the REAL guards, triggers and ledger inside ONE transaction that is ROLLED BACK, so no simulated peso survives. THIS IS THE HONEST FORM OF `massive simulation`: tools/run_companion_100turn_flywheel.py advertises 100 turns x 1225 tests and FABRICATES every outcome (simulate_turn_observations draws pass rates from random.gauss against a sigmoid), which for a money economy is worse than no test because it produces a confident number describing transactions that never happened ([[feedback_measure_the_worked_state_not_the_generator]]). A single probe proves a rule on one job; this asks whether it still holds across hundreds, over SIX exit paths so all 12 request states are genuinely reached. Six invariants: net take = commission - cashback over settled GMV (MEASURED, not asserted - it reads ~4.8% blended, not the headline 4%, because consumer jobs carry 10% commission and industrial 5%, so the real rate depends on MIX); solvency sampled DURING the run rather than only at the end, since a balance that went negative and came back would otherwise be missed; exactly-once commission and cashback per settled job under a deliberate double-tapped release; worst liability cover reported rather than the average, because the study's failure modes are TAIL events; order-independence as a metamorphic relation (same two top-ups in either order reach the same balance - no expected value needed, which is why this property had no test); and a reached-state histogram, because a run that never produced an `expired` or `disputed` arc has not tested them and must SAY so ([[feedback_a_skipped_partition_reads_as_a_covered_one]]). TEETH PROVEN by --inject double-mint / ledger-delete / negative-consumer, each of which must turn the run RED. That teeth test caught ITSELF first: the injections originally fired at i=2, and 2 %% 6 = 2 is the provider-cancel path which never settles, so two of the three reported PASS while never executing - and double-mint turned out to be STRUCTURALLY impossible while the partial unique index stands, so it now drops that index first and asks whether the invariant would notice if the guarantee were ever removed. The daily row cap is announced past via the platform's own workhive.row_cap_system_write GUC and that is stated in the code rather than done silently: it is a real anti-abuse control with its own gate, it fired correctly on synthetic volume, and nothing else is bypassed.",
        "group":   "Platform",
        "severity": "fail",
        "skip_if_fast": True,
    },
    {
        "id":      "money-economy-board",
        "script":  "tools/money_economy_board.py",
        "args":    ["--check"],
        "label":   "MONEY ECONOMY BOARD (M1-M8) - the anti-drift compass for the credit-economy arc, per [[feedback_follow_framework_antidrift_before_building]]: the structure is laid out BEFORE the build and the board is what decides what to do next, so a tangent cannot quietly replace the roadmap. Eight MEASURED rows - M1 money spine (payment record / cashback wired / commission bills what was paid / dispute path), M2 knobs READ, M3 deterministic SQL money cells, M4 the 12 request states reached by a LIVE walk, M5 diverse-persona pairings scored task-success, M6 the six economic simulation invariants, M7 the fraud model, M8 money gates registered. WHY A COMPUTED BOARD AND NOT A TABLE IN A DOC: a table drifts from reality the moment work starts and then it flatters; every row here is read from the live catalog, the test bank and this very registry, so it cannot claim a unit that does not exist. The denominators are fixed in the file BEFORE building precisely so they cannot be shortened later to manufacture a 100% ([[feedback_short_denominator_is_a_false_100]]). DONE = EVERY ROW AT 100%, never the greenest one - a single headline metric at 100% has already masked an open axis here ([[feedback_phase_table_is_one_axis_build_the_compass]]) - and every owed item prints WITH ITS REASON rather than being averaged away ([[feedback_a_skipped_partition_reads_as_a_covered_one]]). The M2 bar is deliberately strict: a knob counts as READ only when its consumer can actually FIRE (has a trigger, or is called), because the first draft credited cashback_pct to mint_service_cashback - a function that reads it and has NO trigger, so it mints for nobody. Forward-only ratchet; --check fails on ANY row regressing.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "persona-task-success",
        "script":  "tools/validate_persona_task_success.py",
        "args":    [],
        "label":   "PERSONA TASK-SUCCESS - can a DIVERSE human finish the money task, not just an idealised one? (Ian 2026-07-31: consider the diversity of human beings.) Every journey in the bank implicitly walked a competent, sighted, literate, English-reading, fast-network, calm user, and almost none of this platform's real users are all six at once - PH plant technicians in their fifties, first-time e-wallet users, someone outdoors in glare wearing gloves, someone on 3G. DIVERSITY IS NOT A PAGE PROPERTY, it is WHO IS WALKING, so it lives on the journey axis. DIVISION OF LABOUR, deliberately: UFAI grades the PAGE (validate_service_ufai_deep measures 390/1280 tap targets and overflow), validate_i18n_coverage owns language, validate_clickable_keyboard_a11y owns keyboard - none can answer 'could THIS PERSON complete THIS TASK'. The 25 personas and their journey pairings live in tools/service_personas.mjs as RUNTIME CONDITIONS (viewport, zoom, colour filter, throttle, locale, input delay), not comments, and 129 unpaired combinations are recorded WITH REASONS rather than dropped - 25 personas x 7 families is 175 walks nobody runs, and an unrunnable matrix silently becomes an unrun one. Seven checks on the families where failure costs pesos: 12 states carry DISTINCT TEXT labels not colour alone (P-COLORBLIND); the release screen discloses who gets what, that the platform never holds the money, and what happens if the job was bad (P-SCAMWARY, the persona who decides whether this economy works at all); the min-balance refusal is announced AND says how to fix it (P-UNBANKED); the release resists a double tap (P-IMPULSIVE); money terms are translatable (P-FILIPINO); the map has a text equivalent, since a map is unusable by a screen reader and without a list discovery is closed entirely (P-SCREENREADER); and a 48px target floor (P-GLOVED, a real industrial constraint). ITS OWN FIRST TWO READINGS WERE INSTRUMENT BUGS: it reported the 12 status labels MISSING because its regex assumed quoted object keys while the source uses bare ones, and reported the min-balance refusal owed because it read only marketplace.html while the message lives on marketplace-seller.html. Both are fixed and both are why it now reads the real SVC_CHIP mapping across BOTH money surfaces instead of pattern-matching one.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "commission-leakage",
        "script":  "tools/validate_commission_leakage.py",
        "args":    [],
        "label":   "COMMISSION LEAKAGE - found by ATTACKING, not by testing (TB-FRAUD-money-economy-attacks A3). Commission bills what was actually PAID, which is the honest base and a deliberate fix, but it hands both parties a lever: a client and provider who agree a PHP50,000 job and declare PHP1 on the payment record pay PHP0.10 instead of PHP2,500. The attack probe measured exactly that, and NOTHING refused it or noticed. This DETECTS rather than refuses, on purpose: a declared payment below the quote is often legitimate (job under scope, a discount, part-payment in materials), and refusing those would block honest work and push people off-platform entirely, which costs more than the leak. So the platform bills honestly on what was declared and MEASURES the gap - the fraud model's standing disposition that an attack is either refused or DETECTED AND NAMED, never silently absorbed. Measures, for every settled job with a payment record, the ratio of declared to agreed (selected offer price, else catalogue rate, else stated budget); severe below 50% and only on jobs over PHP1,000, since a PHP200 job declared at PHP80 is noise. Forward-only ratchet on the severe COUNT so an existing backlog does not block the build while a NEW pattern shows immediately; --accept only ratchets DOWN. Self-test proves the arithmetic on the real attack (PHP1 of PHP50,000 caught, PHP1,800 of PHP2,000 not) without needing the database.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "marketplace-sim",
        "script":  "tools/run_marketplace_sim.py",
        "args":    [],
        "label":   "MARKETPLACE SIMULATION - 115 live scenarios composed from DECLARED dimensions (Ian 2026-08-02: 'we need around diverse 100+ live simulation tests, and from there we could iteratively improve the entire marketplace'). GENERATED by tools/build_marketplace_sim_scenarios.py rather than hand-written, because 100+ hand-authored scenarios drift, duplicate and skew toward whatever the author found interesting that day - composing them from dimensions makes coverage auditable by family, role-pair, persona and defect class, and proves no dimension was skipped. The dimensions are all already measured here: the 12 request states (from the CHECK constraint, not a guess), the 7 journey families, the 25 personas in service_personas.mjs, the 8 user-facing defect classes found on the live walks of 2026-08-01/02, and the money invariants. TWO RULES ENFORCED AT GENERATION TIME, both learned the hard way: every state-CHANGING scenario must declare BOTH roles (feedback_two_sided_journeys_need_a_role_pair measured FOURTEEN of 54 journeys as one-sided - a walk that drives one side proves nothing about what the other sees), and every scenario must assert something FALSIFIABLE rather than 'the page loads', since a vague assertion reports green forever. `mutates` is DECLARED, never inferred - the first validator guessed it from family+oracle and immediately produced two false flags on read-only checks. THE RUNNER REPORTS EXECUTED, NEVER AUTHORED: 15 scenarios are decidable against the live database and run here; 97 need a real browser and 3 need human judgement, and every one of those is listed BY ID as owed-with-reason rather than counted. Reporting 115 as though it were 115 tests would be exactly the false green this bank exists to prevent.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "hail-geo-coverage",
        "script":  "tools/validate_hail_geo_coverage.py",
        "args":    [],
        "label":   "HAIL GEO COVERAGE - is the broadcast radius filtering anything? FOUND ON A LIVE CLIENT WALK 2026-08-01: a hail placed through the real UI lands with location IS NULL, because the form asks for a free-text address and never captures a point (there is no getCurrentPosition anywhere in marketplace.html). That is not cosmetic - the accept gate reads `if v_req.location is not null and v_provider.base_location is not null and not st_dwithin(...)`, so a NULL location makes the whole distance test SKIP while the request still carries broadcast_radius_m=5000 and the UI still speaks of notifying NEARBY providers. The number is displayed and inert, and a provider on the far side of the country is as eligible as one next door. IT STAYED HIDDEN BECAUSE THE SEED DATA IS HEALTHIER THAN THE PRODUCT: every seeded request carries geo, so probes, journeys and scoreboards all see a working radius, and only a hail created through the real form exposes it - the mirror of the dead-fixture class, where seeded state invents a reality the product does not have. This gate deliberately does NOT fail the build for the missing capture: obtaining a client's coordinates needs either a browser geolocation PROMPT or an external geocoder, and both are product/privacy decisions that belong to Ian rather than to a validator. What it does is make the gap MEASURED and FORWARD-ONLY - the count of geo-less hails may never RISE, so it ratchets toward zero if capture is ever added and goes red the day someone adds another geo-less write path. Self-test proves the arithmetic (an inert radius is reported, a fully-geocoded set is not) without touching the database.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "credit-solvency",
        "script":  "tools/validate_credit_solvency.py",
        "args":    [],
        "label":   "CREDIT SOLVENCY - are the credits given away backed by anything? MARKETPLACE_CREDIT_SUSTAINABILITY §5 named liability cover the number that matters, and §4.5 named spending the float the most dangerous failure mode BECAUSE IT IS INVISIBLE UNTIL IT IS FATAL. Credits enter three ways and they are NOT equal: topup is backed by CASH (a provider paid GCash), cashback is backed by REVENUE (funded out of commission, and the hive_service_settings CHECK already refuses cashback_pct > commission_pct + listing_fee_pct so it cannot outrun the take per transaction), and voucher_grant is backed by NOTHING - platform-funded acquisition minted from thin air. Vouchers are therefore the LIVE GAP: nothing currently bounds them, and a generous promo is indistinguishable from an accident until the float is gone. The invariant held here is `unbacked credits (vouchers) <= credits actually EARNED (commission)` - if the platform has given away more than it has ever earned, it is funding acquisition out of other people's prepayments, which works right up until they spend them. ALSO ASSERTED: a negative CONSUMER balance is impossible by construction (consumers only receive cashback and spend it), so one appearing means credits were spent that were never minted; a negative PROVIDER balance is expected and fine, since commission is debited on completion and min_list_balance is what keeps wallets funded. The arithmetic is a pure function so the self-test proves it catches over-granting and negative consumer balances and passes a healthy ledger WITHOUT needing the real ledger in any particular state - and an empty ledger PASSES vacuously while saying so, rather than reporting a false green. Reads service_credit_ledger via docker exec psql; skips when the DB is down.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "payment-rails",
        "script":  "tools/validate_payment_rails.py",
        "args":    [],
        "label":   "PAYMENT RAILS - three GCash accounts meet in this product and only ONE of them may ever be on a given screen. WorkHive has no business registration and therefore no merchant account, so every rail is a PERSONAL number: a buyer pays the PROVIDER's own GCash directly and the platform never touches it; a provider tops up credits by paying the FOUNDER's personal 0995 009 2416; a credits spend moves no GCash at all, being a ledger transfer between two wallets. THE INVARIANT: the founder's number may appear ONLY on the provider's top-up card. Put it on a buyer-facing payment step and the buyer sends job money to a person who is not party to the job, cannot fulfil it, and cannot reconcile it against any request - and NOTHING ERRORS. The money is not lost to a bug but to a stranger's honest reading of the screen, which is worse, because nobody finds out until the provider asks where their payment is. This is also the exact friction Ian named by hand ('I want it hassle free for my users, like the hassle of payment two gcash accounts'): a buyer must see exactly one number, the provider's. Four assertions: every occurrence of the founder number sits on an allowed surface; no buyer-facing payment surface contains it in ANY spacing or punctuation (the regex tolerates '0995 009 2416', '0995-009-2416' and '09950092416' as one number); the buyer's confirm step states that WorkHive holds no money, which is the sentence a wary first-timer actually decides on; and that step names the PROVIDER as payee so 'who do I pay' has one answer where it is asked. Comments and doc blocks are stripped before matching - only RENDERED strings can mislead a person. Teeth: planting the founder's number on marketplace.html's payment step makes this FAIL naming that surface and that consequence; selftest proves all four failures are caught and a correct topology passes. Static, fast, no DB.",
        "group":   "Security",
        "severity": "fail",
    },
    {
        "id":      "no-client-truncate",
        "script":  "tools/validate_no_client_truncate.py",
        "args":    [],
        "label":   "NO CLIENT TRUNCATE - RLS IS NEVER CONSULTED FOR TRUNCATE, so the grant is the only control. FOUND 2026-08-03 by the live-MCP flywheel, three steps from where it started: walking G-trust as an anonymous visitor showed every seller as an unverified Bronze; the read policy turned out to be signed-in-only; widening the READ meant auditing the WRITES; and the write privileges included TRUNCATE. Proven as `anon` in a rolled-back transaction - `truncate table public.marketplace_sellers cascade` SUCCEEDED and the table read 0 rows afterwards. Every seller on the platform, removed by someone who never signed in. Blast radius measured at the time: 140 tables anon-truncatable, 142 for authenticated, ~104,000 rows. WHY EVERY EXISTING GATE MISSED IT: validate_unprotected_write_grant holds 'a base table may grant an end-user write verb ONLY IF row-level security is enabled on it', which is correct for INSERT/UPDATE/DELETE and INERT for TRUNCATE, because RLS is not consulted for it at all - marketplace_sellers has RLS enabled with a full policy set, so it passed that gate cleanly while an anon TRUNCATE emptied it. The July sweep had even flagged the shape in its own notes (an anon TRUNCATE on marketplace_listings failed only with 0A000 'referenced in a foreign key constraint', a coincidence of the schema rather than a control) - marketplace_sellers had no such FK, so nothing stood there. Closed by migration 20260803000028 for the public schema plus ALTER DEFAULT PRIVILEGES so new tables cannot re-open it. The storage.* grants are TRACKED rather than enforced and printed every run: they are owned by supabase_storage_admin, postgres is not superuser in this stack and cannot `set role` to it, so no migration this project writes can revoke them - closing those needs a Supabase-side superuser action. Teeth: re-granting TRUNCATE on any public table makes this FAIL naming that exact table; selftest proves it enforces the public schema, tracks the vendor residual rather than hiding it, and stays quiet when clean.",
        "group":   "Security",
        "severity": "fail",
    },
    {
        "id":      "credit-guards-refuse",
        "script":  "tools/validate_credit_guards_refuse.py",
        "args":    [],
        "label":   "CREDIT GUARDS REFUSE - installed is not the same as enforcing, and the credit-posture gate only proves the triggers EXIST. A trigger can be present while its function has been replaced by `return new`, and every existence check in the suite stays green. The plan's verifications #1, #2 and #4 are the same demand in three forms, so all three are walked against the real schema: (1) a listing cannot outrun its reservation - publishing with less than 10% of the price available is refused; (2) an unsold listing costs NOTHING - publish then delist and the balance returns to EXACTLY its starting value, which is the whole difference between a reservation and the listing fee rejected in July, because a fee is consumed whether or not the item sells and a reservation that returns less has quietly become one; (3) a balance DRAINS - a job carries reward_earn OR reward_spend, never both, because with the reward rate and the spend cap both at 10% a job that pays a reward on the job you spent on is a treadmill where the balance never empties and credits stay a liability forever. TEETH: --inject 1|2|3 NEUTERS that guard in-transaction (`create or replace` to `return new`) and requires the refusal to DISAPPEAR - a probe that cannot be made to pass was never testing the guard. THE TEETH MODE ITSELF SHIPPED A REAL BUG worth remembering: `docker exec psql` runs in AUTOCOMMIT, so a bare `create or replace function` is its own transaction and COMMITS. The first version permanently gutted three live guards on the local database while the DO block rolled back exactly as designed and printed TEETH CONFIRMED; the damage only surfaced on the NEXT clean run, which failed two assertions that had passed minutes earlier, and repair meant replaying migrations 09-26 in order (re-applying 08 alone had also reverted the entry_type CHECK, dropping reward_fund). DDL is transactional in Postgres - but only if you open a transaction, so the whole probe is now wrapped in an explicit BEGIN/ROLLBACK and the guards are verified intact after every injected run. Skips cleanly when the stack is down.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "adversarial-personas",
        "script":  "tools/probe_adversarial_personas.py",
        "args":    [],
        "label":   "ADVERSARIAL PERSONAS REFUSED LEGIBLY - the 500-run simulation proved the ECONOMICS hold (a collusive pair extracts PHP0, the spam cap blocks 274,428 listings, sybil is bounded only by ID strength). It never proved the SCREEN refuses these people in words they can act on, and a guard that blocks in silence cannot be told apart from a guard that is not firing. So each of the four personas asserts TWO things: the attack is contained, AND the refusal is a sentence a human could act on rather than a constraint name (a bare 'violates check constraint' fails the bar). Spammer: capped at 3 live listings with 'sell one, or take one down to make room'. Sybil: the second starter grant returns already_claimed. Collusive pair: a naked user-to-user transfer is refused AND circulation delta is exactly 0. Scam provider: the buyer gets a dated objection deadline and raise_service_objection moves the job to disputed. THE PROBE'S OWN THREE BUGS ARE THE REASON IT IS TRUSTWORTHY, and each is a banked class: (1) it read only stdout while every verdict line is a psql NOTICE on stderr, so all four personas reported 'no verdict' - a false red; (2) it probed the spam cap with NO JWT, and guard_first_listings_need_a_sale opens with `if auth.uid() is null return new` (the backend path seeders need), so all 8 listings published and it read as 'the cap does not work' when the probe was never a person; (3) even with an identity, TWO earlier guards fired first - self-publish is refused outright, and then the reservation guard refused for want of credits - so the cap was never consulted and a PASS proved only the outermost gate (the 'survivor masked by a sibling constraint' shape). It now funds the seller and picks one already AT the cap by the cap's own arithmetic, so the deepest layer is the one that answers. Every persona runs inside BEGIN/ROLLBACK because docker exec psql is AUTOCOMMIT; verified to leave the ledger byte-identical and zero residue.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "credit-loop-closes",
        "script":  "tools/validate_credit_loop_closes.py",
        "args":    [],
        "label":   "THE CREDIT LOOP - cash enters once, and the credits go round. This is the central claim of the whole economy and the plan's verification #3, and every OTHER credit gate checks a rule in isolation: the cap binds, the reservation returns in full, earn-or-spend is exclusive, the supply cannot be exceeded. None of them asks the question the design exists to answer - can a provider fund a listing with credits they RECEIVED, without anyone paying in new cash? If the answer is no, this is not a circuit but a prepaid balance that drains one way, every provider must keep buying credits forever, and 'no revenue' quietly becomes 'revenue, collected as float' (Ian: 'I don't have to earn revenue, it is like, I hold the money I get, in a form of credits exchange'). Walks the REAL triggers and the REAL RPC at every step: one top-up funds seller A, A drafts and an ADMIN publishes (self-publish is refused and backend writes are exempt from the reservation guard, so a probe that inserts straight to 'published' as postgres creates no reservation and proves nothing), the reservation is HELD, the listing SELLS and grant_listing_reward hands that reservation to the BUYER, the buyer pays for a job with apply_credits_to_request and provider B RECEIVES the credits, and B then publishes a listing funded ENTIRELY by what B was paid. Also asserts CIRCULATION NEVER MOVES after that single cash entry - every step is a transfer between two wallets, so the ledger sum must be identical start to finish, and that is not hypothetical: apply_credits_to_request shipped writing only the payer's leg, which destroyed the credits and left the platform holding the cash that backed them while every per-side guard passed. Three of its own bugs are documented in-file, each a real class: a fixture seller sitting at guard_first_listings_need_a_sale's cap (the guard was right, the probe picked the wrong person); a job with NO agreed price, so the spend was asking for 10% of zero; and `set local role postgres` WITHOUT clearing request.jwt.claims, which is transaction-scoped in a DO block - the probe kept running as the buyer and blamed the wallet-privacy guard for refusing to show B's balance to someone else. TEETH: --inject spend (the buyer pays in pesos, so B is never funded) and --inject reward (the sale does not hand over its reservation, so the buyer has nothing to spend), each verified to break the circuit. Always rolled back; verified to leave zero residue.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "credit-posture",
        "script":  "tools/validate_credit_posture.py",
        "args":    [],
        "label":   "CREDIT POSTURE - the structural facts that keep WorkHive Credits out of the heavy regimes, asserted against the LIVE CATALOG instead of documented. Migration 20260803000012 stated that this gate asserts the posture; the file did not exist, so for a day the posture was a comment - which is exactly the failure the comment was written to prevent. Five facts, each one well-meaning feature away from disappearing: NON-WITHDRAWABLE (no function matching withdraw/cash_out/redeem_for_cash/payout_credits, because cash redemption is the prong that separates a closed-loop prepaid instrument from e-money, and the BSP moratorium on new VASP authorities in force since 1 Sep 2022 means that reclassification cannot be applied away); NON-TRANSFERABLE (guard_credits_non_transferable installed, so there is no person-to-person movement and therefore no secondary market - the SEC investment-contract framework weights resale most heavily, and no resale means no realizable gain); FIXED VALUE (1 credit = PHP1 exactly, so nothing appreciates and a Howey analysis has no expectation of profit to bite on); CAPPED SUPPLY (issued <= authorised, the ceiling on lifetime liability); and APPEND-ONLY BY PRIVILEGE (authenticated and anon hold no INSERT/UPDATE/DELETE on service_credit_ledger - load-bearing beyond bookkeeping, since a guard was once added to refuse hand-minted positive entries and it broke settlement while defending against something table privileges already made impossible). The named-trigger roster is the part that earns its keep: CREATE OR REPLACE on a guard function is harmless, but DROPPING its trigger silently un-enforces the rule and nothing else in the suite would notice. Its own first run reported two catastrophic failures on a perfectly healthy schema, because psql renders a raw boolean as 't' while the ::text cast in the query yields 'true' - the gate was wrong about the schema, not the schema about itself, so both spellings are now accepted. TEETH: --inject cashout|transfer|cap|rate|append|trigger, each verified to break precisely its own assertion and no other. Reads pg_proc/pg_trigger/information_schema via docker exec psql; skips when the DB is down.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "credit-circuit-sim",
        "script":  "tools/simulate_credit_circuit.py",
        "args":    [],
        "label":   "CREDIT CIRCUIT SIMULATION - do the economy's defaults still deserve their values? Every knob in the credit circuit was chosen from simulation rather than instinct, and TWO were set AGAINST the first instinct because the numbers contradicted it: reward_max_per_listing=500 (measured 4.9x throughput at scale versus a flat 10%, because a flat rate locks PHP2,500 on a PHP25,000 listing and exhausts the supply) and reward_min_per_listing=0 (a PHP200 floor was the MOST HARMFUL knob tested, 66%->38% healthy, since it makes a PHP500 listing reserve 40% of its own value). A design justified by a measurement has to KEEP being measured, or the justification quietly becomes folklore and the knob drifts to whatever felt right later. Seven assertions, each a claim the design rests on rather than a statistic: the per-listing cap raises throughput at scale; the starter grant raises cold-start throughput (the largest single gain, and cold-start failure lands on the DEMAND side as fill rate falling 51%->30%); hoarding raises cash demand ~71% WITHOUT stopping trade (which is why appreciation was dropped - a credit that grows is a credit you hoard); the holding fee separates spam from slow selling (PHP8 honest versus PHP2,400 for 50 junk listings a year); and the supply cap binds at ~20,000 providers. Two more join the economy to the MARKETPLACE, because the first five only measure whether providers can LIST, which is not the question a buyer asks: credit starvation shows up as UNSERVED BUYERS (half the providers starved costs double digits of fill - a provider inconvenience is a demand-side collapse, which is what makes the starter grant an intervention rather than a courtesy), and widening the broadcast radius 15km->30km moves fill by 20+ points (the largest single lever, and a knob we already own - it was INERT for months because UI hails carried no location so st_dwithin was skipped entirely). Only the DELTAS are asserted, never the absolute fill level: this model's baseline differs from the roadmap sweep's because the geography differs, and tuning constants until the number matched the document would be fitting the instrument to the answer it exists to test. TEETH: --inject cap|grant|fee removes a LEVER and --inject fill|radius removes a GATE from the matching chain, each verified to break precisely its own claim and no other - if assertion 6 survived with the credit gate gone it was never measuring starvation at all. It also guards against ITS OWN last bug - an early version reported a catastrophic industrial jam that did not exist, because int(1*0.5) truncates to zero so one-listing providers never sold; a pinned known-good case now fails if that regresses, and main() refuses to report results when the selftest fails. Pure arithmetic, no DB, fast.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "d9-knob-integrity",
        "script":  "tools/validate_d9_knob_integrity.py",
        "args":    [],
        "label":   "D9 KNOB INTEGRITY - the per-hive service knobs (migrations 20260731000007/8/9) must stay SAFE and stay READ. TIGHTEN-ONLY TRUST: per-hive trust thresholds are a forgery vector - a hive that could set gold@1 would mint its own gold sellers and the tier ladder would stop meaning anything platform-wide. The floors (silver >= 11, gold >= 51, gold > silver) are what keep a badge comparable ACROSS hives: a hive may make its OWN sellers work harder, never easier. Drop those CHECKs and the marketplace's headline trust signal becomes self-service, so this gate reads them from the LIVE CATALOG rather than the migration text - what matters is the constraint that IS on the table, not the one a file once declared. THE KNOBS MUST BE READ: a knob nobody reads is write-only configuration, and this was not hypothetical - the trust half shipped UNWIRED for an hour, with tier_silver_sales/tier_gold_sales existing, validated, and consulted by NOTHING but the resolver returning them. So each family must have a real consumer (sweep_service_broadcasts for timing/reach, recompute_seller_sales_and_tier for trust); service_knob() itself deliberately does NOT count, because it RETURNS a value rather than USING one and counting it would let write-only config pass. Its own first run reported a FALSE UNREAD on both families: prosrc is multi-line and psql returns one row per line, so it was reading only each function's first line - the code was right and the instrument was not, which is why the body is now flattened before matching. Self-test refuses to judge constraints on a table it cannot see (a missing table is a FAILURE, never a silent pass). Static catalog read via docker exec psql; skips when the DB is down.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "local-triggers-dont-call-prod",
        "script":  "tools/validate_local_triggers_dont_call_prod.py",
        "args":    [],
        "label":   "LOCAL TRIGGERS MUST NOT CALL PRODUCTION — found 2026-07-31 while extending the S9-knowledge layer. THREE AFTER-INSERT triggers on the LOCAL database (embed-logbook, embed-pm-completions, embed-skill-badges) called supabase_functions.http_request() against a PRODUCTION URL with a SERVICE-ROLE BEARER EMBEDDED IN THE TRIGGER DEFINITION. Three things were MEASURED, not assumed: the definitions carry the production host and a JWT (read from pg_trigger); net._http_response holds delivered responses including 200s from the same day, so pg_net is live here; and the DB container resolves the production host (getent returns an address). So every COMMITTED local insert into those tables POSTed the row to production — and seeding/manual testing hammer `logbook` — meaning dev data flowed into the production embedding store, the mirror image of [[feedback_live_mcp_writes_pollute_test_db]] and worse because embeddings are not obviously reversible. Separately a service-role key BYPASSES RLS ENTIRELY, and this one sat in the local catalog, readable by anyone with catalog access or a dump — a secret in a place secret scanners never look ([[feedback_pasted_keys_in_docs_leak_scanner_blindspot]]). CONTAINED the same session by DISABLING all three (ALTER TABLE ... DISABLE TRIGGER — local, immediate, reversible with ENABLE); they can no longer fire. The gate distinguishes ENABLED (a live outbound path → FAIL) from DISABLED (contained → reported, not failed) from the KEY still being present in the definition (reported every run regardless, because containment is NOT rotation and only Ian can rotate a production credential). The JWT is matched STRUCTURALLY (three base64url segments), never by the word 'service_role', which lives inside the ENCODED payload — the first cut searched for that word and reported clean on a definition that was carrying a key. Definitions are never printed. Self-test proves all four behaviours (enabled-external caught, disabled-external reported as contained not live, embedded JWT caught, clean local trigger accepted) and main() refuses to report if it fails. It also SKIPPED rather than false-passed when its own query errored on a `text || \"char\"` ambiguity — the cast is now explicit. Static catalog read via docker exec psql; skips when the DB is down.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "voice-paraphrase-invariance",
        "script":  "tools/validate_voice_paraphrase_invariance.py",
        "args":    [],
        "label":   "VOICE PARAPHRASE INVARIANCE (MR5) — a worker says the same thing three ways; voice-action-router must pick the same `kind` from its closed vocabulary (logbook.create | inventory.deduct | pm.complete | asset.lookup | query.ask | unknown) all three times. The transform is a PARAPHRASE, the invariant is the route. This is an MR and NOT an eval on purpose: there is no correct wording, and asserting 'this sentence must yield logbook.create' grades a free-tier model's mood ([[feedback_llm_parrots_fewshot_example_codes]]), so expected-kind agreement is REPORTED and only the relation is enforced. THE NON-VACUITY HALF IS THE WHOLE DESIGN, and it is sharper here than in MR1-MR4: a CONSTANT CLASSIFIER IS PERFECTLY INVARIANT — a router answering 'unknown' to everything would score 100% while being useless — so the gate also requires DISCRIMINATION, that the intents do not all collapse to one kind. Invariance alone would have been a metric that improves as the product gets worse ([[feedback_a_metamorphic_relation_needs_a_non_vacuity_check]]). Live and deliberately so: the DETERMINISTIC half of the router (kind allowlist, confidence clamp, slot-fill guard, asset disambiguation) is already locked by tests/voice-router-determinism.spec.ts against _shared/voice-router-core.ts — what no static test can see is the CHOICE the model makes, which is exactly what a paraphrase perturbs. Reuses validate_ai_live_invoke's plumbing (anon-key discovery, persona sign-in, RUNTIME hive derivation so it survives a reseed) instead of restating it. ~12 free-tier chain calls per run against a 50/hour limit. SKIPS rather than fails when the stack is down, the persona cannot sign in, or the model is unavailable — an infrastructure absence is not a product defect. First live run: 4/4 groups invariant, 4 distinct kinds, 4/4 also matching the humanly-expected kind. Banked as TB-MR5-paraphrase-invariance.",
        "group":   "AI Validation",
        "severity": "fail",
        "skip_if_fast": True,
    },
    {
        "id":      "paginated-order-totality",
        "script":  "tools/validate_paginated_order_totality.py",
        "args":    [],
        "label":   "PAGINATED ORDER TOTALITY — every query that pages or truncates must sort by a TOTAL order, i.e. end its ORDER BY with a column unique per row. Found live 2026-07-31 by metamorphic relation MR4 (rank stability), and PROVEN before it was fixed: marketplace.html browsed with `.order('created_at',{ascending:false}).limit(PAGE_SIZE)`, and created_at alone is not total because a bulk import inserts many rows inside ONE transaction where now() is FIXED, so they share an identical timestamp. Postgres promises nothing about the order of tied rows and it genuinely moves — touching an UNRELATED column on one tied row (an ordinary edit; MVCC appends a new tuple at the end of the heap) made 4 of 12 rows come back at a DIFFERENT RANK while the row SET was identical, and adding the unique id as a tiebreaker took that to 0. Under .limit()/.range() the user-visible failure is a row shown TWICE across a refresh or SKIPPED between pages; under .limit(1) it is quieter and worse — 'the most recent X' silently picks an ARBITRARY row among ties, the shape that once resolved the WRONG HIVE for a signed-in worker ([[feedback_resolving_live_is_not_enough_be_deterministic]]) — so limit(1) is IN scope, not exempt. Detection is conservative: a chain counts only when a .from() binds it (so .order()/.limit() on a plain JS array is never flagged), it has at least one .order('col'), and a .limit(/.range( closes it; a chain whose LAST ordering column is unique-by-construction passes. The unique-column list is declared WITH the reason each is unique (id/uuid = primary key; service_area = v_service_area_presence is one row per area, verified 4 rows / 4 distinct; co_number = unique by constraint), because a wrong entry silently converts a real violation into a pass — the same 'an exclusion must name its mechanism' discipline the guard mutation harness uses. Comments are stripped BEFORE scanning, with line numbers preserved: the gate's own first run flagged the very query the MR4 fix had just corrected, because a six-line explanatory comment between `.order('created_at')` and `.order('id')` pushed the tiebreaker outside the chain window — a gate that reddens on a CORRECT fix teaches the wrong lesson and gets worked around ([[feedback_teach_the_gate_not_bend_the_code]]), so that exact shape is now a self-test case. Self-test proves teeth four ways: a known-bad chain must be CAUGHT, a known-good one (id tiebreaker) must PASS, .limit(1) must be treated as pagination, and a tiebreaker separated from its .order() by a comment must still be seen; main() refuses to report a count if its own self-test fails, because a detector that silently stops detecting is this platform's recurring false-green. Forward-only ratchet over 162 known non-total orders across 38 files (169 paginated+ordered chains scanned) — a backlog named rather than averaged away, where the fix is always the same one line: end the ordering with .order('id'). Static file scan, fast, no DB.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "hive-capture-invariant",
        "script":  "tools/validate_hive_capture_invariant.py",
        "args":    [],
        "label":   "HIVE-CAPTURE INVARIANT — a load-time hive capture is only safe while nothing can change the active hive mid-page. marketplace.html does `const HIVE_ID = whHiveId()` once at load and stamps it on every hail and listing, so if the active hive could change while the page is open, work would be filed into the WRONG TENANT. It cannot today: the only pages that write `wh_active_hive_id` are hive.html (the switcher) and index.html (the sign-in bootstrap), and reaching the marketplace from either is a full page load, so the const is always read fresh. That was recorded as the A4 finding on `TB-A345-architecture-quality` — no defect — and it is a conclusion resting on an invariant nobody enforced: add an in-page hive switcher to the marketplace and every subsequent hail carries a stale tenant id with no test going red. Per this platform's disposition rule, a covered-by-nature cell still gets a gate asserting the contract it rests on. TWO ASSERTIONS: (A) the WRITER ALLOWLIST — exactly hive.html and index.html may write the key, and a third page appearing goes red with the instruction to re-check capture scope on every page that reads it, because adding a writer is a decision rather than automatically a bug; (B) THE CAPTURING PAGES MUST NOT WRITE IT — marketplace.html / marketplace-seller.html / marketplace-admin.html must contain zero writers, which is the live-bug condition, since a writer in the same document can run after the capture. CHECKING THE PREMISE CORRECTED THE FINDING TWICE, both errors mine: the cell claimed every write lives on hive.html (index.html:2953 writes it too — the conclusion survived, the stated premise was false), and index.html ALSO reads whHiveId() into a `const HIVE_ID`, which looks like the same stale-capture shape but is not, because that capture is FUNCTION-scoped inside the ops-home renderer (re-read per call) and the write is deliberately followed by `_initDashboard(...)` to re-render against the new hive — verified by reading both sites rather than trusting the comment. So the distinction that matters is SCOPE, not filename. The gate deliberately does NOT try to compute JS scope from a regex: brace and regex-literal counting over inline script is the brittle-validator trap this platform has already been bitten by, so it asserts the two cheap, unarguable properties instead. Self-test injects a writer into marketplace.html THROUGH THE READER (no file on disk is touched, the same discipline as injecting a mutant inside a transaction) and requires the gate to go red naming that page — without it, a green result would mean nothing. Static file scan, fast, always runs.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "push-runtime-delivery",
        "script":  "tools/validate_push_runtime_delivery.py",
        "args":    [],
        "label":   "PUSH RUNTIME DELIVERY (TB-S5 runtime tier) — the rung above push-handler-contract (which asserts sw.js STATICALLY) and below the OS notification tray (which no harness can read, and stays the honest residual gap). Runs tests/push-runtime-delivery.spec.ts: registers the worker, delivers a REAL push through the DevTools protocol ServiceWorker.deliverPushMessage — the same entry point the browser uses for a push from FCM, so sw.js's `push` listener runs its actual code path rather than a hand-called function — and reads the notification back off registration.getNotifications(). WHY IT EXISTS: building it found a LIVE PRODUCT DEFECT. svcEnablePush() in marketplace-seller.html did a bare `await navigator.serviceWorker.ready`, and `ready` resolves ONLY when an active registration exists for the scope. A repo-wide grep finds serviceWorker.register on exactly ONE page in the entire app (report-sender.html) and NOT on this one, nor in utils.js, nor any shared include. Measured live: getRegistrations()=0, controller=false, ready NEVER SETTLED. So a provider tapped 'Enable job alerts', granted the notification permission, and then nothing happened — no subscription, no toast, no error, no log, forever. The function's catch block is thorough about permission / VAPID / unsupported-browser failures, but `ready` does not REJECT, it simply never resolves, so the ONE failure that fires in practice was the only one the catch could not see. Fixed by registering the worker on that path and bounding the wait so a worker that will not activate says so instead of leaving a dead button. THREE CONTEXT SETTINGS the spec cannot work without, each a dead end that first looked like a product failure: serviceWorkers:'allow' (Playwright BLOCKS registration by default, replacing navigator.serviceWorker.register with a warning stub, so any SW assertion under a default context measures NOTHING); permissions:['notifications']; and channel:'chromium' — the deciding one, because the BUNDLED headless Chromium has no notification platform bridge, so the permission cannot be granted at all and getNotifications() is always empty, which is the exact symptom of a handler that renders nothing. Probed both ways: default headless -> perm 'denied', count 0; Chrome's new headless -> perm 'granted', count 1. I was one step from recording that as an un-probeable ceiling; it was a one-line config. Invoked via `node node_modules/@playwright/test/cli.js` (this project's path contains an '&' the npx shim mis-parses), and 'No tests found' is reported as the gate's OWN invocation failure, never as a broken product. skip_if_fast: browser minutes.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "push-handler-contract",
        "script":  "tools/validate_push_handler_contract.py",
        "args":    [],
        "label":   "PUSH HANDLER CONTRACT — a delivered push must actually reach the person. FOUND 2026-07-30 while dispositioning the test bank's TB-S5-edge-push-delivery-roundtrip cell, whose note read 'nothing proves a real subscription RENDERS the notification'. Checked rather than assumed: the SEND side is well covered (notify-push is VAPID-signed and was proven E2E against the real FCM service) and TWO service-worker validators already exist — validate_sw_offline and validate_sw_shell_membership — but NEITHER mentions push, showNotification or notificationclick even once. The receive side had no gate at all. That gap matters because every failure mode is SILENT, and sw.js says so itself: 'Without these handlers a delivered push silently no-ops.' The push arrives, the worker wakes, nothing appears, and nothing errors anywhere a person or a log would see it — a provider just misses the job. SEVEN invariants, each a silent failure: (1) a `push` listener exists (else the push is delivered and discarded); (2) the handler calls showNotification (else the worker wakes and renders nothing); (3) that call is INSIDE event.waitUntil — brace-matched, and the check requires waitUntil to WRAP it rather than merely appear in the handler, because a bare showNotification works on a warm worker and fails on a cold one, which is the hardest kind of bug to reproduce; (4) e.data.json() is guarded by try/catch, since a non-JSON payload THROWS and one malformed push then silently suppresses the notification; (5) a `notificationclick` listener exists (else the tap does nothing); (6) it focuses a tab or opens one (else the notification is a dead end); (7) it closes the notification (else the tray keeps an item the user already acted on). Static by design — these are properties of the file that ships to installed PWAs, and the CACHE_NAME comment records the cost of getting it wrong: 'without this bump installed PWAs keep the handler-less worker'. WHAT THIS DELIBERATELY DOES NOT CLAIM: the OS notification tray is outside any harness, so 'the human saw it' stays unprobeable; the runtime tier (dispatch a push event to a registered worker and assert showNotification fired) remains recorded as owed with this gate named as its first half, so the residual gap has a shape instead of a shrug. Self-test proves all 7 hold on the shipped worker AND that five deliberately broken workers are each caught.",
        "group":   "Platform",
        "severity": "fail",
    },
    {
        "id":      "unprotected-write-grant",
        "script":  "tools/validate_unprotected_write_grant.py",
        "args":    [],
        "label":   "UNPROTECTED WRITE GRANT — no end-user write privilege may stand on the GRANT alone. FOUND 2026-07-30 by teaching the marketplace test bank's SQL runner the `anon` partition: it had enumerated 18 anon obligations and executed NONE, because the runner needed a uid to mint and `anon` is not a different identity, it is the ABSENCE of one (`set local role anon`, no JWT). On the marketplace surface RLS held everywhere — anon moved 0 rows on insert/update/delete and the service tables refuse at the GRANT layer (42501) before RLS is consulted. The finding was one level up, in 'where is RLS not there to catch it?': 16 public tables with relrowsecurity=false that granted anon INSERT/UPDATE/DELETE/TRUNCATE. A rolled-back `delete … where true` as anon destroyed 1,430 ROWS — 766 embedding_cache, 434 persona_knowledge, 207 multilingual_terms, the 3 service_slo_targets the gate panel grades against, and the single ai_global_budget row that caps AI spend (delete that and either the AI chain stops for everyone or, if any reader treats a missing row as 'no cap', the spend ceiling silently disappears). WHY THE CLASS HIDES: the grants are the Supabase template default (GRANT ALL … TO anon, authenticated), harmless on the ~130 tables where RLS is on and catastrophic on these 16 — the same grant, and the only difference is one line of DDL somewhere else. So the invariant is a CONJUNCTION, never a grant rule: a base table may grant a write verb ONLY IF row-level security is enabled on it. Corollary: no view may grant one — 13 v_* views were auto-updatable with anon write and 11 were not security_invoker, the textbook bypass setup (a write through a non-invoker view runs as the view OWNER, postgres, and an owner is RLS-exempt when forced=false); PROBED, it did not bypass (0 rows, and even SELECT returned 0), recorded as measured rather than reasoned, and revoked anyway because a repo-wide grep finds zero writes through any v_* view. TRUNCATE is the verb RLS would never have caught — RLS does not apply to TRUNCATE, and anon TRUNCATE on marketplace_listings fails today only with 0A000 'referenced in a foreign key constraint', a coincidence of the schema that evaporates the day that FK is dropped. Fixed by mig 20260730000002; this gate stops the next GRANT ALL or the next table created without ENABLE ROW LEVEL SECURITY from re-opening it silently. Runs in --fast (two catalog queries), skips cleanly if the stack is down, and its self-test PLANTS the defect and requires detection.",
        "group":   "Security",
        "severity": "fail",
    },
    {
        "id":      "marketplace-test-bank",
        "script":  "tools/validate_marketplace_test_bank.py",
        "args":    [],
        "label":   "MARKETPLACE TEST BANK — SQL lane (MARKETPLACE_DEEPWALK_EXPANSION_ROADMAP §10). The bank's denominator is DERIVED from the four guard functions by tools/derive_transition_matrix.py — each guarded transition names its authorised actor, so the obligations compute (212: 22 positive · 102 authority-negative · 88 sneak-path) and a transition added by a later migration grows the denominator BY ITSELF rather than silently not existing. WHY THIS EXISTS: deriving it exposed that of 22 authorised transitions only 4 had any gate — every existing gate was written AFTER a security finding, so they all encode 'this must not happen' and NOTHING asserted 'this must still work'. That asymmetry is how a guard tightened one notch too far ships green (this platform watched pm_assets go supervisor-only and two gates redden for the old permission, not a real break). This lane proves BOTH directions: the authorised actor CAN fire each transition (expect 1 row) and every other actor is refused (exception or 0 rows). SQL altitude on purpose — a transition's legality is a database fact, and proving it through a browser would buy nothing and cost determinism (Google: UI tests are the most flake-prone, and flakiness masks real bugs). Every check runs inside begin/rollback with SELF-MINTED probe identities: zero pollution, no dependence on seeded state. Fixtures mirror reality — a request in an ACTIVE state always has an on_job provider, because accept_service_request sets that under the workhive.service_system_write bypass; planting 'online' instead tests an unreachable world and looks exactly like a product bug. Self-test proves teeth in both directions. Skips if docker/psql is absent.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "service-triage-eval",
        "script":  "tools/validate_service_triage_eval.py",
        "args":    [],
        "label":   "SERVICE TRIAGE EVAL (§10 S7-ai) — the AI's suggestion must be something the PRODUCT CAN USE. The one layer of the marketplace test bank that cannot have an exact-match oracle: asking a free-tier LLM to return one specific string every time tests the model's mood, not the product. So the oracle is a RUBRIC — never 'did it say Plumbing', always 'is what it said in the vocabulary'. WHY THAT IS THE INVARIANT THAT BITES: marketplace.html applies a triage suggestion by finding the matching <option> (`sel.options.find(o => o.textContent.startsWith(t.category))`), so an out-of-vocabulary answer — 'Plumbing Services', 'Aircon Repair', 'urgent' — finds nothing, sets nothing and reports nothing; the person presses Ask AI, watches the form not move, and cannot tell whether the AI failed or simply had no opinion. Nothing throws. Same shape as the `urgency = 'emergency'` branch this session found DEAD in the push fan-out (mig 20260729000017): a value written against a vocabulary that does not exist. The catalog categories and the urgency/mode CHECK vocabularies are read from the DATABASE every run, so a new category is graded against without touching the gate. An ABSENT field is legitimate ('no clear match' is honest). A rate-limited or unreachable chain is a SKIP, never a PASS — green there would mean the feature is down. Driven through supabase-js (tools/service_triage_capture.mjs), the page's own client path, because the gateway resolves its caller via auth.getUser() and a raw HTTP POST tests the auth wall instead of the agent. Self-test proves the grader in five directions.",
        "group":   "AI Validation",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "payment-disclosure",
        "script":  "tools/validate_payment_disclosure.py",
        "args":    [],
        "label":   "PAYMENT DISCLOSURE (§10 MK8) — while the platform holds no money, it must SAY so, AT the money step. WorkHive's marketplace is contact-only: PAYMENTS_ENABLED=false, no escrow, the buyer arranges payment with a stranger off-platform — so 100% of the money risk sits at one moment, the inquiry that takes the conversation off the site. RA 11967 (the PH Internet Transactions Act) requires consumer education on the red flags in internet transactions, and silence lets a buyer assume protection by default, because the default assumption everywhere else online is that the platform holds the money. TWO INVARIANTS: (1) the money step states that WorkHive NEVER HOLDS the payment, states the consequence (it therefore CANNOT REVERSE it), and gives a concrete precaution — 'payment is off-platform' states a fact but does not warn; (2) no buyer-facing copy promises buyer/purchase protection, a money-back guarantee, held funds or escrow — promises the switch makes false. Checked as CLAIMS rather than one exact sentence, so the wording stays free to improve while the substance may not quietly drop out. <script> and HTML comments are stripped first: a reassurance living in a comment reassures nobody. marketplace_orders DOES carry an escrow-shaped vocabulary (pending_payment/escrow_hold/released/refunded) for a flow that is switched off — fine as schema, which is why the gate searches PROSE and not status strings. SKIPS entirely if PAYMENTS_ENABLED flips to true: these invariants describe a different product then and must be re-derived, not silently kept. Self-test proves all four directions including the comment-only case.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "lifecycle-state-reachability",
        "script":  "tools/validate_lifecycle_state_reachability.py",
        "args":    [],
        "label":   "LIFECYCLE STATE REACHABILITY (§10 MK4) — every state in a `status` CHECK must be both SURFACED and REACHABLE. A CHECK vocabulary is a promise about what the product does, and it breaks two ways, silently in both directions because unreachable code raises nothing. FOUND 2026-07-29: `marketplace_listings.sold` is fully dressed — a blue 'Sold' chip, a `.listing-item.sold` border rule, a schema.org/SoldOut mapping in the runtime JSON-LD, and `recompute_seller_sales_and_tier` COUNTS listings WHERE status='sold' to drive the seller's tier — and NOTHING anywhere writes it. A seller who sells something cannot say so, and the tier that counts sales counts a number that is always zero. (The mirror case is already recorded as a schema question for Ian: the same table carries moderation_reason/moderated_at/moderated_by with no `rejected` in its vocabulary — a consumer with no state.) THE PRODUCER TEST UNIONS THREE SIGNALS because none alone is right: the DERIVED guard matrix (a guard's allow-list only covers USER writes, missing `accepted` via the workhive.service_system_write bypass and `expired` via the sweep cron), a DB assignment (`SET status =` / `status :=` ONLY — matching `status = 'x'` anywhere counts WHERE-clause READS as writes, which produced a FALSE PASS on the one real finding twice in a row), and a page write including the literal passed as an ARGUMENT (the seller advances a job through `svcAdvance(id, next)`, so a payload-only test calls seven wired states unreachable). Forward-only: the known gap is NAMED in lifecycle_reachability_baseline.json and still prints every run; a NEW unreachable or invisible state FAILs. Self-test proves both baseline directions.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "jsonld-truth",
        "script":  "tools/validate_jsonld_truth.py",
        "args":    [],
        "label":   "JSON-LD TRUTH (§10 MK7) — RUNTIME structured data may not claim more than the canonical row. The registered `seo-technical` gate reads JSON-LD WRITTEN INTO the HTML (retired @types, malformed blocks); it cannot see structured data BUILT AT RUNTIME from database values — and that is exactly where the claims with something at stake live: a star rating and a listing count are what a buyer sees in the search result before they ever reach the page. Two failure modes, both reasoned about correctly in marketplace-seller-profile.html#injectJsonLd and neither of them locked until now. (a) A FALSE STAR RATING: an `aggregateRating` gated on the AVERAGE ALONE ships a rating for a seller with no reviews — an average can be non-null with zero reviews, which is precisely how a trust signal ends up standing on nothing, and Google treats a fabricated AggregateRating as a structured-data violation, so it is a trust lie AND a ranking penalty. The gate requires the claim to sit behind a review COUNT. (b) STRUCTURED DATA FOR A MISSING ENTITY: a Person schema on a page whose own body says 'Seller not found' is a claim the page contradicts — the emitter must bail on its subject's absence. Also catches a truncated `itemListElement` shipping alongside a `numberOfItems` that claims the full total. Balanced-brace extraction, static/fast. Self-test proves all four directions.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "gate-panel-honesty",
        "script":  "tools/validate_gate_panel_honesty.py",
        "args":    [],
        "label":   "GATE PANEL HONESTY — the surface that REPORTS the gates was itself watched by nothing, and it had already failed twice. (a) G2: the failing-gate list printed each gate's `label`, prose written for the engineer reading run_platform_checks.py, carrying file paths and roadmap filenames straight into user-facing chrome. (b) TRUNCATION, found 2026-07-29 by this gate's own hunt: the regressions block rendered `regs.slice(0, 6)` with NO overflow line — and a regression is the highest-severity signal the console carries, a gate that was PASSING and now is not. Everything past the sixth vanished, and a truncated list with nothing after it reads as 'that is all of them'. Three invariants: the visible text is the short id-derived name; the full label survives as the tooltip so shortening is not hiding; and any list that truncates DISCLOSES the remainder. Static on founder-console.html because the claim is about rendered text — a browser walk would add flake and prove the same thing. NOTE: this gate reddened TWICE on correct page code while its own detector was wrong (a regex spelling out the title-attribute quoting, then a .find() that anchored on the CSS rule instead of the render site); both were fixed in the detector, never by bending the page.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "offline-write-guard",
        "script":  "tools/validate_offline_write_guard.py",
        "args":    [],
        "label":   "OFFLINE WRITE GUARD — a user-triggered write must REFUSE before it fires, not after. Found 2026-07-29 while building the test bank's S2-pwa cell: marketplace.html already had svcRequireOnline() ('You're offline. <action> needs a connection - nothing was sent, so nothing is half-done.') wired into exactly TWO of its seven client writes. The other five fired into a dead network — svcSettle ('I paid', money, no idea whether it landed), svcApplyVoucher, svcPickQuote, svcPickStar, and svcClientCancel, whose confirm dialog made the person commit to cancelling before failing opaquely. marketplace-seller.html was worse: svcAccept reasoned about the offline race in a comment and the other NINE writes had nothing, including svcFileTopup where the provider may have ALREADY sent the GCash payment. WHY THE EXISTING GATES MISSED IT: degraded-state-central proves every page adopts the offline BANNER — and both pages did, the whole time; a passive warning does not stop a button. offline-queue-confirm proves a drain never calls 0 rows 'synced' — but these surfaces deliberately do NOT queue, because a queued accept would claim a job someone else already took. Adoption of a warning and correctness of a drain both passed while every individual write was unguarded. This gate asserts the third thing. Balanced-brace function extraction (not a fixed window), only user-invokable functions (window-attached or inline handler), read-only RPCs exempted BY NAME, and the check's POSITION is verified — a guard after the write is a post-mortem. Self-test proves all four directions including the order case.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "marketplace-bank-journey",
        "script":  "tools/validate_marketplace_bank_journey.py",
        "args":    [],
        "label":   "MARKETPLACE TEST BANK — journey lane, TWO BROWSER CONTEXTS (§10). Runs tests/marketplace-bank-two-context.spec.ts: two independent Playwright contexts holding two real Supabase Auth sessions, one shared row of truth between them. WHY IT EXISTS: every other spec in this repo drives ONE identity, which is why the marketplace's two-sided journeys were never end-to-end — J29 (live map) was walked by P-client-supervisor and P-client-worker, two WATCHERS and zero PUBLISHERS, and still satisfied the arc's '>=2 personas' rule because the rule counted personas instead of naming the SIDES. A handoff between two parties cannot be proven from one browser. The cell: the client presses the real 'Track provider' control, the matched provider's own seller page publishes via watchPosition from its own session (the run logs which path fired), and the client's map must repaint at the NEW coordinate within two 10s poll cycles with no reload. The SQL half — publisher writes, watcher reads, stranger reads 0 rows — is already banked separately; this lane asserts only what SQL cannot, because a silent tracking failure is indistinguishable from a provider who has not moved. Teeth are PROVEN, not assumed: --selftest sets WH_TB_FREEZE=1 to park the publisher at its original position and requires the watcher assertion to go RED. Invoked as `node node_modules/@playwright/test/cli.js` because this project's path contains an '&' that the npx shim mis-parses, and 'No tests found' is reported as the gate's own invocation failure rather than as a broken journey. skip_if_fast: browser minutes, while the SQL lane stays in --fast.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "service-idempotency",
        "script":  "tools/validate_service_idempotency.py",
        "args":    [],
        "label":   "C14 (SERVICE_HAILING_ROADMAP §4b) once-only on the money/dispatch paths. The roadmap originally asked for an `Idempotency-Key` header contract; reading the code first showed the platform already does something STRICTLY STRONGER — partial UNIQUE indexes enforce once-only in the DATABASE, so the guarantee holds even when the client sends no key, the wrong key, or is a script hitting PostgREST directly. 8 invariants: the four indexes exist (one commission per request · one top-up per GCash ref · one offer per provider+request · one open PM auto-hail) AND still BITE (a partial predicate can be narrowed to uselessness without dropping the index, so presence alone is not proof — each replay is attempted live in a rolled-back transaction and must be REFUSED), plus the duplicate must be reported HONESTLY ('That reference number is already filed'), never as raw 23505 text a user reads as failure and re-sends. Skips if docker/psql is absent.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "slo-budget",
        "script":  "tools/validate_slo_budget.py",
        "args":    [],
        "label":   "C15 (SERVICE_HAILING_ROADMAP §4b) the arc's north-star metrics are MEASURED, not adjectives. D9 named allocation rate / time-to-accept / completion rate and never gave them a number; `v_service_slo` now computes each against a target stored as tunable DATA (`service_slo_targets` — changing a target is Ian's business call, never a migration). Asserts every SLI has a numeric target + valid comparator, computes from live data, and reports an empty denominator as NULL ('not measurable yet') rather than a fabricated 0 that would read as a breach. Also asserts the AI-chain breaker is INTACT (recordSlotFailure parks a failing model/provider, isSlotBlocked skips it, Retry-After is honored) — validated as already-present, not rebuilt. DELIBERATELY does NOT fail on a BREACHED SLO: a breach is a business signal, and a gate that reds for non-code reasons is exactly what gets excluded — which is how 9 cron jobs stayed dead behind a 'reasonable' exclusion for weeks. Breaches print loudly; exit stays 0.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "outbox-delivery",
        "script":  "tools/validate_outbox_delivery.py",
        "args":    [],
        "label":   "C12 (SERVICE_HAILING_ROADMAP §4b) durable side-effects: a boundary-crossing effect must survive a consumer that is down. 12 live invariants over `service_outbox` + the `FOR UPDATE SKIP LOCKED` relay: schema/RLS/no-client-grant · enqueue+drain+reconcile are EXECUTE-revoked (a DEFINER helper is user-callable BY DEFAULT — this arc already shipped one live IDOR from that) · enqueue is a plain INSERT so it commits iff the transition does (an HTTP call inside the transition tx is the coupling the outbox removes) · a failed delivery is pushed OUT in time, not retried hot · a payload past max_attempts DEAD-LETTERS instead of looping · nothing is stranded 'in_flight' · SOMETHING ACTUALLY CALLS THE FAN-OUT · and a real enqueue→relay→2xx→done round-trip, minted and swept by the gate itself (residue is not evidence). WHY THE BLUNT ONES: Web Push shipped fully built and NEVER INVOKED — subscriptions, sw.js handler, VAPID, subscribe UI and notify-push all existed while no caller did, so providers subscribed and received nothing. 'Built but never called' must never be green again. Skips if docker/psql is absent.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "star-returning",
        "script":  "tools/validate_star_returning.py",
        "args":    [],
        "label":   "A bare .select() after a write is `select *`, and a star RETURNING on a table with a column-level SELECT revoke fails 42501 *after the row has already committed* — a PHANTOM WRITE: the user is told the create failed while the row is there, inviting a retry that makes another one. FOUND LIVE 2026-07-29: project-manager.html ended both create paths with .insert(payload).select().single() while projects.budget_php is supervisor-only (migs 024/030), so project creation was wholly broken AND leaking orphan rows. FAILs a star read OR write on any table that has a SELECT-revoked column; WARNs bare-select writes on other tables as latent debt (they become the same bug the day a column there is revoked). Reads the grant catalog LIVE rather than hardcoding the table list, so a FUTURE revoke arms the check automatically. Backup mirrors (dot-dirs) are excluded — they are not served. Skips (exit 0) if docker/psql is unreachable.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "crud-rollback",
        "script":  "tools/validate_crud_rollback.py",
        "args":    [],
        "label":   "Per-page P3 CRUD-at-DB gate for SIDE-EFFECT tables (LIVE, rolled-back psql) — 9 tables (logbook / inventory_items / resume_documents / marketplace_listings / ai_reply_feedback / asset_nodes / worker_profiles / resume_versions / report_contacts) that can't go through `page-crud` because a persisted INSERT fires expensive/stateful triggers (embed http_request, achievement XP, rate-limit, daily-cap, approval-guard). Runs a single WORKER-JWT transaction per table (INSERT with FORGED worker_name -> assert PINNED by bind_*_submitter where applicable + correct hive_id/auth_uid -> own-scoped UPDATE [or NO-OP for immutable/update_noop tables like resume_versions] -> own-scoped DELETE) then ROLLS BACK (undoes the row AND the after-commit side-effects = 0 pollution). Data-driven (each table emits its own pin/hive/auth booleans in SQL). Modes: default (pinned) / immutable (ai_reply_feedback: update+delete no-op) / update_noop (resume_versions: no UPDATE policy but own-DELETE works) / update_only (worker_profiles: create-ONCE non-deletable identity row — gates a forged-auth_uid insert is RLS-blocked + own-UPDATE lands, no delete round-trip by design). Bug-hunt roadmap P3, 2026-07-19..22 (asset_nodes closes asset-hub P3, worker_profiles closes index P3 — P3 axis now 100 platform-wide). A dropped bind trigger / broken own-write RLS / lost hive_id FAILs. Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "role-gate-server-backstop",
        "script":  "tools/validate_role_gate_server_backstop.py",
        "args":    [],
        "label":   "P5 UI-role-gate server-backstop gate (LIVE) — the LAST P5 sub-property: several pages source HIVE_ROLE from localStorage (tamperable) and hide supervisor-only actions on `HIVE_ROLE==='supervisor'`/`WHRoles.isSupervisor()`. That is safe ONLY because the server independently enforces supervisor/admin on every such write — so a worker who tampers localStorage sees a button the server still rejects (42501), not a privilege escalation. This gate LOCKS that invariant: every table written behind a supervisor UI gate (asset_nodes/rcm_fmea_modes/rcm_strategies/inventory_items/shift_plans/integration_configs/hive_retention_config/api_keys/sso_configs/marketplace_sellers) MUST carry a server-side supervisor enforcement — an RLS write policy referencing the supervisor role / is_marketplace_admin, a `tg_guard_approval` trigger, OR a fully write-locked (`WITH CHECK false`, service-role-only) policy. A FUTURE page adding a client-only supervisor gate on an un-backstopped table = the UI-only-auth privilege-escalation class found+exploited live 2026-07-07 (asset_risk_scores), and this FAILs it. Curated list (adding a supervisor-privileged write is a conscious security decision that updates it). Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "input-validation-guard",
        "script":  "tools/validate_input_validation_guard.py",
        "args":    [],
        "label":   "P4 client input-validation gate (static teeth) — every write-submit handler that reads a USER-TYPED field (getElementById().value / .trim()) and issues a `db.from().insert/upsert/update` or `db.rpc` mutation MUST validate that input BEFORE the write, via EITHER a runtime capture contract (whValidateCapture) OR a pre-write validation guard (an if→return branch and/or an error surface: showFormError/showToast/errEl/.textContent/.focus/classList error). A form that POSTs raw user input with no guard leans entirely on the server and shows a confusing raw PostgREST error. REAL bug locked 2026-07-21: project-manager.html saveProgressLog inserted log_date (date NOT NULL) + pct_complete (smallint 0..100 CHECK) straight from the inputs → an empty date / out-of-range % produced a raw 22007/23514; fixed with a friendly pre-write guard. Server-derived writes (no user field) + read-only .select handlers are excluded. This closes the LAST P4 sub-property (client empty/format) not already gated (XSS: innerhtml-eschtml/dom-xss-fields; server bounds: text-caps/numeric-bounds; duplicate-submit: double-submit-lock). Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "double-submit-lock",
        "script":  "tools/validate_double_submit_lock.py",
        "args":    [],
        "label":   "P7 double-submit lock gate (static teeth) — every `getElementById('...').addEventListener('click', H)` bound to a WRITE handler H (name submit/save/confirm/create/add/send/publish/approve/reject/delete OR the body issues a `db.from().insert/upsert/update/delete` / `db.rpc` write) MUST be single-flight-locked, EITHER by wrapping the binding in `withButtonLock(this, H)` OR by H disabling its button before the await. A bare unlocked click->write binding = a double-tap fires the write TWICE (PRODUCTION_FIXES #47). REAL bugs locked 2026-07-21: inventory.html submitUse/submitRestock/submitPart (bare -> the non-idempotent inventory_deduct/restock RPC = a DOUBLE stock deduction) now wrapped in withButtonLock; logbook.html submitAsset (bare -> 2nd tap 23505s the (hive_id,tag) unique index) now self-disables. Read-only handlers (all db.from().select) + JS Set/Array .delete()/.update() are excluded (Map.size class). Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "p6-concurrency-class",
        "script":  "tools/validate_p6_concurrency_class.py",
        "args":    [],
        "label":   "P6 concurrent-edit disposition gate (LIVE + static teeth) — locks the concurrency-safety CLASS of the 9 remaining P6-partial pages so each reaches gated-100, complementing oc-updated-at-backed (OC-guarded: inventory/pm-scheduler) + readonly-p6-no-edit (12 read-only). Classes + load-bearing DB invariant each asserts: (a) idempotent-upsert (skillmatrix skill_profiles onConflict worker_name · marketplace-seller marketplace_sellers · dayplanner schedule_items) — full-object upsert on a UNIQUE-index-backed key => two concurrent writes CONVERGE to 1 row, no partial lost-update (verified: index exists + no read-modify-write delta on the table + a LIVE rolled-back double-upsert converges to 1 row w/ 2nd value); (b) owner-scoped-update (resume resume_documents · marketplace marketplace_saved_searches · marketplace-seller marketplace_inquiries · voice-journal worker_profiles) — UPDATE RLS is own-identity/party-scoped (references auth.uid()/auth_worker_names(), not true) so no CROSS-user lost-update; (c) forward-only-status (shift-brain shift_plans) — a forward-only status trigger blocks a concurrent regress; (d) create-once-insert (index worker_profiles, unique auth_uid). Also static-asserts each page still contains its declared write shape, so a class change (e.g. a page adds a read-modify-write delta) trips the gate for re-scoring. Bug-hunt roadmap P6, 2026-07-21. Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "empty-state-discrimination",
        "script":  "tools/validate_empty_state_discrimination.py",
        "args":    [],
        "label":   "DEEPWALK D3 gate (static teeth) — a list render that owns BOTH a first-run empty-state ('No entries yet — log your first X' CTA) AND a search no-results ('nothing matched your filters') must route a 0-result SEARCH to no-results, NEVER to the first-run empty-state. For a SERVER-filtered view (the list var IS the query result => `filtered === entries`) an early `if (entries.length === 0){ show empty-state; return }` fires FIRST and makes the no-results branch DEAD, so a supervisor who searched the whole TEAM feed and got 0 rows sees 'Log your first repair' (a nonsensical CTA). REAL bug found + fixed live 2026-07-22 in logbook.html renderEntries (the length-0 branch is now view-aware: team->no-results, mine->empty-state). Client-filtered views (inventory `filtered = items.filter(...)`) are correct and out of scope. Curated list of server-filtered search views; adding one is a conscious UX decision that must extend the gate. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "qty-input-contract",
        "script":  "tools/validate_qty_input_contract.py",
        "args":    [],
        "label":   "DEEPWALK D5 gate (static teeth) — the 'number input's declared min/step/bounds are NOT enforced on the write path' class, across TWO central parsers. (a) QTY: a `<input type=number min=1 step=1>` in a modal that submits via a BUTTON (not a native <form>) never has min/step enforced; a bare `parseFloat()||0` lets 2.5 / 1e-9 through => a fractional/absurd stock deduction (inventory submitUse/submitRestock). (b) PRICE: the marketplace post/edit forms are `novalidate`, so min=0 is unenforced; an unvalidated negative hit the DB price_nonneg CHECK (raw 23514) and an over-precision value hit numeric(14,2) overflow, both cryptic to the seller (marketplace handlePostSubmit / marketplace-seller handleEditSubmit). REAL bugs found+fixed live 2026-07-22. FIX (central, METHOD LAW): window.whParseQty (integer qty) + window.whParsePrice (currency: blank=negotiable, 0=free, 2dp, ₱10M cap) in utils.js; every curated number-write handler adopts the right one. Gate locks: both helpers exist + window-exposed, every handler calls its helper, and none has a bare parseFloat/Number inline read (a naive revert). Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "refresh-retry-dedup",
        "script":  "tools/validate_refresh_retry_dedup.py",
        "args":    [],
        "label":   "DEEPWALK D2 gate (static teeth) — a NON-idempotent client write (a fresh-id INSERT or a decrement/increment RPC) has no idempotency key, so a refresh-mid-submit then retry creates a DUPLICATE / double effect (the button-lock only stops a same-page double-tap; a refresh spawns a fresh page that bypasses it). REAL, live-confirmed 2026-07-22: logbook addEntry (fresh Date.now() id => dup entry), inventory submitUse (inventory_deduct AGAIN => DOUBLE stock deduction), submitRestock (double restock), marketplace handlePostSubmit (dup listing). FIX (central, METHOD LAW): window.whRecentDuplicate(db, table, matchObj, {windowMs, tsColumn}) in utils.js queries for an identical recent row (tight window + specific match => no false-block; best-effort, never blocks a write on error); each handler calls it BEFORE the write and skips on a hit. Live-verified: retry dedups, different value not matched. Gate locks: the helper exists + window-exposed + every curated non-idempotent write calls it. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "optimistic-input-restore",
        "script":  "tools/validate_optimistic_input_restore.py",
        "args":    [],
        "label":   "DEEPWALK D4 gate (static teeth) — a chat/message send that clears its input OPTIMISTICALLY (`input.value=''` BEFORE the async turn, to show the user bubble immediately) MUST restore it on the failure path, else a 429/timeout/network error WIPES the user's typed question even though the error says 'try again' (forcing a full retype). REAL bug found+fixed live 2026-07-22 (assistant.html sendMessage): the catch now does `if(!input.value.trim()){ input.value = text; }` — one-tap retry, guarded so it never clobbers a NEW question typed during the wait. Sibling sweep: community submitReply clears AFTER success (correct, N/A). Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "cmms-import-rollback",
        "script":  "tools/validate_cmms_import_rollback.py",
        "args":    [],
        "label":   "P3 gate for integrations.html's bulk CMMS import (LIVE rolled-back SUPERVISOR-JWT psql + static teeth) — the last deferred P3-write frontier, closed 2026-07-21 with 4 REAL fixes it now locks: (1) normalizeRow STATUS CLAMP (an unmapped raw code passed through as-is 23514-killed the WHOLE 500-row chunk via external_sync.status CHECK; a mapped 'Cancelled' killed the logbook insert via logbook_status_check); (2) NO client fault_knowledge write (client-INSERT-LOCKED since mig 20260513000003; the import's direct insert silently failed for ~2 months and would have poisoned the RAG index with unembedded duplicates — knowledge flows via embed-logbook trigger -> embed-entry edge fn); (3) ERROR-CHECKED batches (supabase-js does not throw, the old try/catch was dead code and failed chunks counted as imported); (4) inventory_items.id text-NOT-NULL-no-default -> import inserts 23502-failed (mig 20260721000001 gives the 3 opaque text-id tables a DB default — the Arc-K logbook.id class closed platform-wide). Live half mirrors all 4 entity batches in the page's exact shapes (upserts run TWICE = re-import idempotency; attribution pins asserted; duplicate-guard read via v_external_sync_truth; cmms_audit_log write) then ROLLS BACK = 0 pollution. Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "onconflict-index",
        "script":  "tools/validate_onconflict_index.py",
        "args":    [],
        "label":   "Per-page P3/P4 gate: every supabase-js `.upsert(rows,{onConflict:'a,b'})` in the page HTML must have a MATCHING unique index in the live DB (Postgres ON CONFLICT arbiter inference is set-based, order-insensitive). ROOT BUG locked (found live 2026-07-19): integrations.html's CMMS inventory import upserted `inventory_items` with onConflict:'part_number,hive_id' but NO such unique index existed (only the pkey) -> Postgres threw 'no unique or exclusion constraint matching the ON CONFLICT specification' at RUNTIME = the supervisor's inventory import CRASHED; the same gap left submitPart's client-only 'already exists' check a double-submit RACE. Fixed by migration 20260719000001. Parses the (possibly multi-line) `.from('t').upsert(...onConflict)` and set-matches against pg_index. A new onConflict without a backing unique index FAILs before it ships. Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "marketplace-trust-integrity",
        "script":  "tools/validate_marketplace_trust_integrity.py",
        "args":    [],
        "label":   "Per-page P5/P6 marketplace SELLER-TRUST forge lock (LIVE, rolled-back psql as a real authenticated worker). The marketplace runs on the seller trust signal (rating_avg/rating_count/total_sales/tier shown in search/community/seller-profile/schema.org). Two live-found self-dealing vectors: (A) FAKE SALES — `trg_seller_tier` bumps total_sales on a marketplace_orders `status->released` transition, and RLS let a buyer self-insert an order naming ANY seller then jump status straight to released (no escrow/payment) -> +1 fake sale + tier promotion; locked by guard_marketplace_order_status (mig 20260719000002: a JWT client cannot set status released/refunded). (B) FAKE REVIEWS — `update_seller_rating` averaged ALL reviews with no verified_purchase filter, and RLS let a worker self-insert a 5-star verified_purchase=false review for any listing -> inflated (or overwrote the seeded) rating; locked by mig 20260719000003 (only verified_purchase=true reviews move the rating; an unverified review is a no-op). (C) regression — guard_marketplace_seller_trust_columns still blocks a direct client update of total_sales/rating_avg. Asserts all three forges are blocked/no-op, then ROLLS BACK (0 pollution). Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "service-state-machine",
        "script":  "tools/validate_service_state_machine.py",
        "args":    [],
        "label":   "SERVICE_HAILING C1 lock (LIVE, rolled-back psql as a runtime-resolved NON-admin worker — an admin identity legitimately bypasses every guard, so an admin-run suite reads as fail-open). Re-runs the P1 adversarial suite as a standing anti-regression over mig 20260728000024: born-terminal request blocked; illegal jump (requested->completed) blocked; the legal client path works AND journals 2 service_job_events; attribution forge (filing a request as another uid) blocked; client credit-mint into service_credit_ledger blocked (money = trust-forge class); GCash top-up self-verify is a no-op (row stays pending_verification — the founder/GUC path is the only mint); provider self-verification and self-set on_job blocked; the atomic accept guard's 2nd status-guarded UPDATE hits 0 rows; live_location column privacy holds (revoke-first grant). Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "service-dispatch-isolation",
        "script":  "tools/validate_service_dispatch_isolation.py",
        "args":    [],
        "label":   "SERVICE_HAILING C3 lock (LIVE, rolled-back psql; every check SELF-CONTAINED — it mints its own probe auth.users + temp providers/requests inside the transaction, because a borrowed seeded identity is never clean: my_service_provider_ids() surfaces hive providers for their MEMBERS and a verified pre-existing identity outranks the probe's temp provider = false refusals). Asserts the dispatch rules of mig 20260728000025: accept_service_request refuses your own hail (own_request), a category you don't serve (category_mismatch), and an out-of-radius job even when the id is obtained out-of-band (RLS hides stranger broadcasts from the raw table — the feed view is the sanctioned path); the accept race has EXACTLY ONE winner (2nd caller gets lost_race_or_closed — the fix for the reference repo's select-then-insert TOCTOU); v_service_open_broadcasts never shows your own hail but shows an in-scope stranger hail; v_service_job_tracking (the ONLY live_location read path) shows an active job to its client and provider and NOTHING to a stranger. Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "service-geo-privacy",
        "script":  "tools/validate_service_geo_privacy.py",
        "args":    [],
        "label":   "SERVICE_HAILING C10 lock (LIVE, rolled-back psql; self-minting hex-uuid actors at literal Manila/Davao coordinates). The arc's §3 D-Geo axis had column privacy locked by C1 but NOTHING asserting the MATCHING behaviour a hailing product lives on: a provider 2km inside a 10km broadcast FINDS the hail in v_service_open_broadcasts; one ~700km away is refused out_of_radius by accept_service_request even holding the id; the client CAN read the matched provider's live position mid-job through v_service_job_tracking (the only path); and a stranger reads 0 rows from it - location is never ambient. Skips if docker/DB unreachable.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "service-roadmap-executed",
        "script":  os.path.join("tools", "verify_service_hailing_roadmap.py"),
        "args":    [],
        "label":   "SERVICE_HAILING itemized execution audit (Ian 2026-07-29: 'itemize everything written in the roadmap, then check one by one if we have executed it'). 85 concrete promises - every Fuel table, Engine view/RPC, Brain agent, Dashboard surface, stack layer, §1c booster, C1-C11 lock, §3 dimension, G1-G4 gap, phase deliverable, D1-D14 decision and safety rail - each re-derived from the LIVE database, filesystem and gate registry, never from a hand-kept checklist. FAILs naming any promise that stops being true.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "regression",
    },
    {
        "id":      "service-ufai-deep",
        "script":  os.path.join("tools", "validate_service_ufai_deep.py"),
        "args":    [],
        "label":   "SERVICE_HAILING UFAI DEEP (LIVE browser): the verification ufai_pillar_map.py explicitly excludes from its coarse lens slice - measured 44px tap targets at 390, vendored axe-core, and a 360/390/768/1280/1920 horizontal-overflow sweep across the arc's four surfaces. Caught two SERIOUS defects the page-level rubric could not see (a bare a.btn with NO rule rendering browser-default blue at 1.88:1 and 21px tall; a select labelled only by title=). Bar: 0 sub-44px, 0 overflow, 0 serious/critical axe.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "regression",
    },
    {
        "id":      "service-hailing-scoreboard",
        "script":  "tools/service_hailing_scoreboard.py",
        "args":    ["--check"],
        "label":   "SERVICE_HAILING arc compass (forward-only ratchet over service_hailing_state.json). The P0-P9 phase table went green while three axes the roadmap ALSO names were unmeasured - §3 journey coverage, §3b per-surface UFAI, §2 class gates - so a green headline masked them. This scores all three boards and FAILs if any regresses. The W (walk) phase is DERIVED from walked personas x states (>=2 x >=2), never hand-set, so 'I drove it once as the admin' cannot score as covered. --accept ratchets up.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "regression",
    },
    {
        "id":      "read-battery",
        "script":  "tools/validate_read_battery.py",
        "args":    [],
        "label":   "Per-page P3 read-correctness + P7 empty-vs-error gate (LIVE headless Playwright, real Baguio supervisor). For 8 READ-heavy pages compares what the page RENDERS to the DB truth (docker-psql admin) for the signed-in hive: audit-log #feed child-count == count(hive_audit_log) [EXACT rendered==DB]; integrations/plant-connections DB==0 -> empty-state + hero counters read 0 (error NOT swallowed as empty) [P7]; public-feed/project-report/shift-brain/analytics render real rows when DB>0; ai-quality renders #content OR its intentional maturity gate (feedback_platform_intentional_blank_states). Complements validate_hive_battery.py (hive.html deep render==DB) + truth-view-read-isolation (DATA/RLS layer). A regression (stale/dropped/mangled render, error swallowed as empty, stuck skeleton) FAILs. Every expectation derived from a LIVE DB count = reseed-robust. Re-drive: node tools/validate_read_battery.mjs [--headed]. Skips cleanly if node or the local stack is absent.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "truth-view-read-isolation",
        "script":  "tools/validate_truth_view_read_isolation.py",
        "args":    [],
        "label":   "Cross-hive READ isolation across ALL truth views (LIVE, rolled-back - batch generalization of the security_invoker read-leak class, mig 001). As a real authenticated member of hive A, reads EVERY hive-scoped v_*_truth view filtered to hive B and asserts 0 rows - so a future view shipped without security_invoker (or a base-table SELECT-RLS regression) leaks a foreign tenant's data and FAILs here. 31 hive-private truth views covered (covering every page's reads); the 4 cross-hive-PUBLIC-by-design views are excluded (marketplace listings/sellers, public community posts, public reputation). Actors + a data-rich foreign hive picked dynamically = reseed-robust. Skips if DB / a two-hive fixture is absent.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "no-client-counter-write",
        "script":  "tools/validate_no_client_counter_write.py",
        "args":    [],
        "label":   "P6 lost-update regression gate (STATIC): asserts NO page HTML writes a value-integrity counter (qty_on_hand/xp_total/total_sales/rating_avg/votes/points/balance/...) via client .update()/.upsert() with a client-computed absolute value - every such mutation must go through an atomic server RPC (inventory_deduct/inventory_restock FOR-UPDATE, increment_*, grade_*) that serialises the read-modify-write under a row lock. Locks the class fixed by mig 20260713000008; the 2026-07-14 live sweep found 0 client counter-writes and this keeps it at 0. Static (no DB) so it runs in --fast and never flakes.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "substrate-freshness",
        "script":  "tools/validate_substrate_freshness.py",
        "args":    [],
        "label":   "Platform Knowledge Substrate freshness (PKS Layer-2 anti-regression - PLATFORM_KNOWLEDGE_SUBSTRATE_ROADMAP.md). The substrate/ chunk index (tools/build_substrate.py: metadata-prefixed .md chunks over pages / edge-fns / table-RLS / DEFINER-RPCs / skills / docs) lets a task RETRIEVE the relevant slice (a ~1KB page map) instead of a Workflow fan-out re-reading the whole platform (logbook.html 301KB, etc.) every run - the token-sustainability fix (Ian 2026-07-13: fan-out burned 0.5-3M tokens/run). This gate anchors every chunk to its source by a source_sha (file-content hash for page/edge-fn/skill/doc; live DB introspection for table-rls/rpc) and FAILs if any chunk DRIFTED (source changed but the chunk was not rebuilt) - treats the substrate as code, the doc-drift CI model. FIX on FAIL: python tools/build_substrate.py. DB-dependent chunks skip cleanly if docker absent; file-based always checked; fast (file hashing + one introspection pass).",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "memory-cache-coverage",
        "script":  "tools/memory_cache.py",
        "args":    ["--check"],
        "label":   "PKS P3 memory retrieval cache - coverage + budget (PLATFORM_KNOWLEDGE_SUBSTRATE_ROADMAP L3). The SQLite FTS5+TF-IDF cache (Memento memory.db - project_memento_local_memory_cache P0-P10, already built) delivers the prompt-matched memory slice (<2.5K tokens) per prompt; so MEMORY.md is kept a slim DOCTRINE-CORE + recent refs, with older reference/project pointers RETRIEVAL-ONLY (surfaced on demand, not loaded whole). This gate asserts (a) every durable reference/project memory file on disk is INDEXED in memory.db (FTS5-retrievable - so a pointer-light MEMORY.md loses nothing), and (b) MEMORY.md is under the 24.4KB native hard load cap (FAIL over cap = entries silently truncating). FIX: re-run the Memento indexer (coverage gap) or `python tools/memory_cache.py --slim --apply` (over budget). Ends the whole-MEMORY.md-load budget pressure that climbed to the cap this session (Ian 2026-07-13).",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "night-crawler-freshness",
        "script":  "tools/validate_night_crawler_freshness.py",
        "args":    [],
        "label":   "Night Crawler external-substrate freshness (NIGHT_CRAWLER — the on-demand web crawler tools/night_crawler.py that distills external sources into substrate/external/*.md so the agent RETRIEVES the ~2KB distilled chunk instead of re-crawling + re-understanding raw HTML every session = the token-waste fix, the automation of the PKS L4 reference-distillation tier). Unlike the INTERNAL substrate whose source_sha re-derives from local files, an external chunk's source lives on the public web and drifts SILENTLY; this gate reports every external chunk whose age exceeds its own ttl_days (default 30) so staleness is surfaced, then hands the fix: python tools/night_crawler.py --refresh-stale. NON-BLOCKING BY DESIGN — external staleness is expected and must never break a commit, so the gate ALWAYS exits 0 (reports, never fails). SKIPs cleanly if substrate/external/ is unseeded.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "night-crawler-selftest",
        "script":  "tools/night_crawler.py",
        "args":    ["--selftest"],
        "label":   "Night Crawler distill quality guard self-test (tools/night_crawler.py --selftest — deterministic, no network/AI, instant). The crawler's distiller now EVALUATES its output before bagging it (distill_quality, an Evaluator-Optimizer step): a thin / link-inflated / all-provenance / boilerplate distill is REFUSED not written, and a soft-404 / bot-wall error page is skipped BEFORE distilling (is_error_page) — so a nav/link-index or dead-URL page can't pollute substrate/external/. Born 2026-07-17 from the 12-Factor README distilling to license mush + 2 NN/g chunks the old harvest distilled from 404 pages. This gate runs the guard's fixtures (link_density + distill_quality + is_error_page: a good chunk passes; mush / 404 / all-provenance / NO_DURABLE_CONTENT fail) so a regression in the quality heuristics breaks the build. FIX on FAIL: the guard logic in tools/night_crawler.py changed — restore the fixtures' invariants.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "rubric-parity",
        "script":  "tools/validate_rubric_parity.py",
        "args":    [],
        "label":   "UFAI rubric SSOT parity (UR-P0 lock, 2026-07-21) — the prose ruler (substrate/reference/ufai-ux-rubric.md) and the code lens (survey_ufai_rubric.js, which tags each dim via M('A1')/J('D2')/NA('C2')) must AGREE: every dim the doc declares is encoded, and vice-versa, EXCEPT the cross-page S2/S3 owned by family_rubric_sweep; AND no header may claim a stale count. Born from the measured drift where ONE ruler had THREE counts (doc header 49, code header 44, body 63). Add a class to the prose without encoding it (or leave a header count stale) and this FAILs. The teeth of the UFAI_RUBRIC_CENTRALIZATION_ROADMAP §0 lock. FIX on FAIL: encode/document the missing dim, or reconcile the header count (a stale header IS the drift). Self-test: --self-test (deterministic, no files).",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "test-hive-fixtures",
        "script":  "tools/validate_test_hive_fixtures.py",
        "args":    [],
        "label":   "Stale test-hive fixture detector (2026-07-21) — a reseed re-mints hive UUIDs, so ANY pinned hive UUID in a harness/gate rots: the signed-in user isn't a member → RLS 0-rows / 403 not_a_member → the surface is SKIPPED or scanned EMPTY → the gate VACUOUSLY PASSES (silently disables itself). Proven: 3 generations of rot (9b4eaeac → 636cf7e8 → deleted; Lucena c9def338 → 4eec150e); asset-hub's Arc-W 'focal regression' was this class. Scans tools/** + root for hive-UUID pins on code lines, live-checks each against the hives table (SKIPs cleanly if DB down), exempts documented fallbacks + synthetic probe ids (>=6-char runs, e.g. isolation spoof PKs), and forward-ratchets the STALE count (baseline test_hive_fixture_baseline.json — may only FALL; started 54). THE FIX per hit: resolve at runtime — Python tools/lib/test_identity.py; JS live_page_journeys signIn()/h.hive. Never pin a newer UUID (that was 'the fix' twice; it rotted twice). Self-test: --self-test.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "accessor-load-order",
        "script":  "tools/validate_accessor_load_order.py",
        "args":    [],
        "label":   "Accessor-before-utils.js load-order (2026-07-22) — a utils.js-defined accessor (whWorker/whHiveId/…) called UNGUARDED in an inline script ABOVE the <script src=utils.js> tag throws ReferenceError at document-order execution. Born from the storage-SSOT sweep shipping dayplanner.html with `whWorker()` at L459 while utils loaded at L1710 → init IIFE threw → the page stuck on 'Loading day plan…' for EVERY user (invisible to console-only probes — it fires pageerror). Requires early calls to be `(typeof whWorker==='function'?…:fallback)`-guarded. Deterministic, offline, forward-only ratchet (baseline 0). Self-test: --self-test. FIX on FAIL: typeof-guard the early call + re-read the accessor at init after utils loads.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "client-write-grants",
        "script":  "tools/validate_client_write_grants.py",
        "args":    [],
        "label":   "Client-write GRANT parity (2026-07-22) — the LOCK for the 42501 'permission denied for table' class. For every base table a client page WRITES via .from('T').insert|upsert|update|delete, asserts `authenticated` (or PUBLIC) holds the matching privilege: insert→INSERT, update→UPDATE, delete→DELETE, upsert→INSERT+UPDATE+SELECT (ON CONFLICT read + PostgREST RETURNING). Born from Arc-K MS3: marketplace_sellers granted I/U/D but NOT SELECT → every seller's messenger/cert upsert 42501'd platform-wide (masked because reads go via a truth VIEW). 42501 is a GRANT-layer denial evaluated BEFORE RLS, so this can't be caught by policy checks. Teeth-proven both ways (revoke SELECT → flags the exact table+fix; restore → 0). Forward-only ratchet (baseline 0); skips cleanly if the DB is down. Complements validate_migration_grant_regression (the OVER-grant direction). FIX on FAIL: GRANT the named privilege, or add a `grant-check-allow` marker if the write is intentionally unreachable. Self-test: --self-test.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "redundant-widgets",
        "script":  "tools/validate_redundant_widgets.py",
        "args":    [],
        "label":   "Redundant status-chrome + duplicate-action widgets (2026-07-22) — the LOCK for the redundant-widget consolidation (Ian: 'redundant displays on every page … online and live pill … a bottom updated x min ago … a + widget but there are already a function of that'). Check A (deterministic): whFreshnessFooter must STAY a no-op — the bottom-right 'Updated X ago' footer DUPLICATED each page's own source chip (.wh-source-chip 'Live · refreshed…'), so it was neutered at its utils.js SSOT (removed the display on all ~18 adopters + the ~25 guarded call-sites in one edit); re-stamping it via whFreshnessChip() re-introduces the duplicate freshness platform-wide. Check B (forward ratchet, baseline 4): a create/primary action wired to 2+ STATIC buttons on one page (e.g. pm-scheduler's Add-asset '+' FAB + the 'Add Asset' bottom-nav tab, both goAddAsset(), both visible) is a redundant widget — route it to ONE labeled entry, not a second floating FAB. State-branch pairs (empty-vs-populated) stay in the baseline. Also silenced: the 'Live' realtime pill (hive+community) + the nav-hub 'Online' pill now hide when healthy, surface only on degrade. Self-test: --self-test. FIX on FAIL: keep the footer a no-op; remove the duplicate create-action button.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "rubric-coverage",
        "script":  "tools/rubric_coverage.py",
        "args":    ["--check"],
        "label":   "UFAI rubric coverage board (UR-P4, 2026-07-21) — aggregates the 61 single-page dims (family_rubric_scoreboard.json) + the 2 cross-page dims S2/S3 (component_consistency_corpus.json) into ONE 63-dim board (rubric_coverage.json), asserting every dim in ufai-rubric-spec.json has a measurement source. A new rubric dim with no source FAILs. Self-test: --self-test.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "journey-ux-dims",
        "script":  "tools/validate_journey_ux_dims.py",
        "args":    [],
        "label":   "UFAI experience-in-motion source-grep dims (2026-07-22, PDDA_UX_PAINPOINT_JOURNEY_ROADMAP) — the 3 journey dims the runtime __RUBRIC lens can't cleanly see, measured from page SOURCE + forward-ratcheted: J3 consequence (every destructive handler routes through the shared whConfirm OR is soft-delete-undoable — NN/g 'undo > confirmation'), G5 system-memory (a filterable page persists the user's filter/view/sort choice to localStorage), S4 behavioral-consistency (destructive actions use the ONE shared whConfirm, no raw window.confirm). Emits journey_ux_dims_report.json (the coverage-gate source for J3/G5/S4). Baselines in journey_ux_dims_baseline.json ratchet forward. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "ai-surface-quota",
        "script":  "tools/validate_ai_surface_quota.py",
        "args":    ["--check"],
        "label":   "D12 per-SURFACE AI cost/quota adoption (2026-07-23, the D-ledger's 'per-surface oracle unbuilt' cell, now built). `ai_rate_limits` is keyed by hive_id ALONE - one hourly+daily budget shared by EVERY AI surface - so a single runaway surface (looping companion, batch brief, retry storm) can drain the hive's whole AI allowance and starve assistant/voice/RAG/report-gen. This is a fairness+DoS bound, not just cost. The per-surface limiter ALREADY EXISTS (`_shared/rate-limit.ts` checkRouteRateLimit -> hive_route_quotas.hourly_cap + hive_route_calls counter keyed by (hive,route,hour), with an `enforce` flag so a surface can onboard in LOG-ONLY mode first) - so this is an ADOPTION gap, the METHOD-LAW shape (one unadopted central component, not N bespoke fixes). Currently 2/19 = 10.5% (ai-gateway, platform-gateway). Forward-only ratchet: a NEW rate-limited AI surface wired to the global cap alone drops the % and FAILs. Measurement only - changes no enforcement. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "ufai-deep-u",
        "script":  "tools/validate_ufai_deep_u.py",
        "args":    [],
        "label":   "UFAI U-pillar deep-verification lock (2026-07-23, PDDA §11 comprehensive deepwalk) — the live per-page deep-probe found the coarse A-Z lens (Z3 = 24px WCAG floor) was blind to the deeper UFAI U2 field standard (44px gloved-hand tap goal) + the Z2d responsive-image floor. The fix is a set of SHARED rules in tokens.css (the ONE file every page loads): input.wh-input/select.wh-select 44px, .btn-secondary/.btn-ghost 44px, img{max-width:100%}. This static gate asserts those shared rules STAY — remove one and every form control / secondary button / image on every page silently regresses below the field standard. Forward-only. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "file-upload-safety",
        "script":  "tools/validate_file_upload_safety.py",
        "args":    [],
        "label":   "File-upload safety — P12 upload-safety scanner (bug-hunt denominator v2, 2026-07-17). VERIFIED the platform has NO server-side file storage (zero storage.from().upload()); files are read client-side (resume->AI-extract, logbook photo->data-URI) and discarded, so classic unrestricted-upload/path-traversal (CWE-434/22) are low/N/A. The REAL residual on every <input type=file> surface is client-side: an accept= type allowlist AND a file.size cap (a huge file OOMs FileReader/canvas/the AI extractor = DoS). This gate asserts BOTH per surface; heuristic v1 (regex, so 'guarded'=references a byte-magnitude file.size, may display-not-enforce — refine to parse an actual cap comparison). Current: 9 surfaces, 2 gaps (integrations.html, inventory.html). ADVISORY / non-blocking (always exits 0) — surfaces the gap while per-page size-cap fixes land, then ratchets guarded-only. Self-test: --selftest (deterministic).",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "oc-updated-at-backed",
        "script":  "tools/validate_oc_updated_at_backed.py",
        "args":    [],
        "label":   "Optimistic-concurrency backing (LIVE) — every client `updated_at` write must be backed by a real column (bug-hunt roadmap P6, 2026-07-17). Scans client pages for `.from('T')...update({...updated_at...})` and asserts table T has an updated_at column in the DB. A write to a column-less table = a DEAD optimistic-concurrency guard + a phantom-column write (lost-update race + a likely 400 on the edit) — static analysis sees 'OC present' and misses it; only the live DB reveals the missing column. Born from pm_assets (pm-scheduler asset-edit OC was a dead no-op) + immediately caught the sibling marketplace_disputes (dispute-resolution admin flow). FIX: ADD COLUMN updated_at timestamptz DEFAULT now() + reuse the canonical touch_updated_at() trigger. Skips cleanly if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "attribution-pinned",
        "script":  "tools/validate_attribution_pinned.py",
        "args":    [],
        "label":   "Attribution-forge lock (LIVE) — every hive-scoped ACTION-attribution column (actor, approved_by, acknowledged_by, resolved_by, reviewed_by, assigned_by, submitted_by, dismissed_by, closed_by, rejected_by, completed_by, sent_by) must be pinned to the caller's hive_members identity by a bind trigger (bug-hunt roadmap P3/P5, 2026-07-18). RLS gates the ROLE (member/supervisor of the hive) but NOT the NAME — without a pin a caller stamps ANOTHER person's name on an approval/ack/assignment (intra-hive impersonation of an accountability record). Found live: alert_dismissals.actor + anomaly_signals.acknowledged_by/resolved_by (mig 000014) + 10 more approved_by/acknowledged_by/reviewed_by/assigned_by (mig 000015), all forge-probe verified. Same class as the worker_name sweep (migs 010/011) but different column names. Locks those pins against a dropped trigger AND catches any NEW unpinned attribution column. Skips if docker/DB unreachable. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "ai-hive-context",
        "script":  "tools/validate_ai_hive_context.py",
        "args":    [],
        "label":   "AI-context hive-resolution consistency (static) — a hive-id variable must never be ASSIGNED from the LEGACY `wh_hive_id` alone; the canonical resolution is `wh_active_hive_id || wh_hive_id || <default>` (bug-hunt roadmap P5, 2026-07-19). Live bug it locks: assistant.html's AI-gateway + semantic-RAG calls used `getItem('wh_hive_id') || null` while every data read used the active-first form — so in the modern flow (wh_active_hive_id set, wh_hive_id null) the assistant sent NULL hive context and answered WITHOUT the team knowledge base. Legit legacy reads (a `legId` backfill, the notif-key string concat) don't match the bug shape and are exempt. Forward-only, fast, no stack. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "approval-lock",
        "script":  "tools/validate_approval_lock.py",
        "args":    [],
        "label":   "Approval optimistic-lock class (static) — every client approve-write that stamps `approved_at: new Date()` must carry an optimistic lock (`.eq('status','pending')` OR `.is('approved_at',null)`) in the SAME chained update (bug-hunt roadmap P6/P7, 2026-07-19). Without it a concurrent approve / double-click / stale card silently OVERWRITES the first supervisor's approval attribution (approved_by/approved_at) = a last-write-wins accountability leak. Live-proven on rcm_fmea_modes (writerB re-approve overwrote 'Supervisor A'); the sweep it locks found 3 gaps — asset-hub approveFmeaMode/approveStrategy + alert-hub actOnAmcBrief (amc_briefings) + project-manager cancelCO — all fixed to mirror approveAssetNode/approveCO. Clears/restores (approved_at:null) are exempt. Forward-only, fast, no stack. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "readonly-p6-no-edit",
        "script":  "tools/validate_readonly_p6_no_edit.py",
        "args":    [],
        "label":   "Read-only P6 lock (static) — 11 pages VERIFIED to have no client edit surface (no .update/.upsert on a shared row) were scored P6=100 covered-by-nature (no concurrent-edit race possible). This gate asserts they STAY edit-free; if one gains a .update/.upsert its covered-by-nature basis is void → FAIL, forcing a real P6 hunt + re-score (bug-hunt roadmap, 2026-07-17). Forward-only, fast. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "anomaly-status-forward",
        "script":  "tools/validate_anomaly_status_forward.py",
        "args":    [],
        "label":   "Anomaly status forward-only machine (LIVE) — anomaly_signals must keep the BEFORE UPDATE OF status trigger that makes resolved/expired TERMINAL (bug-hunt alert-hub P6, 2026-07-17). Without it, a stale/concurrent Acknowledge regresses a resolved alert back to acknowledged (lost-update on the state machine; live-verified). Asserts trigger tg_anomaly_signals_forward_status + fn anomaly_signals_forward_only_status exist and still guard terminal states. Skips if docker/DB unreachable. FIX: re-apply mig 20260717000007. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "i18n-coverage",
        "script":  "tools/validate_i18n_coverage.py",
        "args":    [],
        "label":   "i18n coverage — P11 EN/FIL adoption of the shared data-i/_t localization system (bug-hunt denominator v2, 2026-07-17). Counts i18n markers (data-i= + _t( + whT() per USER-FACING page and classifies adoption (covered>=25 / partial / thin / none); internal-admin/dev/utility surfaces exempt. Current: 31 user-facing pages, 25 i18n-adopted (81%), 6 gaps (resume.html=0 worst). The P5 lever-ladder fix is adopting the SHARED system on the gaps, not per-page translation. Heuristic v1 (marker COUNT is an adoption proxy, not exact translated/total %). ADVISORY / non-blocking (always exits 0), ratchets. Self-test: --selftest.",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "intelligence-jsonb-shape",
        "script":  "tools/validate_intelligence_jsonb_shape.py",
        "args":    [],
        "label":   "Intelligence-layer JSONB shape (LIVE: asserts every jsonb column the Asset/Alert/Shift pages read as an array/object is actually stored as that jsonb type, never a double-encoded JSON *string* scalar. A seeder/producer doing `json.dumps(list)` into a jsonb column yields jsonb_typeof='string', which the consumers' `Array.isArray(x)?x:[]` guard silently reads as EMPTY — the staging card showed 0 parts while the rationale said '3 parts', and alert-hub printed '0 parts recommended … 3 parts appear'. Found+fixed 2026-07-12 [Asset/Alert/Shift PDDA F1]: seeders parts_staging.py + shift_plans.py did json.dumps; this LIVE type-shape gate caught a SECOND instance [shift_plans.payload 3/5 rows string] that static key-drift analysis cannot see. Covers parts_staging_recommendations.parts, anomaly_signals.top_reasons, shift_plans.payload, asset_risk_scores.top_factors. Skips per-column if empty/absent, whole gate if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "intelligence-write-isolation",
        "script":  "tools/validate_intelligence_write_isolation.py",
        "args":    [],
        "label":   "Intelligence-layer write isolation (LIVE two-tenant, rolled-back: simulates a real authenticated member and asserts a member CANNOT fabricate [INSERT] nor overwrite [UPDATE] an asset_risk_scores row — the nightly-batch-owned risk cache feeding asset-hub/alert-hub/shift-brain/analytics — nor insert an asset_node into a foreign hive, while their own-hive risk READ still works. Locks F11 [live-exploited 2026-07-12, Asset/Alert/Shift PDDA]: asset_risk_scores was a FOR ALL policy open to any active member, so a worker could inject a phantom 'critical' or bury a real one as 'low'; now service-role-only writes [matching sensor_readings/anomaly_signals]. + F10 defense-in-depth: asset_nodes_write USING owner-branch now hive-gated. Migration 20260712000013. Actors picked dynamically = reseed-robust. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "growth-write-isolation",
        "script":  "tools/validate_growth_write_isolation.py",
        "args":    [],
        "label":   "Growth-layer write isolation (LIVE, rolled-back: simulates a real authenticated member and asserts a member CANNOT self-mint a skill_badge [competence + 250 XP forgery] nor write a forged skill_exam_attempt nor write a skill_profile attributed to another worker [BOLA], that grade_skill_exam() exists + is SECURITY DEFINER [the only server-graded earn path], and that own-badge READ still works. Locks K1 [live-exploited 2026-07-12, Dayplanner/Growth PDDA]: skill_badges/skill_exam_attempts were client-writable + the exam was client-scored, so a worker could console-mint any badge; now client writes are locked + the exam is graded server-side vs the write-locked skill_exam_keys. + K6: skill_profiles WITH CHECK now pins auth_uid. Migrations 20260712000015/16. Actors picked dynamically = reseed-robust. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "reliability-kpi-faithfulness",
        "script":  "tools/validate_reliability_kpi_faithfulness.py",
        "args":    [],
        "label":   "Reliability-KPI faithfulness (LIVE: precomputed `asset_risk_scores.mtbf_days` must mirror the live canonical `get_mtbf_by_machine` engine — a divergence is allowed ONLY when a logbook event postdates the score's generated_at [bounded staleness the next cron folds in]. A divergence with NO newer source = a methodology fork / silent wrong reliability number = the temporal seesaw [ARC DI §10.5]. Measured live 2026-07-08: 90 machines, 1 bounded-stale, 0 unexplained. + a structural guard that batch-risk-scoring still sources mtbf from the canonical RPC. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "benchmark-rollup-faithfulness",
        "script":  "tools/validate_benchmark_rollup_faithfulness.py",
        "args":    [],
        "label":   "Cross-hive benchmark rollup faithfulness (LIVE: every `network_benchmarks` cross-tenant rollup must == the EXACT aggregate of the current per-hive `hive_benchmarks` in its segment [avg=mean, p25/p75=percentile_disc, sample_hives=distinct-hive count], sample_hives>=3 for privacy, no orphan rollup with no inputs — locks the cross-tenant seesaw [ARC DI §10.5]: a per-hive change that doesn't propagate benchmarks a hive against a stale/forked peer number. Measured live 2026-07-08: 5 rollups, 0 unfaithful/privacy/orphan; teeth-proven [a per-hive mutation was DETECTED]. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "embedding-no-stale-duplicates",
        "script":  "tools/validate_embedding_no_stale_duplicates.py",
        "args":    [],
        "label":   "Embedding re-embed-on-edit (LIVE: each logbook source entry must carry exactly ONE fault_knowledge embedding — a logbook edit-in-place re-calls embed-entry, which used to `.insert()` a SECOND embedding [no unique key on logbook_id], leaving a STALE duplicate in the RAG index [semantic search could return pre-edit text; ARC DI §10.5 embedding seesaw]. Migration 20260708000002 adds a UNIQUE index on fault_knowledge(logbook_id) + embed-entry now UPSERTs on it [re-embed REPLACES]. fix-to-ZERO. Skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "edge-observed-coverage",
        "script":  "tools/validate_edge_observed_coverage.py",
        "args":    [],
        "label":   "Edge observability coverage (fix-to-ZERO: every AI edge fn in ai_seams_catalog.ai_fns has serveObserved in its index.ts — the Arc-T net that lands a wh_traces error row on any unhandled throw must COVER every AI surface; a new AI fn shipped without the wrapper is an observability hole and blocks CI. Static fast half; the LIVE fire-proof is observability_fault_walk.py. Binds deep-walk D21 for the AI sub-grid).",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "frontend-floor-cells",
        "script":  "tools/validate_frontend_floor_cells.py",
        "args":    [],
        "label":   "Frontend floor cells (fix-to-ZERO ratchet over the live-mined F-lens in frontend_ufai_results.json: F1 consoleErrors==0 [D17 SMOKE — page loads clean] + F6 loading/empty/error present [D15 honest degraded states], on every production page the sweep covers. Fast half of the two-tool pattern [mine_frontend_ufai_surfaces.mjs probes, this ratchets]; a page that starts throwing a console error or drops a degraded state blocks CI. SKIPs if the artifact is absent).",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "deepwalk-flywheel",
        "script":  "tools/deepwalk_flywheel.py",
        "args":    [],
        "label":   "PLATFORM deep-walk FLYWHEEL v2 (Ian 2026-07-08): the WHOLE-platform quality ruler — GLOB-discovers the grid each cycle (40 pages × 13 oracle dims + 33 AI edge fns × 8 AI dims = ~784 cells → deepwalk_grid.json), EVIDENCE-BINDS every cell to an on-disk validator via its `# DEEPWALK-CELL: <surface> <dim>` self-tag (auto-joins a new validator with zero edits), derives ✅ (locked gate green) / 🟡 (oracle exists, unratcheted) / ⬜ (no oracle = the frontier), runs the DISCOVERED gate-floor (every tagged+registered-blocking validator), and names the lowest-coverage cell as the next --drive target. MEASURED %, not eyeballed; folds the DI §10.2 grid (100%) in as one sub-report. Exit 1 only if a locked gate regresses; coverage <100 is reported, not failed. Baseline 2026-07-08: 36.3% (page 28.7% · AI 50.8%).",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "warn",
    },
    {
        "id":      "rpc-write-integrity",
        "script":  "tools/validate_rpc_write_integrity.py",
        "args":    [],
        "label":   "RPC write-integrity (LIVE: every public plpgsql function's INSERT covers its target's NOT NULL columns + only writes tables that EXIST — locks two silent-100%-fatal classes found live 2026-07-07: NOT-NULL-omission [store_memory_turn] and stale-table-reference [delete_worker_data still UPDATEd the dropped `assets`]; both made a GDPR erasure / companion memory fail on every call behind a swallowed error; skips cleanly if the local DB is down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "cron-health",
        "script":  "tools/validate_cron_health.py",
        "args":    [],
        "label":   "Cron health (LIVE: no active pg_cron job's latest run failed with a CODE error — locks the unattended-silent-failure class found live 2026-07-07, where the soft-delete retention cron [hard_delete_expired_soft_deletes] errored 'column deleted_at does not exist' on 28 straight runs and nothing surfaced; excludes transient startup-timeouts + the local-only app.supabase_functions_url GUC; skips if pg_cron/DB absent)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "private-memory-isolation",
        "script":  "tools/validate_private_memory_isolation.py",
        "args":    [],
        "label":   "Private-memory isolation (LIVE: the per-worker AI-companion conversation tables [agent_memory/voice_journal_entries/dialog_state] must have OWNER-only SELECT policies — no hive_members read branch — locks the privacy leak found+proven-live 2026-07-07 where agent_memory_read let any hive member read another worker's private companion turns; dim-3; skips if DB down)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "leave-audit-ordering",
        "script":  "tools/validate_leave_audit_ordering.py",
        "args":    [],
        "label":   "Leave-audit ordering (hive.html writeAuditLog is awaitable + performLeave AWAITS the member_left audit BEFORE the hive_members self-delete — locks the race found live 2026-07-07 where fire-and-forget audit + awaited delete silently lost the audit trail once the delete committed first and RLS [hive_id IN user_hive_ids()] rejected the late insert; dim-6 destructive-action audit-trail)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "axe-live-authed",
        "script":  "tools/validate_axe_live.py",
        "args":    [],
        "label":   "Axe a11y — AUTHENTICATED write surfaces (LIVE: password-grants a seeded supervisor + scans the 9 Tier-1 write pages [hive/inventory/logbook/pm-scheduler/skillmatrix/community/dayplanner/marketplace/project-manager] through axe-core WCAG 2.2 AA @390px — the auth-gated pages the static axe_scan.js SKIPS, i.e. the highest-a11y-risk forms/modals/destructive surfaces. Integrity-at-zero: baseline 0, any NEW violation FAILs; proven 0 live 2026-07-07 [dim-8]. Skips cleanly if node/local-stack absent)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "assistant-recall",
        "script":  "tools/validate_assistant_recall.py",
        "args":    [],
        "label":   "Assistant multi-turn recall (ai-orchestrator's 0-agents 'not enough data' deflection must stay MEMORY-AWARE — guarded by memoryBlock + RECALL_RE — so a 'what did I just tell you?' recall question answers from the working buffer instead of deflecting; locks the CL5 defect found+fixed+live-verified 2026-07-08 where the Work Assistant had ZERO multi-turn recall while voice-journal recalled fine; dim-13)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "persona-echo-live",
        "script":  "tools/validate_persona_echo_live.py",
        "args":    [],
        "label":   "CL9 persona-echo LIVE (the floating companion's persona SELECTION must reach the backend: ai-gateway agent=voice-journal with context.persona=hezekiah|zaniah must echo data.persona back as the same value. Locks the fix for the live-caught bug where companion-launcher read an undefined getCurrentPersona + wrong key 'wh_persona' → the widget ALWAYS sent 'zaniah' while the avatar showed the real pick. Live-tier: GoTrue-auths a seeded worker, skips cleanly if the local stack is down; teeth-proven. 2026-07-08; dim-13)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "faithfulness-rail",
        "script":  "tools/validate_faithfulness_rail.py",
        "args":    [],
        "label":   "CL10 faithfulness rails (the assistant/chat brain is read-only advisory; two live-caught fabrication classes must stay guarded before an answer ships: (1) ACTION fabrication — 'Updated maintenance record'/'Log entry added' claims of writes it can't do [verified 0 logbook rows / 0 followups], stripped by _shared/action_provenance.ts; (2) ungrounded-KPI — token-accurate grounding + the no-provenance 'Your split is X%' hedge. Asserts both rails imported, token-accurate, committed-tested, and wired before the synthesis return; teeth-proven. Found+fixed+live-verified 2026-07-08; dim-13)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "clickable-keyboard-a11y",
        "script":  "tools/validate_clickable_keyboard_a11y.py",
        "args":    [],
        "label":   "Clickable keyboard a11y (dim-8 RESOLVED, not ratcheted: a runtime polyfill in utils.js [whClickableKbdA11y] makes every mouse-only clickable div/span/li keyboard-operable — focusable + role=button + Enter/Space activation, incl. dynamic renders. Gate asserts the polyfill is present + every active clickable-bearing page loads utils.js/fixes inline. Found+FIXED live 2026-07-07 platform-wide, not baselined)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "arc-u-focus-trap",
        "script":  "tools/validate_arc_u_focus_trap.py",
        "args":    [],
        "label":   "Arc U modal focus-trap + focus-restore (WCAG 2.1.2 No Keyboard Trap + 2.4.3 Focus Order — axe is STATIC and cannot see a focus trap. LIVE headless probe [tools/arc_u_focus_trap_probe.mjs, reuses FB2 programmatic sign-in, not the thrash-prone MCP browser] opens the marketplace Post modal [representative of all 9 sheets wired via wireSheetA11y->whModalA11y], Tab-walks 40x -> asserts focus-escapes=0 + Escape closes + focus returns to the opener #fab-post. Locks whModalA11y against regression. Verified clean 2026-07-11 [Arc U]. Skips cleanly if node/local-stack absent)",
        "group":   "Platform",
        "skip_if_fast": True,
        "severity": "fail",
    },
    {
        "id":      "plain-language",
        "script":  "tools/validate_plain_language.py",
        "args":    [],
        "label":   "Plain language (no consumer-tech jargon [KYB/IDOR/RLS], internal terms, or removed-payment vestige [escrow/2307/GMV] in user-facing static copy — audience is EVERY Filipino worker, not just engineers; Ian 2026-07-06. Industrial acronyms MTBF/OEE/RCM are WARN-only, expand on first use; marketplace marketing articles rewritten free/contact-only)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "supervisor-approval-backstop",
        "script":  "tools/validate_supervisor_approval_backstop.py",
        "args":    [],
        "label":   "Supervisor-approval backstop (approval-gated tables asset_nodes/rcm_fmea_modes/rcm_strategies carry the tg_guard_approval trigger so a worker cannot self-approve or delete signed-off work via direct PostgREST — locks the UI-only-gate privilege-escalation class found + exploited live 2026-07-07; dim-2)",
        "group":   "Platform",
        "skip_if_fast": False,
        "severity": "fail",
    },
    {
        "id":      "deeplink-param-contracts",
        "script":  "validate_deeplink_param_contracts.py",
        "args":    [],
        "label":   "Deep-Link Param Contracts (forward-only: no NEW emitted ?param lacks a .get() reader in its destination — catches the dead-param class from the Phase-6b edge walk)",
        "group":   "Platform",
        "report":  "deeplink_param_contracts_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "kpi-source-registry",
        "script":  "validate_kpi_source_registry.py",
        "args":    [],
        "label":   "KPI Source Registry (one metric = one official derivation; consumers must read it and never re-derive a documented wrong way — catches the F4 26-vs-4 class)",
        "group":   "Platform",
        "report":  "kpi_source_registry_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "tester-coverage",
        "script":  "validate_tester_coverage.py",
        "args":    [],
        "label":   "Tester Coverage Validator (every live tool page is in PUBLIC_PAGES + 4 flow PAGES lists)",
        "group":   "Platform",
        "report":  "tester_coverage_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "schema-coverage",
        "script":  "validate_schema_coverage.py",
        "args":    [],
        "label":   "Schema Coverage Validator (auto-derived from migrations, table+column existence)",
        "group":   "Platform",
        "report":  "schema_coverage_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "reset-coverage",
        "script":  "validate_reset_coverage.py",
        "args":    [],
        "label":   "Reset Coverage Validator (every migration table is in reset.py)",
        "group":   "Platform",
        "report":  "reset_coverage_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "edge-config",
        "script":  "validate_edge_config.py",
        "args":    [],
        "label":   "Edge Function Config Validator (config.toml coverage)",
        "group":   "Platform",
        "report":  "edge_config_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "cross-page",
        "script":  "validate_cross_page.py",
        "args":    [],
        "label":   "Cross-Page Flow Validator",
        "group":   "Platform",
        "report":  "cross_page_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "dom-refs",
        "script":  "validate_dom_refs.py",
        "args":    [],
        "label":   "DOM Reference Integrity Validator (bare getElementById on missing elements)",
        "group":   "Platform",
        "report":  "dom_refs_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "asset-brain",
        "script":  "validate_asset_brain.py",
        "args":    [],
        "label":   "Asset Brain Foundation Validator (schema, RLS, realtime publication)",
        "group":   "Platform",
        "report":  "asset_brain_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "canonical-sources",
        "script":  "validate_canonical_sources.py",
        "args":    [],
        "label":   "Canonical Sources Registry Validator (truth-scattering fix foundation + L2 drift detection)",
        "group":   "Platform",
        "report":  "canonical_sources_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "kpi-chip-coverage",
        "script":  "validate_kpi_chip_coverage.py",
        "args":    [],
        "label":   "KPI Chip Coverage Validator (pages reading v_*_truth must render renderSourceChip)",
        "group":   "Platform",
        "report":  "kpi_chip_coverage_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        "id":      "calm-canonical-audit",
        "script":  "tools/audit_calm_dashboard_canonical.py",
        "args":    [],
        "label":   "Calm Dashboard Canonical-Wiring Audit (per-tile classify: canonical/drift/gap/allowed)",
        "group":   "Platform",
        "report":  "calm_canonical_audit_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        # Arc P (Pareto Page Revamp) content gate. Forward-only ratchet on the ONE
        # signal Ian named: DISPLAYED defensive-copy count = 0 platform-wide ("kill
        # 'we won't fake this'"). Scans HTML visible text + maturity-gate-consumer
        # inline JS + shared DOM-renderer .js, stripping comments / JSON-LD / AI
        # system prompts first (the R0 3x-over-count lesson). Baseline auto-tightens
        # DOWN (Rule B); FAILS only on a NEW defensive phrase. Wave 0 drives 10 -> 0.
        "id":      "pareto-content",
        "script":  "validate_pareto_content.py",
        "args":    ["--gate"],
        "label":   "Pareto Content Gate (Arc P: displayed defensive-copy ratchet -> 0; per-page P1/P3 metrics)",
        "group":   "Platform",
        "report":  "pareto_content_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        # Arc P P4 lens: NO EM DASH in displayed copy (the standing no-em-dash rule).
        # Prose em dashes hide in dynamically-rendered strings the empty-state walks miss
        # (found 11 on ph-intelligence/ai-quality only after walking them populated).
        # Forward-only ratchet (Rule B): FAILS only when the displayed em-dash count RISES
        # above the frozen baseline; auto-tightens DOWN as pages are cleaned. Scans HTML
        # visible text + title/aria/placeholder attrs + inline JS display strings + content
        # .js, excluding comments / non-display harness JS. Baseline seeded at the honest
        # current count; the sweep drives it toward 0 over sessions.
        "id":      "no-em-dash",
        "script":  "validate_no_em_dash.py",
        "args":    ["--gate"],
        "label":   "No-Em-Dash Gate (Arc P: displayed em-dash ratchet, forward-only toward 0)",
        "group":   "Platform",
        "report":  "no_em_dash_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        # L-1.5 platform-wide canonical-drift miner. Closes the seam between
        # validate_canonical_sources (which grandfathers via KNOWN_DRIFT /
        # HTML_OWNERS) and audit_calm_dashboard_canonical (which only scans
        # Calm-opted-in pages). Caught the "21 PM overdue on hive vs 0 on
        # pm-scheduler" mismatch on 2026-05-20: pm-scheduler was grandfathered
        # owner of pm_scope_items AND reimplemented FREQ_DAYS/calcNextDue
        # locally. The miner tags pages that render hero KPIs and read raw
        # tables that have a v_*_truth view as TIER A — drift here produces
        # the "two pages, two numbers" symptom users notice.
        "id":      "canonical-drift-platform-miner",
        "script":  os.path.join("tools", "mine_canonical_drift_platform.py"),
        "args":    [],
        "label":   "Canonical Drift — Platform-Wide Miner (L-1.5: TIER A = KPI page + canonical drift; produces baseline)",
        "group":   "Platform",
        "report":  "canonical_drift_platform_report.json",
        "skip_if_fast": False,
        "severity": "blocker",
    },
    {
        # L0 forward-only ratchet over the L-1.5 miner. FAILs when:
        #   - a page that wasn't TIER A becomes TIER A
        #   - a TIER A page's drift count regresses upward
        #   - local truth-math is introduced where baseline had none
        # Baseline lives in canonical_drift_baseline.json and only moves
        # downward (via --update-baseline after a deliberate reduction).
        "id":      "user-facing-kpi-canonical",
        "script":  "validate_user_facing_kpi_canonical.py",
        "args":    [],
        "label":   "User-Facing KPI Canonical Gate (L0: forward-only ratchet over L-1.5 TIER A footprint)",
        "group":   "Platform",
        "report":  "user_facing_kpi_canonical_report.json",
        "skip_if_fast": False,
    },
    {
        # Cross-migration table-collision auditor. Catches the agent_memory
        # class of bug where two migrations both `CREATE TABLE IF NOT EXISTS X`
        # with incompatible column sets. The static counterpart to the runtime
        # sentinel that surfaced this on 2026-05-20 (5 collisions found across
        # 102 migrations, all documented with `-- table-collision-allow:` markers).
        # Exits 1 on any unallowed collision.
        "id":      "table-collision-audit",
        "script":  os.path.join("tools", "audit_table_collision.py"),
        "args":    [],
        "label":   "Cross-Migration Table-Collision Auditor (catches CREATE TABLE IF NOT EXISTS with incompatible column sets across migrations)",
        "group":   "Platform",
        "report":  "table_collision_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "phantom-captures",
        "script":  "tools/audit_phantom_captures.py",
        "args":    [],
        "label":   "Phantom Capture Auditor (reverse-lineage: every <input>/<select> must have >=1 downstream consumer)",
        "group":   "Platform",
        "report":  "phantom_captures_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "phantom-columns",
        "script":  "tools/audit_phantom_columns.py",
        "args":    [],
        "label":   "Phantom Column Auditor (schema-bloat: every column in registry must have >=1 consumer)",
        "group":   "Platform",
        "report":  "phantom_columns_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "tier-contracts",
        "script":  "tools/audit_tier_contracts.py",
        "args":    [],
        "label":   "Tier Contract Auditor (Fuel/Engine/Brain/Glue registry health + chain integrity)",
        "group":   "Platform",
        "report":  "tier_contracts_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "standards-alignment",
        "script":  "tools/audit_standards_alignment.py",
        "args":    [],
        "label":   "Standards Alignment Auditor (Tier S — formula required_inputs supersets cited standard OR honestly declared partial_variant)",
        "group":   "Platform",
        "report":  "standards_alignment_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ai-prompt-standards",
        "script":  "tools/audit_ai_prompt_standards.py",
        "args":    [],
        "label":   "AI Prompt Standards Audit (Tier B — edge fn prompts mentioning a metric must cite its canonical standard)",
        "group":   "Platform",
        "report":  "ai_prompt_standards_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "displayed-values",
        "script":  "tools/audit_displayed_values.py",
        "args":    [],
        "label":   "Displayed Values Audit (Tier S coverage — every value rendered to users should map to a formula contract OR be classified as raw display)",
        "group":   "Platform",
        "report":  "displayed_values_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "correctness-scoreboard",
        "script":  "tools/build_correctness_scoreboard.py",
        "args":    ["--check"],
        "label":   "CORRECTNESS anti-drift scoreboard — the value-at-the-glass sibling of bughunt-scoreboard. Regenerates CORRECTNESS_SCOREBOARD.md mapping every contracted user-facing metric to the QA WHAT-axis (a canonical-source · b calculation · c cross-surface parity · d db-truth · e provenance) and its covering gate; FAILs if a contracted metric loses source/formula/static-parity coverage. Reads displayed_values_report.json (so runs after the displayed-values audit refreshes). 2026-07-20: 10 metrics · 10 COVERED · 0 GAP · 6 multi-page. Residual tracked build = RUNTIME cross-surface parity (a live probe that a multi-page hive KPI renders the same value on each page)",
        "group":   "Platform",
        "skip_if_fast": True,
    },
    {
        "id":      "partial-label-honesty",
        "script":  "tools/audit_partial_label_honesty.py",
        "args":    [],
        "label":   "Partial-Label Honesty Audit (Tier S rendering — every page displaying a partial-variant metric must render the honesty marker near the value)",
        "group":   "Platform",
        "report":  "partial_label_honesty_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "home-stack-coverage",
        "script":  "validate_home_stack_coverage.py",
        "args":    [],
        "label":   "Home Stack Coverage Validator (primary-nav cardinality + hidden tools have deep-links)",
        "group":   "Platform",
        "report":  "home_stack_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "js-syntax-sanity",
        "script":  "validate_js_syntax_sanity.py",
        "args":    [],
        "label":   "JS Syntax Sanity (no `await` inside non-async function/IIFE in inline scripts)",
        "group":   "Platform",
        "report":  "js_syntax_sanity_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "silo-monitor",
        "script":  "validate_silo_monitor.py",
        "args":    [],
        "label":   "Silo Monitor (4-layer: drift + orphans + unregistered hotspots + cross-system matrix)",
        "group":   "Platform",
        "report":  "silo_monitor_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "canonical-anchor",
        "script":  "validate_canonical_anchor.py",
        "args":    [],
        "label":   "Canonical Anchor Gate (8-layer forward-anchor: fuel/engine/Tier A/Tier C/formula/standard/dashboard/capture)",
        "group":   "Platform",
        "report":  "canonical_anchor_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — meta-validator: every consumer-scanning audit must cover
        # supabase/functions/_shared/**/*.ts + subdirectory HTML, or the next
        # contributor will reintroduce the false-positive phantom-column class
        # caught 2026-05-20 (memory: feedback_audit_scanner_scope.md).
        "id":      "audit-scanner-scope",
        "script":  "validate_audit_scanner_scope.py",
        "args":    [],
        "label":   "Audit Scanner Scope (meta-validator: every consumer-scanning audit covers _shared + subdir HTML)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — catches semantic drift INSIDE the same canonical signal:
        # surfaces that read a v_*_truth column but locally re-derive its math
        # (qty_on_hand <= reorder_point, FREQ_DAYS, Date.now() - last_completed,
        # 'nodata' fallback for never-serviced items). Three real bugs caught
        # on first run: pm-scheduler.html, index.html low-stock, logbook.html.
        "id":      "truth-view-signal-trust",
        "script":  "validate_truth_view_signal_trust.py",
        "args":    [],
        "label":   "Truth-View Signal-Trust (no local re-derivation alongside v_*_truth reads; forward-only ratchet)",
        "group":   "Platform",
        "report":  "truth_view_signal_trust_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — catches KPI tiles declared in HTML with default values
        # ("0", "—") that no JS setter ever populates. Caught the marketplace
        # `mk-total-hero` / skillmatrix `sm-*-hero` class on first pass (turned
        # out wired via setCard dispatch; baseline 0 locks the cleaned state).
        "id":      "orphan-kpi-tiles",
        "script":  "validate_orphan_kpi_tiles.py",
        "args":    [],
        "label":   "Orphan KPI Tiles (every default-value tile must have a JS setter; forward-only ratchet)",
        "group":   "Platform",
        "report":  "orphan_kpi_tiles_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — catches the home-tile undercount class: a page does
        # `db.from(v_*_truth)...limit(N)` then renders `arr.length` as a
        # KPI count. The number caps at N silently when actual data exceeds.
        # Caught the index.html Open Jobs / Risk Alerts bug (limit(5)) and
        # marketplace-seller.html badges (limit(50)).
        "id":      "kpi-count-query-safety",
        "script":  "validate_kpi_count_query_safety.py",
        "args":    [],
        "label":   "KPI Count-Query Safety (no .limit(N) + .length as canonical KPI count; forward-only ratchet)",
        "group":   "Platform",
        "report":  "kpi_count_query_safety_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every renderSourceChip({ source: 'v_X_truth + ...' })
        # must reference views the page actually reads. Catches stale chip
        # declarations that lie about lineage after a refactor (page stopped
        # reading view X, but the chip still claims it). Baseline tightened
        # from 7 to 0 the same day by fixing hive chips + allow-markering
        # RPC/wrapper-backed chips.
        "id":      "source-chip-truth",
        "script":  "validate_source_chip_truth.py",
        "args":    [],
        "label":   "Source-Chip Truth (every renderSourceChip view is actually .from()-read on the page; forward-only ratchet)",
        "group":   "Platform",
        "report":  "source_chip_truth_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-06-14 (STREAMLINE §13/§14 E1) — keeps developer jargon OFF the glass.
        # Ian screenshotted dashboard captions leaking v_*_truth view names, RPC/edge-fn
        # names, code idents (_pmOverdueCount, hideZeroStat()), *.md doc refs and raw SQL
        # predicates (qty_on_hand <= min_qty). The provenance chip is good; its TEXT was
        # authored in engineer voice. Scans user-VISIBLE strings only — chip
        # freshness/window/notes + HTML explainer blocks — NOT the source: field (that
        # stays canonical for source-chip-truth and is translated via WH_SOURCE_LABELS in
        # utils.js) and NOT JS/HTML comments or <code>/<pre>. Forward-only ratchet.
        "id":      "user-facing-jargon",
        "script":  "validate_user_facing_jargon.py",
        "args":    [],
        "label":   "User-Facing Jargon (no v_*_truth / RPC / code-ident / *.md / SQL on the glass; chip source: exempt; forward-only ratchet)",
        "group":   "Platform",
        "report":  "user_facing_jargon_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-06-14 (STREAMLINE §14 E4) — the design palette/type/spacing from
        # designer SKILL.md was raw hex inline on every page (a wrong orange
        # #e8920a once drifted into parts-tracker/assistant). E4 promotes it to
        # CSS custom properties in components.css :root. This gate: L1 the token
        # block must declare every canonical value (palette can't drift/delete),
        # L2 the drift hex #e8920a is banned on the glass, L3 raw-brand-hex
        # inline usage ratchets forward-only (use var(--wh-*)).
        "id":      "design-tokens",
        "script":  "validate_design_tokens.py",
        "args":    [],
        "label":   "Design Tokens (components.css :root canonical palette intact + no #e8920a drift + raw-brand-hex forward-only ratchet)",
        "group":   "Platform",
        "report":  "design_tokens_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-07-16 (FULLSTACK_COMPONENT_LIBRARY_ROADMAP §2.3 F-P2) — FAMILY_UFAI
        # §10 proved dims fail exactly where canonical components sit unadopted
        # (whListSkeleton, .wh-disclose, whFmt*…). This ratchet recomputes adoption
        # LIVE per design_component_registry.json row over the 32 family pages and
        # fails any drop below the component_adoption_baseline.json floor;
        # rises auto-tighten. Also fails registry/floor orphans + inline
        # redefinitions of canonical utils.js functions.
        "id":      "component-adoption",
        "script":  "validate_component_adoption.py",
        "args":    [],
        "label":   "Component Adoption (canonical design-library adoption per registry row; forward-only floors, auto-tighten; no inline redefinitions)",
        "group":   "Platform",
        "report":  "component_adoption_gate_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-07-17 (FULLSTACK_COMPONENT_LIBRARY_ROADMAP Layer A, A-P2) — the Layer-A
        # sibling of component-adoption: canonical _shared/ module adoption per
        # api_component_registry.json row, recomputed live over every edge function's
        # index.ts. A function dropping its cors/envelope/rate-limit/tenant-context
        # import fails; rises auto-tighten. Exemptions documented in the registry
        # (voice-model-call orphan; fixed-endpoint outbound fns).
        "id":      "api-adoption",
        "script":  "validate_api_adoption.py",
        "args":    [],
        "label":   "API Adoption (canonical _shared/ module adoption per edge function; forward-only floors, auto-tighten)",
        "group":   "Platform",
        "report":  "api_adoption_gate_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-07-17 (FULLSTACK_COMPONENT_LIBRARY_ROADMAP Layer D, D-P2) — canonical DB
        # PATTERN adoption over the substrate's live-DB-derived chunks: RLS on tenant
        # tables, hive-membership scoping, auth_uid ownership policies, security_invoker
        # views. A view/table dropping its pattern fails; rises auto-tighten. Source
        # chunks are freshness-gated by validate_substrate_freshness.py.
        "id":      "db-adoption",
        "script":  "validate_db_adoption.py",
        "args":    [],
        "label":   "DB Adoption (canonical RLS/policy/invoker pattern adoption per table/view; forward-only floors, auto-tighten)",
        "group":   "Platform",
        "report":  "db_adoption_gate_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-07-17 (FULLSTACK_COMPONENT_LIBRARY_ROADMAP Layer AU, AU-P2) — the client
        # session/identity floor: restoreIdentityFromSession + session-settled reads
        # (the cold-load-401 class) per family page. A page dropping either regresses.
        "id":      "au-adoption",
        "script":  "validate_au_adoption.py",
        "args":    [],
        "label":   "AU Adoption (client auth floor: identity restore + session-settled reads per page; forward-only floors)",
        "group":   "Platform",
        "report":  "au_adoption_gate_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-07-17 (FULLSTACK_COMPONENT_LIBRARY_ROADMAP Layer AV) — the offline canonical
        # set (banner/queue/connectivity/session-timeout/device-fingerprint) ships as ONE
        # unit on every non-exempt family page (29/29 at wave completion). A page dropping
        # any of the five, or carrying a partial set, fails.
        "id":      "av-adoption",
        "script":  "validate_av_adoption.py",
        "args":    [],
        "label":   "AV Adoption (offline canonical set per page: full 5-script unit; forward-only floor + no-partial rule)",
        "group":   "Platform",
        "report":  "av_adoption_gate_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — catches enum-column filter case/spelling drift across
        # surfaces. Two pages filtering `.eq('status', 'Open')` vs
        # `.eq('status', 'open')` return different result sets from the SAME
        # column. Tracks `(column, lowercase(value))` and fails when 2+
        # files use distinct case variants. Allow with `// filter-case-allow`.
        "id":      "filter-case-consistency",
        "script":  "validate_filter_case_consistency.py",
        "args":    [],
        "label":   "Filter Case Consistency (same enum-column filter must use consistent case across files; forward-only ratchet)",
        "group":   "Platform",
        "report":  "filter_case_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — catches realtime subscription drift. `hive.html` had
        # been subscribing to `postgres_changes` on the DEAD `assets` table
        # for months — supervisors never got realtime "asset pending approval"
        # notifications because workers actually submit to `asset_nodes`.
        # Fixed in same commit. Validator subscribes-table must match (or be
        # an underlying-table of) the page's .from() reads.
        "id":      "realtime-subscription",
        "script":  "validate_realtime_subscription_consistency.py",
        "args":    [],
        "label":   "Realtime Subscription Consistency (every postgres_changes table must be read by the page; forward-only ratchet)",
        "group":   "Platform",
        "report":  "realtime_subscription_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — catches dead-link CTAs (href / location.href targets
        # to a .html file that doesn't exist on disk). User clicks → 404.
        # Caught voice-journal.html → login.html on first run (the canonical
        # signin redirect is index.html?signin=1; login.html never existed).
        "id":      "link-target-existence",
        "script":  "validate_link_target_existence.py",
        "args":    [],
        "label":   "Link Target Existence (every <a href>/location.href to a .html target must exist on disk; forward-only ratchet)",
        "group":   "Platform",
        "report":  "link_target_existence_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every payload.new.X / payload.old.X in a
        # postgres_changes callback must be a real column of the subscribed
        # table. Sibling to realtime-subscription (which checks table).
        "id":      "realtime-payload-columns",
        "script":  "validate_realtime_payload_columns.py",
        "args":    [],
        "label":   "Realtime Payload Columns (payload.new/old.X must be a real column on the subscribed table; forward-only ratchet)",
        "group":   "Platform",
        "report":  "realtime_payload_columns_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every functions.invoke('NAME') must point at a real
        # edge fn directory. Caught silent-404 risk when fn renamed.
        "id":      "edge-function-invoke",
        "script":  "validate_edge_function_invoke.py",
        "args":    [],
        "label":   "Edge Function Invoke (every functions.invoke('X') target must exist; forward-only ratchet)",
        "group":   "Platform",
        "report":  "edge_function_invoke_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every db.rpc('X', { p_y: ... }) must use real arg
        # keys for the RPC's signature. Caught registry bug where the
        # CREATE FUNCTION regex truncated args at vector(384) — fixed there
        # so this validator can do its job cleanly.
        "id":      "rpc-argument-consistency",
        "script":  "validate_rpc_argument_consistency.py",
        "args":    [],
        "label":   "RPC Argument Consistency (every db.rpc() name + arg keys exist; forward-only ratchet)",
        "group":   "Platform",
        "report":  "rpc_argument_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every <img src>, <link href>, <script src>, css url()
        # pointing at a local asset must resolve to a file. Catches broken
        # image icons and 404'd CSS/JS includes after a rename.
        "id":      "image-asset-existence",
        "script":  "validate_image_asset_existence.py",
        "args":    [],
        "label":   "Image / Asset Existence (every local asset ref must resolve to a file; forward-only ratchet)",
        "group":   "Platform",
        "report":  "image_asset_existence_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every path in sw.js's SHELL_FILES = [...] array
        # must exist. Otherwise SW precache install fails silently.
        "id":      "service-worker-shell",
        "script":  "validate_service_worker_shell.py",
        "args":    [],
        "label":   "Service Worker SHELL_FILES (every precache path must exist; forward-only ratchet)",
        "group":   "Platform",
        "report":  "service_worker_shell_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every column in .select/.eq/.in/.gt/.gte/.lt/.lte/
        # .order/.is on a known table must be a real column. Catches schema-
        # rename drift where a column was removed/renamed but consumer code
        # still references the old name. Includes a registry-miner fix for
        # multi-clause ALTER TABLE ADD COLUMN.
        "id":      "query-column-existence",
        "script":  "validate_query_column_existence.py",
        "args":    [],
        "label":   "Query Column Existence (every .select/.eq/.in column must exist on the table; forward-only ratchet)",
        "group":   "Platform",
        "report":  "query_column_existence_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-28 — sibling of query-column-existence: closes its blind spot
        # (`cols = table_cols.get(table); if cols is None: continue` silently
        # skips refs to objects that don't exist AT ALL). Every .from('T')/
        # /rest/v1/T must be a real table/view; every .rpc('fn')/rest/v1/rpc/fn
        # a real function. Found via the MCP cockpit flywheel (Playwright 404 +
        # Postgres cross-verify). Allow with `// obj-exist-allow: <reason>`.
        "id":      "supabase-object-existence",
        "script":  "validate_supabase_object_existence.py",
        "args":    [],
        "label":   "Supabase Object Existence (every .from/.rpc/REST object must exist in the canonical registry; forward-only ratchet)",
        "group":   "Platform",
        "report":  "supabase_object_existence_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-28 — GH hardening bridge from the cockpit flywheel: every NAMED
        # relative import under supabase/functions/** must resolve to a real
        # export. Catches the boot-break class (Deno "module does not provide an
        # export named X") that passes every static gate and only 503s at
        # `functions serve`. Caught cors.ts/corsHeaders + pdf-ingest/embedText.
        "id":      "edge-import-exports",
        "script":  "validate_edge_import_exports.py",
        "args":    [],
        "label":   "Edge Import/Export Resolution (every named relative import resolves to a real export; forward-only ratchet)",
        "group":   "Platform",
        "report":  "edge_import_exports_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-30 — memory-stack flywheel Turn 1 (layer 02 Episodic). Keeps the
        # durable agent_episodic_memory layer (Phase 7) wired into the live
        # gateway path: recallEpisodic before forward + persistEpisodic after,
        # via the single-source-of-truth _shared/episodic-memory.ts. Guards
        # against a refactor silently re-orphaning the episodic layer (it was
        # dead substrate — table + CRUD fn existed, gateway never called them).
        "id":      "episodic-memory-wiring",
        "script":  "validate_episodic_memory_wiring.py",
        "args":    [],
        "label":   "Episodic Memory Wiring (agent_episodic_memory recall+persist stays wired into ai-gateway; forward-only ratchet)",
        "group":   "Platform",
        "report":  "episodic_memory_wiring_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-30 — memory-stack flywheel Turn 2 (layer 07 Shared Memory).
        # Keeps the verified-state / conflict-resolution surface over
        # unified_events (v_asset_state_truth, resolved by source trust
        # precedence then recency) wired through _shared/verified-state.ts into
        # the gateway. Guards "one truth, every agent aligned" from regression.
        "id":      "verified-state-wiring",
        "script":  "validate_verified_state_wiring.py",
        "args":    [],
        "label":   "Verified-State Wiring (v_asset_state_truth conflict resolution stays wired into ai-gateway; forward-only ratchet)",
        "group":   "Platform",
        "report":  "verified_state_wiring_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every getElementById('X')/querySelector('#X') must
        # match an HTML element with id=X. Sibling of orphan-kpi-tiles
        # (which finds the opposite: HTML elements with no JS setter).
        "id":      "getelementbyid-orphan-setter",
        "script":  "validate_getelementbyid_orphan_setter.py",
        "args":    [],
        "label":   "getElementById Orphan Setter (every JS id lookup must have a matching <id> in HTML; forward-only ratchet)",
        "group":   "Platform",
        "report":  "getelementbyid_orphan_setter_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — surfaces hardcoded `N * 86400000` day windows where
        # the same context keyword (overdue/completed/recent/...) is used
        # with DIFFERENT N values across files. Catches "different numbers
        # because different windows" silent drift.
        "id":      "time-window-consistency",
        "script":  "validate_time_window_consistency.py",
        "args":    [],
        "label":   "Time-Window Consistency (same context keyword must use same N*day window across files; forward-only ratchet)",
        "group":   "Platform",
        "report":  "time_window_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — role-string permission-gate consistency. Every
        # `role === 'X'` literal must use a canonical role name; off-canon
        # strings are typo / privilege-drift candidates.
        "id":      "role-string-consistency",
        "script":  "validate_role_string_consistency.py",
        "args":    [],
        "label":   "Role String Consistency (every role === '...' literal must use a canonical role name; forward-only ratchet)",
        "group":   "Platform",
        "report":  "role_string_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — inline onclick/onchange/... handlers must reference
        # a defined function. Caught engineering-design.html → syncEGSoilInput()
        # which was a stale handler (function never existed). Fixed by removing
        # the dead onchange attribute.
        "id":      "inline-onclick-handler",
        "script":  "validate_inline_onclick_handler.py",
        "args":    [],
        "label":   "Inline Handler Existence (every onclick/onchange/... fn must be defined; forward-only ratchet)",
        "group":   "Platform",
        "report":  "inline_onclick_handler_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-21 paydown — bug-class L0 ratchets added during flywheel
        # turns 31-35 that landed on disk but were never wired into the
        # platform-check runner (caught by auto-discovery
        # validator_registered check).
        "id":      "empty-catch",
        "script":  "validate_empty_catch.py",
        "args":    [],
        "label":   "Empty Catch Block (try/catch{} that silently swallows errors; forward-only ratchet)",
        "group":   "Platform",
        "report":  "empty_catch_report.json",
        "skip_if_fast": False,
    },
    {
        # Locks the 2026-07-23 wayfinding-pill CLS flicker: wayfinding.js sets body.paddingTop
        # POST-PAINT on bare pages (via nav-hub), so under contention a DIFFERENT bare page shifts
        # ~64px = ~0.1 CLS each sweep (the intermittent rotating I1 the dynamic sweep can't reliably
        # catch). Every page that WILL get the pill (not-home + loads nav-hub + no in-layout back
        # affordance + has <main>/<h1>) must ship the static `body{padding-top:calc(64px+env(...))}`
        # reserve so the pill band is present at first paint (wayfinding's `if(band>cur)` then skips).
        "id":      "pill-reserve",
        "script":  "validate_pill_reserve.py",
        "args":    [],
        "label":   "Wayfinding Pill CLS-Reserve (every pill-page ships the static back-pill band reserve; absolute, baseline 0)",
        "group":   "Platform",
        "report":  "pill_reserve_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "settimeout-string",
        "script":  "validate_settimeout_string.py",
        "args":    [],
        "label":   "setTimeout/setInterval String Arg (string-form is eval-equivalent; forward-only ratchet)",
        "group":   "Platform",
        "report":  "settimeout_string_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "document-write",
        "script":  "validate_document_write.py",
        "args":    [],
        "label":   "document.write Usage (forbidden API; forward-only ratchet)",
        "group":   "Platform",
        "report":  "document_write_report.json",
        "skip_if_fast": False,
    },
    {
        # Deterministic half of the Holistic/Cross-Page Critic (Grounded MCP Sweep
        # Phase 4.7): redundancy is a RELATIONSHIP between files, invisible to the
        # per-element critic. Wraps jscpd (clone detector); forward-only ratchet on
        # DUPLICATED-LINES (S12 2026-06-14: switched from clone-COUNT, which S8's page
        # fusions made misleading — count fell while % rose; predictive.html now excluded).
        # Baseline clone_debt_baseline.json = 4742 lines / 25.92%. Degrades to SKIP if jscpd
        # absent (npm i -D jscpd to activate). Blocks NEW copy-paste; collapsing ratchets it down.
        "id":      "clone-debt",
        "script":  "validate_clone_debt.py",
        "args":    [],
        "label":   "Clone Debt (jscpd cross-page duplication; forward-only ratchet — redundancy critic)",
        "group":   "Platform",
        "report":  "clone_debt_baseline.json",
        "skip_if_fast": False,
    },
    {
        "id":      "tabindex-positive",
        "script":  "validate_tabindex_positive.py",
        "args":    [],
        "label":   "Positive tabindex (a11y anti-pattern: tabindex >= 1 breaks tab order; forward-only ratchet)",
        "group":   "Platform",
        "report":  "tabindex_positive_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "viewport-user-scalable",
        "script":  "validate_viewport_user_scalable.py",
        "args":    [],
        "label":   "Viewport user-scalable=no (a11y anti-pattern: blocks pinch-zoom; forward-only ratchet)",
        "group":   "Platform",
        "report":  "viewport_user_scalable_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — innerHTML = `...${interp}...` template literals must
        # run interpolations through escHtml/sanitize/e() escaper. XSS class
        # guard with forward-only ratchet.
        "id":      "innerhtml-eschtml",
        "script":  "validate_innerhtml_eschtml.py",
        "args":    [],
        "label":   "innerHTML escHtml Audit (interpolating template literals must escape; XSS guard, forward-only ratchet)",
        "group":   "Platform",
        "report":  "innerhtml_eschtml_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — Deno.env.get('X') / process.env.X references in edge
        # fns + python-api must be documented in .env.example/README. Catches
        # secret-rename drift that would crash edge fns at runtime.
        "id":      "env-variable-existence",
        "script":  "validate_env_variable_existence.py",
        "args":    [],
        "label":   "Env Variable Existence (every env reference must be in .env.example/README; forward-only ratchet)",
        "group":   "Platform",
        "report":  "env_variable_existence_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — interactive elements (button, input) must have an
        # accessible name (aria-label / aria-labelledby / title / associated
        # label / visible text). Accessibility class with forward-only ratchet.
        "id":      "aria-label-coverage",
        "script":  "validate_aria_label_coverage.py",
        "args":    [],
        "label":   "ARIA Label Coverage (every interactive element has an accessible name; forward-only ratchet)",
        "group":   "Platform",
        "report":  "aria_label_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every db.channel(...) must have matching db.removeChannel()
        # OR a beforeunload/pagehide cleanup listener. Without cleanup, navigating
        # between pages leaks websocket channels; free-tier hits its 200-channel
        # ceiling and silently stops delivering events.
        "id":      "realtime-channel-cleanup",
        "script":  "validate_realtime_channel_cleanup.py",
        "args":    [],
        "label":   "Realtime Channel Cleanup (every db.channel() has cleanup; forward-only ratchet)",
        "group":   "Platform",
        "report":  "realtime_channel_cleanup_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every page.locator('#X') in tests/journey-*.spec.ts
        # must point at an id that exists on the target HTML page. Catches
        # tests that flake silently after a page rename.
        "id":      "playwright-selector-existence",
        "script":  "validate_playwright_selector_existence.py",
        "args":    [],
        "label":   "Playwright Selector Existence (every locator('#X') id must exist on target page; forward-only ratchet)",
        "group":   "Platform",
        "report":  "playwright_selector_existence_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — localStorage / sessionStorage keys must be both set
        # AND read somewhere in the codebase. Catches cache-key drift where
        # writer + reader disagree on the key name.
        "id":      "localstorage-key-consistency",
        "script":  "validate_localstorage_key_consistency.py",
        "args":    [],
        "label":   "localStorage Key Consistency (every key must be set AND read; forward-only ratchet)",
        "group":   "Platform",
        "report":  "localstorage_key_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 — every classList.add/remove/toggle('X') must have a
        # matching `.X` CSS rule somewhere (style block or CSS file). Catches
        # JS-only classes where the CSS was deleted but the toggle stayed.
        "id":      "css-class-existence",
        "script":  "validate_css_class_existence.py",
        "args":    [],
        "label":   "CSS Class Existence (every classList.* class must have a CSS rule; forward-only ratchet)",
        "group":   "Platform",
        "report":  "css_class_existence_report.json",
        "skip_if_fast": False,
    },
    {"id":"pg-cron-target","script":"validate_pg_cron_target_existence.py","args":[],
     "label":"pg_cron Target Existence (jobs reference real tables + RPCs; forward-only ratchet)",
     "group":"Platform","report":"pg_cron_target_existence_report.json","skip_if_fast":False},
    {"id":"trigger-function","script":"validate_trigger_function_existence.py","args":[],
     "label":"Trigger Function Existence (CREATE TRIGGER target functions exist; forward-only ratchet)",
     "group":"Platform","report":"trigger_function_existence_report.json","skip_if_fast":False},
    {"id":"meta-description","script":"validate_meta_description_coverage.py","args":[],
     "label":"Meta Description Coverage (every page has description + og:title + og:image + canonical; forward-only ratchet)",
     "group":"Platform","report":"meta_description_coverage_report.json","skip_if_fast":False},
    {"id":"sitemap-page-existence","script":"validate_sitemap_page_existence.py","args":[],
     "label":"Sitemap Page Existence (every sitemap.xml URL resolves to a file; forward-only ratchet)",
     "group":"Platform","report":"sitemap_page_existence_report.json","skip_if_fast":False},
    {"id":"unbounded-query","script":"validate_unbounded_query.py","args":[],
     "label":"Unbounded Query Detection (every .from() chain has .limit/.single/.range/.eq-on-id; forward-only ratchet)",
     "group":"Platform","report":"unbounded_query_report.json","skip_if_fast":False},
    {"id":"heading-hierarchy","script":"validate_heading_hierarchy.py","args":[],
     "label":"Heading Hierarchy (no skipped levels, no multiple h1; forward-only ratchet)",
     "group":"Platform","report":"heading_hierarchy_report.json","skip_if_fast":False},
    {"id":"canonical-url","script":"validate_canonical_url_consistency.py","args":[],
     "label":"Canonical URL Consistency (<link rel=canonical> points at the page; forward-only ratchet)",
     "group":"Platform","report":"canonical_url_consistency_report.json","skip_if_fast":False},
    {"id":"event-listener-cleanup","script":"validate_event_listener_cleanup.py","args":[],
     "label":"Event Listener Cleanup (pages with 10+ addEventListener need removes; forward-only ratchet)",
     "group":"Platform","report":"event_listener_cleanup_report.json","skip_if_fast":False},
    # 2026-05-20 Flywheel 5-turn sweep: 5 new bug-class L0 ratchets.
    {"id":"external-link-rel","script":"validate_external_link_rel.py","args":[],
     "label":"External Link rel=noopener (every <a target=_blank> sets rel=noopener/noreferrer; forward-only ratchet)",
     "group":"Platform","report":"external_link_rel_report.json","skip_if_fast":False},
    {"id":"button-type-in-form","script":"validate_button_type_in_form.py","args":[],
     "label":"Button Type in Form (every <button> inside <form> declares type=button/submit/reset; forward-only ratchet)",
     "group":"Platform","report":"button_type_in_form_report.json","skip_if_fast":False},
    {"id":"security-definer-search-path","script":"validate_security_definer_search_path.py","args":[],
     "label":"SECURITY DEFINER search_path (every definer fn pins search_path; covers ALTER FUNCTION hardening; forward-only ratchet)",
     "group":"Platform","report":"security_definer_search_path_report.json","skip_if_fast":False},
    {"id":"duplicate-script-tags","script":"validate_duplicate_script_tags.py","args":[],
     "label":"Duplicate <script>/<link> Tags (no per-page duplicates of script src or stylesheet href; forward-only ratchet)",
     "group":"Platform","report":"duplicate_script_tags_report.json","skip_if_fast":False},
    {"id":"native-dialog-calls","script":"validate_native_dialog_calls.py","args":[],
     "label":"Native alert/confirm/prompt (production code must use the platform toast/modal stack; forward-only ratchet)",
     "group":"Platform","report":"native_dialog_calls_report.json","skip_if_fast":False},
    # Flywheel turns 6-10 (2026-05-20): 5 more bug-class L0 ratchets.
    {"id":"duplicate-html-id","script":"validate_duplicate_html_id.py","args":[],
     "label":"Duplicate HTML id (every static id is unique per document; forward-only ratchet)",
     "group":"Platform","report":"duplicate_html_id_report.json","skip_if_fast":False},
    {"id":"img-alt-coverage","script":"validate_img_alt_coverage.py","args":[],
     "label":"<img> alt Coverage (every <img> declares an alt attribute; forward-only ratchet)",
     "group":"Platform","report":"img_alt_coverage_report.json","skip_if_fast":False},
    {"id":"json-parse-safety","script":"validate_json_parse_safety.py","args":[],
     "label":"JSON.parse Safety (every JSON.parse() is inside try/catch; forward-only ratchet)",
     "group":"Platform","report":"json_parse_safety_report.json","skip_if_fast":False},
    {"id":"fetch-error-handling","script":"validate_fetch_error_handling.py","args":[],
     "label":"fetch() Error Handling (every fetch() is in try/catch or chained to .catch; forward-only ratchet)",
     "group":"Platform","report":"fetch_error_handling_report.json","skip_if_fast":False},
    {"id":"edge-status-body","script":"validate_edge_status_body_consistency.py","args":[],
     "label":"Edge Status/Body Consistency (HTTP status matches body ok/error semantics; forward-only ratchet)",
     "group":"Platform","report":"edge_status_body_consistency_report.json","skip_if_fast":False},
    # Flywheel turns 11-15 (2026-05-21): 5 more bug-class L0 ratchets.
    {"id":"edge-unpinned-imports","script":"validate_edge_unpinned_imports.py","args":[],
     "label":"Edge Unpinned Imports (every remote import pins @version; supply-chain hardening; forward-only ratchet)",
     "group":"Platform","report":"edge_unpinned_imports_report.json","skip_if_fast":False},
    {"id":"timer-cleanup","script":"validate_timer_cleanup.py","args":[],
     "label":"Timer Cleanup (setInterval has clearInterval; high-count setTimeout has clearTimeout; forward-only ratchet)",
     "group":"Platform","report":"timer_cleanup_report.json","skip_if_fast":False},
    {"id":"css-id-existence","script":"validate_css_id_existence.py","args":[],
     "label":"CSS id Existence (every CSS #id selector matches a declared id; dead-rule guard; forward-only ratchet)",
     "group":"Platform","report":"css_id_existence_report.json","skip_if_fast":False},
    {"id":"add-column-default","script":"validate_add_column_default.py","args":[],
     "label":"ADD COLUMN DEFAULT (every ADD COLUMN NOT NULL has a DEFAULT; backfill safety; forward-only ratchet)",
     "group":"Platform","report":"add_column_default_report.json","skip_if_fast":False},
    {"id":"form-submission-target","script":"validate_form_submission_target.py","args":[],
     "label":"<form> Submission Target (every form has action OR onsubmit OR addEventListener('submit'); forward-only ratchet)",
     "group":"Platform","report":"form_submission_target_report.json","skip_if_fast":False},
    # Flywheel turns 16-20 (2026-05-21): 5 more bug-class L0 ratchets.
    {"id":"edge-options-preflight","script":"validate_edge_options_preflight.py","args":[],
     "label":"Edge OPTIONS Preflight (body-consuming edge fn handles CORS preflight; forward-only ratchet)",
     "group":"Platform","report":"edge_options_preflight_report.json","skip_if_fast":False},
    {"id":"password-input-form","script":"validate_password_input_form.py","args":[],
     "label":"<input type=password> Form Wrapper (password inputs wrapped in <form> for autofill+save; forward-only ratchet)",
     "group":"Platform","report":"password_input_form_report.json","skip_if_fast":False},
    {"id":"fk-on-delete","script":"validate_fk_on_delete.py","args":[],
     "label":"FK ON DELETE (every REFERENCES declares explicit ON DELETE behavior; covers ALTER ADD CONSTRAINT supersede; forward-only ratchet)",
     "group":"Platform","report":"fk_on_delete_report.json","skip_if_fast":False},
    {"id":"edge-body-size-guard","script":"validate_edge_body_size_guard.py","args":[],
     "label":"Edge Body Size Guard (req.json() in try/catch or has Content-Length/sizeLimit check; DoS hardening; forward-only ratchet)",
     "group":"Platform","report":"edge_body_size_guard_report.json","skip_if_fast":False},
    {"id":"select-placeholder","script":"validate_select_placeholder.py","args":[],
     "label":"<select> Placeholder (every <select> has explicit selected/value=''/disabled-placeholder first option; forward-only ratchet)",
     "group":"Platform","report":"select_placeholder_report.json","skip_if_fast":False},
    # Flywheel turns 21-25 (2026-05-21): 5 more bug-class L0 ratchets.
    {"id":"rls-open-policy","script":"validate_rls_open_policy.py","args":[],
     "label":"RLS Open Policy (CREATE POLICY USING(true)/WITH CHECK(true) flagged; covers DROP POLICY supersede; forward-only ratchet)",
     "group":"Platform","report":"rls_open_policy_report.json","skip_if_fast":False},
    {"id":"console-log-drift","script":"validate_console_log_drift.py","args":[],
     "label":"console.log Production Drift (no console.log outside catch/DEBUG-guard in production code; forward-only ratchet)",
     "group":"Platform","report":"console_log_drift_report.json","skip_if_fast":False},
    {"id":"javascript-href","script":"validate_javascript_href.py","args":[],
     "label":"<a href='javascript:'> Anti-Pattern (use <button> for actions; reserve <a href> for navigation; forward-only ratchet)",
     "group":"Platform","report":"javascript_href_report.json","skip_if_fast":False},
    {"id":"view-select-star","script":"validate_view_select_star.py","args":[],
     "label":"CREATE VIEW SELECT * (every view projects explicit columns; preserves canonical-registry coverage; forward-only ratchet)",
     "group":"Platform","report":"view_select_star_report.json","skip_if_fast":False},
    {"id":"meta-refresh","script":"validate_meta_refresh.py","args":[],
     "label":"<meta http-equiv=refresh> (no auto-redirect anti-pattern; use JS or 30x; forward-only ratchet)",
     "group":"Platform","report":"meta_refresh_report.json","skip_if_fast":False},
    # Flywheel turns 26-30 (2026-05-21): 5 more bug-class L0 ratchets.
    {"id":"like-escape","script":"validate_like_escape.py","args":[],
     "label":"SQL LIKE Escape (.ilike/.like templates escape % and _; tracks file-wide escape-helper vars; forward-only ratchet)",
     "group":"Platform","report":"like_escape_report.json","skip_if_fast":False},
    {"id":"icon-button-label","script":"validate_icon_button_label.py","args":[],
     "label":"Icon-Only Button aria-label (svg-only <button> has aria-label/title/sr-only; forward-only ratchet)",
     "group":"Platform","report":"icon_button_label_report.json","skip_if_fast":False},
    {"id":"edge-response-content-type","script":"validate_edge_response_content_type.py","args":[],
     "label":"Edge Response Content-Type (every new Response(JSON.stringify) sets application/json; comment-stripped; forward-only ratchet)",
     "group":"Platform","report":"edge_response_content_type_report.json","skip_if_fast":False},
    {"id":"drop-if-exists","script":"validate_drop_if_exists.py","args":[],
     "label":"DROP IF EXISTS Idempotency (every DROP TABLE/VIEW/FUNCTION/POLICY/INDEX/TRIGGER/TYPE includes IF EXISTS; forward-only ratchet)",
     "group":"Platform","report":"drop_if_exists_report.json","skip_if_fast":False},
    {"id":"table-accessible-name","script":"validate_table_accessible_name.py","args":[],
     "label":"<table> Accessible Name (every table has caption/aria-label/role=presentation; forward-only ratchet)",
     "group":"Platform","report":"table_accessible_name_report.json","skip_if_fast":False},
    {
        # 2026-05-20 — Flywheel orchestrator: one turn per Mega Gate run.
        # Walks L-1 -> L-1.5 -> L0 -> L2 -> L13, diffs against the previous
        # turn's snapshot, surfaces RATCHETS (baselines tightened) +
        # REGRESSIONS (baselines loosened). Reporting-only — exit 0 always.
        "id":      "flywheel-turn",
        "script":  os.path.join("tools", "flywheel_orchestrator.py"),
        "args":    [],
        "label":   "Flywheel Turn (walks every Mega Gate layer; ratchet/regression diff vs prior turn)",
        "group":   "Platform",
        "report":  "flywheel_state.json",
        "skip_if_fast": False,
    },
    {
        "id":      "persona-contract",
        "script":  "validate_persona_contract.py",
        "args":    [],
        "label":   "Persona Contract Validator (8-layer: modules + server + client + gateway + hive + migrations + key parity + Step D differentiation)",
        "group":   "Platform",
        "report":  "persona_contract_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-19 Companion Streamline Step C/D hardening: prevents any
        # production JS file from re-introducing the legacy Cloudflare Worker
        # fetch pattern. Added after voice-handler.js was caught still calling
        # the dead worker, which silently triggered the "Sorry, I'm offline"
        # fallback in Zaniah's (then "Rosa") voice command UI.
        "id":      "legacy-worker-decommission",
        "script":  "validate_legacy_worker_decommission.py",
        "args":    [],
        "label":   "Legacy Worker Decommission Validator (no production JS calls workhive-assistant.workers.dev)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-19 Hardening Loop for the Zaniah-offline incident (formerly "Rosa", f5a8d99):
        # locks in ANON_OK_AGENTS Set + auth-gate skip + persistence guard +
        # AGENT_ROUTES registration so the voice-journal anon path can't
        # silently regress to 401 -> "Sorry, I'm offline" again.
        "id":      "gateway-anon-voice-journal",
        "script":  "validate_gateway_anon_voice_journal.py",
        "args":    [],
        "label":   "ai-gateway Anon Voice-Journal Contract (4-layer: ANON_OK_AGENTS set + auth-gate skip + authUid persistence guard + AGENT_ROUTES entry)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "voice-canonical-anchor",
        "script":  "validate_voice_canonical_anchor.py",
        "args":    [],
        "label":   "Voice Canonical Anchor Validator (4-layer: classifier + fetch + wiring + DATA block in prompt)",
        "group":   "Platform",
        "report":  "voice_canonical_anchor_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "voice-routing-unification",
        "script":  "validate_voice_routing_unification.py",
        "args":    [],
        "label":   "Voice Routing Unification (Phase 0: router output passing)",
        "group":   "Platform",
        "report":  "voice_routing_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "voice-phase1",
        "script":  "validate_voice_companion_phase1.py",
        "args":    [],
        "label":   "Voice Companion Phase 1 (multi-agent orchestrator)",
        "group":   "Platform",
        "report":  "voice_phase1_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "voice-phase1-5",
        "script":  "validate_voice_companion_phase1_5.py",
        "args":    [],
        "label":   "Voice Companion Phase 1.5 (semantic RAG with pgvector)",
        "group":   "Platform",
        "report":  "voice_phase1_5_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "voice-phase2",
        "script":  "validate_voice_companion_phase2.py",
        "args":    [],
        "label":   "Voice Companion Phase 2 (multi-model A/B testing)",
        "group":   "Platform",
        "report":  "voice_phase2_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "voice-phase3",
        "script":  "validate_voice_companion_phase3.py",
        "args":    [],
        "label":   "Voice Companion Phase 3 (error recovery + anon memory)",
        "group":   "Platform",
        "report":  "voice_phase3_report.json",
        "skip_if_fast": False,
    },
    # `companion-page-coverage` and `companion-source-coverage` were registered TWICE here, with a second
    # identical pair further down (same id, same script, same args). Both copies of each ran every suite, so
    # three scripts were executing twice for no added assertion and the registry's own gate count was
    # overstated by three. The duplicates removed are these two, not the later pair, because the later
    # `companion-page-coverage` carries a `report` path this one set to None — deleting the copy that emits
    # the report would have quietly dropped an artifact. See the id-uniqueness assertion in main(), added so
    # this cannot recur silently: nothing was checking that a gate id appears once.
    {
        "id":      "memory-integrity",
        "script":  "validate_memory_integrity.py",
        "args":    [],
        "label":   "Memory Integrity (Phase 2: session memory, turn tracking, dedup)",
        "group":   "Platform",
        "report":  "memory_integrity_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "dialog-flow",
        "script":  "validate_dialog_flow.py",
        "args":    [],
        "label":   "Dialog Flow (Phase 4: intent refinement, clarification, slot-filling)",
        "group":   "Platform",
        "report":  "dialog_flow_report.json",
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 Hardening Loop for the "Yes, the details → topic-switch
        # UI" bug class. Locks _isFollowupAffirmation + the call-site bypass
        # + _shouldClarify symmetry guard so short PH/English affirmations
        # ('yes', 'sige', 'oo', 'the details') resume the prior topic
        # instead of tripping the clarification UI. Paired with the L2
        # sentinels in tests/journey-voice-journal.spec.ts.
        "id":      "dialog-affirmation-bypass",
        "script":  "validate_dialog_affirmation_bypass.py",
        "args":    [],
        "label":   "Dialog Affirmation Bypass (5-layer: regex + vocabulary + word-cap + callsite bypass + shouldClarify symmetry)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 Sister hardening loop covering the NEGATIVE side +
        # noise + clarification-loop ceiling. Locks _isFollowupNegation
        # ('no', 'cancel', 'wala', 'hindi'), _isNoisyTranscript (empty /
        # 1-2 char / lone filler), and _clarifyStreak (caps consecutive
        # clarifications at 2 then switches shape + resets). Paired with
        # 3 L2 sentinels in tests/journey-voice-journal.spec.ts.
        "id":      "dialog-followup-handlers",
        "script":  "validate_dialog_followup_handlers.py",
        "args":    [],
        "label":   "Dialog Follow-up Handlers (6-layer: negation + vocabulary + noise + state-clear + upstream + clarify-streak ceiling)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 Flywheel turn #3 of the AI Companion dialog-quality
        # stack. Locks the multi-turn CONTINUITY surface inside
        # _buildVoiceSystemPrompt: PRIOR TOPIC HANDLE block (pronoun
        # resolution — 'it' / 'that' / 'yan' / 'yun' resolved to the
        # prior intent) + natural-language SLOT ENUMERATION ('You already
        # know: asset tag = P-203'). Without these the LLM has no
        # deterministic anchor for short follow-ups and the worker feels
        # the companion 'forgot' them. Paired with L2 sentinels:
        # dialog-prior-topic-handle + dialog-slot-enumeration + the
        # case-invariance probes against the affirmation/negation regex.
        "id":      "dialog-continuity",
        "script":  "validate_dialog_continuity.py",
        "args":    [],
        "label":   "Dialog Continuity (5-layer: prompt builder + DIALOG STATE block + PRIOR TOPIC HANDLE + slot enumeration + PH/English pronoun vocabulary)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 Flywheel turn #4 of the AI Companion dialog-quality
        # stack. Two concerns share the validator:
        #   Phase 4.7 — clarification-recovery routing: bare "logbook" /
        #               "PM" / "analytics" replies after the streak-ceiling
        #               prompt route directly to that intent so the loop
        #               actually breaks.
        #   Phase 4.8 — crisis-line safety override: persona.ts MUST keep
        #               its 'self-harm' + 'helpline' clause positioned in
        #               the conversational reply rules block. Voice
        #               journals are a high-trust surface — this clause
        #               can NEVER be silently optimised away.
        "id":      "dialog-recovery-safety",
        "script":  "validate_dialog_recovery_safety.py",
        "args":    [],
        "label":   "Dialog Recovery + Safety (5-layer: recovery helper + recovery vocabulary + clarification_pending guard + crisis line present + crisis line positioned)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 Flywheel turns #5-#14 (10-turn dialog-quality
        # expansion bundle). Each layer locks one bug class:
        #   T5  persona-switch utterance       T10 first-turn greeting
        #   T6  stale dialog-state guard       T11 code-switch anchor
        #   T7  topic-interruption signal      T12 sensitive-topic redirect
        #   T8  thanks / ack handler           T13 worker-name personalization
        #   T9  asset-context auto-priming     T14 repeat-that handler
        "id":      "dialog-quality-extended",
        "script":  "validate_dialog_quality_extended.py",
        "args":    [],
        "label":   "Dialog Quality Extended (10-layer: turns #5-#14 — persona-switch + stale-guard + topic-interrupt + thanks + asset-prime + greeting + code-switch + sensitive-topic + worker-name + repeat)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-20 Flywheel turns #15-#24 — different DIMENSION from
        # the dialog-state stack. TRUST (hallucination, citation),
        # AUDIO QUALITY (interrupt, acronym pronunciation),
        # OBSERVABILITY (TTS latency, rate-limit, cost-cap, fallback
        # UX), CROSS-SURFACE COHERENCE (assistant.html pulls voice-
        # journal entries), and lifecycle (conversation-end ack).
        "id":      "ai-companion-trust-observability",
        "script":  "validate_ai_companion_trust_observability.py",
        "args":    [],
        "label":   "AI Companion Trust + Observability (10-layer: turns #15-#24 — hallucination guard + citation + audio interrupt + TTS latency + rate-limit + fallback UX + acronym SSML + assistant journal pull + cost-cap + end ack)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21 Flywheel turns #25-#34 — CONTEXT AWARENESS +
        # INTELLIGENCE layer. Shift, repeated-issue, standards lookup,
        # voice shortcuts, quality thumbs, worker discipline, goodbye,
        # confidence calibration, long-session pacing, alerts override.
        "id":      "ai-companion-intelligence",
        "script":  "validate_ai_companion_intelligence.py",
        "args":    [],
        "label":   "AI Companion Intelligence (10-layer: turns #25-#34 — shift + repeated-issue + standards + shortcuts + thumbs + discipline + goodbye + confidence + pacing + alerts override)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21 Flywheel turns #35-#44 — COLLABORATION + WELLBEING.
        # Action confirmation, wellbeing nudge, encouragement, skill gap,
        # shift handover, batch action, explainability, co-worker
        # mention, fatigue signal, transcript export.
        "id":      "ai-companion-collaboration",
        "script":  "validate_ai_companion_collaboration.py",
        "args":    [],
        "label":   "AI Companion Collaboration + Wellbeing (10-layer: turns #35-#44 — action confirm + wellbeing + encouragement + skill gap + handover + batch + explainability + co-worker mention + fatigue + transcript export)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21 Flywheel turns #45-#54 — RESILIENCE + MEMORY +
        # TRUST OPS. Offline tracker, 10-min reply cache, feedback
        # escalation, custom plant terminology resolver, conversation
        # branching stack, multi-modal photo intent, avatar emotion
        # state, cross-hive anonymised benchmark, summary-on-demand,
        # identity drift tracker.
        "id":      "ai-companion-resilience",
        "script":  "validate_ai_companion_resilience.py",
        "args":    [],
        "label":   "AI Companion Resilience + Memory (10-layer: turns #45-#54 — offline + cache + escalation + terminology + branching + photo intent + avatar state + benchmark + summary + identity drift)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21 Flywheel turns #55-#64 — WORKFLOW + PERSONALIZATION.
        # Proactive companion turn (open accepts alert payload), maturity-
        # stair gating, per-slot expiry windows, action replay, language
        # opt-in, brevity preference, timer follow-up, URL-context pre-
        # fill, mic quality meter, multi-step action queue.
        "id":      "ai-companion-workflow",
        "script":  "validate_ai_companion_workflow.py",
        "args":    [],
        "label":   "AI Companion Workflow + Personalization (10-layer: turns #55-#64 — proactive + maturity + slot expiry + action replay + language + brevity + timer + URL prefill + mic quality + action queue)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion seventh 10-turn flywheel batch
        # (turns #65-#74). ORCHESTRATION + INTEGRATION layer: PDF
        # export detector → Report Sender, per-device pronunciation
        # library, voice-execute safety lock (default OFF), persona
        # portrait animation, cross-hive benchmark RPC wiring, daily
        # digest mode, push notification readiness, multi-worker
        # concurrency lock, accent / voice-signature adaptation,
        # streaming SSE response indicator.
        "id":      "ai-companion-orchestration",
        "script":  "validate_ai_companion_orchestration.py",
        "args":    [],
        "label":   "AI Companion Orchestration + Integration (10-layer: turns #65-#74 — pdf export + pronunciation + voice-execute lock + avatar animation + cross-hive RPC + digest + push + session lock + accent + streaming)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion eighth 10-turn flywheel batch
        # (turns #75-#84). TRUST DEPLOYMENT layer — production
        # safety + collaboration: toxicity guard, question shape
        # classifier, freshness disclosure, rate-limit cooldown,
        # conversation share link, readback request, scope
        # disclosure, multi-turn correction, confidence label
        # tier, crisis escalation extension (self-harm + workplace
        # violence).
        "id":      "ai-companion-trust-deployment",
        "script":  "validate_ai_companion_trust_deployment.py",
        "args":    [],
        "label":   "AI Companion Trust Deployment (10-layer: turns #75-#84 — toxicity + question shape + freshness + rate-limit + share + readback + scope + correction + confidence label + crisis extension)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion ninth 10-turn flywheel batch
        # (turns #85-#94). INPUT NORMALIZATION + ONBOARDING layer.
        "id":      "ai-companion-input-normalization",
        "script":  "validate_ai_companion_input_normalization.py",
        "args":    [],
        "label":   "AI Companion Input Normalization + Onboarding (10-layer: turns #85-#94 — precision rule + asset-tag normalization + time-range + ack style + forbidden topics + mic env + pin + help + KPI translation + new-worker welcome)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion tenth 10-turn flywheel batch
        # (turns #95-#104). INTEGRATION + AUDIT layer.
        "id":      "ai-companion-integration-audit",
        "script":  "validate_ai_companion_integration_audit.py",
        "args":    [],
        "label":   "AI Companion Integration + Audit (10-layer: turns #95-#104 — audit log + quiet hours + preflight + idle cleanup + error analytics + session tag + deep link + grammar guess + phrase pool + shift-end)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion eleventh 10-turn flywheel batch
        # (turns #105-#114). PROACTIVE ASSISTANCE + LEARNING layer.
        "id":      "ai-companion-learning",
        "script":  "validate_ai_companion_learning.py",
        "args":    [],
        "label":   "AI Companion Proactive Assistance + Learning (10-layer: turns #105-#114 — PM sync drift + skill-level adaptation + cross-asset pattern + intent history + sentiment over time + asset warm-up + symptom normalizer + shift boundary + knowledge gap + mentor handoff)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion twelfth 10-turn flywheel batch
        # (turns #115-#124). COMPLIANCE + DATA GOVERNANCE.
        "id":      "ai-companion-compliance",
        "script":  "validate_ai_companion_compliance.py",
        "args":    [],
        "label":   "AI Companion Compliance + Data Governance (10-layer: turns #115-#124 — PII scrubber + consent capture + retention + right-to-erasure + audit CSV + suspicious activity + AI disclosure + locale-aware dates + monthly cost cap + voice drift advisory)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion thirteenth 10-turn flywheel batch
        # (turns #125-#134). MULTI-MODAL + ACCESSIBILITY.
        "id":      "ai-companion-accessibility",
        "script":  "validate_ai_companion_accessibility.py",
        "args":    [],
        "label":   "AI Companion Multi-Modal + Accessibility (10-layer: turns #125-#134 — camera capture + file attachment + reduced motion + aria-live + keyboard nav + CB-safe palette + large text + haptic + voice-only mode + live captions)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion fourteenth 10-turn flywheel batch
        # (turns #135-#144). OPERATIONAL EXCELLENCE.
        "id":      "ai-companion-operational",
        "script":  "validate_ai_companion_operational.py",
        "args":    [],
        "label":   "AI Companion Operational Excellence (10-layer: turns #135-#144 — health ping + self-test + feature flags + browser support + network adapt + memory pressure + clock drift + background pause + crash recovery + presence heartbeat)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion fifteenth 10-turn flywheel batch
        # (turns #145-#154). TEAM COORDINATION + CROSS-WORKER.
        "id":      "ai-companion-team-coordination",
        "script":  "validate_ai_companion_team_coordination.py",
        "args":    [],
        "label":   "AI Companion Team Coordination (10-layer: turns #145-#154 — active sessions + handoff + shared notes + concurrency alert + watchlist + broadcast + resolution + cross-shift continuity + buddy mode + mention notifications)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion sixteenth 10-turn flywheel batch
        # (turns #155-#164). EXTERNAL INTEGRATION.
        "id":      "ai-companion-external-integration",
        "script":  "validate_ai_companion_external_integration.py",
        "args":    [],
        "label":   "AI Companion External Integration (10-layer: turns #155-#164 — SAP PM webhook + Maximo poll + OPC-UA tag + MQTT topic + Slack + email digest + Teams card + ICS calendar + signature compare + outbound retry queue)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion seventeenth 10-turn flywheel batch
        # (turns #165-#174). ADVANCED ANALYTICS.
        "id":      "ai-companion-analytics",
        "script":  "validate_ai_companion_analytics.py",
        "args":    [],
        "label":   "AI Companion Advanced Analytics (10-layer: turns #165-#174 — 3σ anomaly + Weibull MTBF + Pareto + linear trend + seasonal peak + trimmed mean + z-score + correlation + Weibull CDF + availability)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion eighteenth 10-turn flywheel batch
        # (turns #175-#184). SAFETY + PERMIT-TO-WORK.
        "id":      "ai-companion-safety",
        "script":  "validate_ai_companion_safety.py",
        "args":    [],
        "label":   "AI Companion Safety + Permit-to-Work (10-layer: turns #175-#184 — LOTO + hot work + confined space + PPE matrix + near-miss + JSA + gas test + incident + energy isolation + permit expiry)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: Phase 1 of AGENTIC_RAG_ROADMAP.md.
        # 5-stage self-correcting agentic RAG loop (Router → Retriever → Grader →
        # Generator → Checker), free-tier multi-provider chain only, per-stage
        # cost-logged, trace-persisted to agentic_rag_traces.
        "id":      "agentic-rag-loop",
        "script":  "validate_agentic_rag_loop.py",
        "args":    [],
        "label":   "Agentic RAG Loop Phase 1 (18-layer: edge fn + 5 stages + hive scoping + FREE-TIER-ONLY + callAI + rate limit + retry cap + grader threshold + question cap + trace + cost log + migration + 4-place sync + em-dash safety + JSON mode)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: Phase 2 of AGENTIC_RAG_ROADMAP.md.
        # Hierarchical period summaries (Daily → Weekly → Monthly → Quarterly →
        # Yearly) pre-digested in canonical_period_summaries. Agentic RAG
        # Retriever reads these instead of raw logbook for time-bound queries.
        "id":      "hierarchical-summaries",
        "script":  "validate_hierarchical_summaries.py",
        "args":    [],
        "label":   "Hierarchical Period Summaries Phase 2 (16-layer: migration + 5 levels + RLS + aggregator + Breakdown/Corrective filter + FREE-TIER-ONLY + callAI + hive scoping + row cap + empty short-circuit + upsert + 4-place sync + em-dash safety + cost log)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: Phase 4 of AGENTIC_RAG_ROADMAP.md.
        # Tiered Model Router — adds taskProfile parameter to callAI; reorders
        # the free-tier multi-provider chain per task. Drops TPM pressure ~40%
        # by routing cheap tasks (grader, checker, intent) to the 8B model
        # instead of 17B Scout. All 11 expected task profiles covered.
        "id":      "model-router",
        "script":  "validate_model_router.py",
        "args":    [],
        "label":   "Tiered Model Router Phase 4 (9-layer: TASK_PROFILES + 11 profiles + free-tier values + reorderChain + callAI signature + reorderChain usage + Phase 1 stages wired + Phase 2 digest wired + no paid models)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: Phase 8 of AGENTIC_RAG_ROADMAP.md.
        # Supervisor-facing observability dashboard reading agentic_rag_traces.
        "id":      "agentic-rag-observability",
        "script":  "validate_agentic_rag_observability.py",
        "args":    [],
        "label":   "Agentic RAG Observability Phase 8 (10-layer: page exists + calm-dashboard meta + utils + hive gate + hive-scoped query + narrow select + 4 render fns + escHtml + bounded fetch + window filter)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: Phase 3 of AGENTIC_RAG_ROADMAP.md.
        # Supervisor-worker temporal RAG orchestrator: decomposes time-bound
        # questions across N parallel sub-agents on canonical_period_summaries,
        # then folds. Bounded concurrency keeps Groq TPM contention safe.
        "id":      "temporal-orchestrator",
        "script":  "validate_temporal_orchestrator.py",
        "args":    [],
        "label":   "Temporal RAG Orchestrator Phase 3 (17-layer: edge fn + decompose + 3 granularities + auto-heuristic + MAX_PERIODS + MAX_PARALLEL + runBounded + reads Phase 2 + 2x callAI + sub/fold taskProfiles + FREE-TIER + hive scoping + rate limit before fan-out + 4-place sync + cost log + em-dash safety)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: Phase 7 of AGENTIC_RAG_ROADMAP.md.
        # agent_episodic_memory + agent-memory-store edge fn. Durable facts
        # (factual/procedural/episodic/semantic) extracted by Phase 1 Checker
        # at run end, recalled at run start. LRU eviction with importance
        # weighting. Distinct from agent_memory (which is conversation-turn).
        "id":      "agent-episodic-memory",
        "script":  "validate_agent_memory_store.py",
        "args":    [],
        "label":   "Agent Episodic Memory Phase 7 (12-layer: migration + 4 types + RLS + edge fn + recall+store ops + caps + content cap + importance×log rank + batch cap + hive scoping + 4-place sync + no raw fetch)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: Phase 5 of AGENTIC_RAG_ROADMAP.md (scaffolding).
        # unified_events + data-fabric-normalizer edge fn. Canonical event
        # schema that normalizes SAP/Maximo/OPC-UA/MQTT/CMMS/voice/photo/
        # sensor/email/manual sources into one shape for cross-source RAG.
        "id":      "data-fabric",
        "script":  "validate_data_fabric.py",
        "args":    [],
        "label":   "Data Fabric Normalizer Phase 5 (9-layer scaffolding: migration + 10 sources + RLS + edge fn + 3 adapters + SHA-256 dedup + hive scoping + duplicate handling + no LLM + 4-place sync)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: Phase 6 of AGENTIC_RAG_ROADMAP.md.
        # 2026-05-31 (memory-stack Turn 3): cold-archive-query is now WIRED -
        # reads per-hive Parquet snapshots in-process via hyparquet, returns 200
        # ok:true on read paths (the 503 scaffold is gone). Paired exporter is
        # tools/cold_archive_exporter.py. See COLD_ARCHIVE_SCALEUP_ROADMAP.md.
        "id":      "cold-archive",
        "script":  "validate_cold_archive.py",
        "args":    [],
        "label":   "Cold Lakehouse Archive Phase 6 (10-layer contract: edge fn + 4 supported tables + 200 ok:true hyparquet read + storage list + hive scoping + Python exporter + --commit dry-run default + ARCHIVE_AGE_MONTHS=18 + no auto-delete safety + 4-place sync)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-31 (memory-stack Turn 3): asserts the cold-tier read path is
        # genuinely wired with hyparquet (not a stub) - _shared/cold-archive.ts
        # helpers + parquetReadObjects + storage.download + TABLE_FILE map +
        # MAX_QUARTERS/LIMIT_CAP bounds + ok:true contract. Must pass at 0.
        # Sibling to episodic-memory-wiring / verified-state-wiring.
        "id":      "cold-archive-wiring",
        "script":  "validate_cold_archive_wiring.py",
        "args":    [],
        "label":   "Cold Archive Wiring (Hierarchical layer: hyparquet Parquet read stays wired into cold-archive-query - _shared helpers + parquetReadObjects + bounds + ok:true)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-31 (memory-stack Turn 4): the Semantic layer (layer 03) per-hive
        # entity extractor is genuinely wired - reads v_logbook_truth, extracts
        # typed S-P-O triples via the free-tier chain, embeds them, and idempotently
        # upserts into knowledge_graph_facts (source_type 'ai_extraction') against
        # uq_kgf_triple_source. Fills the store voice-handler._fetchKGContext reads.
        # Must pass at 0. Sibling to episodic/verified-state/cold-archive wiring.
        "id":      "semantic-fact-extractor-wiring",
        "script":  "validate_semantic_fact_extractor_wiring.py",
        "args":    [],
        "label":   "Semantic Fact Extractor Wiring (Semantic layer: logbook -> KG triples -> embed -> idempotent upsert into knowledge_graph_facts; _shared/semantic-facts.ts helpers + dedupe migration + 4-place sync)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-31 (memory-stack Turn 5): the Procedural layer (layer 04) skill
        # library + matcher is wired end to end - persistEpisodic embeds procedural
        # memories, match_procedural_memories (RPC + idx_aem_embedding) retrieves
        # them by cosine, _shared/skill-library.ts wraps it, and ai-gateway injects
        # the top proven procedures for fix-oriented agents. Must pass at 0. Sibling
        # to episodic/verified-state/cold-archive/semantic-fact wiring.
        "id":      "skill-library-wiring",
        "script":  "validate_skill_library_wiring.py",
        "args":    [],
        "label":   "Skill Library Wiring (Procedural layer: embed procedural memories + match_procedural_memories cosine RPC + _shared/skill-library.ts matcher + ai-gateway injection for fix agents)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-31 (memory-stack Turn 6): the Prospective layer (layer 06)
        # deferred follow-up queue is wired end to end - agent_followups store
        # (non-open RLS), _shared/followups.ts enqueues (capped) + recalls only
        # DUE items (marking them surfaced), and ai-gateway both surfaces due
        # follow-ups into context and enqueues new ones from the specialist
        # envelope. Must pass at 0. Final sibling in the memory-stack wiring set.
        "id":      "followup-queue-wiring",
        "script":  "validate_followup_queue_wiring.py",
        "args":    [],
        "label":   "Follow-up Queue Wiring (Prospective layer: agent_followups store + _shared/followups.ts enqueue/recall-due/surface + ai-gateway surfacing + envelope-driven enqueue for task agents)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: RAG Flywheel processor + multi-turn loop orchestrator.
        # tools/rag_flywheel_processor.py + run_rag_flywheel_loop.py drive
        # synthetic walks; this validator ratchets the contract surface
        # (canonical tile tags, KPI seeds, walk template branches, lane D).
        "id":      "rag-flywheel",
        "script":  "validate_rag_flywheel.py",
        "args":    [],
        "label":   "RAG Flywheel (processor + loop orchestrator + canonical tile tags + KPI seeds + walk template branches + lane D retriever)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-22: RAG Flywheel hard locks (immutable contracts that the
        # loop must never regress: 5s inter-tile throttle, domain prefix on
        # rag_tile inserts, rule-9 view-name self-check, positive-framing
        # seeds, live-query cold_archive demotion).
        "id":      "rag-flywheel-locks",
        "script":  "validate_rag_flywheel_locks.py",
        "args":    [],
        "label":   "RAG Flywheel Locks (inter-tile throttle + domain prefix + view-name self-check + positive-framing seeds + cold_archive demotion)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion nineteenth 10-turn flywheel batch
        # (turns #185-#194). KNOWLEDGE GRAPH.
        "id":      "ai-companion-knowledge-graph",
        "script":  "validate_ai_companion_knowledge_graph.py",
        "args":    [],
        "label":   "AI Companion Knowledge Graph (10-layer: turns #185-#194 — entity + relation + triple + RAG block + FNV hash + chunking + citation + query rewrite + reasoning trace + KB version)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion twentieth 10-turn flywheel batch
        # (turns #195-#204). ENERGY + SUSTAINABILITY.
        "id":      "ai-companion-sustainability",
        "script":  "validate_ai_companion_sustainability.py",
        "args":    [],
        "label":   "AI Companion Energy + Sustainability (10-layer: turns #195-#204 — EnPI + PH carbon factor + peak demand + 5σ energy anomaly + standby waste + water + air leak + motor efficiency + sustainability bundle + energy query)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-21: AI Companion twenty-first 10-turn flywheel batch
        # (turns #205-#214). MULTI-LANGUAGE NLU.
        "id":      "ai-companion-multilang",
        "script":  "validate_ai_companion_multilang.py",
        "args":    [],
        "label":   "AI Companion Multi-Language NLU (10-layer: turns #205-#214 — Cebuano + Ilonggo + Tagalog imperative + code-switch ratio + politeness register + PH time phrases + number words + filler strip + stop words + slang dict)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "proactive-alerts",
        "script":  "validate_proactive_alerts.py",
        "args":    [],
        "label":   "Proactive Alerts (Phase 5: KPI spikes, risk escalation, overdue PM)",
        "group":   "Platform",
        "report":  "proactive_alerts_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "voice-alert-formatting",
        "script":  "validate_voice_alert_formatting.py",
        "args":    [],
        "label":   "Voice Alert Formatting (Phase 5: alerts render with descriptions, not IDs)",
        "group":   "Platform",
        "report":  "voice_alert_formatting_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "offline-resilience",
        "script":  "validate_offline_resilience_phase6.py",
        "args":    [],
        "label":   "Offline Resilience (Phase 6: snapshot caching, response queue)",
        "group":   "Platform",
        "report":  "offline_resilience_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "tts-quality",
        "script":  "validate_tts_quality_phase7.py",
        "args":    [],
        "label":   "TTS Quality Metrics (Phase 7: latency logging, cache)",
        "group":   "Platform",
        "report":  "tts_quality_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "avatar-state",
        "script":  "validate_avatar_state_phase10.py",
        "args":    [],
        "label":   "Avatar State Management (Phase 10: emotion tracking, animations)",
        "group":   "Platform",
        "report":  "avatar_state_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "multilingual-support",
        "script":  "validate_multilingual_phase11.py",
        "args":    [],
        "label":   "Multilingual Support (Phase 11: term translation, language prefs)",
        "group":   "Platform",
        "report":  "multilingual_support_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "voice-data-flow",
        "script":  "validate_voice_data_flow.py",
        "args":    [],
        "label":   "Voice Data Flow Audit (Phase 3/5/8: KB RAG, proactive alerts, analytics)",
        "group":   "Platform",
        "report":  "voice_data_flow_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "rag-integrity",
        "script":  "validate_rag_integrity.py",
        "args":    [],
        "label":   "RAG Integrity (Phase 1.5: semantic search, KB chunks, embeddings)",
        "group":   "Platform",
        "report":  "rag_integrity_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "analytics-integrity",
        "script":  "validate_analytics_integrity.py",
        "args":    [],
        "label":   "Analytics Integrity (Phase 8: conversation quality metrics, health view)",
        "group":   "Platform",
        "report":  "analytics_integrity_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "team-coordination",
        "script":  "validate_team_coordination.py",
        "args":    [],
        "label":   "Team Coordination (Phase 9: cross-hive alerts, best practices sharing)",
        "group":   "Platform",
        "report":  "team_coordination_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "tier-c-contracts",
        "script":  "validate_tier_c_contracts.py",
        "args":    [],
        "label":   "Tier C Contract Regression Validator (good/bad fixtures per agent contract)",
        "group":   "Platform",
        "report":  "tier_c_contracts_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "capture-contracts",
        "script":  "validate_capture_contracts.py",
        "args":    [],
        "label":   "Tier F Capture Contract Regression Validator (good/bad payload fixtures per input surface)",
        "group":   "Platform",
        "report":  "capture_contracts_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "formula-invocation",
        "script":  "validate_formula_invocation.py",
        "args":    [],
        "label":   "Formula Invocation Drift (Tier D-f refinement: same formula called with different period_days across consumers)",
        "group":   "Platform",
        "report":  "formula_invocation_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "capability-dedup",
        "script":  "validate_capability_dedup.py",
        "args":    [],
        "label":   "Tier G / Layer 9 Capability Catalog & Dedup (every user-facing function pinned to one primary surface)",
        "group":   "Platform",
        "report":  "capability_dedup_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "playwright-coverage",
        "script":  "validate_playwright_coverage.py",
        "args":    [],
        "label":   "Playwright Coverage (every LIVE_TOOL_PAGE has tests/<page>.spec.ts with a real goto)",
        "group":   "Platform",
        "report":  "playwright_coverage_report.json",
        "skip_if_fast": False,  # static check, ~50ms
    },
    {
        "id":      "seed-consumer-contract",
        "script":  "validate_seed_consumer_contract.py",
        "args":    [],
        "label":   "Seed -> Consumer Contract (TZ-aware date columns + JSONB key contract for AMC-like blobs)",
        "group":   "Platform",
        "report":  "seed_consumer_contract_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ux-contract",
        "script":  "validate_ux_contract.py",
        "args":    [],
        "label":   "WorkHive UX Contract (input labels [ratchet] + destructive confirm + page title + role-gate)",
        "group":   "Platform",
        "report":  "ux_contract_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "supabase-singleton",
        "script":  "validate_supabase_singleton.py",
        "args":    [],
        "label":   "Supabase Client Singleton (at-most-one createClient per page; shared JS uses singleton)",
        "group":   "Platform",
        "report":  "supabase_singleton_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "playwright-smoke",
        "script":  "validate_playwright_smoke.py",
        "args":    [],
        "label":   "Playwright UI Smoke Suite (real browser, silent-failure regression locks per page)",
        "group":   "Platform",
        "report":  "playwright_smoke_report.json",
        "skip_if_fast": True,   # ~3 min runtime; opt-in via full guardian
    },
    {
        "id":      "write-path-monitor",
        "script":  "validate_write_path_monitor.py",
        "args":    [],
        "label":   "Write Path Monitor (4-layer: shape drift + orphan RPCs + write hotspots + single-layer writers)",
        "group":   "Platform",
        "report":  "write_path_monitor_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "schema-phantom",
        "script":  "validate_schema_phantom.py",
        "args":    [],
        "label":   "Schema Phantom Column Detector (4-layer: phantom reads + dead columns + alias drift + layer hotspots)",
        "group":   "Platform",
        "report":  "schema_phantom_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "embed-integrity",
        "script":  "validate_embed_integrity.py",
        "args":    [],
        "label":   "PostgREST Embed Integrity (4-layer: phantom target + phantom embed column + missing FK + embed distribution)",
        "group":   "Platform",
        "report":  "embed_integrity_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "kg-scope-split",
        "script":  "validate_kg_scope_split.py",
        "args":    [],
        "label":   "KG Facts Scope Split (4-layer: platform table + RPC + voice-handler fan-out + no broadcast pattern)",
        "group":   "Platform",
        "report":  "kg_scope_split_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "service-role-exposure",
        "script":  "validate_service_role_exposure.py",
        "args":    [],
        "label":   "Service-Role Key Exposure (5-layer: service_role identifier + JWT in client + secret env + anon-key inventory + JWT in the live DB catalog)",
        "group":   "Platform",
        "report":  "service_role_exposure_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "migration-immutability",
        "script":  "validate_migration_immutability.py",
        "args":    [],
        "label":   "Migration Immutability (4-layer: edited-after-first-commit + filename convention + whitespace-only + recency)",
        "group":   "Platform",
        "report":  "migration_immutability_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "rls-symmetry",
        "script":  "validate_rls_symmetry.py",
        "args":    [],
        "label":   "RLS Policy Symmetry (4-layer: write-without-read + read-without-create + update gap + CRUD matrix)",
        "group":   "Platform",
        "report":  "rls_symmetry_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "optimistic-concurrency",
        "script":  "validate_optimistic_concurrency.py",
        "args":    [],
        "label":   "Optimistic Concurrency (4-layer: content-without-guard + no-defence-available + writer matrix + adoption count)",
        "group":   "Platform",
        "report":  "optimistic_concurrency_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "pii-egress",
        "script":  "validate_pii_egress.py",
        "args":    [],
        "label":   "PII Egress to Third Parties (4-layer: direct-fetch+PII + AI-prompt+PII + host distribution + PII reach)",
        "group":   "Platform",
        "report":  "pii_egress_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "index-coverage",
        "script":  "validate_index_coverage.py",
        "args":    [],
        "label":   "Index Coverage (4-layer: high-freq unindexed + med-freq unindexed + coverage matrix + tables-with-only-PK)",
        "group":   "Platform",
        "report":  "index_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "cors-wildcard",
        "script":  "validate_cors_wildcard.py",
        "args":    [],
        "label":   "CORS Wildcard Audit (4-layer: hardcoded-* + wildcard-on-data + strategy distribution + echo-without-allowlist)",
        "group":   "Platform",
        "report":  "cors_wildcard_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "abort-timeout",
        "script":  "validate_abort_timeout.py",
        "args":    [],
        "label":   "AbortSignal Timeout Coverage (4-layer: external-no-signal + loop-no-timeout + timeout distribution + no-fetch fns)",
        "group":   "Platform",
        "report":  "abort_timeout_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "cold-start-memoization",
        "script":  "validate_cold_start_memoization.py",
        "args":    [],
        "label":   "Cold-Start Memoization (4-layer: createClient-in-handler + multiple-calls + adoption + budget)",
        "group":   "Platform",
        "report":  "cold_start_memoization_report.json",
        "skip_if_fast": False,
    },
    {
        # Layer -1 Convention Mining -- discovers emergent edge-fn patterns
        # and flags outliers. Always exits 0 (informational). Promotion
        # candidates are surfaced in edge_pattern_mining_report.md for
        # human review; real rules then graduate to their own validators.
        "id":      "edge-pattern-mining",
        "script":  os.path.join("tools", "mine_edge_patterns.py"),
        "args":    [],
        "label":   "Edge-Fn Pattern Miner (L-1 Convention Mining -- informational, surfaces drift)",
        "group":   "Platform",
        "report":  "edge_pattern_mining_report.json",
        "skip_if_fast": True,
    },
    {
        # Layer -1 Convention Mining -- HTML page cluster. Companion to the
        # edge-fn miner; proves L-1 generalises across heterogeneous file
        # types. Static-HTML scan only: cannot see runtime-injected scripts.
        "id":      "html-pattern-mining",
        "script":  os.path.join("tools", "mine_html_patterns.py"),
        "args":    [],
        "label":   "HTML Page Pattern Miner (L-1 Convention Mining -- informational, surfaces drift)",
        "group":   "Platform",
        "report":  "html_pattern_mining_report.json",
        "skip_if_fast": True,
    },
    {
        # L-1 cluster A: JS shared modules (utils, nav-hub, wh-*, etc.).
        # Tighter threshold (>=85% / <=3 outliers) because the cluster is
        # small (24 files).
        "id":      "js-module-pattern-mining",
        "script":  os.path.join("tools", "mine_js_module_patterns.py"),
        "args":    [],
        "label":   "JS Shared Module Pattern Miner (L-1 Convention Mining -- informational)",
        "group":   "Platform",
        "report":  "js_module_pattern_mining_report.json",
        "skip_if_fast": True,
    },
    {
        # L-1 cluster B: SQL migrations. Largest cluster (~145 files).
        # Lesson #14 applied: SQL-specific comment-strip (-- + /* */).
        "id":      "migration-pattern-mining",
        "script":  os.path.join("tools", "mine_migration_patterns.py"),
        "args":    [],
        "label":   "SQL Migration Pattern Miner (L-1 Convention Mining -- informational)",
        "group":   "Platform",
        "report":  "migration_pattern_mining_report.json",
        "skip_if_fast": True,
    },
    {
        # L-1 cluster C: Python tools (tools/*.py).
        "id":      "python-tool-pattern-mining",
        "script":  os.path.join("tools", "mine_python_tool_patterns.py"),
        "args":    [],
        "label":   "Python Tool Pattern Miner (L-1 Convention Mining -- informational)",
        "group":   "Platform",
        "report":  "python_tool_pattern_mining_report.json",
        "skip_if_fast": True,
    },
    {
        # L-1 cluster D: Validators themselves (meta). Homogeneous cluster
        # -> threshold raised to >=90%. Most useful for surfacing validators
        # that diverge from the established skeleton (missing cp1252 guard,
        # missing format_result, missing main guard).
        "id":      "validator-pattern-mining",
        "script":  os.path.join("tools", "mine_validator_patterns.py"),
        "args":    [],
        "label":   "Validator Pattern Miner [META] (L-1 Convention Mining -- informational)",
        "group":   "Platform",
        "report":  "validator_pattern_mining_report.json",
        "skip_if_fast": True,
    },
    {
        # L-1 cluster E: Seeders (test-data-seeder/seeders/*.py).
        "id":      "seeder-pattern-mining",
        "script":  os.path.join("tools", "mine_seeder_patterns.py"),
        "args":    [],
        "label":   "Seeder Pattern Miner (L-1 Convention Mining -- informational)",
        "group":   "Platform",
        "report":  "seeder_pattern_mining_report.json",
        "skip_if_fast": True,
    },
    {
        # L-1.5 Skill-Rule Mining -- documented rules from SKILL.md files
        # enforced via skill_rules_manifest.json. Surfaces violations of
        # rules the user has written but never had automatically checked.
        # First run on 2026-05-18 found 8 critical + 6 high-severity
        # violations across 23 rules from 5 skills.
        "id":      "skill-rule-mining",
        "script":  os.path.join("tools", "mine_skill_rules.py"),
        "args":    [],
        "label":   "Skill-Rule Miner [L-1.5] (documented rules from SKILL.md -- informational)",
        "group":   "Platform",
        "report":  "skill_rules_mining_report.json",
        "skip_if_fast": True,
    },
    {
        # L-1 Foundation: Canonical Source Registry. Walks migrations +
        # HTML surfaces + edge fns to build an inventory of every table,
        # RPC, view, and who reads/writes each. Output is the
        # "what's already on the platform" reference -- consulted before
        # proposing any new surface/column/RPC. Also surfaces duplicate
        # signals: surface-pair table-overlap, near-duplicate columns,
        # dead tables, phantom tables. Informational; never blocks.
        "id":      "canonical-registry",
        "script":  os.path.join("tools", "mine_canonical_registry.py"),
        "args":    [],
        "label":   "Canonical Source Registry [L-1 Foundation] (tables/RPCs/views/surfaces inventory + duplicate signals)",
        "group":   "Platform",
        "report":  "canonical_registry.json",
        "skip_if_fast": True,
    },
    {
        # L-1 Layer 2: Canonical Overlap Validator. Reads the registry +
        # an allowlist (canonical_overlap_allowlist.json) and FAILs the
        # gate on (a) phantom tables -- refs in code, no migration def --
        # and (b) NEW surface-pair overlaps not in the allowlist. New
        # duplicate-creation gets blocked; legit role-views must be
        # explicitly documented. Adding to the allowlist is the
        # "this is intentional" switch.
        "id":      "canonical-overlap",
        "script":  "validate_canonical_overlap.py",
        "args":    [],
        "label":   "Canonical Overlap (L-1 Layer 2 -- blocks phantom tables + undocumented surface overlaps)",
        "group":   "Platform",
        "report":  "canonical_overlap_report.json",
        "skip_if_fast": False,
    },
    {
        # First validator graduated from L-1 Convention Mining (86%
        # conformance candidate from mine_html_patterns.py, now an
        # enforced Layer 0 rule). escHtml() XSS defence + Supabase
        # singleton both live in utils.js -- pages that skip it are
        # either pure brochure (allowlisted) or accidental XSS holes.
        "id":      "loads-utils-js",
        "script":  "validate_loads_utils_js.py",
        "args":    [],
        "label":   "Loads-Utils-JS (3-layer: required + allowlist-freshness + census)",
        "group":   "Platform",
        "report":  "loads_utils_js_report.json",
        "skip_if_fast": False,
    },
    {
        # Second validator graduated from L-1 Convention Mining
        # (mine_validator_patterns.py surfaced 33 outliers at 82%
        # conformance; all patched on 2026-05-18, now 100%). Locks the
        # rule so a new validator authored without the cp1252 stdout
        # guard fails Mega Gate immediately rather than crashing on
        # Windows when its output hits a Unicode character.
        "id":      "validator-cp1252-guard",
        "script":  "validate_validator_cp1252_guard.py",
        "args":    [],
        "label":   "Validator cp1252-Guard (3-layer: required + allowlist + placement)",
        "group":   "Platform",
        "report":  "validator_cp1252_guard_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "cascade-behavior",
        "script":  "validate_cascade_behavior.py",
        "args":    [],
        "label":   "Cascade Behavior (4-layer: no-on-delete-clause + explicit-no-action + distribution + orphan-risk)",
        "group":   "Platform",
        "report":  "cascade_behavior_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "hardcoded-secrets",
        "script":  "validate_hardcoded_secrets.py",
        "args":    [],
        "label":   "Hardcoded Secret Detector (4-layer: provider tokens + generic assignments + provider distribution + allowlist inventory)",
        "group":   "Platform",
        "report":  "hardcoded_secrets_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "loading-state",
        "script":  "validate_loading_state.py",
        "args":    [],
        "label":   "Loading State Coverage (4-layer: async-no-loading + submit-no-preventDefault + mechanism distribution + async density)",
        "group":   "Platform",
        "report":  "loading_state_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "jsonb-drift",
        "script":  "validate_jsonb_drift.py",
        "args":    [],
        "label":   "JSONB Schema Drift (4-layer: unread JSONB + reader-without-writer + key inventory + column census)",
        "group":   "Platform",
        "report":  "jsonb_drift_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "validator-self-coverage",
        "script":  "validate_validator_self_coverage.py",
        "args":    [],
        "label":   "Validator Self-Coverage Meta-Gate (4-layer: missing script + unregistered + report mismatch + census)",
        "group":   "Platform",
        "report":  "validator_self_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        # P3 of SELF_IMPROVING_GATE_ROADMAP.md — the gate's freshness sense.
        # Catches the #1 rot vector (a validator asserting a literal/shape the
        # code already moved past) CHEAPLY at G-1, before a full-gate run trips
        # it opaquely. L1 (FAIL): author-declared FRESHNESS_ANCHORS must still
        # match their target file. L2 (INFO): ledger-cross-referenced decay
        # census (never-fired validator whose code-under-test out-paces it).
        "id":      "validator-freshness",
        "script":  "validate_validator_freshness.py",
        "args":    [],
        "label":   "Validator Freshness / Decay Meta-Gate (P3: declared anchors still match target + never-fired-stale-target census)",
        "group":   "Platform",
        "report":  "validator_freshness_report.json",
        "skip_if_fast": False,
    },
    {
        # C5 of SELF_IMPROVING_GATE_ROADMAP.md — version/baseline AI assets
        # like migrations. C2's eval gate scores against artifacts the gate
        # itself doesn't gate today (golden fixtures, judge prompt, model
        # chain, persona block) — a silent edit there invalidates every
        # baseline downstream. This validator FAILs if any manifest asset's
        # hash moved without its declared version bumping. Policy lives in
        # tools/ai_asset_baseline.py; this wraps `verify`.
        "id":      "ai-asset-versioning",
        "script":  "validate_ai_asset_versioning.py",
        "args":    [],
        "label":   "AI Asset Versioning (C5: prompts/eval-sets/model-chain/judge versioned + hash-locked like migrations)",
        "group":   "Platform",
        "report":  "ai_asset_baseline_report.json",
        "skip_if_fast": False,
    },
    {
        # C3 Phase 1 of SELF_IMPROVING_GATE_ROADMAP.md — promote the C2 AI
        # eval regression gate (`tools/ai_eval_gate.py gate`) to a G0
        # validator. Degrade-to-SKIP by design: no committed golden baseline
        # OR no fresh results = exit 0 with an explanatory message; only a
        # locked-test regression beyond tolerance returns exit 1. Mirrors
        # how P1's ledger and P6's split shipped standalone first. C3 Phase
        # 2 (clock + prod off `ai_quality_log` via Grafana/Sentry) is the
        # production extension — separate, needs deploy.
        "id":      "ai-eval-regression",
        "script":  "validate_ai_eval_regression.py",
        "args":    [],
        "label":   "AI Eval Regression Gate (C3 Phase 1: score locked-test split vs frozen golden; degrade-to-SKIP without data)",
        "group":   "Platform",
        "report":  "ai_eval_baseline.json",
        "skip_if_fast": False,
    },
    {
        # Phase 8 §8.3 of AI_SURFACE_MAP.md — the per-COMPANION-DIMENSION regression gate
        # (agent/rag/memory/persona), sibling to ai-eval-regression (which gates the frozen
        # functionality/safety axis). Wraps `tools/ai_eval_gate.py companion_gate()`: for each
        # registry-`active` dim with a frozen baseline in companion_dim_baselines.json, score the
        # dim's latest results on the LOCKED-TEST split and exit 1 only if a *blocking* dim
        # regressed beyond tolerance. Degrade-to-SKIP (exit 0) without a baseline or fresh
        # results. Agent shipped active+forward-only (blocking=false) at n=2 locked-test;
        # flips blocking=true once the golden set is expanded. RAG/Memory/Persona join as built.
        "id":      "companion-dim-gate",
        "script":  "validate_companion_dim_gate.py",
        "args":    [],
        "label":   "Companion Per-Dimension Regression Gate (Phase 8 §8.3: agent/rag/memory/persona locked-test; degrade-to-SKIP without data)",
        "group":   "Platform",
        "report":  "companion_dim_baselines.json",
        "skip_if_fast": False,
    },
    {
        # §0.7 Grounding Doctrine / G-Accept — the STANDING HELD-OUT diverse gate. Ian's invariant:
        # "millions of questions can be right yet a real user still fails." The TEMPLATED fabrication
        # families overfit; the `--diverse` bank (novel/adversarial phrasings, run ONCE, mechanical
        # DB-truth grader in companion_fabrication_sweep.py) keeps the fabrication FLOOR honest. This
        # gate institutionalizes it: it reads the latest diverse board and FAILS only on a genuine
        # REGRESSION beyond the oscillation-ceiling threshold (the rate OSCILLATES ~0-7% run-to-run
        # vs the rotating free-tier model — so it is threshold-not-zero by design), and DEGRADES-TO-
        # SKIP (exit 0) without a fresh/valid board so it never blocks a commit on missing live infra.
        # Produce fresh data with `python validate_companion_diverse_gate.py --run` (needs the local
        # stack + free-tier keys); a scheduled job runs that for a true standing loop. Threshold +
        # forward-only ratchet live in companion_diverse_baseline.json.
        "id":      "companion-diverse-gate",
        "script":  "validate_companion_diverse_gate.py",
        "args":    [],
        "label":   "Companion Held-Out Diverse Gate (§0.7: novel-phrasing fabrication floor; threshold-not-zero; degrade-to-SKIP without a fresh board)",
        "group":   "Platform",
        "report":  "companion_diverse_baseline.json",
        "skip_if_fast": False,
    },
    {
        # C4 Phase 1 of SELF_IMPROVING_GATE_ROADMAP.md — catalog the AI seams
        # (saas→ai / ai→ai / ai→tenant / ai→quota) and ratchet forward-only
        # on the inventory. "Per-domain green ≠ system green" — a seam bug
        # passes both domain gates individually. This Phase 1 establishes
        # the inventory; Phase 2a will wire per-seam contract tests; Phase
        # 2b's meta-gate consumes the catalog to decide blast radius.
        "id":      "ai-seams-inventory",
        "script":  "validate_ai_seams_inventory.py",
        "args":    [],
        "label":   "AI Seams Inventory (C4 Phase 1: catalog SaaS→AI / AI→tenant / AI→quota boundaries + forward-only ratchet)",
        "group":   "Platform",
        "report":  "ai_seams_catalog.json",
        "skip_if_fast": False,
    },
    {
        # C4 Phase 2a of SELF_IMPROVING_GATE_ROADMAP.md — forward-only ratchet
        # on the count of AI seams that lack a wire-format contract test.
        # Each entry wired into ai_seam_contracts.json (seam_id -> test path)
        # pays the baseline down by 1; the baseline floor only drops, never
        # rises silently. Today's floor = 118 (all uncovered); ratchets to 0
        # as Phase 2a payoff work writes contract tests.
        "id":      "ai-seam-coverage",
        "script":  "validate_ai_seam_coverage.py",
        "args":    [],
        "label":   "AI Seam Contract-Test Coverage (C4 Phase 2a: forward-only on uncovered seam count; floor auto-lowers as tests get wired)",
        "group":   "Platform",
        "report":  "ai_seam_coverage_baseline.json",
        "skip_if_fast": False,
    },
    {
        # C4 Phase 2c of SELF_IMPROVING_GATE_ROADMAP.md — observation-only
        # G0 promotion of the meta-gate. The composition policy in
        # tools/meta_gate.py is strictly MORE PERMISSIVE than the monolithic
        # 354-validator gate (it converts FAILs to warn via blast radius +
        # seam-sharpening, never adds blocks), so promoting it as a hard
        # blocker would be a no-op for ship/block. What this promotion DOES
        # add: every gate run writes a per-domain composition reasoning
        # line to meta_gate_decisions.jsonl. That's the macro-loop input
        # P2's promotion engine will later mine — same pattern as P1's
        # efficacy ledger (ship the observer first; make it a driver later).
        "id":      "meta-gate",
        "script":  "validate_meta_gate.py",
        "args":    [],
        "label":   "Meta-Gate Recorder (C4 Phase 2c: observation-mode promotion; writes per-domain decision to meta_gate_decisions.jsonl per gate run)",
        "group":   "Platform",
        "report":  "meta_gate_decisions.jsonl",
        "skip_if_fast": False,
    },
    {
        # Meta-check for the Self-Improving Gate's C-track stack. The 7 C-track
        # phases shipped over 6 in-session turns produced 9 artifacts + 5
        # validators. Once in place, the next risk is silent erosion (a
        # baseline gets deleted, a catalog rename buries the validator that
        # reads it, etc.). This validator asserts every C-track artifact +
        # validator + registry entry + roadmap label is intact + well-formed.
        # FAILs loud the moment any piece goes missing.
        "id":      "c-track-self-coverage",
        "script":  "validate_c_track_self_coverage.py",
        "args":    [],
        "label":   "C-track Self-Coverage (meta: 9 artifacts + 5 validators + registry + roadmap labels of the Self-Improving Gate C-track)",
        "group":   "Platform",
        "report":  "c_track_self_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        # Standing Rule D for the Grounded MCP Sweep: every page marked done in
        # GROUNDED_SWEEP_ROADMAP.md must keep its crystallized live lock (a
        # journey-*.spec.ts assertion named in grounded_sweep_locks.json). FAILs
        # the moment a done page has no lock, or a lock's spec/marker vanishes —
        # so the sweep's guards can't silently erode. Makes the sweep a
        # self-policed part of the self-improving gate, not an adjacent ritual.
        "id":      "grounded-sweep",
        "script":  "validate_grounded_sweep.py",
        "args":    [],
        "label":   "Grounded MCP Sweep Self-Coverage (meta: every done page in the roadmap keeps its crystallized journey lock)",
        "group":   "Platform",
        "report":  "grounded_sweep_report.json",
        "skip_if_fast": False,
    },
    {
        # Step 7 capstone (Companion Stack Battery): the AI sibling of the UFAI
        # sweep. Keeps companion_battery.js (window.__CSB) + the durable
        # journey-companion-comprehensive.spec.ts wired, and forward-only
        # ratchets the rubric's max_major_defects (the capstone's invariant: every
        # HARD grounded proof — model_chain / agent_memory row / cited[] / no-leak
        # — passes). Degrade-to-SKIP if the rubric isn't established yet.
        "id":      "companion-stack",
        "script":  "validate_companion_stack.py",
        "args":    [],
        "label":   "Companion Stack capstone self-coverage (Agent/Memory/RAG/Safety; forward-only on Major grounded defects)",
        "group":   "Platform",
        "report":  "companion_stack_report.json",
        "skip_if_fast": False,
    },
    {
        # Grounded Sweep critique C7, promoted to a gate rule: forward-only DEBT
        # ratchet on hand-rolled modal a11y (role="dialog"+aria-modal). Baselines
        # today's debt (modal_a11y_baseline.json) so it doesn't break the gate,
        # FAILs only when a NEW non-a11y modal ships, and ratchets down as C7
        # retrofits land. Turns a systemic critique into an enforced, tracked metric.
        "id":      "modal-a11y",
        "script":  "validate_modal_a11y.py",
        "args":    [],
        "label":   "Modal A11y Debt Ratchet (no NEW hand-rolled modal without role=dialog+aria-modal; critique C7)",
        "group":   "Platform",
        "report":  "modal_a11y_report.json",
        "skip_if_fast": False,
    },
    {
        # Grounded Sweep (link-destination class): no committed resource attribute
        # (<script src>, <link href>, <img src>, srcset, or <a href>) may hardcode
        # the dev-only /workhive/ prefix. The local URL bridge only rewrites <a href>
        # at runtime, so a committed /workhive/ in any src/link 404s in production.
        # Caught the learn + legal feedback-FAB leak (41 pages dead in prod).
        "id":      "prod-path-leak",
        "script":  "validate_prod_path_leak.py",
        "args":    [],
        "label":   "Prod path leak (no committed /workhive/ resource paths — they 404 in production)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Grounded Sweep critique W3 (status-enum-constants): deterministic guard
        # that utils.js window.WH_STATUS_ENUMS never silently diverges from the
        # canonical capture-contract enum in supabase/migrations. Prevents the class
        # of bug where a hand-typed status literal (e.g. 'closed' vs the real
        # pending/in_progress/done/blocked/skipped) miscounts a KPI — the dayplanner
        # overdue bug. Source-vs-source compare, no page scan, zero false positives.
        "id":      "status-enum-drift",
        "script":  "validate_status_enum_drift.py",
        "args":    [],
        "label":   "Status-Enum Drift Guard (WH_STATUS_ENUMS == canonical DB enum; critique W3)",
        "group":   "Platform",
        "report":  "status_enum_drift_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "provider-bypass",
        "script":  "validate_provider_bypass.py",
        "args":    [],
        "label":   "Direct Provider Bypass (4-layer: client provider + edge bypass + SDK drift + distribution)",
        "group":   "Platform",
        "report":  "provider_bypass_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "cache-invalidation",
        "script":  "validate_cache_invalidation.py",
        "args":    [],
        "label":   "Cache Invalidation (4-layer: shell missing + shell drift + version history + shell inventory)",
        "group":   "Platform",
        "report":  "cache_invalidation_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "realtime-filter",
        "script":  "validate_realtime_filter.py",
        "args":    [],
        "label":   "Cross-Hive Realtime Filter Coverage (4-layer: missing filter + channel naming + scoped distribution + density)",
        "group":   "Platform",
        "report":  "realtime_filter_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "optimistic-reconciliation",
        "script":  "validate_optimistic_reconciliation.py",
        "args":    [],
        "label":   "Optimistic Update Reconciliation (4-layer: no error path + catch w/o rollback + pattern density + handler distribution)",
        "group":   "Platform",
        "report":  "optimistic_reconciliation_report.json",
        "skip_if_fast": False,
    },
    # REMOVED: a second `memory-integrity` registration pointing at the same script, labelled "4-layer:
    # schema + RLS + index + retention". That label was also WRONG — validate_memory_integrity.py checks the
    # agent_memory schema, per-tab session_id tracking, >90%-similarity dedup and the memory window passed to
    # the LLM. Neither RLS, nor indexes, nor retention. So the duplicate was both redundant work and a false
    # description of what the gate proves, which is the more expensive half: a reader trusting that label
    # would believe retention was covered when nothing asserts it
    # ([[feedback_the_prose_was_stale_the_registry_was_right]], inverted — here the prose was the registry).
    {
        "id":      "gateway-routing",
        "script":  "validate_gateway_routing.py",
        "args":    [],
        "label":   "AI Gateway Routing (4-layer: gateway present + routes exist + canonical coverage + inventory)",
        "group":   "Platform",
        "report":  "gateway_routing_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "agent-handoff-contract",
        "script":  "validate_agent_handoff_contract.py",
        "args":    [],
        "label":   "Agent Handoff Contract (4-layer: handoff keys + specialist awareness + worker_name trust + inventory)",
        "group":   "Platform",
        "report":  "agent_handoff_contract_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "function-security",
        "script":  "validate_function_security.py",
        "args":    [],
        "label":   "SQL Function Security Posture (4-layer: DEFINER+search_path + trigger explicit + matrix + aggregate)",
        "group":   "Platform",
        "report":  "function_security_report.json",
        "skip_if_fast": False,
    },
    {
        # Companion to function-security: that checks the search_path-shadowing
        # class; this checks the TENANT-isolation class. A SECURITY DEFINER fn
        # taking a hive_id bypasses RLS, so if it's reachable by anon/auth and
        # has no in-function membership gate it's a cross-hive IDOR vector
        # (invisible to RLS-policy validators). FAIL-at-0: gated OR service_role-only.
        "id":      "definer-membership-gate",
        "script":  "validate_definer_membership_gate.py",
        "args":    [],
        "label":   "SECURITY DEFINER Hive-Membership Gate (every DEFINER hive-fn gated OR service_role-only)",
        "group":   "Platform",
        "report":  "definer_membership_gate_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "admin-gates",
        "script":  "validate_admin_gates.py",
        "args":    [],
        "label":   "Admin Gate Enforcement (founder-console, marketplace-admin must verify admin)",
        "group":   "Platform",
        "report":  "admin_gates_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "html-id-unique",
        "script":  "validate_html_id_unique.py",
        "args":    [],
        "label":   "HTML ID Uniqueness (4-layer: dup-within-file + cross-page drift + density + reserved-name)",
        "group":   "Platform",
        "report":  "html_id_unique_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "trigger-reentrancy",
        "script":  "validate_trigger_reentrancy.py",
        "args":    [],
        "label":   "Trigger Reentrancy Safety (4-layer: self-write guard + indirect loop + inventory + depth adoption)",
        "group":   "Platform",
        "report":  "trigger_reentrancy_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "migration-order",
        "script":  "validate_migration_order.py",
        "args":    [],
        "label":   "Schema Migration Order Safety (4-layer: table order + column order + function order + dependency matrix)",
        "group":   "Platform",
        "report":  "migration_order_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "auth-boundary",
        "script":  "validate_auth_boundary.py",
        "args":    [],
        "label":   "Auth Boundary Coverage (4-layer: HTML identity + edge auth + identity distribution + anon writes)",
        "group":   "Platform",
        "report":  "auth_boundary_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ai-eval-coverage",
        "script":  "validate_ai_eval_coverage.py",
        "args":    [],
        "label":   "AI Evaluation Coverage (4-layer: registry present + fixture coverage + eval cron + quality log)",
        "group":   "Platform",
        "report":  "ai_eval_coverage_report.json",
        "skip_if_fast": False,
    },
    {"id": "bundle-bloat", "script": "validate_bundle_bloat.py", "args": [],
     "label": "Edge Function Bundle Bloat (4-layer: LOC + imports + distribution + dynamic adoption)",
     "group": "Platform", "report": "bundle_bloat_report.json", "skip_if_fast": False},
    {"id": "sw-offline", "script": "validate_sw_offline.py", "args": [],
     "label": "Service Worker Offline Coverage (4-layer: critical-in-shell + offline fallback + resilience + register)",
     "group": "Platform", "report": "sw_offline_report.json", "skip_if_fast": False},
    {"id": "module-scope-state", "script": "validate_module_scope_state.py", "args": [],
     "label": "Module-Scope Mutable State (4-layer: unbounded growth + eviction adoption + inventory + clean fns)",
     "group": "Platform", "report": "module_scope_state_report.json", "skip_if_fast": False},
    {"id": "date-arithmetic", "script": "validate_date_arithmetic.py", "args": [],
     "label": "Date Arithmetic Safety (4-layer: space-date + parse-vs-ISO + ms literals + TZ-naive helpers)",
     "group": "Platform", "report": "date_arithmetic_report.json", "skip_if_fast": False},
    {"id": "cron-functional", "script": "validate_cron_functional.py", "args": [],
     "label": "Cron Job Functional Coverage (4-layer: target exists + config entry + AI gate + density)",
     "group": "Platform", "report": "cron_functional_report.json", "skip_if_fast": False},
    {"id": "jsonb-index", "script": "validate_jsonb_index.py", "args": [],
     "label": "JSONB Index Drift (4-layer: missing GIN + arrow freq + inventory + op distribution)",
     "group": "Platform", "report": "jsonb_index_report.json", "skip_if_fast": False},
    {"id": "test-page-drift", "script": "validate_test_page_drift.py", "args": [],
     "label": "Test Page Drift (4-layer: smaller + larger + orphans + inventory)",
     "group": "Platform", "report": "test_page_drift_report.json", "skip_if_fast": False},
    {"id": "embedding-coverage", "script": "validate_embedding_coverage.py", "args": [],
     "label": "Embedding Coverage & Freshness (4-layer: refresh pipeline + vector index + source coverage + dim inventory)",
     "group": "Platform", "report": "embedding_coverage_report.json", "skip_if_fast": False},
    {"id": "ai-cost-observability", "script": "validate_ai_cost_observability.py", "args": [],
     "label": "AI Cost Observability (4-layer: ledger + callAI logs + dashboard + invocations)",
     "group": "Platform", "report": "ai_cost_observability_report.json", "skip_if_fast": False},
    {"id": "hive-quota", "script": "validate_hive_quota.py", "args": [],
     "label": "Per-Hive Resource Quota (4-layer: quota table + trigger coverage + inventory + adoption)",
     "group": "Platform", "report": "hive_quota_report.json", "skip_if_fast": False},
    {"id": "logbook-quota", "script": "tools/validate_logbook_quota.py", "args": [],
     "label": "Q0 Logbook Quota Pilot (per-day rate-limit trigger + server text caps + friendly UX + photo size assert; the Q2-replication template)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "quota-coverage", "script": "tools/validate_quota_coverage.py", "args": [],
     "label": "Q2/Q5 Quota Coverage Ratchet (every high-write table has a per-day cap on a REAL timestamp column; FAILs if a new surface ships uncapped)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "text-cap-coverage", "script": "tools/validate_text_cap_coverage.py", "args": [],
     "label": "Q3 Text+Upload Cap Ratchet (server-side text-cap trigger per high-write table + upload size/duration caps; no unbounded user input)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "quota-board", "script": "tools/quota_board.py", "args": ["--check"],
     "label": "Q5 Unified Quota Board (aggregates all quota dimensions into one measured board; FAILs if any bound is red)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "quota-page-audit", "script": "tools/quota_page_audit.py", "args": ["--check"],
     "label": "Per-Page Quota Audit (EVERY production feature page's write tables are capped or documented-excluded; FAILs on any uncapped page write)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "global-ai-budget", "script": "tools/validate_global_ai_budget.py", "args": [],
     "label": "Q6 Global LLM Budget Guard (the org-shared-pool layer above per-tenant caps: atomic row-locked consume RPC + daily circuit-breaker + per-minute burst smoother that sheds background/passes interactive + fail-open + wired at the gateway; FAILs if any regress)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "cumulative-quota-enforce", "script": "tools/validate_cumulative_quota_enforcement.py", "args": [],
     "label": "Q1 Cumulative Quota Enforcement (hive_quotas.enforce_blocking flipped ON + generous abuse-ceiling caps backfilled + new-hive auto-seed + all 5 cumulative triggers ATTACHED + status-fixed RAISE 54000; catches the trigger-drift + 'warn'-status bug classes)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "embedding-retention", "script": "tools/validate_embedding_retention.py", "args": [],
     "label": "Q5-b Embedding/Growth Retention (embedding_cache LRU auto-prune cron + prune fn; canonical big tables via the safe DRY-RUN-default, double-gated cold_archive_prune step-3 whose safety gate provably never deletes without a verified Parquet snapshot)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "realtime-channel-cap", "script": "tools/validate_realtime_channel_cap.py", "args": [],
     "label": "Q5 Realtime Cap + Graceful-429 (whRealtimeSubscribe bounds channels PER CLIENT against the verified 200-concurrent free-tier wall + degrades overflow/offline to visibility-aware polling + frees the slot on stop; scope-aware 429 UX maps each gateway body (burst/platform/daily/hourly) to the right hint; C5+C6 run Node behavioural tests as real teeth)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "inline-image-guard", "script": "tools/validate_inline_image_guard.py", "args": [],
     "label": "Q5-a Inline Image Detector-Guard (server-side base64 photo size cap on logbook+inventory_items backstopping the <=700KB client compression + photo_attach_stats() telemetry; the right-sized move since measured attach-rate is 0% — full Storage-offload stays deferred until the rate climbs)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "ai-daily-ceiling", "script": "tools/validate_ai_daily_ceiling.py", "args": [],
     "label": "Q4 AI Daily Ceiling (per-day AI window on ai_rate_limits+ai_user_rate_limits denies scope='day' at the daily cap; the deno-gated live-runtime 429 is proven via a Node local-substitute that drives the REAL checkAIRateLimit/checkSoloRateLimit decision — deploy Ian-gated)",
     "group": "Platform", "report": None, "skip_if_fast": False},
    {"id": "data-retention", "script": "validate_data_retention.py", "args": [],
     "label": "Data Retention / Right-to-Erasure (4-layer: delete path + helper + PII inventory + retention)",
     "group": "Platform", "report": "data_retention_report.json", "skip_if_fast": False},
    {"id": "ai-safety", "script": "validate_ai_safety.py", "args": [],
     "label": "AI Input Bounds / Safety (4-layer: field slices + any slice + slice constants + input inventory)",
     "group": "Platform", "report": "ai_safety_report.json", "skip_if_fast": False},
    {"id": "ai-alignment", "script": "validate_ai_alignment.py", "args": [],
     "label": "AI Alignment / Provenance (4-layer: source stamp + provenance cols + dashboard filter + inventory)",
     "group": "Platform", "report": "ai_alignment_report.json", "skip_if_fast": False},
    {"id": "ai-payload-hygiene", "script": "validate_ai_payload_hygiene.py", "args": [],
     "label": "AI Payload Hygiene (4-layer: no select-star + module prompts + limit bounds + payload inventory)",
     "group": "Platform", "report": "ai_payload_hygiene_report.json", "skip_if_fast": False},
    {"id": "pgvector-consistency", "script": "validate_pgvector_consistency.py", "args": [],
     "label": "pgvector Consistency (4-layer: dim match + hive filter + embedding RLS + dim distribution)",
     "group": "Platform", "report": "pgvector_consistency_report.json", "skip_if_fast": False},
    {"id": "pdf-pipeline", "script": "validate_pdf_pipeline.py", "args": [],
     "label": "PDF Pipeline / Knowledge Ingestion (4-layer: jobs table + runner fn + coverage + inventory)",
     "group": "Platform", "report": "pdf_pipeline_report.json", "skip_if_fast": False},
    {"id": "rag-completeness", "script": "validate_rag_completeness.py", "args": [],
     "label": "RAG Completeness (4-layer: rerank helper + budget helper + rerank adoption + inventory)",
     "group": "Platform", "report": "rag_completeness_report.json", "skip_if_fast": False},
    {"id": "gateway-coverage", "script": "validate_gateway_coverage.py", "args": [],
     "label": "Platform Gateway Coverage (4-layer: gateway present + routes exist + coverage + inventory)",
     "group": "Platform", "report": "gateway_coverage_report.json", "skip_if_fast": False},
    {"id": "gateway-audit", "script": "validate_gateway_audit.py", "args": [],
     "label": "Platform Gateway Audit Completeness (4-layer: schema + writes + RLS + retention)",
     "group": "Platform", "report": "gateway_audit_report.json", "skip_if_fast": False},
    {"id": "gateway-tenancy", "script": "validate_gateway_tenancy.py", "args": [],
     "label": "Gateway Tenancy Verification (Pillar I: client hive_id must be membership-verified; ratchet 34->0)",
     "group": "Platform", "report": "gateway_tenancy_report.json", "skip_if_fast": False},
    {"id": "policy-hive-binding", "script": "validate_policy_hive_binding.py", "args": [],
     "label": "Gateway Policy Hive-Binding (Pillar P: anon-capable fns must rate-limit on the verified tenant, never a raw client hive_id)",
     "group": "Platform", "report": "policy_hive_binding_report.json", "skip_if_fast": False},
    {
        "id":      "ai-pattern-compliance",
        "script":  "validate_ai_pattern_compliance.py",
        "args":    [],
        "label":   "AI Pattern Compliance (4-layer: rate-gate-first + fallback chain + JSON mode + cost concentration)",
        "group":   "Platform",
        "report":  "ai_pattern_compliance_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "state-machine-integrity",
        "script":  "validate_state_machine_integrity.py",
        "args":    [],
        "label":   "State Machine Integrity (4-layer: invalid writes + unreachable states + unconstrained columns + writer matrix)",
        "group":   "Platform",
        "report":  "state_machine_integrity_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "audit-log-coverage",
        "script":  "validate_audit_log_coverage.py",
        "args":    [],
        "label":   "Audit Log Coverage (4-layer: unaudited writers + dead audit columns + critical-table coverage + writer matrix)",
        "group":   "Platform",
        "report":  "audit_log_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "cron-schedule-integrity",
        "script":  "validate_cron_schedule_integrity.py",
        "args":    [],
        "label":   "Cron Schedule Integrity (4-layer: function existence + scheduled-agents routing + config drift + schedule sanity)",
        "group":   "Platform",
        "report":  "cron_schedule_integrity_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "rls-readiness",
        "script":  "validate_rls_readiness.py",
        "args":    [],
        "label":   "RLS Readiness Audit (4-layer: lockout traps + dead policies + permissive USING(true) catalog + verb completeness)",
        "group":   "Platform",
        "report":  "rls_readiness_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "auth-migration-readiness",
        "script":  "validate_auth_migration_readiness.py",
        "args":    [],
        "label":   "Auth Migration Readiness (Phase A audit: sibling coverage + auth_uid columns + identity gate strength)",
        "group":   "Platform",
        "report":  "auth_migration_readiness_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "edge-caller-contract",
        "script":  "validate_edge_caller_contract.py",
        "args":    [],
        "label":   "Edge Function Caller Contract (4-layer: function existence + required field coverage + phantom fields + orphan functions)",
        "group":   "Platform",
        "report":  "edge_caller_contract_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "env-secret-coverage",
        "script":  "validate_env_secret_coverage.py",
        "args":    [],
        "label":   "Env Secret Coverage (4-layer: declared coverage + required-vs-optional + orphan keys + hardcoded secret detection)",
        "group":   "Platform",
        "report":  "env_secret_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "realtime-payload-contract",
        "script":  "validate_realtime_payload_contract.py",
        "args":    [],
        "label":   "Realtime Payload Consumer Contract (4-layer: subscribed table + payload columns + filter columns + channel name uniqueness)",
        "group":   "Platform",
        "report":  "realtime_payload_contract_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "edge-response-contract",
        "script":  "validate_edge_response_contract.py",
        "args":    [],
        "label":   "Edge Function Response Contract (4-layer: function returns + caller field validity + introspection coverage + error-only detection)",
        "group":   "Platform",
        "report":  "edge_response_contract_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "realtime-cleanup",
        "script":  "validate_realtime_cleanup.py",
        "args":    [],
        "label":   "Realtime Subscription Cleanup (4-layer: cleanup pairing + lifecycle wiring + const-decl warning + asymmetry metric)",
        "group":   "Platform",
        "report":  "realtime_cleanup_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "reliability-workbench",
        "script":  "validate_reliability_workbench.py",
        "args":    [],
        "label":   "Reliability Workbench Validator (FMEA + RCM + Weibull + P-F schema, RLS, canonical registration)",
        "group":   "Platform",
        "report":  "reliability_workbench_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "maturity-gating",
        "script":  "validate_maturity_gating.py",
        "args":    [],
        "label":   "Maturity Gating Validator (Phase 0.5: gated pages load maturity-gate.js + call checkMaturityGate + render honest empty state)",
        "group":   "Platform",
        "report":  "maturity_gating_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "amc",
        "script":  "validate_amc.py",
        "args":    [],
        "label":   "AMC Validator (Phase 1.9: amc_briefings migration + cost log + realtime + alert-hub subscription + canonical anchor)",
        "group":   "Platform",
        "report":  "amc_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "visual-defect",
        "script":  "validate_visual_defect.py",
        "args":    [],
        "label":   "Visual Defect Capture Validator (Phase 1.9: callAIMultimodal + rate-limit + MIME whitelist + fire-and-forget embed + cost log)",
        "group":   "Platform",
        "report":  "visual_defect_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "sensor-pipeline",
        "script":  "validate_sensor_pipeline.py",
        "args":    [],
        "label":   "Sensor Pipeline Validator (Phase 1.9: sensor_readings schema + realtime + asset-hub subscription + anomaly module)",
        "group":   "Platform",
        "report":  "sensor_pipeline_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "achievements",
        "script":  "validate_achievements.py",
        "args":    [],
        "label":   "Achievements Validator (Phase 1.9: badge_key + catalog-not-in-reset + worker_achievements realtime + ON CONFLICT shape)",
        "group":   "Platform",
        "report":  "achievements_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "dayplanner",
        "script":  "validate_dayplanner.py",
        "args":    [],
        "label":   "Day Planner Validator (Phase 1.9: DILO/WILO/MILO/YILO tabs + schedule_items + nav-hub linkage + auth-aware)",
        "group":   "Platform",
        "report":  "dayplanner_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "resilience",
        "script":  "validate_resilience.py",
        "args":    [],
        "label":   "Resilience Validator (Phase 1.10 reframe: offline queue + network-loss UI + fetchWithTimeout + shared-device sign-out)",
        "group":   "Platform",
        "report":  "resilience_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "adoption-observability",
        "script":  "validate_adoption_observability.py",
        "args":    [],
        "label":   "Adoption Observability Validator (Phase 3.6: hive_adoption_score migration + supervisor card + onboarding stepper + intent capture + canonical anchors)",
        "group":   "Platform",
        "report":  "adoption_observability_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "revenue-surfaces",
        "script":  "validate_revenue_surfaces.py",
        "args":    [],
        "label":   "Revenue Surfaces Validator (Phase 4: AI Quality Stair 2 gate + Anomaly Engine 2.0 Stair 3 gate + Knowledge Pipeline tile + canonical anchors)",
        "group":   "Platform",
        "report":  "revenue_surfaces_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "enterprise-unlock",
        "script":  "validate_enterprise_unlock.py",
        "args":    [],
        "label":   "Enterprise Unlock Validator (Phase 5: retention + soft-delete cron + PDPA export + auth_session_events + MFA scaffold + SSO scaffold + Plant Connections Console)",
        "group":   "Platform",
        "report":  "enterprise_unlock_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "industry-defining",
        "script":  "validate_industry_defining.py",
        "args":    [],
        "label":   "Industry-Defining Validator (Phase 6: knowledge graph + drone inspections + standards registry + federated opt-in + insurance bridge view + MaaS consulting engagements)",
        "group":   "Platform",
        "report":  "industry_defining_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "audit-trail-coverage",
        "script":  "validate_audit_trail_coverage.py",
        "args":    [],
        "label":   "Audit Trail Coverage (2-layer: lifecycle status updates write to hive_audit_log + every action name has ACTION_ICON entry)",
        "group":   "Platform",
        "report":  "audit_trail_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "realtime-publication",
        "script":  "validate_realtime_publication.py",
        "args":    [],
        "label":   "Realtime Publication Coverage Validator (subscribed tables in supabase_realtime)",
        "group":   "Platform",
        "report":  "realtime_publication_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "hive-state-consistency",
        "script":  "validate_hive_state_consistency.py",
        "args":    [],
        "label":   "Hive-State LocalStorage Consistency Validator (branch-symmetry on hive.html)",
        "group":   "Platform",
        "report":  "hive_state_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "arc-x-cognitive",
        "script":  "validate_arc_x_cognitive.py",
        "args":    [],
        "label":   "Arc X Cognitive-Load HARD Gate (L1 real-login hive resolution / Issue #1)",
        "group":   "Platform",
        "report":  "arc_x_cognitive_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "arc-x-cfamily",
        "script":  "tools/validate_arc_x_cfamily.py",
        "args":    [],
        "label":   "Arc X Family C scanner (C2 placeholder-as-label + C1 recall-entity floor at 0)",
        "group":   "Platform",
        "report":  "arc_x_cfamily_report.json",
        "skip_if_fast": True,
    },
    {
        "id":      "arc-x-befamily",
        "script":  "tools/validate_arc_x_befamily.py",
        "args":    [],
        "label":   "Arc X Family B+E scanner (B2 information-scent floor at 0; B3/E3 candidate lists)",
        "group":   "Platform",
        "report":  "arc_x_befamily_report.json",
        "skip_if_fast": True,
    },
    {
        "id":      "soft-delete",
        "script":  "validate_soft_delete.py",
        "args":    [],
        "label":   "Soft-Delete Read-Path Validator (.is(deleted_at, null) on every SELECT)",
        "group":   "Platform",
        "report":  "soft_delete_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "schema-drift",
        "script":  "validate_schema_drift.py",
        "args":    [],
        "label":   "Schema Drift Validator (HTML SELECT columns exist in EXPECTED_SCHEMA)",
        "group":   "Platform",
        "report":  "schema_drift_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "logbook-consistency",
        "script":  "validate_logbook_consistency.py",
        "args":    [],
        "label":   "Logbook Consistency (closed_at set, Open no closed_at, parts txn parity)",
        "group":   "Data Quality",
        "report":  "logbook_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "pattern-alerts",
        "script":  "validate_pattern_alerts.py",
        "args":    [],
        "label":   "Pattern Alerts Quality (no <think> leak, valid rule_ids, non-empty text)",
        "group":   "Data Quality",
        "report":  "pattern_alerts_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "inventory-integrity",
        "script":  "validate_inventory_integrity.py",
        "args":    [],
        "label":   "Inventory Integrity (no negative qty, valid txn types, qty_after accuracy)",
        "group":   "Data Quality",
        "report":  "inventory_integrity_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "hive",
        "script":  "validate_hive.py",
        "args":    [],
        "label":   "Hive Validator",
        "group":   "Platform",
        "report":  "hive_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "logbook",
        "script":  "validate_logbook.py",
        "args":    [],
        "label":   "Logbook Validator",
        "group":   "Platform",
        "report":  "logbook_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "inventory",
        "script":  "validate_inventory.py",
        "args":    [],
        "label":   "Inventory Validator",
        "group":   "Platform",
        "report":  "inventory_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "marketplace",
        "script":  "validate_marketplace.py",
        "args":    [],
        "label":   "Marketplace Validator (4-layer: schema + edge functions + UI gates + money flow)",
        "group":   "Platform",
        "report":  "marketplace_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "pm",
        "script":  "validate_pm.py",
        "args":    [],
        "label":   "PM Scheduler Validator",
        "group":   "Platform",
        "report":  "pm_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "skillmatrix",
        "script":  "validate_skillmatrix.py",
        "args":    [],
        "label":   "Skill Matrix Validator",
        "group":   "Platform",
        "report":  "skillmatrix_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "report-sender",
        "script":  "validate_report_sender.py",
        "args":    [],
        "label":   "Report Sender Validator (32 checks: structure + UI + logic + PWA)",
        "group":   "Platform",
        "report":  "report_sender_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "community",
        "script":  "validate_community.py",
        "args":    [],
        "label":   "Community Validator (24 checks: XSS + isolation + access + realtime + standards + feature schema completeness)",
        "group":   "Platform",
        "report":  "community_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "assistant",
        "script":  "validate_assistant.py",
        "args":    [],
        "label":   "Assistant Validator",
        "group":   "Platform",
        "report":  "assistant_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ai-context",
        "script":  "validate_ai_context.py",
        "args":    [],
        "label":   "AI Context Quality Validator",
        "group":   "Platform",
        "report":  "ai_context_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "input-guards",
        "script":  "validate_input_guards.py",
        "args":    [],
        "label":   "Input Guards Validator",
        "group":   "Platform",
        "report":  "input_guards_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "schema",
        "script":  "validate_schema.py",
        "args":    [],
        "label":   "Schema Consistency Validator",
        "group":   "Platform",
        "report":  "schema_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "observability",
        "script":  "validate_observability.py",
        "args":    [],
        "label":   "Observability Validator",
        "group":   "Platform",
        "report":  "observability_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "governance",
        "script":  "validate_governance.py",
        "args":    [],
        "label":   "Data Governance Validator",
        "group":   "Platform",
        "report":  "governance_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "pwa",
        "script":  "validate_pwa.py",
        "args":    [],
        "label":   "PWA Integrity Validator",
        "group":   "Platform",
        "report":  "pwa_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "accessibility",
        "script":  "validate_accessibility.py",
        "args":    [],
        "label":   "Accessibility Baseline Validator",
        "group":   "Platform",
        "report":  "accessibility_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "tenant-boundary",
        "script":  "validate_tenant_boundary.py",
        "args":    [],
        "label":   "Tenant Boundary Escape Validator (5-layer, +nullable auth_uid RLS trap)",
        "group":   "Platform",
        "report":  "tenant_boundary_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ai-regression",
        "script":  "validate_ai_regression.py",
        "args":    [],
        "label":   "AI Prompt Regression Validator (4-layer: consistency + content + parity + Tier-S citation)",
        "group":   "Platform",
        "report":  "ai_regression_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "timers",
        "script":  "validate_timers.py",
        "args":    [],
        "label":   "Timer and Scheduled Job Hygiene",
        "group":   "Platform",
        "report":  "timers_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "xss",
        "script":  "validate_xss.py",
        "args":    [],
        "label":   "XSS / escHtml Coverage Validator",
        "group":   "Platform",
        "report":  "xss_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "seo",
        "script":  "validate_seo.py",
        "args":    [],
        "label":   "SEO and Page Metadata Validator",
        "group":   "Platform",
        "report":  "seo_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "mobile",
        "script":  "validate_mobile.py",
        "args":    [],
        # Checks: viewport-fit=cover, input font-size >=16px, safe-area-inset-bottom,
        # touch targets >=44px, will-change:filter mobile override (iOS GPU crash guard),
        # body{animation} prefers-reduced-motion override (blank page guard)
        "label":   "Mobile UX Compliance Validator",
        "group":   "Platform",
        "report":  "mobile_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "nav-registry",
        "script":  "validate_nav_registry.py",
        "args":    [],
        "label":   "Nav Hub Registry Validator",
        "group":   "Platform",
        "report":  "nav_registry_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "performance",
        "script":  "validate_performance.py",
        "args":    [],
        # Checks: unbounded queries, select('*') on wide tables, N+1 loops,
        # sequential awaits, body{animation} animationend safety guard (blank page guard)
        "label":   "Performance Anti-Pattern Validator",
        "group":   "Platform",
        "report":  "performance_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "catalog-scope",
        "script":  "validate_catalog_scope.py",
        "args":    [],
        "label":   "Catalog Approval Status Validator",
        "group":   "Platform",
        "report":  "catalog_scope_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "drawings",
        "script":  "validate_drawings.py",
        "args":    [],
        "label":   "Drawing Standards Compliance Validator",
        "group":   "Platform",
        "report":  "drawings_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "diagram_inputs",
        "script":  "validate_diagram_inputs.py",
        "args":    [],
        "label":   "Diagram Inputs Contract Validator (inp.xxx vs collectInputs keys)",
        "group":   "Platform",
        "report":  "diagram_inputs_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "compliance",
        "script":  "validate_compliance.py",
        "args":    [],
        "label":   "Enterprise Compliance Baseline Validator",
        "group":   "Platform",
        "report":  "compliance_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "notifications",
        "script":  "validate_notifications.py",
        "args":    [],
        "label":   "Notification and Alert Health Validator",
        "group":   "Platform",
        "report":  "notifications_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "predictive",
        "script":  "validate_predictive.py",
        "args":    [],
        "label":   "Predictive Analytics Data Quality Validator",
        "group":   "Platform",
        "report":  "predictive_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "vector-schema",
        "script":  "validate_vector_schema.py",
        "args":    [],
        "label":   "Vector Knowledge Base Schema Validator",
        "group":   "Platform",
        "report":  "vector_schema_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "groq-fallback",
        "script":  "validate_groq_fallback.py",
        "args":    [],
        "label":   "AI Provider Chain Validator",
        "group":   "Platform",
        "report":  "groq_fallback_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "edge-contracts",
        "script":  "validate_edge_contracts.py",
        "args":    [],
        "label":   "Edge Function API Contract Validator",
        "group":   "Platform",
        "report":  "edge_contracts_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ops-snapshot-agents",
        "script":  "validate_ops_snapshot_agents.py",
        "args":    [],
        "label":   "Ops-Snapshot Agent Coverage (every factual-answer agent is grounded, not just the companion)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        "id":      "ai-attribution",
        "script":  "validate_ai_attribution.py",
        "args":    [],
        "label":   "AI Output Attribution Validator",
        "group":   "Platform",
        "report":  "ai_attribution_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "context-window",
        "script":  "validate_context_window.py",
        "args":    [],
        "label":   "Context Window Management Validator",
        "group":   "Platform",
        "report":  "context_window_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "knowledge-freshness",
        "script":  "validate_knowledge_freshness.py",
        "args":    [],
        "label":   "Knowledge Base Freshness Validator",
        "group":   "Platform",
        "report":  "knowledge_freshness_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "sso-readiness",
        "script":  "validate_sso_readiness.py",
        "args":    [],
        "label":   "SSO Readiness Validator",
        "group":   "Platform",
        "report":  "sso_readiness_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "idempotency",
        "script":  "validate_idempotency.py",
        "args":    [],
        "label":   "Webhook and Integration Idempotency Validator (5-layer, +UPDATE col exists, +backfill timing)",
        "group":   "Platform",
        "report":  "idempotency_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "integration-security",
        "script":  "validate_integration_security.py",
        "args":    [],
        "label":   "Integration Security Baseline Validator (3-layer, +cors dynamic, +deploy coverage)",
        "group":   "Platform",
        "report":  "integration_security_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "cmms-contracts",
        "script":  "validate_cmms_contracts.py",
        "args":    [],
        "label":   "CMMS Contracts Validator (STATUS_MAP parity, DB column targets, shared imports)",
        "group":   "Platform",
        "report":  "cmms_contracts_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "cmms-reconciliation",
        "script":  "validate_cmms_reconciliation.py",
        "args":    [],
        "label":   "CMMS Reconciliation Validator (external_sync vs table counts, audit coverage, quality scores)",
        "group":   "Platform",
        "report":  "cmms_reconciliation_report.json",
        "skip_if_fast": True,   # requires live Supabase
    },
    {
        "id":      "digital-twin",
        "script":  "validate_digital_twin.py",
        "args":    [],
        "label":   "Digital Twin Schema Readiness Validator",
        "group":   "Platform",
        "report":  "digital_twin_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "iot-protocols",
        "script":  "validate_iot_protocols.py",
        "args":    [],
        "label":   "IoT and MQTT Protocol Safety Validator",
        "group":   "Platform",
        "report":  "iot_protocols_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "content-quality",
        "script":  "validate_content_quality.py",
        "args":    [],
        "label":   "Content Quality Validator (embed guard, schema drift, label quality)",
        "group":   "Platform",
        "report":  "content_quality_report.json",
        "skip_if_fast": False,
    },
    {
        # Content Grounding Gate (the 3rd sibling) — folded into the DEFAULT run so
        # outward content<->platform drift is caught on every routine gate run, not
        # only when content_dev.py is invoked by hand (D2 self-running, 2026-06-29).
        # The loop was a SENSOR that went 17 days stale; this makes it self-running.
        # Ratcheted (forward-only): PASS on pre-existing drift, FAIL on NEW drift.
        # 12 checks incl. derive-and-render surface_render_drift + llms_article_completeness.
        # Headless (~2s, offline; no server/DB/model). skip_if_fast like its heavy siblings.
        "id":      "content-grounding",
        "script":  "tools/content_grounding_gate.py",
        "args":    [],
        "label":   "Content Grounding Gate (12-check outward content drift: feature/count/link/capability/surface-render/llms-completeness; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "content_grounding_report.json",
        "skip_if_fast": True,
    },
    {
        # Article<->Page taxonomy consistency (2026-07-05): a feature /learn/ article's
        # stated taxonomy-noun counts (disciplines/calculators/templates/tabs/...) must
        # match its OWN linked feature page. Catches the class content_grounding's
        # capability_drift misses: the eng-calculators article claimed "6 disciplines /
        # 30+ calculators" vs the page's 6 real disciplines + 53 calcs; skill-matrix says
        # "4 of 6 disciplines" vs the page's "5 disciplines". Prose-only, deterministic,
        # offline (~1s) → runs even in --fast. Forward-only ratchet.
        "id":      "article-taxonomy",
        "script":  "tools/validate_article_taxonomy.py",
        "args":    [],
        "label":   "Content Grounding: Article<->Page Taxonomy Consistency (forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "article_taxonomy.json",
        "skip_if_fast": False,
    },
    {
        # SEO Technical Gate (SEO/AEO/GEO Arc P1) — the on-page technical levers
        # validate_seo.py lacks: exactly-one-H1, <img> alt, JSON-LD VALIDITY (parses,
        # not just present), and no NEW retired FAQ/HowTo rich-result schema (Google
        # retired both). Surface list is CATALOG-DERIVED, so a new /learn article is
        # covered automatically (validate_seo.py's hand-list had drifted 28-vs-38).
        # Ratcheted forward-only; PASS on pre-existing, FAIL on NEW drift. ~1s offline.
        "id":      "seo-technical",
        "script":  "tools/seo_technical_gate.py",
        "args":    [],
        "label":   "SEO Technical Gate (P1: one-H1 + img-alt + JSON-LD validity + no-new-retired-schema; catalog-derived surfaces; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "seo_technical_report.json",
        "skip_if_fast": True,
    },
    {
        # Extractability Gate (SEO/AEO/GEO Arc P2) — the on-page AEO/GEO levers
        # WorkHive fully controls (Princeton/SIGKDD GEO triad): a crisp answer-first
        # opener + >=1 statistic + >=1 cited source per /learn article. Catalog-derived,
        # ratcheted forward-only (a new article can't ship without the levers). ~1s offline.
        "id":      "extractability",
        "script":  "tools/extractability_gate.py",
        "args":    [],
        "label":   "Extractability Gate (P2: answer-first + statistic + cited-source per article; Princeton GEO triad; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "extractability_report.json",
        "skip_if_fast": True,
    },
    {
        # Landing Extractability Gate (SEO/AEO/GEO Arc P2.5) — the layer the article
        # gates missed: index.html is the ONLY index,follow page, yet its richest
        # content (the 28-tool catalog) + most internal tool links live ONLY inside a
        # JS stageData popup (innerHTML on click), invisible to AI crawlers (don't run
        # JS) and to Googlebot (never fires the click). Measures the SCRIPT-STRIPPED DOM
        # — what a crawler actually sees (display:none in-DOM links DO count). Catalog-/
        # stageData-derived, ratcheted forward-only. Detection-only. ~1s offline.
        "id":      "landing-extractability",
        "script":  "tools/landing_extractability_gate.py",
        "args":    [],
        "label":   "Landing Extractability Gate (P2.5: catalog tool-page links + popup copy/links crawlable + featureList; script-stripped DOM; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "landing_extractability_report.json",
        "skip_if_fast": True,
    },
    {
        # Programmatic calculator-page gate (SEO_AEO_GEO_STRATEGY_V2.md, Pillar 3) — the
        # 58 engineering calculators are the largest programmatic-SEO surface WorkHive
        # owns, but they live ONLY in a noindex client-side JS app (engineering-design.js),
        # invisible to AI crawlers that fetch-but-don't-execute JS
        # (external-ai-crawlers-fetch-but-do-not-execute-javascript-). This gate proves
        # every generated /tools/<calc>-calculator/ STATIC page is crawlable (numeric
        # worked result in raw HTML, not JS-injected), answer-first (a .answer-first stat
        # right after the H1), schema-valid (SoftwareApplication + FAQPage + HowTo),
        # non-orphan (>=2 internal /learn|/tools links), and non-thin. Scans
        # seo_assets/calc_pages_staging/ (pre-ship) + any shipped tools/*-calculator/.
        # PASSES when no pages exist yet (nothing to gate). Static, offline (~1s).
        # Self-test: `python tools/validate_calc_pages.py --self-test`.
        "id":      "calc-pages",
        "script":  "tools/validate_calc_pages.py",
        "args":    [],
        "label":   "Programmatic Calculator-Page Gate (Pillar 3: crawlable + answer-first + SoftwareApplication/FAQPage schema + non-orphan; static HTML for AI crawlers)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # AIO-readiness gate (SEO_AEO_GEO_V3 §5) — the instrument for the pillar V3 split
        # out of GEO. Three of AIO's four levers were already built; the fourth,
        # MULTI-SOURCE CREDIBILITY, is the one our own pages cannot supply, and nothing
        # measured it. At first run every cluster pillar NAMED standards bodies in prose
        # (SMRP, ISO, DOE, NFPA) and LINKED zero of them — and an AI Overview assembles
        # agreeing INDEPENDENT sources, so a cluster whose every link points back to
        # workhiveph.com reads as one unverified source. Hence the bar is LINKED, not
        # named: >=2 independent external domains per pillar, plus schema completeness and
        # a resolvable Organization entity. `entity_resolvable` is the one component no
        # local work can move (it needs real profile URLs in index.html's sameAs), which is
        # why it is reported separately rather than folded into a single score. Ratcheted
        # forward-only — the honest initial state was mostly failing, and a permanently-red
        # gate teaches everyone to ignore it. Static, offline (~0.1s).
        # Self-test: `python tools/aio_readiness_gate.py --self-test`.
        # Calculator-claim consistency (SEO_AEO_GEO_V3 §5, AIO multi-source credibility).
        # Nothing checked whether the numbers WorkHive states ABOUT ITSELF are true, so
        # they drifted while every other gate stayed green: the public surface claimed
        # 51, 53, 58 AND 60 calculators across 6, 7 and 8 disciplines — four sizes for one
        # product — with the calculator guide contradicting ITSELF (60 in four places, 53
        # in three) and its visible "Updated 17 May" disagreeing with its own dateModified
        # of 5 August. That is a GEO defect, not a typo: an answer engine quotes a specific
        # figure, and the AIO pillar is scored on multi-source credibility. A site that
        # cannot corroborate its own headline number gives an engine no way to pick the
        # right one, so the safe move for the engine is to cite somebody else.
        # TWO SSOTs, kept separate because they count DIFFERENT THINGS: the workbench
        # registry (CALC_TYPES_UI, 55/6) and the standalone pages (CALC_DATA, 60/8). A page
        # may quote either, so the gate does not demand one number — it demands that every
        # number quoted matches a DERIVED one. Word forms count too ("Six disciplines"),
        # because the drift hid in both forms; and a discipline claim only counts when
        # calculator language sits within 120 chars, so skill-matrix's "5 disciplines"
        # (about skills) is not swept in. Static, offline (~1s).
        # Self-test: `python tools/calc_claim_consistency_gate.py --self-test`.
        "id":      "calc-claim-consistency",
        "script":  "tools/calc_claim_consistency_gate.py",
        "args":    [],
        "label":   "Calculator-Claim Consistency Gate (V3 §5: every self-reported calculator/discipline count matches a derived SSOT; visible Updated == schema dateModified; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "calc_claim_consistency_report.json",
        "skip_if_fast": True,
    },
    {
        # AIO scores MULTI-SOURCE CREDIBILITY, and aio-readiness enforces that a source be
        # LINKED rather than merely named. Nothing checked that the link still RESOLVES. A
        # citation pointing at a 404 is worse than no citation: it is a claim a reader can
        # disprove in one click, on exactly the pages built to look authoritative.
        #
        # NOT a naive status check, and that distinction is the whole design. First
        # measurement returned 5 of 14 authority URLs as 403 -- dole.gov.ph, erc.gov.ph,
        # iso.org, and both officialgazette.gov.ph laws. Reporting those as broken would
        # have been a FABRICATED finding: re-checked through a real browser every one
        # returned a page titled "Just a moment...", which is Cloudflare's bot challenge,
        # and iec.ch returned CloudFront's block page. They are alive for a human and
        # closed to a robot. So 404/410 counts as DEAD; 403/429/503 carrying a challenge
        # marker is SHIELDED and reported but never failed; a network error is never DEAD,
        # because that may be our connection rather than their site.
        #
        # ADVISORY (exit 0 unless a link is provably dead AND new). A gate that reaches the
        # network flakes under load, and a check that reddens for something the author
        # cannot fix is one the team learns to ignore -- this repo has both precedents.
        # Current state: 15 citations, 9 alive, 6 shielded, 0 dead.
        # Self-test: `python tools/authority_link_gate.py --self-test`.
        "id":      "authority-links",
        "script":  "tools/authority_link_gate.py",
        "args":    [],
        "label":   "Authority-link resolution (V3 5, AIO: every outbound citation still resolves; "
                   "404/410 = dead and ratcheted, bot-challenge 403 = shielded and reported, never failed)",
        "group":   "AI Validation",
        "report":  "authority_link_report.json",
        "skip_if_fast": True,
    },
    {
        "id":      "aio-readiness",
        "script":  "tools/aio_readiness_gate.py",
        "args":    [],
        "label":   "AIO-Readiness Gate (V3 §5: per-pillar schema + >=2 LINKED independent sources + resolvable entity; multi-source credibility for AI Overviews/Copilot; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "aio_readiness_report.json",
        "skip_if_fast": True,
    },
    {
        # CTA gate (SEO_AEO_GEO_V3 §6, SXO) — the last post-click lever with no instrument.
        # Winning the citation is the expensive half; a visitor who arrives from an AI
        # answer, reads to the end and finds nowhere to go is the cheapest loss on the
        # board. Nothing noticed that 19 of 53 /learn articles ended with no next action.
        # What counts is an IN-BODY link to an ACTION surface (a WorkHive tool or the join
        # flow). Deliberately excluded: links to other articles (a good next read is not a
        # next action) and header/footer chrome — every page carries those, so counting
        # them would score 100% and measure nothing, which is the failure mode this gate
        # exists to avoid. Ratcheted forward-only. Static, offline (~0.8s).
        # Self-test: `python tools/cta_gate.py --self-test`.
        "id":      "cta",
        "script":  "tools/cta_gate.py",
        "args":    [],
        "label":   "CTA Coverage Gate (V3 §6 SXO: every public content page offers a next ACTION; in-body tool/join links only, chrome and cross-article links excluded; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "cta_report.json",
        "skip_if_fast": True,
    },
    {
        # Content-surface mobile gate (SEO_AEO_GEO_V3 §6, SXO) — validate_mobile.py targets
        # the APP pages and always has; its checks (safe-area insets, overscroll
        # containment, animation cascade) are about a stateful JS surface and
        # false-positive on static articles, so extending it was the wrong move. This is
        # the content-surface equivalent: viewport, responsiveness, >=16px body prose, and
        # no fixed layout width outside a media query — the four properties that decide
        # whether a phone visitor arriving from a search result can read the page at all.
        # Three false-positive classes are pinned by its self-test after measuring produced
        # each one: `\bwidth` matching inside `max-width` (27 phantom defects, every one an
        # @media breakpoint), 11px on an eyebrow LABEL read as unreadable body text, and
        # judging Tailwind responsiveness by @media (27/114 on a site built from one shared
        # responsive template). Ratcheted forward-only. Static, offline (~0.7s).
        # Self-test: `python tools/content_mobile_gate.py --self-test`.
        "id":      "content-mobile",
        "script":  "tools/content_mobile_gate.py",
        "args":    [],
        "label":   "Content-Surface Mobile Gate (V3 §6 SXO: viewport + responsive + >=16px prose + no fixed width across /learn and /tools; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "content_mobile_report.json",
        "skip_if_fast": True,
    },
    {
        # Content-freshness census (SEO_AEO_GEO_STRATEGY_V2 §4.3) — ADVISORY, always exit 0.
        # Perplexity cites content updated within the last 30 days 82% of the time, and the
        # refresh cadence was prescribed with nothing measuring it, so it silently did not
        # happen: at first run 43 of 53 articles were 31-90 days old and only 10 were inside
        # the window. Staleness tiers differ by what the page is for (pillar/comparison 30d,
        # article 90d, calculator 365d — a formula and a standard do not move).
        # DELIBERATELY NOT A FAILING CHECK: a blocking gate here would push toward bumping
        # `dateModified` without editing the content, which is a lie to the crawler, is
        # trivially detectable by diffing against the previous crawl, and burns exactly the
        # trust the freshness signal measures. It ranks the refresh queue so a REAL refresh
        # lands where it pays most. Static, offline (~0.3s).
        # Self-test: `python tools/content_freshness_gate.py --self-test`.
        "id":      "content-freshness",
        "script":  "tools/content_freshness_gate.py",
        "args":    [],
        "label":   "Content-Freshness Census (V2 §4.3: staleness per page against tiered targets, ranked refresh queue; ADVISORY — never fails, so it cannot incentivise a fake date bump)",
        "group":   "AI Validation",
        "report":  "content_freshness_report.json",
        "skip_if_fast": True,
    },
    {
        # Landing + Home-Dashboard Deep Arc gate (LANDING_DASHBOARD_DEEP_ARC.md) —
        # locks the confirmed front-door defects the arc fixed so they cannot
        # regress: (G6/F4) og:title + twitter:title must equal <title> (the arc
        # found the social cards silently dropped "Filipino"); (AI3) no fabricated
        # "NN% precision/accuracy" metric in the marketing copy (found "98%
        # precision" on AI worker-matching with zero source behind
        # v_worker_assignment_truth); (F4) every landing subdir carries a
        # twitter:card (feedback/ shipped without one). Static, offline (~1s) →
        # runs even in --fast. Forward-only ratchet.
        "id":      "landing-deep",
        "script":  "tools/validate_landing.py",
        "args":    [],
        "label":   "Landing Deep-Arc Gate (title-token consistency + no-fabricated-metric + subdir twitter:card; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "landing_validation.json",
        "skip_if_fast": False,
    },
    {
        # CSP Hardening ratchet (CSP_HARDENING_ARC.md, Landing arc I6a). Ian chose the
        # STRICT + nonce path (a multi-phase build: server nonce + inline-handler removal +
        # Tailwind-CDN->built-CSS + strict CSP). Until it lands, this FREEZES the inline-
        # handler + un-nonced-script debt on index.html (baseline 46 handlers / 12 scripts):
        # the counts may only SHRINK, never grow (a new onclick= makes the eventual strict
        # CSP strictly harder). Also reports the measured distance to strict-CSP-done. Flip
        # STRICT_ENFORCED=True in the script when the build completes. Static, offline (~1s).
        "id":      "csp-ratchet",
        "script":  "tools/validate_csp.py",
        "args":    [],
        "label":   "CSP Hardening Ratchet (index.html inline-handler/un-nonced-script debt frozen; forward-only toward strict CSP)",
        "group":   "AI Validation",
        "report":  "csp_baseline.json",
        "skip_if_fast": False,
    },
    {
        # Orphan / click-depth (SEO/AEO/GEO Arc, Crawl-index cell) — every public surface
        # must have >=1 crawlable inbound <a href> (no orphans) AND be reachable from
        # index.html in <=3 clicks. Builds the internal-link graph from the SCRIPT-STRIPPED
        # DOM (crawler view) over the catalog-derived public surfaces; BFS from the homepage.
        # Pure-code, ratcheted forward-only. ~1s offline.
        "id":      "orphan-depth",
        "script":  "tools/orphan_depth_gate.py",
        "args":    [],
        "label":   "Orphan / Click-Depth Gate (P1: 0 orphaned public pages + every page <=3 clicks from index.html; crawl-graph over script-stripped DOM; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "orphan_depth_report.json",
        "skip_if_fast": True,
    },
    {
        # Core Web Vitals (SEO/AEO/GEO Arc, P3 CWV cell) — the FAST half of a two-tool scorer:
        # tools/cwv_probe.mjs drives headless mobile Chromium across the public surfaces (warm-
        # median LCP/INP/CLS, written to cwv_measurements.json), and THIS gate ratchets the
        # measurements (LCP<=2500/INP<=200/CLS<=0.1 + a coverage check). Sub-second (reads JSON);
        # the heavy browser sweep is on-demand. Forward-only ratchet. ~0.1s offline.
        "id":      "cwv",
        "script":  "tools/cwv_gate.py",
        "args":    [],
        "label":   "Core Web Vitals Gate (P3: warm-median mobile LCP/INP/CLS over public surfaces vs 2026 thresholds + coverage; reads cwv_measurements.json; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "cwv_report.json",
        "skip_if_fast": True,
    },
    {
        # Platform Name Alignment (Platform Alignment Arc) — the PAGES are the naming
        # ground truth; this flags every feature whose catalog name or landing-popup
        # name has drifted from the page's own <title>. (Root: the catalog name field
        # is hand-authored intel that drifted — schema_featurelist passes against the
        # stale catalog while the displayed names are stale-vs-reality.) Ratcheted
        # forward-only; burns down via the page-truth re-anchor + surface sync. ~1s.
        "id":      "name-alignment",
        "script":  "tools/platform_name_alignment.py",
        "args":    [],
        "label":   "Platform Name Alignment (page <title> = authority; catalog/popup name drift; forward-only ratchet)",
        "group":   "AI Validation",
        "report":  "platform_name_alignment_report.json",
        "skip_if_fast": True,
    },
    {
        "id":      "data-governance-kb",
        "script":  "validate_data_governance.py",
        "args":    [],
        "label":   "Data Governance Validator (ownership, metadata, write path, versioning)",
        "group":   "Platform",
        "report":  "data_governance_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ai-data-pipeline",
        "script":  "validate_ai_data_pipeline.py",
        "args":    [],
        "label":   "AI Data Pipeline Validator (stale data, silos, latency, observability)",
        "group":   "Platform",
        "report":  "ai_data_pipeline_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "data-quality",
        "script":  "validate_data_quality.py",
        "args":    [],
        "label":   "Data Quality Validator (duplicates, incomplete, bias, inconsistent formats)",
        "group":   "Platform",
        "report":  "data_quality_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "analytics",
        "script":  "validate_analytics.py",
        "args":    [],
        "label":   "Analytics Engine Validator (4-layer: HTML + Edge + Python + AST)",
        "group":   "Platform",
        "report":  "analytics_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "project-manager",
        "script":  "validate_project_manager.py",
        "args":    [],
        "label":   "Project Manager Validator (4-layer: HTML + Edge + Python + Smoke)",
        "group":   "Platform",
        "report":  "project_manager_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ml-layer",
        "script":  "validate_ml.py",
        "args":    [],
        "label":   "ML Layer Validator (5-layer: features + API + artifacts + edge fns + UI)",
        "group":   "Platform",
        "report":  "ml_report.json",
        "skip_if_fast": False,
    },
    # ── Analytics Live Integration Test ──────────────────────────────────────
    {
        "id":      "analytics-live",
        "script":  "validate_analytics_live.py",
        "args":    [],
        "label":   "Analytics Live Test (L4 — deployed endpoint, all 4 phases)",
        "group":   "Platform",
        "report":  "analytics_live_report.json",
        "skip_if_fast": True,   # skip with --fast
    },
    # ── Engineering Calc Integration Test (Layer 3) ───────────────────────────
    {
        "id":      "calc-integration",
        "script":  "validate_integration.py",
        "args":    [],
        "label":   "Calc Integration Test (L3 — live edge function)",
        "group":   "Engineering Calculator",
        "report":  None,
        "skip_if_fast": True,   # skip with --fast
    },
    {
        "id":      "playwright-staleness",
        "script":  "validate_playwright_staleness.py",
        "args":    [],
        "label":   "Playwright Staleness Gate (L13 — walkthrough coverage + finding closure + chip assertions)",
        "group":   "Platform",
        "report":  "playwright_staleness_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "companion-page-coverage",
        "script":  "validate_companion_page_coverage.py",
        "args":    [],
        "label":   "Companion Launcher Page Coverage (L0 — every nav-hub page has companion-launcher.js)",
        "group":   "Platform",
        "report":  "companion_page_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "companion-source-coverage",
        "script":  "validate_companion_source_coverage.py",
        "args":    [],
        "label":   "Companion Source Coverage (L0 — the Sources Gateway: every v_*_truth view triaged in companion_source_registry.json)",
        "group":   "Platform",
        "skip_if_fast": False,
    },
    {
        "id":      "voice_kb_context",
        "script":  "tools/validate_voice_kb_context.py",
        "args":    [],
        "label":   "AI Self-Improvement: Voice Kb Context",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "voice_alert_order",
        "script":  "tools/validate_voice_alert_order.py",
        "args":    [],
        "label":   "AI Self-Improvement: Voice Alert Order",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "voice_response_latency",
        "script":  "tools/validate_voice_response_latency.py",
        "args":    [],
        "label":   "AI Self-Improvement: Voice Response Latency",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "response_format_validation",
        "script":  "tools/validate_response_format_validation.py",
        "args":    [],
        "label":   "AI Self-Improvement: Response Format Validation",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "data_completeness",
        "script":  "tools/validate_data_completeness.py",
        "args":    [],
        "label":   "AI Self-Improvement: Data Completeness",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "calc_formula_accuracy",
        "script":  "tools/validate_calc_formula_accuracy.py",
        "args":    [],
        "label":   "AI Self-Improvement: Calc Formula Accuracy",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "calc_live_value",
        "script":  "tools/validate_calc_live_value.py",
        "args":    [],
        "label":   "Arc Q: Calc LIVE Value-at-the-Glass (63/63 types — running API serves the standard-correct number)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,   # needs the python-api container up (live HTTP)
    },
    {
        "id":      "engines_live_value",
        "script":  "tools/validate_engines_live_value.py",
        "args":    [],
        "label":   "Arc Q: Engines LIVE Value-at-the-Glass (analytics MTBF/OEE/MTTR + reliability P-F + projects EVM/CPM — running API serves standard-correct)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,   # needs the python-api container up (live HTTP)
    },
    {
        "id":      "calc_api_serializable",
        "script":  "tools/validate_calc_api_serializable.py",
        "args":    [],
        "label":   "Calc API JSON-Serializability (numpy-500 / silent-TS-fallback class)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "engdesign_registry",
        "script":  "tools/validate_engdesign_registry.py",
        "args":    [],
        "label":   "Deep-arc P1: Engineering-Design registry SSOT (counts derive from CALC_TYPES_UI; no drift/orphans)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "engdesign_write_isolation",
        "script":  "tools/validate_engdesign_write_isolation.py",
        "args":    [],
        "label":   "Deep-arc P2/I-2: engineering_calcs WRITE-side isolation (foreign auth_uid insert blocked, self allowed) — LIVE",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,   # needs the local supabase_db_workhive container
    },
    {
        "id":      "engdesign_a11y",
        "script":  "tools/validate_engdesign_a11y.py",
        "args":    [],
        "label":   "Deep-arc P3: Engineering-Design report a11y (contrast U-1/U-4, 44px U-6, label/announce passes U-2/U-3/U-8)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "engdesign_xss",
        "script":  "tools/validate_engdesign_xss.py",
        "args":    [],
        "label":   "Deep-arc P4: Engineering-Design XSS/output-encoding (no row-into-onclick I-7, no raw narrative I-6, validateBeforeSave I-5)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "engdesign_ai",
        "script":  "tools/validate_engdesign_ai.py",
        "args":    [],
        "label":   "Deep-arc P5: Engineering-Design AI egress integrity (timeout AI-4, honest copy AI-5, disclosure AI-7, friendly errors AI-8, narration grounding AI-1)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "engdesign_ai_citations",
        "script":  "tools/validate_engdesign_ai_citations.py",
        "args":    [],
        "label":   "Deep-arc P5/AI-6: Engineering-Design AI citation grounding (fabricated-standard detector w/ teeth; live narratives cite only real standard families)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,   # live tier needs the edge runtime up; hermetic teeth run regardless
    },
    {
        "id":      "engdesign_silent_zero",
        "script":  "tools/validate_engdesign_silent_zero.py",
        "args":    [],
        "label":   "Deep-arc P7/F-5: Engineering-Design silent-zero ratchet (result `|| 0` alias-chains can't grow past baseline)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "engdesign_units",
        "script":  "tools/validate_engdesign_units.py",
        "args":    [],
        "label":   "Deep-arc P6/A-6: Engineering-Design scoped SI/IP units toggle (engine normalized to SI; universal/ambiguous units excluded)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "analytics_correctness",
        "script":  "tools/validate_analytics_correctness.py",
        "args":    [],
        "label":   "AI Self-Improvement: Analytics Engine Value Accuracy",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Anti-drift lock for ANALYTICS_UFAI_ROADMAP.md's 97.2% scoreboard: re-asserts the
        # code-side invariant behind every dim driven to 100% (CLS reserves, 44px targets,
        # tabular nums, reduced-motion, i18n wiring, h2 headings, Pareto encoding, and the
        # ISO8601 date parse that stopped a silent 99.4% row loss). A doc drifts; a gate does not.
        "id":      "analytics_ufai_scoreboard",
        "script":  "tools/validate_analytics_ufai_scoreboard.py",
        "args":    [],
        "label":   "UFAI: Analytics Engine scoreboard invariants (anti-drift lock)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "projects_correctness",
        "script":  "tools/validate_projects_correctness.py",
        "args":    [],
        "label":   "AI Self-Improvement: Project Manager EVM + CPM Value Accuracy",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "reliability_correctness",
        "script":  "tools/validate_reliability_correctness.py",
        "args":    [],
        "label":   "AI Self-Improvement: Reliability P-F Interval Value Accuracy",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc F (Python Compute API UFAI) B1 keystone — edge↔python shared-secret gate.
        "id":      "python_api_auth",
        "script":  "tools/validate_python_api_auth.py",
        "args":    ["--self-test"],
        "label":   "Arc F: Python API auth gate (edge↔python shared secret)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc F B3 — whole-API supply-chain gate (generalizes validate_ml_deps + pip-audit CVE scan).
        "id":      "python_api_deps",
        "script":  "tools/validate_python_api_deps.py",
        "args":    [],
        "label":   "Arc F: Python API supply-chain (hard-import declaration + CVE scan)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc H H2 — voice-router DETERMINISTIC routing/tool-selection oracle. Hermetic value-oracle
        # (no seeder/model/DB): runs tests/voice-router-determinism.spec.ts against the REAL exported
        # core (kind allowlist, confidence clamp [0,1], slot-fill guard, asset disambiguation). The
        # edge fn imports the same _shared/voice-router-core.ts the test exercises — one source, zero drift.
        "id":      "voice_router_oracle",
        "script":  "validate_voice_router_oracle.py",
        "args":    [],
        "label":   "Arc H: Voice-router determinism oracle (routing/tool-selection value-correctness)",
        "group":   "AI Validation",
        "report":  "voice_router_oracle_report.json",
        "skip_if_fast": False,
    },
    {
        # Arc H H2/F — voice-router slot-fill guard LIVE end-to-end (real JWT+LLM invoke of voice-action-router):
        # no confident asset-required intent without a resolved asset (the A3 junk-write protection). $0 free-tier;
        # needs the seeder + edge runtime, so skip in --fast.
        "id":      "voice_router_live",
        "script":  "validate_voice_router_live.py",
        "args":    [],
        "label":   "Arc H: Voice-router LIVE slot-fill guard (no junk-write; runtime path)",
        "group":   "AI Validation",
        "report":  "voice_router_live_report.json",
        "skip_if_fast": True,
    },
    {
        # Arc G G1 — SECURITY DEFINER tenant-gate (DEFINER bypasses RLS; FORCE-RLS=0). Needs the
        # live DB (docker exec psql), so skip in --fast; the readiness gate requires it in full mode.
        "id":      "definer_tenant_gate",
        "script":  "tools/validate_definer_tenant_gate.py",
        "args":    [],
        "label":   "Arc G: DEFINER tenant-gate (no un-gated cross-tenant DEFINER mutator)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc G G2 — legacy always-true RLS policy detector (auth-migration enforcement gap).
        # Forward-only DOWN ratchet: regression (a NEW exposed table) fails; needs live DB.
        "id":      "rls_permissive_bypass",
        "script":  "tools/validate_rls_no_permissive_bypass.py",
        "args":    [],
        "label":   "Arc G: RLS no-permissive-bypass (legacy USING(true) tenant-isolation gap)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc G G4 — VIEW security_invoker (read-path twin of the DEFINER IDOR). A non-security_invoker
        # view runs as its BYPASSRLS owner and leaks every hive's rows. Needs live DB; skip in --fast.
        "id":      "view_security_invoker",
        "script":  "tools/validate_view_security_invoker.py",
        "args":    [],
        "label":   "Arc G: view security_invoker (no view bypasses base-table RLS = cross-tenant read)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc G G2 — LIVE per-table two-tenant RLS isolation (a member sees 0 of another hive's rows).
        # Needs the live DB; by-design cross-hive tables (community/feedback/admin-analytics) are curated.
        "id":      "rls_tenant_isolation",
        "script":  "tools/validate_rls_tenant_isolation.py",
        "args":    [],
        "label":   "Arc G: RLS tenant isolation (live two-tenant; member sees 0 cross-hive rows)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc G G1 — non-RLS hive-scoped table detector (RLS entirely disabled). DOWN ratchet @0;
        # a NEW non-RLS hive table regresses. Needs live DB.
        "id":      "rls_coverage",
        "script":  "tools/validate_rls_coverage.py",
        "args":    [],
        "label":   "Arc G: RLS coverage (no hive OR personal auth_uid table ships with RLS disabled)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc G G4 — v_*_truth views must be security_invoker so base-table RLS applies to the READ path
        # (an owner-running truth view bypasses RLS = cross-tenant read). Baseline 0; needs live DB.
        "id":      "truth_view_security_invoker",
        "script":  "tools/validate_truth_view_security_invoker.py",
        "args":    [],
        "label":   "Arc G: truth-view security_invoker (read path respects RLS, no view RLS-bypass)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc G G3 (U/F) — RPC return-shape consumer contract: no app RPC returns bare record/SETOF record
        # without OUT/TABLE params (opaque to PostgREST/callers). Baseline 0 opaque; needs live DB.
        "id":      "rpc_return_shape",
        "script":  "tools/validate_rpc_return_shape.py",
        "args":    [],
        "label":   "Arc G: RPC return-shape (no opaque record returns; introspectable consumer contract)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc H H1 — AI retrieval tenant-isolation (OWASP LLM08): a user-callable SECURITY DEFINER retrieval
        # RPC that filters by a client hive_id/auth_uid must self-gate membership (DEFINER bypasses RLS).
        # Baseline 0; also catches the PUBLIC-default grant blind spot. Needs live DB.
        "id":      "ai_retrieval_isolation",
        "script":  "tools/validate_ai_retrieval_isolation.py",
        "args":    [],
        "label":   "Arc H: AI retrieval isolation (no cross-tenant DEFINER read/vector IDOR; LLM08)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc J keystone — Realtime subscription isolation (read-path twin of the DEFINER/view IDOR).
        # The publication is the live broadcast set; channel-name + client `filter` are NOT boundaries —
        # the table's SELECT RLS policy is. A published table with RLS-off or an always-true policy is a
        # cross-tenant LIVE stream. Forward-only DOWN ratchet; needs live DB; skip in --fast.
        "id":      "realtime_subscription_isolation",
        "script":  "tools/validate_realtime_subscription_isolation.py",
        "args":    [],
        "label":   "Arc J: realtime subscription isolation (no realtime-published table streams to anon)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc J/J7 — auth-migration completion: an unauthenticated (anon) client must read 0 rows from
        # every core hive table (DB enforcement proof, positive twin of rls_no_permissive_bypass) AND every
        # production hive-read page must establish a session. Forward-only; needs live DB; skip in --fast.
        "id":      "anon_key_retirement",
        "script":  "tools/validate_anon_key_retirement.py",
        "args":    [],
        "label":   "Arc J/J7: anon-key retirement (anon reads 0 hive rows; pages session-gated)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc H H7/I — every frontend-direct LLM edge fn must rate-limit (OWASP LLM10 Unbounded
        # Consumption). Static gate; gateway-fronted fns exempt (rate-limited upstream). Baseline 0.
        "id":      "ai_rate_limit_coverage",
        "script":  "tools/validate_ai_rate_limit_coverage.py",
        "args":    [],
        "label":   "Arc H: AI rate-limit coverage (no unbounded frontend-direct LLM call; LLM10)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R (Z, OWASP A10) — no unguarded user/tenant-controlled outbound fetch. The shared
        # _shared/ssrf-guard.ts (safeFetch) must wrap every tenant-URL fetch (cmms-sync /
        # cmms-push-completion endpoint_url, equipment-label-ocr image_url). Static; teeth.
        "id":      "ssrf_egress",
        "script":  "tools/validate_ssrf_egress.py",
        "args":    [],
        "label":   "Arc R: SSRF egress (tenant-controlled fetch routed through ssrf-guard; A10)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R (Z, OWASP A01) — every verify_jwt=false edge fn that calls an LLM must enforce its
        # OWN guard (auth OR rate-limit). Catches the open-LLM-proxy class (voice-model-call /
        # ai-eval-runner / voice-embeddings) the rate-limit-coverage gate missed. Static; teeth.
        "id":      "public_fn_authz",
        "script":  "tools/validate_public_fn_authz.py",
        "args":    [],
        "label":   "Arc R: public-fn authZ (no verify_jwt=false LLM fn without auth/rate-limit; A01)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R (Z, OWASP A01) — a security lock must not silently RE-OPEN. Once a migration explicitly
        # revokes anon/authenticated EXECUTE on a fn (a deliberate app-role lock-out), no LATER migration
        # may re-grant it to public/anon/authenticated without a `-- regrant-approved` marker. Catches the
        # exact C2.1 regression (20260624 episodic_supersedes re-granted match_procedural_memories that
        # 20260620 had locked → cross-tenant retrieval IDOR). Static/offline; teeth (self-test).
        "id":      "migration_grant_regression",
        "script":  "tools/validate_migration_grant_regression.py",
        "args":    [],
        "label":   "Arc R: migration grant-regression (a revoked lock not silently re-granted; A01)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R (Z, OWASP A01/BFLA) — a verify_jwt=false edge fn that WRITES on the service-role client
        # must enforce an auth/cron/signature gate. Sibling of public_fn_authz (LLM-proxy subset) for the
        # WRITE surface. Caught pdf-ingest = anon-triggerable all-hives drainer (R2, 2026-07-01). Static; teeth.
        "id":      "public_fn_write_authz",
        "script":  "tools/validate_public_fn_write_authz.py",
        "args":    [],
        "label":   "Arc R: public-fn write authZ (no anon-triggerable service-role writer; A01/BFLA)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R (X, OWASP A03) — no UNESCAPED worker-writable DB free-text field interpolated into
        # an HTML template (the stored-XSS class validate_xss's presence check misses). Baseline 0; teeth.
        "id":      "dom_xss_fields",
        "script":  "tools/validate_dom_xss_fields.py",
        "args":    [],
        "label":   "Arc R: DOM-XSS DB-field escaping (DB free-text in HTML must be escHtml; A03)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Hive Board Deep Arc (PDDA 2026-07-10) — locks this arc's structural fixes:
        # no write to the DROPPED `assets` table, the #supervisor-summary CLS reserve is
        # role-scoped (no worker void), and the RLS-hardening migration is present.
        "id":      "hive_board",
        "script":  "tools/validate_hive_board.py",
        "args":    [],
        "label":   "Hive Board: asset write on asset_nodes + role-scoped reserve + RLS migration",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R (P, OWASP LLM10/A03) — user text entering an LLM prompt must be length-capped
        # (ai-orchestrator/scheduled-agents/walkthrough-analyzer/voice-model-call). Deterministic
        # static gate (never flakes — unlike an LLM-grading gate); locks the caps against regression.
        "id":      "ai_input_caps",
        "script":  "tools/validate_ai_input_caps.py",
        "args":    [],
        "label":   "Arc R: AI input caps (user text length-capped before LLM; LLM10)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Memory hygiene (2026-06-24) — the auto-memory MEMORY.md index must stay under the session
        # LOAD CAP so older memories don't silently truncate at session start. Detect layer of the
        # Prevent(one-liner rule)→Detect(this)→Fix(compact_memory_index.py --apply)→Govern(doctrine)
        # discipline. WARN over the soft budget (still loads); FAIL only over the hard load cap.
        "id":      "memory_index_budget",
        "script":  "tools/compact_memory_index.py",
        "args":    ["--check"],
        "label":   "Memory hygiene: MEMORY.md index under the session load cap (auto-memory)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Marketplace Deepwalk EXPANSION arc (2026-07-24) — the ANTI-DRIFT COMPASS with teeth.
        # The arc grows TWO denominators: journeys (20 x 5 phases G/W/O/H/R, each requiring >=2
        # personas AND >=2 states) and new MK dimension classes (10 x 6 stages). This gate is the
        # FORWARD-ONLY RATCHET: the measured % may only RISE. A dropped journey, a downgraded phase,
        # or a deleted MK class FAILs the build — so the roadmap cannot silently rot into a stale
        # doc (feedback_roadmap_percent_is_the_anti_drift_compass + measured_percent_not_qualitative).
        # Offline + deterministic (pure JSON maths, no DB/network) -> runs in --fast. Self-test:
        # `python tools/marketplace_deepwalk_scoreboard.py --selftest`. Ratchet up with --accept.
        # RENAMED from `marketplace_deepwalk_ratchet`, which this entry SHARED with a different gate
        # (`validate_marketplace_deepwalk.py`, ~230 lines below). Two different scripts under one id collide
        # in the results dict, so whichever ran second overwrote the first — and `gate_efficacy_ledger.json`
        # proves which way it went: its lone `marketplace_deepwalk_ratchet` entry carries the OTHER gate's
        # label, meaning THIS gate's verdict was being discarded from the ledger and could have gone red
        # without registering. Found by the id-uniqueness assertion added to main() in the same pass that
        # removed three exact-duplicate registrations. The other entry keeps the original id so its ledger
        # history stays correctly attached; this one takes a name that says what it is.
        "id":      "marketplace_deepwalk_scoreboard",
        "script":  "tools/marketplace_deepwalk_scoreboard.py",
        "args":    ["--check"],
        "label":   "Marketplace deepwalk expansion %-board (forward-only ratchet: journeys x phases + MK dimension classes may only rise)",
        "group":   "AI Validation",
        "report":  "MARKETPLACE_DEEPWALK_SCOREBOARD.md",
    },
    {
        # The ⑥ R-resolve LOCK for the classes closed by the Marketplace Deepwalk EXPANSION arc
        # (2026-07-24). Each check encodes a live-found defect so a regression FAILs the build instead
        # of waiting for the next deepwalk to rediscover it:
        #   MK2 — all THREE moderation surfaces (platform-actions live; marketplace-admin +
        #         founder-console retired-but-preserved) must capture moderation_reason on reject.
        #         Fixing one and missing another is the J20 divergence this arc exists to catch.
        #   MK7 — no `marketplace.html#listing-<id>` dead deep links (the page only reads ?listing=).
        #   MK3 — the anon-granted public seller RPC must project no messenger_username/hive_id/auth_uid.
        #   MK1 — a star rating must be guarded by a real review count (no unattributable score).
        # Static/offline (file parsing only) -> runs in --fast, never flakes. Self-test: --selftest.
        # MK8 marketplace safety: the ONLY gate modelling adversarial USER BEHAVIOUR rather than
        # adversarial input. This is a contact-only marketplace with no escrow, so a buyer's whole
        # risk sits at the off-platform meet-and-pay step. Three live signals: duplicate/spam
        # listings, price anomalies vs the category median (with a peer-count floor so a thin
        # category is never judged), and copy pressuring payment before inspection - the scam-shaped
        # ask that contradicts the safety guidance the contact step now shows. Integrity-at-zero
        # forward-only. Reads the live DB and SKIPS cleanly when it is down. Self-test: --selftest.
        "id":      "marketplace_fraud_signals",
        "script":  "tools/validate_marketplace_fraud_signals.py",
        "args":    [],
        "label":   "Marketplace fraud signals (MK8: duplicate/spam listings, price anomalies, off-platform payment pressure)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        "id":      "marketplace_deepwalk_classes",
        "script":  "tools/validate_marketplace_deepwalk_classes.py",
        "args":    [],
        "label":   "Marketplace deepwalk class locks (MK1 attributable trust signals / MK2 moderation reason across all 3 surfaces / MK3 public-RPC PII / MK4 watchlist sold-surface / MK7 no dead deep links / MK8 contact-step safety / MK9 computed response SLA / MK10 ranking disclosure)",
        "group":   "AI Validation",
        "report":  None,
    },
    {
        "id":      "reachable_capability",
        "script":  "tools/validate_reachable_capability.py",
        "args":    [],
        "label":   "MK13 - reachable capability: a page that LISTS table T and shows a forward-looking empty state (\"they will appear here\") must have some client path that can INSERT into T, or the empty state is promising a capability the product does not have. Born from the walk: both admin consoles said \"No open disputes\" for a queue no buyer can ever file into, and the same detector then found marketplace_reviews is SELECT-only everywhere - there is no review-submission UI, so a seller cannot currently earn a rating in-product. Views and reviewed server-fed tables (trigger/edge-fn/cron) are allowlisted, since unwritable-from-the-client is legitimate for those. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
    },
    {
        # The SIBLING of reachable_capability, and it exists because that one could not see this.
        # MK13 asks whether an EMPTY STATE promises a capability nothing can produce. It cannot see a
        # REAL control that a full-screen retirement overlay has made unreachable — founder-console.html
        # hid the GCash top-up verify queue, the single control that mints every credit, for ~2 weeks
        # while 5 specs stayed green by calling its handler by hand and ~35 static validators kept
        # passing over its deliberately-preserved markup. Money could not enter the system.
        "id":      "retired_page_sole_control",
        "script":  "tools/validate_retired_page_sole_control.py",
        "args":    [],
        "label":   "Retired-page sole control (retiring a PAGE must not silently delete a capability: "
                   "every write/RPC on an overlay-retired page must also be reachable from a live one; "
                   "forward-only, 2 known strandings printed loudly rather than allowlisted)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # THE BANK'S OWN HONESTY GATE. The live-MCP registry read 343 green / 0 owed and Ian did not
        # believe it; he was right. A green row carried no typed evidence, never expired, and a
        # STRUCTURAL probe ("the page renders") was allowed to satisfy a BEHAVIOURAL oracle ("the
        # number matches its source"). The credits-back chip settled the argument: the surface
        # rendered perfectly while the one number a buyer needs had vanished from every listing.
        # Under this gate the same bank reads 124 green / 240 owed. That is the real starting line.
        "id":      "live_mcp_bank",
        "script":  "tools/validate_live_mcp_bank.py",
        "args":    [],
        "label":   "Live-MCP bank honesty (every non-owed scenario carries typed evidence — kind/ref/"
                   "asserts — and that evidence EXPIRES when a file it depends on changes; forward-only "
                   "ratchet on green, with stale excluded so drift surfaces instead of being absorbed)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # THE EXPIRY RULE ABOVE IS ONLY AS GOOD AS ITS DIGEST, AND THE DIGEST WAS COUNTING PROSE.
        # This bank collapsed four times (752 green -> 34, then 342, ~365, ~320 rows), each read at
        # the time as "shared-library edits are expensive, batch them". They were not. fn_digests v3
        # segments top-level code by counting brackets PER LINE, INSIDE COMMENTS INCLUDED, and this
        # repo's house style names calls in prose. One line -- "// every client routes through getDb(
        # and _timeoutFetch" -- carries an unbalanced paren, glues every following line into a single
        # statement, and vanishes 881 of 881 utils.js keys. 93% of what v3 hashed as that file's
        # "top-level statements" was prose. Writing a SENTENCE ABOUT the code counted as changing it.
        #
        # v4 strips comments (string-aware; and <!-- --> for .html, where the larger half of the bank
        # actually lives) as a NEW VERSION, never a redefinition -- fn_digests_still_hold dispatches
        # on the version each row recorded, because the last unversioned change here expired 661 rows
        # in one run and the ratchet correctly refused it.
        #
        # This test exists because the fix has a converse that is easy to lose and fatal to miss: a
        # v4 that merely stopped expiring would mint FALSE GREENS, which is strictly worse than the
        # over-sensitivity it replaces. So it asserts BOTH directions -- prose expires nothing, real
        # code and real markup edits still expire -- plus version isolation, plus that a narrowed
        # stamp still retains every top-level key (filtering by exercised FUNCTIONS alone silently
        # deleted them once, and a row recording no top-level statement cannot notice a top-level
        # change). It mutates utils.js and marketplace.html and restores them BYTE-for-byte: the
        # ad-hoc probe that found the defect used text mode and converted 4,024 CRLF endings to LF,
        # manufacturing an 18-row phantom regression. Static, offline (~4s).
        "id":      "fn-digest-contract",
        "script":  "tools/test_fn_digest_versions.py",
        "args":    [],
        "label":   "Digest contract (v3 prose defect stays fixed; v4 expires real code AND real markup; "
                   "v3 recordings never reinterpreted; narrowing keeps top-level keys; mutated sources "
                   "restored byte-for-byte)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # THE INSTRUMENT BEHIND 136 OF THAT BANK'S ROWS. Those rows assert things no page can show you
        # — the ledger conserves credits, every grant has a caller-aware policy behind it, a DEFINER
        # helper is not callable by a stranger — and until now each was walked BY HAND, which proves
        # only that it held on the afternoon someone looked. Making each one a QUERY found three real
        # holes on its first honest run: voice transcripts readable by anon (mig 50), a nightly sweep
        # any visitor could fire — it returned 3, three real records expired on demand (mig 51), and
        # the platform's own AI spend counters world-readable (mig 52).
        #
        # It is also why the bank's rows now declare `supabase/migrations` instead of whichever page
        # was open during the walk: a DB claim must expire when a MIGRATION lands, and under the old
        # declaration mig 50 would have expired nothing (gate rule R7).
        # BOLA / BFLA / JWT-not-body / tenant boundary, asked of the SERVER with a real session.
        # It probes as a verified NON-ADMIN, because the standing test account (pabloaguilar) is in
        # marketplace_platform_admins — probing as him showed a "critical" listing takeover that was
        # simply moderation working, since the policy reads
        #   USING ((seller_name IN (SELECT auth_worker_names())) OR is_marketplace_admin())
        # Every write runs inside a rolled-back transaction: the first version of this probe proved a
        # read boundary by writing, and left a live listing titled "TAKEN OVER BY A STRANGER" with no
        # recoverable original.
        "id":      "identity_boundaries",
        "script":  "tools/verify_identity_boundaries.py",
        "args":    [],
        "label":   "Identity boundaries (another person's draft is invisible; their listing is "
                   "unwritable; a forged seller_name in the body is refused; an admin-gated function "
                   "is refused at the server — probed as a verified non-admin, all writes rolled back)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,          # needs the local database and gateway up
    },
    {
        # THE MONEY LIFECYCLE. Registered the day a commission was found debiting the ledger and never
        # retiring the credits, so `issued_credits` published a supply 360.00 larger than the credits
        # that existed. That defect lived on the DB side of every screen, which is why it survived
        # every hand-walk: the page showed a balance, and the claim was about what the ledger did.
        # Every probe that writes runs inside a single psql call ending in rollback.
        "id":      "money_lifecycle",
        "script":  "tools/verify_money_lifecycle.py",
        "args":    [],
        "label":   "The money lifecycle asked of the database (a verified top-up mints exactly once "
                   "and an unverified one mints nothing; a verification cannot be undone by UPDATE; "
                   "commission is paired with retirement; credits cover at most the knob's share of a "
                   "purchase and a spend AT the cap is still accepted; a job earns or spends, never "
                   "both; credits cannot be moved between accounts and there is no cash-out function; "
                   "no account is overdrawn; an auto-confirmed payment never also names a human)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,          # needs the local database up
    },
    {
        "id":      "layer_invariants",
        "script":  "tools/verify_layer_invariants.py",
        "args":    [],
        "label":   "Layer + seam invariants asserted against the live system (ledger conserves against "
                   "the treasury; every grant has a caller-aware policy; DEFINER cron helpers are not "
                   "user-callable; realtime publishes nothing RLS-free; NULL keeps its meaning across "
                   "the client seam; pg_cron is not allowed more jobs than there are workers)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,          # needs the local database up
    },
    {
        # The READ-side sibling of client_write_grants, and it exists because three gates each asked
        # a neighbouring question and left this one uncovered. credit_treasury — one row holding the
        # platform's whole money position — was granted SELECT to anon AND authenticated under
        # `using (id = 1)`, a predicate that picks a row without ever checking a person. rls_coverage
        # classifies by TENANT COLUMN and this table has none; the rls_open_policy flywheel check
        # greps migration text for `USING (true)` and this is not that string; write_grants asks who
        # can WRITE. Nobody wrote. The leak was a read, and every gate passed.
        "id":      "public_read_surface",
        "script":  "tools/validate_public_read_surface.py",
        "args":    [],
        "label":   "Public read surface (every table a client can SELECT must either consult the "
                   "caller, inherit scoping through a subquery, deny by default, or be DECLARED "
                   "public with a reason; reads the LIVE catalogue, not migration text)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        "id":      "post_action_coherence",
        "script":  "tools/validate_post_action_coherence.py",
        "args":    [],
        "label":   "MK12 · post-action coherence — a handler that writes and then tells the user it SUCCEEDED must also re-derive the surfaces it just invalidated, or the page contradicts its own receipt. Born from the walk: saving a marketplace search toasted \"Search saved.\" while the counter beside it still read 0 until a full reload, because the handler refreshed the sheet but never called updateSavedSearchBadge(), which already existed. Deliberately tolerant, since a gate that cries wolf on correct code gets ignored: an OPTIMISTIC refresh made BEFORE the write counts (the watchlist toggle updates the heart, then writes, then confirms — better than refreshing after), a degraded/queued notice (\"saved offline, will sync\") is not a commit receipt, and a handler that navigates away or is realtime-backed is exempt. All three shapes were live findings pinned as self-test cases. Forward-only, currently 0. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "error_remedy_actionable",
        "script":  "tools/validate_error_remedy_actionable.py",
        "args":    [],
        "label":   "MK11 · error-remedy actionability — a catch around a client WRITE (insert/upsert/update/delete/rpc/functions.invoke) that tells the user to \"try again\" must FIRST branch on the auth/permission case, because a 42501/401 means the session is gone and retrying reproduces the failure exactly. Born from the walk, not a reading list: the 2026-07-24 deepwalk hit this shape four independent times (buyer inquiry, platform-actions, founder-console, saved-search save) — on the inquiry step the user had already typed a phone number before being told to retry something that could never work. Standard: nngroup.com/articles/error-message-guidelines (\"context and potential remedies\", \"instructions on how to resolve\"). The branch is centralized as window.whIsAuthFailure / whWriteError in utils.js, and the detector accepts either the helper or an inline signature test, so adopting the helper never reads as a regression. Forward-only; 12 -> 2 on the seeding sweep. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "hive_deepwalk_ratchet",
        "script":  "validate_hive_deepwalk.py",
        "args":    [],
        "label":   "Hive deepwalk ANTI-DRIFT ratchet (HIVE_DEEPWALK_EXPANSION_ROADMAP.md §4) — the measured %-board (14 journeys x 5 phases G/W/O/H/R, HK classes x 6 stages) held as a forward-only FLOOR, so a cell that was walked/observed/resolved/locked cannot silently revert. Computed from hive_deepwalk_state.json, never asserted in prose. Carries the shallow_W guard: a journey cannot claim W=done without >=2 personas AND >=2 states recorded, because without it 'walked' degrades into 'opened the page once as myself' — the exact shallowness this arc exists to kill (it caught over-crediting twice on the marketplace board). `--accept` ratchets the floor up after real progress. Static/fast. Self-test: --selftest.",
        "group":   "AI Validation",
        "report":  None,
    },
    {
        "id":      "corrective_definition_parity",
        "script":  "tools/validate_corrective_definition_parity.py",
        "args":    [],
        "label":   "LG2 · corrective-definition parity — one derived semantic must not carry three definitions. 'Corrective' is expressed three ways: v_logbook_truth.is_corrective is a REGEX, v_asset_truth.last_failure_at and the five analytics RPCs (get_mtbf / get_mttr / failure_frequency / downtime_pareto / repeat_failures) use the EXACT string 'Breakdown / Corrective', and trigger-ml-retrain uses ILIKE. They agree today only because every corrective row happens to use the exact string (1,146 = 1,146 = 1,146) — luck of vocabulary, not a guarantee. Add one entry typed 'Emergency Breakdown' and is_corrective counts it while last_failure_at and EVERY MTBF/MTTR/failure-frequency KPI silently miss it, so the asset reads as MORE reliable than it is, which is the direction that gets someone hurt. Collapsing the three into one definition means editing a view, five RPCs and an edge function that all feed KPIs a plant would act on, so this takes the middle disposition instead: the duplicate representations are allowed, and divergence is made impossible-then-DETECTABLE as a fix-to-ZERO ratchet caught at CI on the first divergent row. Live-tier, skips cleanly without docker. Teeth proven by inserting a divergent value (FAIL, names the offending vocabulary) and removing it (PASS). Self-test: --selftest.",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        "id":      "offline_queue_confirm",
        "script":  "tools/validate_offline_queue_confirm.py",
        "args":    [],
        "label":   "LG3 · offline-queue drain confirmation — a queued write that changed 0 ROWS must never be reported as synced. A PostgREST update/delete matching nothing is not an error (supabase-js returns error:null, status 204), so every drain's `if (!error)` success test treated 'wrote nowhere' as 'written': it deleted the queued item and toasted success. Walked live 2026-07-28 (LB7): a tech edits an entry offline, the entry is deleted server-side, and on reconnect the app says '1 offline change synced.' while the text is destroyed. Zero rows is the NORMAL outcome under RLS — logbook's UPDATE policy is owner-scoped on auth_uid while SELECT is hive-scoped, so a worker can see entries the database will never let them edit. The shared helper carries the same shape to 6 more surfaces (community_posts, schedule_items, inventory_items, pm_completions, rcm_fmea_modes, skill_profiles). Invariant: inside a drain, an update/delete whose success path removes the queued item must .select(...) the affected rows AND gate the removal on receiving one. Scoped to drain functions on purpose — a .update() elsewhere has a human watching it. Teeth proven by reverting: FAILs on the real pre-fix code at all 3 sites. Static/fast. Self-test: --selftest (pins the pre-fix and the looks-right-but-ignores-the-rows shapes as must-fail fixtures).",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "pm_ontime_vs_compliance",
        "script":  "tools/validate_pm_ontime_vs_compliance.py",
        "args":    [],
        "label":   "PMK1 · on-time vs compliance — a PM completed LATE still counts as compliant, so the headline can flatter the program to the person least able to check it. Walked live 2026-07-28 as two personas in two hives: the page reads '0 of 31 on track now · 88% PM compliance (SMRP)' for a supervisor with 20 overdue, and '3 of 30 on track · 86%' for a worker with 24 overdue. Measured at the DB, which explains how both are true at once: 331 of 1,224 consecutive-completion intervals (27.0%) ran past frequency_days, 14.5% past 1.5x, and get_pm_compliance_smrp counts every one. Currently compliance 86.3% vs on-time 73.0% — a 13.3-point gap. Deliberately does NOT redefine the RPC: it implements a NAMED standard (SMRP 2.1.1) with verified analytics parity, so changing it silently would break a documented contract and move a number a plant acts on. Instead it holds the GAP as a forward-only ratchet, so the day delivery drifts further from on-time the build fails before anyone reads a healthy percentage and relaxes. Standard harvested on a genuine bag miss (the external corpus held 144 chunks and none on maintenance): substrate/external/external-pm-schedule-compliance-metric.md, which states the formula, the 90% world-class benchmark and the explicit late-PM blind spot. Live-tier, skips cleanly without docker. Teeth proven by tightening the ceiling. Self-test: --selftest.",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        "id":      "source_chip_freshness",
        "script":  "tools/validate_source_chip_freshness.py",
        "args":    [],
        "label":   "PM5 · a saved copy must not claim to be live — the source chip is the platform's provenance UI, so reporting freshness is its only job and overstating it is worse than having no chip. Walked 2026-07-28: analytics.html renders analytics_snapshots (the first view of the PHT day computes and saves; every later view replays the saved copy and only Refresh recomputes — a deliberate, good feature) while the chip hardcoded 'Live recomputation each refresh' on EVERY load. Measured: the KPI numbers were on screen at 0ms, up to ~24h old, under a chip promising they were live. For this arc's journey that means a technician completes a PM, opens analytics, sees compliance unmoved, and nothing on the page says the figure predates their work. The existing 'Source-chip truth' dimension in canonical_status.py checks that a chip names views the page actually READS and says nothing about the freshness CLAIM, which is how this shipped green. Asserts: any page that reads a *_snapshots / *_cache table must COMPUTE its freshness string rather than hardcode a liveness claim; pages with no cache path may keep a literal, because for them it is true. Static/fast. Teeth proven by restoring the hardcoded claim (exit 1). Self-test pins the pre-fix shape as must-detect, the computed fix as must-not-flag, and a cache-free page as must-not-flag.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "pm_frequency_mapping",
        "script":  "tools/validate_pm_frequency_mapping.py",
        "args":    [],
        "label":   "PM08 · one interval-to-frequency mapping, never rarer than asked — a PM's frequency is a WORD in the database and the schedule is DERIVED from that word by a CASE in v_pm_scope_items_truth, so every writer converting an interval in DAYS into that word is deciding the real schedule. Walked 2026-07-28: integrations.html (the CMMS/CSV import a plant uses to onboard its existing program) carried a local map with NO Daily bucket, taking the first bucket >= days over [7,30,90,180,365] — measured, a 1-day interval became 'Weekly' (7x rarer than the source system asked), 14 became 'Monthly' (2.1x), 45 became 'Quarterly' (2x). Every drift ran the SAME direction: less often than specified, which is the direction that leaves equipment un-inspected. asset-hub.html rounded to the NEAREST bucket instead, so a 300-day RCM interval became 'Annual' (365). Fixed with ONE shared mapping (whFreqFromDays/whFreqDays in utils.js) that snaps DOWN — rounding to a shorter interval costs labour, rounding to a longer one is a safety decision. Asserts three things: PARITY (utils.js day-values equal the view's frequency_days CASE label-for-label, including the biweekly/fortnightly synonyms the UI's canonFreq resolves to 7 while the view says 14 — latent today, since no such rows exist, and pinned here so it stays impossible-then-detectable like the logbook arc's 'corrective' vocabulary); SAFE DIRECTION (no interval 1..400 maps to a longer period); NO PRIVATE COPIES (neither writer reintroduces its own bucket list). Parity is live-tier and skips cleanly without docker; the rest is static. Teeth proven by restoring the private map: exit 1. Self-test: --selftest pins the bucket-list shape as must-match and a non-frequency numeric array as must-not.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "workflow_states_present",
        "script":  "tools/validate_workflow_states_present.py",
        "args":    [],
        "label":   "AHK3 - a workflow state with no rows is a state nobody has walked, and the seeder is part of the test surface. The Asset Hub arc hit this THREE times for three different reasons: asset_nodes had 95 rows ALL status='approved' with 0 auth_uid (assets.py computed the author, asset_brain.py dropped it in the hand-off and hardcoded the status) - which is why the PDDA arc's F21 sat undiagnosed and AH3's authority hole hid behind the same gap; rcm_strategies was 172 approved / 0 unapproved (reliability.py set approved_at unconditionally while the fmea rows twelve lines above already branched), so pushStrategyToPm's REFUSAL had never once run; and weibull_fits had 91 fits and 0 'insufficient_data', so the state that tells a planner NOT to act on a number had never been rendered. Holds SEVEN states open (asset pending/rejected/authored/cold-start, strategy unapproved/pushed, weibull insufficient_data) - the cold-start one added by AH1, where 0 of 79 approved assets lacked a Weibull fit because reliability.py fitted every node unconditionally, so the state every newly-commissioned machine and every new customer is in had never been rendered. Demands REPRESENTATION, not a ratio - the point is that the next walk has something to walk. Teeth proven by emptying one state: exit 1. Live-tier, skips without docker. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "schedule_health_falsifiable",
        "script":  "tools/validate_schedule_health_falsifiable.py",
        "args":    [],
        "label":   "PJK2 - a number that decides what may slip, or what a CLIENT is told, must be falsifiable. Half of what this gate holds is that the ENGINE IS GOOD, asserted so nobody 'simplifies' it away: prescriptive.py cites PMBOK 7 §6.5.2.2 + AACE 24R-03 and uses networkx.dag_longest_path() rather than hand-rolled graph code (its own docstring records that the PREVIOUS hand-rolled version silently miscomputed cycles), and diagnostic.py cites PMBOK 7 + AACE RP 80R-13, states every EVM formula, attributes the green/amber/red bands and returns {available:False, reason:...} rather than guessing. THE DEFECTS IT LOCKS OUT: (1) TWO IMPLEMENTATIONS - clientRollup re-computed EVM in the browser, uncited, and had already diverged by rounding pct_complete to an integer where the engine keeps the float, moving EV by up to 0.5% of BAC (about PHP 9,250 on a PHP 1,850,000 project) and being the number a supervisor saw whenever the edge fn had not answered; deleted, not patched, because a cost figure that silently disagrees with the cited engine is worse than none. (2) AN ABSENCE RENDERED AS A VERDICT - renderCpm defaulted to an empty critical path when the rollup was unavailable, so every task drew as NON-critical with ZERO slack, a positive and self-contradictory answer since zero slack is normally what MAKES a task critical; renderBudget likewise told a supervisor to 'add a budget, start date and end date' when all three already existed. Also asserts the EVM contract is registered partial_variant with a partial_reason admitting AC is an hours x rate PROXY (no cost ledger; the rate defaults to PHP 200/hr and measured, no caller passes the override). NOTE: this gate STRIPS COMMENTS before hunting the deleted implementation - its own first run failed because the comment RECORDING the removal quotes the removed code, the third comment-vs-code scanner bug found in one session. Teeth proven by reinstating the magic rate in code: FAIL.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "project_authority",
        "script":  "tools/validate_project_authority.py",
        "args":    [],
        "label":   "PJK3 - authority is enforced where the DATA is, not in the renderer. project-manager.html carried three claims only its renderer believed, each probed live as an ordinary worker and each true of the screen and false of the database: renderBudget printed 'Budget visibility is restricted to supervisors' while projects_hive_rw granted every member SELECT (a worker read CAP-2026-001's PHP 1,850,000 off the table, and budget_php was in the MAIN list select for everyone so the figure reached the browser before any pane decided to show it); the Delete button had no role check and neither did the DB, so a worker soft-deleted a shutdown project they did not own while hive_audit_log held ZERO project rows; and ackLog wrote acknowledged_by = WORKER_NAME with no role check, so any member could acknowledge any progress report including their own. A UI-only gate is not a control, it is a label. This gate asserts each is now enforced in the database. IT CHECKS MECHANISMS, NOT NAMES - the budget one is enforced by COLUMN PRIVILEGES and a column-level REVOKE is a NO-OP while a table-wide GRANT stands, which is exactly how the first attempt failed silently with information_schema still listing authenticated on budget_php while the page looked fixed. So it asks the CATALOG 'does authenticated hold SELECT on budget_php' rather than grepping a migration for the word REVOKE. Also holds: budget_php absent from v_project_truth (security_invoker, so re-adding it re-opens the read AND breaks every select('*') caller), the supervisor-only RPC still exists, and the three guard triggers are attached and NOT disabled (tgenabled <> 'D' - a disabled trigger looks present and enforces nothing). Teeth proven by re-granting the column: FAIL with the no-op warning inline.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "change_order_immutability",
        "script":  "tools/validate_change_order_immutability.py",
        "args":    [],
        "label":   "PJK1 - a raised change order is a CONTRACT, not a draft. project_change_orders carries cost_impact_php and schedule_impact_days, so approving one commits money. The approval ACT was already guarded (wh_guard_supervisor_approval refuses a non-supervisor approving, rejecting, or editing an APPROVED order - I asserted otherwise from the policy layer and the walk refuted me), but nothing protected the CONTENT or EXISTENCE of a request awaiting review. Proven live as an ordinary worker: rewrote ANOTHER worker's pending order from PHP 500,000 to PHP 9,999,999 and replaced its scope text, with the row still reading requested_by = Wilfredo Malabanan; the same worker could DELETE a pending order outright. That is the worst place for it to be open, because the supervisor approves WHAT THEY ARE SHOWN and what they are shown was editable by anyone in the hive right up to the click - and with no auth_uid on the table and no audit trigger on projects, nothing recorded that the figure changed or who changed it. The guard is IMMUTABILITY rather than a role check, chosen after measuring the legitimate callers: exactly THREE update paths exist (approveCO/rejectCO/cancelCO), all setting status plus approver fields, with NO edit-CO path anywhere and NO delete path in any page or edge fn - so the terms were already write-once in practice and making the database agree breaks zero callers. Holds: the function and trigger exist and the trigger still covers UPDATE **and DELETE** (losing DELETE silently restores the make-it-disappear path); every commercial term is still named in the check (a term dropped from that list becomes quietly editable again, which is exactly the failure found); status/approved_by/approved_at/rejection_reason are NOT frozen, because freezing them would break the lifecycle the table exists for; and LIVE that the trigger is attached and ENABLED (a disabled trigger looks present and enforces nothing). Teeth proven by unfreezing cost_impact_php: FAIL on exactly that term.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "project_tenancy",
        "script":  "tools/validate_project_tenancy.py",
        "args":    [],
        "label":   "PJK4 - a project child row's PARENT must live in its own hive. EARNED BY PROBING, not assumed from the AHK4 analogy: reads were measured clean first (as a member of one hive, projects/project_items/project_change_orders all return 0 rows for another hive - recorded as a real result), then the write side was probed with MY hive_id and ANOTHER hive's project_id and all three were ACCEPTED - project_items, project_progress_logs, and a project_change_order attached to a project the writer cannot even see. Every policy is a single PERMISSIVE FOR ALL testing only hive_id IN user_hive_ids(); nothing joined `projects`. AN INSTRUMENT NOTE: the first probes failed with 23514 (a status enum I got wrong) and 23502 (a NOT NULL I omitted), neither of which is 42501, and taking either as 'isolation holds' would have recorded a false clean - the same trap the AH13 walk hit. SEVERITY MEASURED AND HONESTLY CONTAINED: v_project_truth's rollup subqueries (item_count, estimated_total_hours, approved_change_orders, approved_co_cost_php, link_count) carry NO hive filter, and what stops an injected row reaching the VICTIM's numbers is that the view is security_invoker, so those subqueries run as the READER and RLS hides the foreign row - proven by injecting an item with 999 estimated hours and watching the victim's rollup stay at 7 items / 33.00 est hrs. FIXED ANYWAY because that containment rests entirely on security_invoker staying ON, and earlier the SAME DAY a routine CREATE OR REPLACE silently cleared that option from v_sensor_truth (CREATE VIEW does not carry reloptions forward) - one such slip on v_project_truth turns every unfiltered rollup into a cross-tenant read. Mig ...025 adds five RESTRICTIVE parent-hive policies; 0 existing rows violated them, so nothing that exists was rejected. Holds each policy's existence, RESTRICTIVE-ness (a PERMISSIVE rewrite ORs and would WIDEN while looking like a guard) and that it still JOINS `projects` to compare hive_id, plus a live cross-boundary row scan since WITH CHECK never applies retroactively. Teeth proven by dropping a policy: FAIL on exactly that table.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "reliability_tenancy",
        "script":  "tools/validate_reliability_tenancy.py",
        "args":    [],
        "label":   "AHK4 - reliability data is hive-private, PARENT included. FMEA modes, RCM strategies, Weibull fits and P-F intervals are competitive plant knowledge: what breaks, how often, and what a plant does about it. The AH13 walk found reads correctly isolated (0 rows across all four tables read as a member of another hive - recorded as a real result, not assumed) and WRITES carrying the PM13 gap: the WITH CHECK validated that hive_id is one the caller belongs to and said NOTHING about whether the PARENT lived there. Probed live, both accepted - an FMEA mode with hive_id=MINE and asset_id=ANOTHER hive's node, and a strategy with hive_id=MINE and fmea_mode_id=THEIRS. An instrument error nearly recorded that walk as clean: the first probe came back BLOCKED with 23514 and it looked like isolation holding, but 23514 is check_violation, not 42501 - the decision-enum CHECK rejecting an invalid value of the probe's OWN making, with the tenancy question still untested. Verify WHAT blocked a write, never merely THAT something did. Migration ...017 closed it with four RESTRICTIVE policies; this gate keeps them closed. It asserts each policy EXISTS, is RESTRICTIVE (a PERMISSIVE rewrite ORs with the others and WIDENS access while looking like a guard - a gate checking only 'a policy by this name exists' would pass that happily), and still JOINS the parent table to compare its hive rather than the row's own. Plus a live scan for rows that already cross a boundary, because WITH CHECK never applies retroactively - a guard added over existing violations would silently keep them. Teeth proven three ways: policy dropped -> FAIL, rewritten PERMISSIVE -> FAIL, weakened to own-hive-only -> FAIL, each with the right diagnosis.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "asset_identity_spine",
        "script":  "tools/validate_asset_identity_spine.py",
        "args":    [],
        "label":   "AH11 - a rename must carry the WHOLE identity, and only inside ONE hive. An asset's identity is stored as free text in five tables and sync_pm_asset_identity propagated a rename into exactly one: measured live, renaming GEN-002 moved 2 pm_assets rows and left 116 others pointing at a tag that no longer existed (103 logbook.machine, 12 fault_knowledge.machine, 1 asset_risk_scores). Every one of those columns holds the TAG even where the column is NAMED asset_name, so a display-name change is harmless and a TAG change is what breaks them. fault_knowledge has NO uuid column at all, so a rename severed the AI's learned fault corpus permanently; asset_risk_scores is worse still, because the asset page then renders 'No risk score yet for this asset... a score will appear here' - honest about a cold start, a lie about a rename. THE SECOND DEFECT WAS INTRODUCED BY THE FIX and is the reason this gate is per-statement: the first draft scoped its UPDATEs to 'any hive the caller belongs to', and tags are unique per HIVE not per platform, so renaming Lucena's GEN-002 also rewrote Manila Electronics Assembly's 60 logbook rows, 6 fault_knowledge rows, its risk score, a parts recommendation and a pm_asset. A cross-tenant write caused by the repair; found on the revert leg, repaired to 0 residual. Holds: every identity column is still updated by the RPC (a NEW table denormalising a tag goes red here and nowhere else), and EACH UPDATE carries BOTH hive_id = v_hive AND the caller's membership - v_hive alone would trust a tag from any tenant, membership alone IS the cross-tenant bug. Also that the merge guard exists and excludes the node being renamed (without that it refuses every rename, since callers update asset_nodes first), and that the caller passes the node id and surfaces the refusal. Teeth: the FIRST version of this gate counted '= v_hive' occurrences globally and PASSED with the bug reintroduced - it now slices the migration per UPDATE, and deleting one predicate fails exactly that statement. Live tier reports orphan tags (a row naming a tag no asset in its hive carries) - 77 pre-existing, 72 of them the logbook rows that have no asset_node_id to fall back on.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "fmea_priority_order",
        "script":  "tools/validate_fmea_priority_order.py",
        "args":    [],
        "label":   "AH7 - a severity-9 failure mode must never be buried by RPN. The RPN arithmetic was already sound (rpn is a GENERATED ALWAYS column S x O x D, inputs CHECK-bounded 1..10, 0 of 300 rows disagreeing) - the defect was what the page DID with it: every FMEA surface ordered by rpn DESC alone, and because RPN multiplies severity by how RARE and how DETECTABLE a failure is, a rare easily-caught SAFETY failure scores below a frequent nuisance. Measured: all 17 modes with severity >= 9 sat below the median RPN, and 'Cable insulation breakdown' (S9, safety, RPN 108) ranked BELOW 'Coupling misalignment beyond 0.05 mm' (S6, production, RPN 180) on every asset page and every printed report - a report whose own header cites AIAG-VDA 2019, the standard that replaced RPN precisely because of this. canonical/standards.json had already recorded the caveat; the UI sorted by RPN anyway. Fixed with an Action Priority band (severity >= 9 or RPN >= 200 -> H; severity >= 7 or RPN >= 100 -> M) that only ever RAISES priority, so nothing urgent today is quietly demoted, registered as a PARTIAL formula variant because it is the severity escalation both IEC 60812:2018 and AIAG-VDA agree on and NOT the full ~1000-cell AP lookup - inventing that table's contents would defeat the point of an auditable contract. Holds: the helpers exist, BOTH the screen and the printed report order through the same function (they must not disagree about which failure matters most), the report still explains why it is not in RPN order, and LIVE that rpn is still generated and S/O/D still bounded 1..10 - deliberately NOT 'sort by our own rule then assert our own rule', which can never fail. Teeth proven twice: reverting the report to rpn order -> FAIL, dropping the severity CHECK -> FAIL. Self-test pins the exact real pair above.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "refusal_reason_persists",
        "script":  "tools/validate_refusal_reason_persists.py",
        "args":    [],
        "label":   "AHK2 - when a reliability calculation REFUSES, the reason must outlive the click. python-api/reliability/weibull.py declines below MIN_FAILURES_FOR_FIT=4 and returns beta/eta NULL with an actionable diagnostic ('Need at least 4 corrective events in the lookback window (have 2). Log more breakdowns or widen since_days before refitting.') - that sentence is the entire product of the refusal, telling a planner why there is no number and how to get one. But weibull_fits had NO diagnostic column, so persistFit never wrote it, v_weibull_truth could not expose it, and loadLatestWeibull selected a column set that could not contain it: fit.diagnostic was undefined and the box was cleared. Visible for seconds after Compute, BLANK on every page load after. A planner opening the asset the next day saw beta '--', eta '--', a pill reading 'insufficient data', and an empty bordered box - the F18 dead-card shape landing on the most important sentence in the reliability workbench. Fixed by 20260728000014 plus the fitter writing it and the page selecting it on the LOAD path; verified live end-to-end. Holds the whole round-trip (column, view exposure, the view still returning the LATEST fit per asset via its DISTINCT ON, the fitter persisting, the page selecting, and every refused fit actually carrying a reason) because breaking ANY link restores the silent blank. Teeth proven twice: reverting the page select -> exit 1, dropping the column -> exit 1. Live-tier, skips without docker. Self-test: --selftest.",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        "id":      "approval_authority",
        "script":  "tools/validate_approval_authority.py",
        "args":    [],
        "label":   "AHK1 - approving and REJECTING are the same authority. wh_guard_supervisor_approval correctly refused a non-supervisor who APPROVED, but its UPDATE clause treated a status change as privileged only when 'approved' was on one side, so pending -> rejected slipped through on ALL SIX tables the trigger guards (asset_nodes, inventory_items, logbook, project_change_orders, rcm_fmea_modes, rcm_strategies). Walked live 2026-07-28 once the Asset Hub governance fixture existed to walk at all: a WORKER set their own pending asset to 'rejected' and wrote rejection_reason = 'Rejected by the supervisor - not fit for the register.' - 1 row, no error. Reachable rather than theoretical: asset-hub's reject is caught only incidentally because it also writes approved_by/approved_at, while hive.html's rejectItem() updates { status:'rejected' } ALONE behind a client-side role check. WHY THE REASON FIELD MATTERS: rejection_reason is the REVIEWER'S VOICE - the queue renders it back to the submitter as 'Why: ...' - so a submitter who can write it authors a verdict in a supervisor's name, and the next supervisor cannot tell. Fixed by 20260728000013 (reviewer_states + a rejection_reason clause); safe to tighten because both legitimate reject paths are already supervisor-only in their UI and service_role is exempt. Asserts the guard STATICALLY (both outcomes + the reason field still privileged) and LIVE in a rolled-back probe (worker self-reject blocked, reason-edit blocked, supervisor still able to reject). Teeth proven against the REAL pre-fix guard: 3 of 4 checks fail. Skips cleanly without docker or a worker-authored pending row. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
    },
    {
        "id":      "project_manager_deepwalk_ratchet",
        "script":  "validate_project_manager_deepwalk.py",
        "args":    [],
        "label":   "Project Manager deepwalk expansion - forward-only %-board over 18 journeys x 5 phases + the PJK dimension classes, with the shallow-W guard (a journey may not be credited W=done on fewer than 2 personas AND 2 states). Opened 2026-07-28 after the Asset Hub arc closed at 100%; project-manager was chosen on measured evidence - the WRITE-HEAVIEST surface on the platform (21 client writes across 7 tables: 9 insert / 10 update / 2 delete), 68 interactive elements, 96 top-level functions, and the page where the platform handles MONEY and COMMITMENTS (a change order is a contract amendment, an Earned Value status is a health claim to a client, a critical path decides which work may slip). SIX GROUND FINDINGS the board exists to drive out, all measured before any journey: (G1) six of seven project tables have NO auth_uid column AT ALL - only `projects` has one - so approving a change order is attributable to nobody; (G2) `projects` appears nowhere in hive_audit_log.target_type while assets/logbook/inventory_items/marketplace/worker_profiles all do, so the write-heaviest domain has no tamper-evident trail; (G3) every child table validates only its OWN hive_id and no policy joins `projects`, which is the PM13/AHK4 child-parent gap un-probed; (G4) one PERMISSIVE FOR ALL policy per table means any active member can approve/reject/cancel a change order, and project_roles is the ONLY table with a supervisor predicate; (G5) project_change_orders = 0 rows and project_roles = 0 rows, so the entire CO approve/reject path and the role flow have never had data (the AHK3 class); (G6) renderBudget hides the budget from non-supervisors in the RENDERER while projects_hive_rw grants every member read, so the number is one db.from('projects') away. PJK4 is in the denominator from day one as a CANDIDATE precisely because the Asset Hub board read 100% with its fourth class untracked. Fails on a REGRESSION below the accepted baseline. Self-test: --selftest.",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        "id":      "asset_hub_deepwalk_ratchet",
        "script":  "validate_asset_hub_deepwalk.py",
        "args":    [],
        "label":   "Asset Hub deepwalk expansion - forward-only %-board over 18 journeys x 5 phases + the AHK dimension classes, with the shallow-W guard (a journey may not be credited W=done on fewer than 2 personas AND 2 states). Opened 2026-07-28 after the PM Scheduler arc closed at 100%; Asset Hub was chosen on measured evidence - the widest truth-view surface on the platform (11), 11 DB writes, the asset IDENTITY spine every other page reads, and TWO defects the PM arc found in it independently (an RCM interval rounded to a rarer frequency; a lazy pm_assets create with no role gate). THE GROUND FINDING the board exists to drive out: the page's whole governance workflow is UNWALKABLE - asset_nodes has 95 rows, all seeder-created with auth_uid NULL, all status='approved', ZERO pending, ZERO rejected, zero authored by any worker or supervisor, and rcm_strategies is 172 approved / 0 unapproved. That is why the PDDA arc's F21 (a worker's Pending-assets tile always reads 0) was never diagnosed: there has never been a pending asset to see. Plus 0 audit triggers across asset_nodes / rcm_strategies / rcm_fmea_modes (567 rows). Fails on a REGRESSION below the accepted baseline, so a walked cell cannot silently revert. Self-test: --selftest (pins the scoring and the shallow-W refusal).",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        "id":      "pm_deepwalk_ratchet",
        "script":  "validate_pm_deepwalk.py",
        "args":    [],
        "label":   "PM Scheduler deepwalk ANTI-DRIFT ratchet (PM_DEEPWALK_EXPANSION_ROADMAP.md §4) — the measured %-board (18 journeys x 5 phases G/W/O/H/R, PMK classes x 6 stages) held as a forward-only FLOOR, so a cell that was walked/observed/resolved/locked cannot silently revert. Computed from pm_deepwalk_state.json, never asserted in prose. Carries the shallow_W guard: a journey cannot claim W=done without >=2 personas AND >=2 states, which matters more here than anywhere yet — the PDDA arc NAMED the supervisor-plans/tech-completes split as its heavyweight and then walked it as one signed-in user, and this arc's keystone (27% of PM intervals ran late while the compliance RPC reports 85-87%) is invisible to any single-persona glance. `--accept` ratchets after real progress. Static/fast. Self-test: --selftest.",
        "group":   "AI Validation",
        "report":  None,
    },
    {
        "id":      "logbook_deepwalk_ratchet",
        "script":  "validate_logbook_deepwalk.py",
        "args":    [],
        "label":   "Logbook deepwalk ANTI-DRIFT ratchet (LOGBOOK_DEEPWALK_EXPANSION_ROADMAP.md §4) — the measured %-board (20 journeys x 5 phases G/W/O/H/R, LG classes x 6 stages) held as a forward-only FLOOR, so a cell that was walked/observed/resolved/locked cannot silently revert. Computed from logbook_deepwalk_state.json, never asserted in prose. Carries the shallow_W guard: a journey cannot claim W=done without >=2 personas AND >=2 states recorded — the logbook is the platform's central WRITE surface (v_logbook_truth feeds ~11 pages), so a one-persona 'walk' here is exactly the shallowness that let the offline queue, the edit-others boundary and amendment propagation go unwalked for an entire prior arc. `--accept` ratchets the floor up after real progress. Static/fast. Self-test: --selftest.",
        "group":   "AI Validation",
        "report":  None,
    },
    {
        "id":      "marketplace_deepwalk_ratchet",
        "script":  "validate_marketplace_deepwalk.py",
        "args":    [],
        "label":   "Marketplace deepwalk ANTI-DRIFT ratchet — the measured %-board (20 journeys x 5 phases, 10 MK classes x 6 stages) held as a forward-only FLOOR: a cell that was walked/observed/resolved/locked cannot silently revert. Lives at the repo root under this exact name because the flywheel orchestrator classifies a baseline rise by re-running `validate_<name>.py`; without it, every legitimate rise in the locked-cell count fell into the conservative 'unknown' bucket and was scored as ROT rather than as the adoption floor moving up (77 -> 84 -> 92 in one session). Delegates to tools/marketplace_deepwalk_scoreboard.py, which fails only when the board drops BELOW its accepted baseline; `--accept` ratchets.",
        "group":   "AI Validation",
        "report":  None,
    },
    {
        "id":      "marketplace_partsflow_continuity",
        "script":  "tools/validate_marketplace_partsflow_continuity.py",
        "args":    [],
        "label":   "Marketplace parts-flow continuity (MK6) — locks the inventory <-> marketplace ROUND TRIP that the 2026-07-24 deepwalk walked clean in both directions: (1) inventory emits a `from_inventory` Sell deep link AND marketplace READS it to prefill (a link nobody reads is a dead end); (2) buyer search matches `part_number`, the strong join key, because inventory is material-centric while listings are equipment-centric so their categories diverge and category alone can never match a part; (3) the listing detail routes back into inventory's own ledger-consistent receive path (`receive=1`); (4) LIVE check that `source_inventory_item_id` stays BASE-only and is never projected through v_marketplace_listings_truth, since it is one tenant's internal inventory id and would leak tenant topology to buyers. A clean walk is a real result but not a durable one — this is what makes it stay true. MK6.4 needs the DB and skips cleanly without it; the rest are static. Self-test: --selftest.",
        "group":   "AI Validation",
        "report":  None,
    },
    {
        "id":      "hidden_class_defined",
        "script":  "tools/validate_hidden_class_defined.py",
        "args":    [],
        "label":   "`.hidden` is actually DEFINED for every page that uses it — a page hiding an element with class=\"hidden\" must load a stylesheet carrying a GENERAL `.hidden` rule, or the element ships permanently VISIBLE. Found live 2026-07-24 (deepwalk J9, first-time-seller dashboard): a dead \"Load More\" button under an empty inquiry list, because marketplace-seller.html links only tokens.css and the JS toggled a class nothing defined. Six live pages were in that state (asset-hub / audit-log / community / marketplace-admin / marketplace-seller / shift-brain). Easy to ship because wh-tw.css DOES define it (so the pattern works on most pages), because components.css's rule is SCOPED to `.action-card .ac-cta.hidden` and grep makes it look covered, and because an ID base style like `#toast{display:flex}` outranks the class anyway. The gate resolves it the way the browser does: only a selector that is exactly `.hidden` counts. Design prototypes (*-test.html) and *.backup*.html are exempt (not shipped, not in the SW shell). Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
    },
    {
        # HIVE DEEPWALK · HK1 detector — a role marker must not outlive the role.
        "id":      "role_marker_revocation",
        "script":  "tools/validate_role_marker_revocation.py",
        "args":    [],
        "label":   "A role-derived class on a PERSISTENT ROOT (<html>/<body>) must be removable — if a page adds one, it must also remove it on the path where the role is lost. Found live 2026-07-27 (hive deepwalk H8, remove-member): hive.html painted `html.is-supervisor` early from the CACHED role, deliberately, so supervisor-only chrome would not flash in after the async membership check (a CLS optimisation) — and nothing ever cleared it. Deleting a member's row left her browser carrying a supervisor marker on <html> with no supervisor membership behind it. Harmless ONLY because the board never renders for a removed member; the moment any supervisor-only rule keys off that class on a view a removed member CAN reach, it misapplies. Root elements are the whole point: unlike a card or a button they survive every view switch and re-render, so the removal has to be written, never inherited from a re-render. Verified as an instrument, not assumed — run against the pre-fix hive.html it FAILS on `is-supervisor`, against the fix it passes. Deliberately narrow so a PASS means something: only documentElement/body targets, only role-vocabulary names (so button-lock's `is-loading` is out of scope), and toggle() counts as a removal since it is add-and-remove by construction. This is HK1's SECOND assertion only; the first (a hidden element must be EMPTY, not display:none over real data) is a DOM property the live deepwalk checks, and folding it in here would let a static PASS imply a live guarantee it never made. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
    },
    {
        # HIVE DEEPWALK · HK3 — one adopter per page for the canonical role.
        "id":      "role_adoption_centralized",
        "script":  "tools/validate_role_adoption_centralized.py",
        "args":    [],
        "label":   "A page may adopt the canonical role (`wh_hive_role`) from exactly ONE place. Adopting a role is not one assignment — it is the module variable, the stored hint, AND any paint derived from it, which must move together. Found live 2026-07-27 (hive deepwalk H8b/H8d/H3): hive.html had SEVEN role-adoption sites and only TWO repainted `html.is-supervisor`, whose rules are FUNCTIONAL not cosmetic (they set `#my-work-card{display:none}` and hide `#pm-overdue-alert` / `#stock-alert`). Each unreconciled site was its own door onto the same defect and THREE were confirmed live before being fixed: DEMOTION (role synced down, marker stayed, so a demoted worker lost their own work card and their overdue-PM and stock alerts while the page looked normal), SWITCH (a switch never reloads — it calls initBoard() in place — so the page-load fix never ran), and JOIN (joining a hive where you are a worker while holding supervisor paint from another). The lesson is not 'remember to repaint' but that a value with invariants attached needs ONE adopter, so the invariant is written once instead of remembered seven times; hive.html now routes everything through applyHiveRole(). Verified as an instrument rather than assumed: against pre-centralization hive.html it FAILS with 7 sites (lines 1807/1911/1980/2119/2256/2270/5234), against the fix it passes with 1. Reads are deliberately not counted — counting them would fail every page on the platform — and scan/test harnesses that plant a role to set up a scenario are exempt. Static/fast. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
    },
    {
        # HIVE DEEPWALK · H8c — the client role reader must understand every role the DB stores.
        "id":      "role_vocabulary_coverage",
        "script":  "tools/validate_role_vocabulary_coverage.py",
        "args":    [],
        "label":   "The canonical client RBAC reader (wh-roles.js) must UNDERSTAND every role value hive_members actually stores. Found live 2026-07-27 (hive deepwalk H8c): the reader reads the AUTH key wh_hive_role (which holds what hive_members.role holds) while its capability map mirrors nav-hub's `roles` arrays, written in DISPLAY vocabulary (field|supervisor|engineer). The two were never reconciled. hive_members.role stores 'worker', 'worker' was absent from ROLES, so whRole() returned '' — and an empty role is DELIBERATELY permissive (solo mode / new install, so a lone tech is not locked out of their own tools). Two reasonable decisions combined into an unreasonable outcome: every real worker (12 of 16 seeded memberships) silently satisfied can('approve'), can('manage_hive') and can('audit_log'). Confirmed in the browser before fixing, and fixed by mirroring nav-hub's own worker->field mapping rather than inventing a second vocabulary. It shipped harmless ONLY by accident — nothing calls can() yet — while every comment in the codebase tells the next change to use it, so a latent trap stayed one call away. Compares against LIVE distinct roles on purpose: the failure was a mismatch between what the DB WRITES and what the client UNDERSTANDS, so reading only source would compare the client against itself. Verified as an instrument: against the pre-fix reader it FAILS on 'worker', against the fix it passes, and a hypothetical future role ('contractor') is caught by the selftest. Skips clean when the DB is down. Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # HIVE DEEPWALK · HK2 gate — a shipped capability must be reachable by the data that EXISTS.
        "id":      "fixture_capability_coverage",
        "script":  "tools/validate_fixture_capability_coverage.py",
        "args":    [],
        "label":   "A shipped capability must be EXERCISABLE by the data that actually exists, not merely by seeder code that could create it. Found 2026-07-27 (hive deepwalk): the hive switcher shipped, worked, and was UNWALKABLE BY CONSTRUCTION — seeded data was strictly one worker to one hive, so the switch button (rendered only when the list exceeds 1) never appeared and the switch path had never once been exercised. The moment a fixture existed, the first walk found a real defect behind it: the member list refreshed ONLY when the user had no active hive, so a membership granted after sign-in stayed invisible until sign-out. The class then proved itself again, which is why this gate queries LIVE ROWS rather than reading the seeder: walking H8 (remove a member) DELETED the platform's only multi-hive membership, the seeder still contained the code to create one, and the capability was silently unwalkable again — a seeder-reading gate would have said PASS while the fixture was gone. Prevents the most expensive false confidence there is: a green suite over a feature nobody can enter, which looks exactly like coverage. A failed query counts as a shortfall, never a silent pass, since \"I could not tell\" must not read as \"covered\". Skips clean when the local DB is down (fixture check, not an uptime check). Self-test: --selftest.",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc R (S, OWASP A02) — no real secret in a TRACKED .env.* file (the hardcoded-secrets
        # scanner only opens *.html/js/ts/py, so a committed dotfile credential is invisible). Teeth.
        "id":      "committed_env_secret",
        "script":  "tools/validate_committed_env_secret.py",
        "args":    [],
        "label":   "Arc R: committed .env secret (no credential in a tracked dotfile; A02)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R (S, OWASP A08) — Subresource Integrity on every version-pinned third-party CDN script
        # (CDN compromise => arbitrary JS on the authed page). Floating tags = pin-first backlog. Teeth.
        "id":      "sri_cdn_scripts",
        "script":  "tools/validate_sri.py",
        "args":    [],
        "label":   "Arc R: SRI on pinned CDN scripts (supply-chain; A08)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R (S, OWASP A09 meta) — the SAST posture map must cover the FULL OWASP Top-10 (A07/A09/A10
        # were absent => a false "every category covered" claim). Asserts sast_scan.OWASP completeness. Teeth.
        "id":      "sast_owasp_complete",
        "script":  "tools/validate_sast_owasp_complete.py",
        "args":    [],
        "label":   "Arc R: SAST OWASP-map completeness (full Top-10 mapped; meta)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc R aggregate board — the 4-lens (X/Z/S/P) ratcheted security posture, OWASP-mapped.
        # Runs the underlying validators as subprocesses (slow) — skip in --fast. Floors X100/Z100/S95/P90.
        "id":      "security_adversarial_sweep",
        "script":  "tools/security_adversarial_sweep.py",
        "args":    [],
        "label":   "Arc R: security/adversarial sweep (4 lenses, OWASP Top-10, ratcheted)",
        "group":   "AI Validation",
        "report":  "security_adversarial_results.json",
        "skip_if_fast": True,
    },
    # ── Arc S — Resilience / DR / Chaos (4 lenses F/R/C/D; floors F90/R95/C100/D85) ──
    # 13 file-static gates run in --fast; the aggregate board (skip_if_fast) re-runs all
    # 15 incl. the 2 DB-runtime cells and enforces the floors + the forward-only ratchet.
    {"id": "dedup_constraints",      "script": "validate_dedup_constraints.py",   "args": [], "label": "Arc S/C: dedup UNIQUE constraints (exactly-once on retries)", "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "optimistic_lock",        "script": "validate_optimistic_lock.py",     "args": [], "label": "Arc S/C: optimistic-lock compare-and-set (no lost-update)",     "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "optimistic_ui",          "script": "validate_optimistic_ui.py",       "args": [], "label": "Arc S/C: optimistic-UI rollback (no phantom-saved row)",        "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "atomic_writes",          "script": "validate_atomic_writes.py",       "args": [], "label": "Arc S/C: atomic multi-step writes (no partial-write corruption)", "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "dependency_timeout",     "script": "validate_dependency_timeout.py",  "args": [], "label": "Arc S/F: dependency timeout (no infinite hang)",                "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "ai_alldown_degrade",     "script": "validate_ai_alldown_degrade.py",  "args": [], "label": "Arc S/F: AI all-down degrade (no silent empty)",                "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "cdn_resilience",         "script": "validate_cdn_resilience.py",      "args": [], "label": "Arc S/F: CDN resilience (no silent dead lib)",                  "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "circuit_breaker",        "script": "validate_circuit_breaker.py",     "args": [], "label": "Arc S/F: external circuit-breaker (Resend/CMMS, no hammering)",  "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "offline_resilience",     "script": "validate_offline_resilience.py",  "args": [], "label": "Arc S/D: offline write queue (no lost field write)",            "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "offline_queue_retry",    "script": "validate_offline_queue_retry.py", "args": [], "label": "Arc S/D: offline-queue retry/backoff/dead-letter",              "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "precache_coverage",      "script": "validate_precache_coverage.py",   "args": [], "label": "Arc S/D: precache + offline navigation fallback (no blank tab)", "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "degraded_mode",          "script": "validate_degraded_mode.py",       "args": [], "label": "Arc S/D: backend-degraded detection (not just navigator.onLine)", "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    {"id": "dr_claims",              "script": "validate_dr_claims.py",           "args": [], "label": "Arc S/R: DR claims backed (no false-sense recovery doc)",       "group": "Resilience / DR", "report": None, "skip_if_fast": False},
    # The 2 DB-runtime cells are ALSO aggregated by resilience_dr_sweep below, but are registered
    # individually here so auto-discovery sees every root validate_*.py registered. DB-runtime -> skip in --fast.
    {"id": "data_backup",            "script": "validate_data_backup.py",         "args": [], "label": "Arc S/R: logical dump + restore drill + documented restore path (DB-runtime)", "group": "Resilience / DR", "report": None, "skip_if_fast": True},
    {"id": "dataloss_detection",     "script": "validate_dataloss_detection.py",  "args": [], "label": "Arc S/R: rowcount-snapshot data-loss monitor live (DB-runtime)",          "group": "Resilience / DR", "report": None, "skip_if_fast": True},
    {
        # Arc S aggregate board — the 4-lens (F/R/C/D) ratcheted resilience posture. Re-runs all 15
        # validators incl. the 2 DB-runtime cells (data_backup restore drill + dataloss monitor) as
        # subprocesses (slow) — skip in --fast. Floors F90/R95/C100/D85; baseline resilience_dr_baseline.json.
        "id":      "resilience_dr_sweep",
        "script":  "tools/resilience_dr_sweep.py",
        "args":    [],
        "label":   "Arc S: resilience / DR sweep (4 lenses F/R/C/D, ratcheted)",
        "group":   "Resilience / DR",
        "report":  "resilience_dr_results.json",
        "skip_if_fast": True,
    },
    {
        # Memory-System M1.1 — the agent's own memory.db (~90MB Memento SQLite/FTS5) had ZERO backup
        # and corrupts on interrupted hook writes. This drill proves the full backup->restore round-trip
        # deterministically every run: online-backup the live DB to scratch, reopen, PRAGMA integrity_check,
        # assert chunk count ~matches + schema version, run a REAL FTS5 BM25 query on the restored copy
        # (proves the index, not just the bytes), drop scratch. ~2s DB-runtime op -> skip in --fast.
        "id":      "memory_db_backup",
        "script":  "tools/memory_db_backup.py",
        "args":    ["--drill", "--vacuum-drill"],
        "label":   "Memory M1.1+M1.2: memory.db backup/restore round-trip + VACUUM shrink drill",
        "group":   "Memory System",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # AI6 - agentic write accountability (dimension-expansion loop 21). AI1-AI5 grade the AI's
        # ANSWER; this grades its ACT. 14 AI edge fns WRITE, and 6 write into tables a human later
        # reads as fact. Found live: visual-defect-capture stamped model-generated diagnosis into
        # fault_knowledge under the signed-in WORKER'S NAME, and that table feeds RAG + intelligence
        # reports - so AI output re-entered the knowledge base as human field experience. Denominator
        # is curated by evidence (telemetry tables excluded; self-declaring ai_* tables excluded).
        # Forward-only ratchet on ai_write_provenance_baseline.json. Static grep -> runs in --fast.
        "id":      "ai_write_provenance",
        "script":  "tools/validate_ai_write_provenance.py",
        "args":    [],
        "label":   "AI6: agentic write accountability (AI writes into human-read domain tables declare machine authorship)",
        "group":   "AI Validation",
        "report":  "ai_write_provenance_report.json",
    },
    {
        # Memory-System M2.1 — retrieval recall@k gate. Retriever tuning knobs (IMPORTANCE,
        # half-lives, MIN_FINAL_SCORE, transcript boost, RRF k) were eyeballed with no guard.
        # 25 grounded (query -> canonical memory) golden pairs run against the LIVE retriever;
        # gate on fixed health floors (R@3>=0.60, R@5>=0.80, MRR>=0.40). A tuning change that
        # silently drops recall now FAILs. ~7s of retrieval -> skip in --fast.
        "id":      "memory_recall_eval",
        "script":  "tools/memory_recall_eval.py",
        "args":    [],
        "label":   "Memory M2.1: retriever recall@k eval (25 golden pairs, ratcheted to health floors)",
        "group":   "Memory System",
        "report":  "memory_recall_baseline.json",
        "skip_if_fast": True,
    },
    {
        # Memory-System M3.1 — write-side quality gate for curated memory topic files. The indexer
        # derives a chunk's TYPE (-> importance + decay = ranking) from frontmatter then a filename
        # prefix; a file with neither valid type silently indexes as 'unknown' (degraded recall
        # forever), and empty name/description starve the title/FTS signal. Imports the REAL indexer
        # (parse_frontmatter + detect_type) so the lint can't drift. Static (no DB) -> runs in --fast.
        "id":      "memory_write_quality",
        "script":  "tools/memory_write_quality.py",
        "args":    ["--quiet"],
        "label":   "Memory M3.1: topic-file write-quality lint (type/name/description, no silent type=unknown)",
        "group":   "Memory System",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Memory-System M2.2 — health-regression gate. The retriever's health metrics (silent_rate,
        # p95 latency, file-grounded %, index size) were dashboard-only; this wraps the SAME
        # build_payload() in thresholds so a regression FAILs automatically. Honors the warming-up
        # honesty flag (defers activity thresholds when retrievals_today < 10). Fast DB read.
        "id":      "memory_health_gate",
        "script":  "tools/memory_health_gate.py",
        "args":    [],
        "label":   "Memory M2.2: retriever health-regression gate (silent_rate / median+p95 latency / grounding thresholds)",
        "group":   "Memory System",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Memory-System M3.2 — supersedes down-rank mechanism integrity. A memory with a
        # `supersedes: <slug>` field replaces the older one; the retriever down-ranks the
        # superseded chunk so an obsolete decision can't co-surface with its reversal. The
        # self-test proves the whole chain (frontmatter->map->loader->down-rank) so a future
        # retriever refactor that breaks the penalty FAILs. Static + deterministic -> runs in --fast.
        "id":      "memory_supersedes",
        "script":  "tools/memory_supersedes.py",
        "args":    ["--self-test"],
        "label":   "Memory M3.2: supersedes down-rank mechanism (superseded memory ranks below its replacement)",
        "group":   "Memory System",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Memory-System M4.1 — transcript retention/pruning mechanism. The DB grows unbounded
        # (transcripts ~31% of chunks; vector_query full-scans every row). The scheduled prune
        # (backup-guarded, weekly, 60d retention, wired into SessionStart) evicts ONLY old
        # never-retrieved transcripts. The self-test proves on a real-schema scratch DB that it
        # prunes ONLY old never-retrieved transcripts and keeps retrieved/fresh/curated intact.
        "id":      "memory_prune_transcripts",
        "script":  "tools/memory_prune_transcripts.py",
        "args":    ["--self-test"],
        "label":   "Memory M4.1: transcript prune mechanism (evicts only old never-retrieved, keeps the rest)",
        "group":   "Memory System",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Companion-Memory C1.1 — the per-dimension memory regression gate (ai_eval_gate.companion_gate,
        # G0 via validate_companion_dim_gate.py) is only as strong as its locked-test power. This self-test
        # PINS that the gate actually BLOCKS (exit 1) a degraded memory locked-test run and PASSES a clean
        # one — the C1.1 acceptance bar — deterministically over the REAL locked-test membership, with zero
        # live-LLM calls (so it can't flake). Degrades-to-SKIP if the locked-test memory set is too small
        # to construct an honest blocking scenario. Static + deterministic -> runs in --fast.
        "id":      "companion_memory_gate_teeth",
        "script":  "tools/companion_gate_teeth.py",
        "args":    [],
        "label":   "Companion Memory C1.1: memory gate has teeth (degraded locked-test FAILs, clean passes)",
        "group":   "Companion Memory",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Companion-Memory C2.1 — store-level supersedes down-rank (SAFETY). When an episodic
        # memory is corrected/replaced, the obsolete row must be down-ranked at retrieval so an
        # outdated procedure cannot co-surface as current. Static-checks the migration superseded_by
        # column + RPC ×0.4 penalty + the guarded recallEpisodic down-rank, then proves it LIVE in a
        # rolled-back transaction (zero pollution): match_procedural_memories returns both procedures,
        # then only the replacement after one is superseded. Degrades-to-SKIP if the local DB is down.
        "id":      "companion_memory_supersedes",
        "script":  "tools/companion_supersedes.py",
        "args":    [],
        "label":   "Companion Memory C2.1: supersedes down-rank (obsolete procedure ranks below its replacement)",
        "group":   "Companion Memory",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Companion-Memory C3.1 — backup + restore DRILL of the durable companion memory tables
        # (agent_episodic_memory + agent_memory). pg_dump -> restore into a scratch schema -> assert
        # rowcount round-trips AND a seeded canary fact is still RECALLABLE from the restored copy
        # (rowcount alone doesn't prove the memory survives queryably). Runs against the LOCAL docker
        # DB only; zero net pollution (canary removed in finally). Degrades-to-SKIP if the DB is down.
        # Heavier (pg_dump/restore) so it runs in the full suite, not --fast (the DR-drill convention).
        "id":      "companion_memory_backup_drill",
        "script":  "tools/companion_memory_backup.py",
        "args":    ["--drill"],
        "label":   "Companion Memory C3.1: backup + restore drill (rowcount round-trip + recall survives restore)",
        "group":   "Companion Memory",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Companion-Memory C3.2 — memory health-regression gate (M2.2 pattern). Thresholds the
        # groundable store-health signals: structural (episodic + agent_memory non-empty) + integrity
        # (procedural null-embedding rate — un-embedded procedures are invisible to
        # match_procedural_memories forever). Warming-up clause defers the rate on a tiny sample;
        # surfaces (informational) the response_time_ms/intent_confidence instrumentation gap that
        # blocks latency/silent_rate gating. Degrades-to-SKIP if the local DB is down.
        "id":      "companion_memory_health_gate",
        "script":  "tools/companion_memory_health_gate.py",
        "args":    [],
        "label":   "Companion Memory C3.2: memory health gate (structural + procedural-embedding integrity)",
        "group":   "Companion Memory",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Companion-Memory C2.3 — re-embed retry for null procedural memories. A procedural memory
        # stored with embedding=NULL is invisible to match_procedural_memories forever (the
        # "invisible-forever" skill-library bug). The self-test proves the mechanism in a rolled-back
        # txn (null -> invisible -> re-embed -> searchable); the operational --backfill re-embeds live
        # nulls via embedding_helper (degrades-to-SKIP without a provider). Deterministic self-test.
        "id":      "companion_memory_reembed",
        "script":  "tools/companion_reembed_procedural.py",
        "args":    ["--self-test"],
        "label":   "Companion Memory C2.3: re-embed-retry (null procedural becomes searchable after re-embed)",
        "group":   "Companion Memory",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Companion-Memory C2.2 — write-side semantic dedup. persistEpisodic now MERGES a near-duplicate
        # procedural memory (bump use_count, keep higher importance) instead of inserting a paraphrase
        # (store-hygiene: the skill library doesn't bloat with restatements). Self-test proves it in a
        # rolled-back txn: a near-dup embedding is detected + merged (1 row, use_count bumped) while an
        # orthogonal one is NOT (a distinct procedure still inserts). Deterministic; degrades-to-SKIP if DB down.
        "id":      "companion_memory_dedup",
        "script":  "tools/companion_dedup.py",
        "args":    [],
        "label":   "Companion Memory C2.2: write-side semantic dedup (near-dup procedural merges, distinct inserts)",
        "group":   "Companion Memory",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc I I1/I — account-enumeration resistance (OWASP ASVS V2.2). Login must use a uniform
        # invalid-credential response (no user-exists tell); signup username-availability must route
        # through the rate-limitable check_username_available RPC (by-design carve-out). Static; baseline 0.
        "id":      "signup_enumeration_safety",
        "script":  "tools/validate_signup_enumeration_safety.py",
        "args":    [],
        "label":   "Arc I: account-enumeration resistance (login uniform-response + signup RPC carve-out; ASVS V2.2)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc I I7/I — signup bot-protection wiring (OWASP ASVS V2.1 anti-automation). Asserts the
        # configure-to-enable Turnstile in-page integration stays intact (container + loader + token
        # hand-off, inert when unconfigured). Live bot-block = Supabase dashboard enrollment (attributed).
        "id":      "signup_bot_protection",
        "script":  "tools/validate_signup_bot_protection.py",
        "args":    [],
        "label":   "Arc I: signup bot-protection wiring (Turnstile configure-to-enable; ASVS V2.1)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc I I8/I — GDPR/PDPA account offboarding: soft-deactivate + anonymize. The deactivate_my_account()
        # RPC must be self-scoped (auth.uid, no IDOR param), anonymize PII, PRESERVE operational records,
        # revoke hive access, and be hardened (search_path + PUBLIC-revoke). Static; baseline 0.
        "id":      "account_deactivation",
        "script":  "tools/validate_account_deactivation.py",
        "args":    [],
        "label":   "Arc I: account offboarding (self-scoped anonymize, preserve records; GDPR/PDPA)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc I I7/A — server-side brute-force lockout: the `login` edge proxy gates by a real
        # failed-attempt counter (5 tries → 423) so a correct password can't bypass a lock. Needs live DB.
        "id":      "login_proxy_lockout",
        "script":  "tools/validate_login_proxy_lockout.py",
        "args":    [],
        "label":   "Arc I: login brute-force lockout (server-side proxy; correct pw can't bypass a lock)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc I I3/I — password recovery: supervisor-assisted (no-email field workers) + email fallback.
        # The supervisor-reset is scoped (active supervisor → same-hive WORKER only, not a peer supervisor,
        # no cross-hive) + audit-logged. Needs live DB/runtime for the behavioral half; skip in --fast.
        "id":      "password_recovery",
        "script":  "tools/validate_password_recovery.py",
        "args":    [],
        "label":   "Arc I: password recovery (supervisor-assisted scoped + email fallback)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc H H4/I — OWASP LLM05 output-handling: EXECUTE companion renderMarkdown on XSS payloads,
        # assert escaping (no live tag survives). Hermetic (node), so runs in --fast.
        "id":      "companion_output_escaping",
        "script":  "tools/validate_companion_output_escaping.py",
        "args":    [],
        "label":   "Arc H: companion output escaping (LLM05 — untrusted LLM output can't XSS)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Analytics Engine arc I3/I6 — EXECUTE send-report-email buildEmailHtml on XSS payloads
        # injected into hiveName / r.type / r.summary, assert escaping (no raw tag survives).
        # Hermetic (node), so runs in --fast.
        "id":      "report_email_escaping",
        "script":  "tools/validate_report_email_escaping.py",
        "args":    [],
        "label":   "Analytics I3/I6: send-report-email HTML-injection (every email sink escaped)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Analytics Engine arc AI2/F5 — assert the AI action-plan synthesis reads only REAL
        # 4-phase output keys (no stale key → ungrounded prompt → fabrication). Static, --fast-safe.
        "id":      "analytics_synthesis_grounding",
        "script":  "tools/validate_analytics_synthesis_grounding.py",
        "args":    [],
        "label":   "Analytics AI2/F5: action-plan synthesis reads real phase keys (no ungrounded AI)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Analytics Engine arc page invariants — chart CLS reserve (A4), ISO-55001 honest
        # composite label (AI3), no rendered em-dash (A6). Static, --fast-safe.
        "id":      "analytics_page",
        "script":  "tools/validate_analytics_page.py",
        "args":    [],
        "label":   "Analytics A4/AI3/A6: page invariants (chart CLS reserve, honest label, no em-dash)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Analytics arc F1b — the canonical get_oee_by_machine RPC must derive Quality from
        # good_units/total_units (not quality_pct-only), or report/asset-hub OEE diverges from
        # the analytics page. Static (reads the migration SQL) → --fast-safe.
        "id":      "oee_quality_derivation",
        "script":  "tools/validate_oee_quality_derivation.py",
        "args":    [],
        "label":   "Analytics F1b: canonical OEE quality = good/total (report matches page)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Analytics arc F1d — canonical PM compliance overall_pct = WEIGHTED (SMRP 2.1.1
        # Σcompleted/Σscheduled), not the unweighted mean that contradicts the N-of-M count.
        # Static (migration SQL + descriptive.py) → --fast-safe.
        "id":      "pm_compliance_weighted",
        "script":  "tools/validate_pm_compliance_weighted.py",
        "args":    [],
        "label":   "Analytics F1d: PM compliance is SMRP-weighted (hero matches its count)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Arc I — LIVE data-layer auth proofs via docker psql (synthetic-email isolation, non-active
        # member exclusion, server-derived tenancy, auth-migration backfill trigger). Needs the local
        # DB up, so skip in --fast (mirrors the rls_tenant_isolation / definer_tenant_gate live gates).
        "id":      "auth_live_db",
        "script":  "tools/validate_auth_live_db.py",
        "args":    [],
        "label":   "Arc I: live data-layer auth proofs (synthetic-email/non-active/server-tenancy/backfill)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc I I3/A — GoTrue enforces credential strength server-side (live probe → 422 weak_password).
        # Needs the local stack up, so skip in --fast.
        "id":      "auth_live_gotrue",
        "script":  "tools/validate_auth_live_gotrue.py",
        "args":    [],
        "label":   "Arc I: live credential-strength (GoTrue rejects weak password, 422)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc I I2/A — shared-device idle expiry, LIVE (Playwright drives the real session-timeout.js via the
        # WH_IDLE_TIMEOUT_OVERRIDE clock-seam): idle→prompt→Continue→hard-clear+redirect. Needs the seeder; skip in --fast.
        "id":      "auth_idle_timeout_live",
        "script":  "validate_auth_idle_timeout_live.py",
        "args":    [],
        "label":   "Arc I: live idle-timeout (shared-device idle→prompt→hard-clear sequence)",
        "group":   "AI Validation",
        "report":  "auth_idle_timeout_live_report.json",
        "skip_if_fast": True,
    },
    {
        # Arc I I4/U — role-gated UI render LIVE (journey-permissions): supervisor-only blocks render per role,
        # worker/anon gated+redirected. Needs the seeder + live stack; skip in --fast.
        "id":      "auth_role_render_live",
        "script":  "validate_auth_role_render_live.py",
        "args":    [],
        "label":   "Arc I: live role-gated render (RBAC at the render layer; supervisor-only visibility)",
        "group":   "AI Validation",
        "report":  "auth_role_render_live_report.json",
        "skip_if_fast": True,
    },
    {
        # Arc I I7/F — AI rate-limit ENFORCED live (LLM10): boundary test drives the counter to the limit →
        # real AI edge invoke returns 429. Self-resetting. Needs seeder + edge + docker psql; skip in --fast.
        "id":      "auth_rate_limit_live",
        "script":  "validate_auth_rate_limit_live.py",
        "args":    [],
        "label":   "Arc I: live AI rate-limit enforcement (counter at limit → 429; LLM10)",
        "group":   "AI Validation",
        "report":  "auth_rate_limit_live_report.json",
        "skip_if_fast": True,
    },
    {
        # Arc I I4/A — function-level role guard LIVE: a worker-role JWT → 403 on the supervisor-only
        # export-hive-data edge fn (RBAC at the function layer, not UI-only). Needs seeder+edge; skip in --fast.
        "id":      "auth_role_guard_live",
        "script":  "validate_auth_role_guard_live.py",
        "args":    [],
        "label":   "Arc I: live function-level role guard (worker → 403 on supervisor-only fn)",
        "group":   "AI Validation",
        "report":  "auth_role_guard_live_report.json",
        "skip_if_fast": True,
    },
    {
        # CMMS Integrations PDDA I1/I2/I3 — live authz gate. Real supervisor+worker JWTs vs the
        # served edge + PostgREST: a supervisor CANNOT sync a FOREIGN hive's config_id (BOLA),
        # a worker CANNOT read the plaintext auth_token or repoint a config's endpoint_url, and
        # the supervisor's OWN-config path still works (no over-block). Needs seeder+edge; skip --fast.
        "id":      "integration_configs_authz_live",
        "script":  "tools/validate_integration_configs_authz_live.py",
        "args":    [],
        "label":   "CMMS: live integration_configs authz (config_id BOLA closed; worker token-read/write blocked)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # CMMS Integrations PDDA F1004/I6/F1-b — live webhook hardening gate. A validly-signed
        # webhook with an OLD/FAR-FUTURE timestamp is REJECTED (replay window ±300s), a malformed
        # body → 400 (not 500), wrong-sig → 401, fresh → 200. Complements the F5 idempotency gate.
        # Needs edge + docker psql; skip --fast.
        "id":      "cmms_webhook_security_live",
        "script":  "tools/validate_cmms_webhook_security_live.py",
        "args":    [],
        "label":   "CMMS: live webhook security (replay window + malformed 400 + wrong-sig 401 + fresh 200)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # CMMS Integrations PDDA F1/F2 — live entity-sync gate. The webhook's asset.updated /
        # inventory.updated / pm.overdue handlers were silent no-ops; this drives real signed
        # webhooks and asserts the DB effect (external_sync asset/inventory/pm_schedule rows +
        # inventory_items, idempotent qty update). Self-contained, reseed-resilient. Skip --fast.
        "id":      "cmms_entity_sync_live",
        "script":  "tools/verify_cmms_entity_sync_live.py",
        "args":    [],
        "label":   "CMMS: live entity sync (asset/inventory/pm.overdue webhook handlers land in DB, idempotent)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": True,
    },
    {
        # Arc H H8/I — prompt-injection posture (LLM01): no AI fn interpolates untrusted input INTO the
        # system prompt (role separation). Static; baseline 0. The probabilistic jailbreak residual is
        # the live fabrication/Family-E sweep, not this gate.
        "id":      "ai_prompt_injection",
        "script":  "tools/validate_ai_prompt_injection.py",
        "args":    [],
        "label":   "Arc H: AI prompt-injection posture (untrusted input out of system prompt; LLM01)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # D25 PII-egress floor: the shared _shared/redactPII.ts scrubber (which every AI fn's
        # answer routes through via the ai-gateway) must not regress its ISO-timestamp carve-out —
        # a loose PHONE_RE once ate the YYYY-MM-DD head of ISO datetimes, leaking `<phone>T..`
        # into asset-brain answers. Deterministic ($0, no deno/DB/model): re-runs the carve-out
        # from the .ts regex sources — ISO survives, real phones/emails still redact. Tagged
        # `# DEEPWALK-CELL: ai:* D25` → locks the D25 egress cell across every AI fn.
        "id":      "redact_iso",
        "script":  "tools/validate_redact_iso.py",
        "args":    [],
        "label":   "Arc H: PII-egress redaction ISO carve-out (D25, shared redactPII.ts, deterministic)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # K2 multi-turn PII egress (2026-07-12, live-caught): the current-turn message is fully
        # redacted, but an email/phone a worker stated in a PRIOR turn is carried raw in the
        # agent_memory turn_text + semantic journal recall — the forwarded memory_block AND the
        # summariser transcript were scrubbed only by redactKnownNames (NAMES), so those emails/
        # phones reached the model provider raw (proven: pii.leak.test@plant.ph survived twice).
        # Fix = redactMemoryText (names + email/phone via scrubExceptISO) wired into BOTH egress
        # sites. Deterministic ($0, no deno/DB/model): structural (both sites use redactMemoryText,
        # neither regresses to bare redactKnownNames; the helper still scrubs email/phone) +
        # behavioral (re-runs the scrub from the .ts regex sources: email/phone die, ISO survives).
        # Tagged `# DEEPWALK-CELL: ai:* D25` → locks the multi-turn half of the D25 egress cell.
        "id":      "memory_pii_redaction",
        "script":  "tools/validate_memory_pii_redaction.py",
        "args":    [],
        "label":   "Arc H: multi-turn PII egress rail (K2, memory_block + summariser, redactMemoryText)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # K1 gateway-bypass floor (2026-07-12, live-caught): assistant.html's Step-2 fallback
        # POSTed the full system prompt + chat history + KB context to a PUBLIC Cloudflare Worker
        # (workhive-assistant.*.workers.dev) — no auth / no PII redaction / no rate-limit / no
        # memory — whenever the slow orchestrator path timed out. Fixed by routing the fallback
        # through ai-gateway 'voice-journal'. This gate locks the whole class forward-only:
        # scans every root *.html for a browser network call to a BANNED external model endpoint
        # (*.workers.dev / api.groq/openai/anthropic / openrouter / gemini / mistral / cerebras /
        # /chat/completions / /v1/messages). Ext-1 "gateway-route EVERY AI call". Deterministic.
        # Tagged `# DEEPWALK-CELL: ai:* D26` → locks the AI-gateway-reuse cell across every page.
        "id":      "no_ai_gateway_bypass",
        "script":  "tools/validate_no_ai_gateway_bypass.py",
        "args":    [],
        "label":   "Arc H: no browser page bypasses ai-gateway with a direct external-model call (K1, Ext-1)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # K4 companion-context PII floor (2026-07-12): companion-launcher only transmits a page's
        # setContext summary to the LLM when piiSafe:true. The gateway's context redaction scrubs
        # email/phone but NOT a name in prose — so a piiSafe summary interpolating owner_name/
        # display_name/etc. ships a person's name to the model. project-manager/report shipped that
        # shape (flag omitted → summary dropped → grounding dead); K4 set piiSafe:true + stripped
        # the names + added an asset-hub asset context. This gate locks the invariant forward-only:
        # a piiSafe:true summary interpolating a *_name person field FAILs. Deterministic ($0).
        # Tagged `# DEEPWALK-CELL: ai:* D25` → the client half of the D25 egress cell.
        "id":      "setcontext_pii_safe",
        "script":  "tools/validate_setcontext_pii_safe.py",
        "args":    [],
        "label":   "Arc H: piiSafe companion context carries no person-name (K4, page_context egress)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # X-FIND ASR-confidence clarify-gate (2026-07-12, live-caught): a garbled voice transcript
        # (Cebuano 40% fidelity) was sent to the companion, which CONFABULATED a grounded answer on the
        # garble. Fix = a 4-layer additive chain surfacing the indigenous ASR's avg_logprob so the
        # voice-journal page CLARIFIES ("say it again") below a floor instead of grounding a mis-heard
        # question. This gate asserts every link (asr_server avg_logprob -> audio-chain passthrough ->
        # voice-transcribe low_confidence -> voice-journal.html early-return gate) so the signal can't
        # silently stop flowing. Deterministic ($0). Tagged `# DEEPWALK-CELL: ai:* D27`.
        "id":      "asr_confidence_gate",
        "script":  "tools/validate_asr_confidence_gate.py",
        "args":    [],
        "label":   "Arc H: ASR-confidence clarify-gate intact (X-FIND, garbled voice does not confabulate)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # V-axis V6 SOVEREIGNTY ratchet (NATIVE_AI_ROADMAP.md #6): every AI capability that touches a hot
        # path must keep BOTH a LOCAL-FIRST env-gated slot (so a plant runs inference in-house + its data
        # never leaves the plant) AND a FALLBACK (so no single external provider — or a local outage — can
        # take the feature down). Asserts it across all 4: Embeddings (BGE_EMBED_URL), ASR (WH_ASR_URL),
        # TTS (WH_TTS_URL, built this session), LLM (WH_LLM_URL, built this session). A future edit that
        # drops a local slot or a fallback FAILs. Deterministic ($0). Tagged `# DEEPWALK-CELL: ai:* D28`.
        "id":      "indigenous_stack",
        "script":  "tools/validate_indigenous_stack.py",
        "args":    [],
        "label":   "Arc H/V: indigenous stack keeps local-first + fallback (data sovereignty, no hard external dep)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # AI Companion arc (2026-07-13): voice_family_probe caught the companion leaking its
        # persona/chain-of-thought scaffold verbatim ("We need to respond as Zaniah, strategist...
        # the worker says:...") — an UNTAGGED reasoning leak the <think>-tag strip missed. Case 3
        # in _shared/ai-chain.ts stripReasoningBlocks (+ both Python mirrors) returns "" so callAI
        # falls to the next model. This gate is the teeth: strips the leak corpus, spares real
        # answers, and asserts the TS + both Python mirrors keep the Case-3 signature (no drift).
        "id":      "reasoning_scaffold_strip",
        "script":  "validate_reasoning_scaffold_strip.py",
        "args":    [],
        "label":   "AI Companion: reasoning/persona-scaffold leak strip (untagged CoT never reaches the reply)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # D13 action-faithfulness (CL10 fabrication class): the advisory read-only brain must not
        # claim a COMPLETED system write it didn't make ("Log entry added", "Updated maintenance
        # record"). Asserts the shared rail (_shared/action_provenance.ts) is intact, the ai-gateway
        # centralizes it over EVERY advisory route (a new uncovered advisory route FAILs), and every
        # generative AI fn resolves to a fabrication guard. Deterministic ($0, no deno/DB/model).
        # Tagged `# DEEPWALK-CELL: ai:* D13` → locks the D13 fabrication cell across every AI fn.
        "id":      "ai_fabrication_contract",
        "script":  "tools/validate_ai_fabrication_contract.py",
        "args":    [],
        "label":   "Arc H: AI action-faithfulness rail centralized (D13, no fabricated completed-write)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Deepwalk D18 — destructive-safety: delete/reset flows are gated by the SHARED whConfirm
        # modal (a real cancellable gate, loaded platform-wide, guarding 26 destructive call-sites).
        # A regression that strips confirms below the floor FAILs. Deterministic ($0, static).
        "id":      "destructive_safety",
        "script":  "tools/validate_destructive_safety.py",
        "args":    [],
        "label":   "Deepwalk D18: destructive-safety (delete/reset confirm-gated via shared whConfirm)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Deepwalk D19 — idle-session robustness: the singleton Supabase client auto-refreshes +
        # persists the session and refreshes on tab-wake (visibilitychange) so an idle tab never
        # fires a stale-token 401; no surface opts out. Deterministic ($0, static).
        "id":      "session_resilience",
        "script":  "tools/validate_session_resilience.py",
        "args":    [],
        "label":   "Deepwalk D19: idle-session robustness (autoRefreshToken + wake-refresh, no stale 401)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Deepwalk D20 — client resilience: every client request is AbortController-timeout-bounded
        # (no infinite spinner on a hung backend) + the offline-banner/connectivity widgets exist.
        # Deterministic ($0, static).
        "id":      "client_resilience",
        "script":  "tools/validate_client_resilience.py",
        "args":    [],
        "label":   "Deepwalk D20: client resilience (timeout-bounded fetch + offline/connectivity UX)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # Deepwalk content-surface fold — the 45 static /learn articles' presentation floor across
        # D4 (a11y: lang/single-h1/heading-order-honoring-aria-level/img-alt), D5 (responsive
        # viewport), D7 (no dynamic-HTML sink on a static page), D17 (structurally whole). Caught +
        # fixed a real h2→h4 heading skip on the platform-overview guide. Deterministic ($0, static).
        "id":      "content_page_hygiene",
        "script":  "tools/validate_content_page_hygiene.py",
        "args":    [],
        "label":   "Deepwalk content fold: /learn article presentation floor (D4/D5/D7/D17)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "artifact_alignment",
        "script":  "tools/validate_artifact_alignment.py",
        "args":    [],
        "label":   "AI Self-Improvement: Artifact-Alignment Correctness (§13.13)",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # §13.13 A4 LIVE tier: diagram dimension labels == calc results (needs python-api
        # :8000, so skip in --fast; the readiness gate already requires it in full mode).
        "id":      "diagram_value_alignment",
        "script":  "tools/validate_diagram_value_alignment.py",
        "args":    [],
        "label":   "AI Self-Improvement: Diagram-Value Alignment (§13.13 A4, live)",
        "group":   "AI Validation",
        "report":  "diagram_value_alignment.json",
        "skip_if_fast": True,
    },
    {
        # §13.15 A6: STATIC full-coverage grounding field-contract — every BOM/SOW agent's
        # results.<field> reads must resolve to a real calc output key (forward-only baseline;
        # a NEW drift cell FAILs). Needs python-api :8000 for the live calc key-sets → skip_if_fast.
        "id":      "grounding_contract",
        "script":  "tools/validate_grounding_contract.py",
        "args":    [],
        "label":   "AI Self-Improvement: Grounding Field-Contract (§13.15 A6, forward-only)",
        "group":   "AI Validation",
        "report":  "grounding_contract.json",
        "skip_if_fast": True,
    },
    {
        # §13.13 live grounding tier: the LLM-generated BOM/SOW must cite the calc's
        # primary sized values (catches a hallucinated/dropped quantity). Needs
        # python-api + edge + a (free-tier) model key → skip in --fast.
        "id":      "bom_sow_grounding",
        "script":  "tools/validate_bom_sow_grounding.py",
        "args":    [],
        "label":   "AI Self-Improvement: BOM/SOW Grounding-Consistency (§13.13, live LLM)",
        "group":   "AI Validation",
        "report":  "bom_sow_grounding.json",
        "skip_if_fast": True,
    },
    {
        # §13.16 A7.1: page AI-narrative must cite only TRUE platform numbers (no fabricated
        # metric in rendered prose) — the whole-platform analogue of the companion gate.
        # Invokes a narrative edge fn live (auth + free-tier LLM) → prose #s ⊆ grounding-set.
        # Needs edge + auth + a model key → skip in --fast.
        "id":      "narrative_grounding",
        "script":  "tools/validate_narrative_grounding.py",
        "args":    [],
        "label":   "AI Self-Improvement: Narrative Grounding (§13.16 A7.1, live LLM)",
        "group":   "AI Validation",
        "report":  "narrative_grounding.json",
        "skip_if_fast": True,
    },
    {
        # Arc H proof→LIVE battery: invokes each AI surface end-to-end (user JWT + live LLM + real DB)
        # and asserts a DETERMINISTIC invariant on the live response (fallback fallover via W4 fault-inject,
        # PII-egress redaction, eval-runner verdict, TS↔py chain parity, Whisper transcription round-trip,
        # companion anti-fabrication rail). Drives the Arc-H live-subset to ~100%. Needs the serving edge
        # runtime + compute-API + a model key → skip in --fast (returns 0 / records 0 live when env is down).
        "id":      "ai_live_invoke",
        "script":  "tools/validate_ai_live_invoke.py",
        "args":    [],
        "label":   "Arc H: AI Live-Invoke battery (proof→LIVE, live LLM + edge runtime)",
        "group":   "AI Validation",
        "report":  "ai_live_invoke_results.json",
        "skip_if_fast": True,
    },
    {
        # §13.16 A7.2: CSV export-value contract — each exported column maps to a real source
        # field (a renamed/missing column exports BLANK). Static + docker psql (no LLM/browser).
        "id":      "export_value_contract",
        "script":  "tools/validate_export_value_contract.py",
        "args":    [],
        "label":   "AI Self-Improvement: Export-Value Contract (§13.16 A7.2, CSV)",
        "group":   "AI Validation",
        "report":  "export_value_contract.json",
        "skip_if_fast": True,
    },
    # ── Sentinel Architecture (Layer 0 -> Layer 2 bridge) ────────────────────
    # Runs the sentinel pipeline: coverage map (per-check), gap proposer,
    # pattern consistency, depth, freshness. Produces sentinel_health.json
    # for the Platform Guardian to surface alongside validator results.
    # See SENTINEL_ARCHITECTURE.md and feedback_hardening_loop for the
    # two-bridge model. Cheap (~1-2s deterministic) so always runs.
    {
        "id":      "sentinel-review",
        "script":  "run_sentinel_review.py",
        "args":    [],
        "label":   "Sentinel Review (L0->L2 bridge: coverage + pattern + depth + freshness)",
        "group":   "Sentinel",
        "report":  "sentinel_health.json",
        "skip_if_fast": False,
    },
    {
        "id":      "sentinel-baseline",
        "script":  "validate_sentinel_baseline.py",
        "args":    [],
        "label":   "Sentinel Baseline Ratchet (forward-only behavioral coverage; locks at first run)",
        "group":   "Sentinel",
        "report":  "sentinel_baseline_report.json",
        "skip_if_fast": False,
    },
    # ── SEO / Marketing Closed Loop (2026-05-17) ──────────────────────────────
    # 8 validators that enforce every promise the SEO + marketing work made:
    # no em-dashes, contact consistency, GA4 coverage, audience block per article,
    # tool-aligned CTA per article, sitemap sync, llms.txt sync, AI chain mirror.
    # Without these, today's wins regress silently. Each runs in <1 sec, no DB.
    {
        "id":      "em-dash",
        "script":  "validate_em_dash.py",
        "args":    [],
        "label":   "Em-Dash Validator (no em or en dashes in public body text)",
        "group":   "SEO Closed Loop",
        "report":  "em_dash_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "feedback-widget",
        "script":  "validate_feedback_widget.py",
        "args":    [],
        "label":   "Feedback Widget Validator (3-layer: script wiring + form integrity + schema RLS/rate-limit/resolved_at)",
        "group":   "Platform Feedback",
        "report":  "feedback_widget_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "contact-consistency",
        "script":  "validate_contact_consistency.py",
        "args":    [],
        "label":   "Contact Consistency Validator (3-layer: no stale hello@/ian.beronio37@ + canonical admin@ present)",
        "group":   "SEO Closed Loop",
        "report":  "contact_consistency_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ga4-coverage",
        "script":  "validate_ga4_coverage.py",
        "args":    [],
        "label":   "GA4 Coverage Validator (4-layer: GA4 block + wh-ga4.js load + canonical ID + custom-events file)",
        "group":   "SEO Closed Loop",
        "report":  "ga4_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "audience-block",
        "script":  "validate_audience_block.py",
        "args":    [],
        "label":   "Audience Block Validator (3-layer: every /learn/ article has Who-this-is-for + 4+ roles + beyond-technicians)",
        "group":   "SEO Closed Loop",
        "report":  "audience_block_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "tool-aligned-cta",
        "script":  "validate_tool_aligned_cta.py",
        "args":    [],
        "label":   "Tool-Aligned CTA Validator (3-layer: every /learn/ article anchors to a /<tool>.html + names the tool)",
        "group":   "SEO Closed Loop",
        "report":  "tool_aligned_cta_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "sitemap-sync",
        "script":  "validate_sitemap_sync.py",
        "args":    [],
        "label":   "Sitemap Sync Validator (3-layer: sitemap URLs <-> filesystem in sync + metadata complete)",
        "group":   "SEO Closed Loop",
        "report":  "sitemap_sync_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "llms-sync",
        "script":  "validate_llms_sync.py",
        "args":    [],
        "label":   "llms.txt Sync Validator (4-layer: every article in llms.txt + no stale slugs + sections + contact)",
        "group":   "SEO Closed Loop",
        "report":  "llms_sync_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "ai-chain-mirror",
        "script":  "validate_ai_chain_mirror.py",
        "args":    [],
        "label":   "AI Chain Mirror Validator (4-layer: Python ai_chain.py mirrors TS _shared/ai-chain.ts PROVIDER_CHAIN)",
        "group":   "SEO Closed Loop",
        "report":  "ai_chain_mirror_report.json",
        "skip_if_fast": False,
    },

    # ── P1 Roadmap (turns 5-7, re-registered after revert 2026-05-27) ────────
    {"id": "truth-view-contract",          "script": "validate_truth_view_contract.py",          "args": [], "label": "Truth-View Contract (every v_*_truth declares _source_count/_freshness_ts/_canonical_version)",                       "group": "P1 Roadmap", "report": "truth_view_contract_report.json",          "skip_if_fast": False, "severity": "blocker",    "parallel_safe": True},
    {"id": "envelope-conformance",         "script": "validate_envelope_conformance.py",         "args": [], "label": "Envelope Conformance (every edge fn imports _shared/envelope.ts OR is exempt)",                                       "group": "P1 Roadmap", "report": "envelope_conformance_report.json",         "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "health-endpoint",              "script": "validate_health_endpoint.py",              "args": [], "label": "Health Endpoint (every load-bearing edge fn handles /health)",                                                        "group": "P1 Roadmap", "report": "health_endpoint_report.json",              "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "render-budget",                "script": "validate_render_budget.py",                "args": [], "label": "Render Budget (per-page HTML + inline JS + external script ratchet)",                                                "group": "P1 Roadmap", "report": "render_budget_report.json",                "skip_if_fast": False, "severity": "warn",       "parallel_safe": True},
    # PJ18: a stray comment block above <!DOCTYPE> put project-manager.html into QUIRKS MODE
    # (measured document.compatMode === 'BackCompat') and rendered the comment as page text.
    # node --check reads only <script> bodies and the byte-count gates were happy, so nothing
    # caught it — a browser recovers silently, which is what makes it dangerous.
    {"id": "doctype-first",                "script": "validate_doctype_first.py",                "args": [], "label": "Doctype First (nothing may precede <!DOCTYPE html> — content there forces quirks mode)",                        "group": "P1 Roadmap", "report": None,                                       "skip_if_fast": False, "severity": "blocker",    "parallel_safe": True},
    # PJ18: migration 029 retyped a parameter, so CREATE OR REPLACE made a SECOND overload instead
    # of replacing. PostgREST then refused BOTH call shapes with PGRST203 and project creation was
    # dead — in production. psql resolves overloads by literal type, so every psql check passed.
    {"id": "rpc-overloads",                "script": "validate_rpc_overloads.py",                "args": [], "label": "RPC Overloads (no PostgREST-exposed function may have two signatures — PGRST203 kills the endpoint)", "group": "P1 Roadmap", "report": None,                                       "skip_if_fast": True,  "severity": "blocker",    "parallel_safe": True},
    # PJ15: project-manager embedded scope items and lessons into project_knowledge since Phase 6.5
    # and NOTHING read that table — no db function, no edge function, no page. The page paid an
    # embedding round-trip on every save into an index no answer could ever reach.
    {"id": "embedding-index-read",         "script": "validate_embedding_index_is_read.py",      "args": [], "label": "Embedding Index Is Read (every table with an embedding column has a reader, not just a writer)", "group": "P1 Roadmap", "report": None,                                       "skip_if_fast": True,  "severity": "regression", "parallel_safe": True},
    # PJ2/PJ6/PJ12/PJ14 ratchet: four guards this arc earned by live probe had NOTHING asserting
    # they still existed. Each check is a PROPERTY, not an existence test — a function can exist
    # with its guard clause deleted. Self-test: --selftest.
    {"id": "project-guard-spine",          "script": os.path.join("tools", "validate_project_guard_spine.py"), "args": [], "label": "Project Guard Spine (code-reuse / budget-write / progress-record / attribution-pin / delete-audit / lessons guards still hold)", "group": "P1 Roadmap", "report": None,                        "skip_if_fast": True,  "severity": "blocker",    "parallel_safe": True},
    {"id": "migration-immutability-strict","script": "validate_migration_immutability_strict.py","args": [], "label": "Migration Immutability Strict (sha256 every migration; FAIL on edit-after-first-observation)",                        "group": "P1 Roadmap", "report": "migration_immutability_strict_report.json","skip_if_fast": False, "severity": "blocker",    "parallel_safe": True},
    {"id": "substrate-manifest",           "script": os.path.join("tools", "build_substrate_manifest.py"), "args": [], "label": "Substrate Manifest (L-1.5: aggregate all 13 pattern miners + drift detectors into one view)",          "group": "P1 Roadmap", "report": "substrate_manifest.json",                  "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    {"id": "fullstack-gate-coverage",      "script": os.path.join("tools", "audit_fullstack_gate_coverage.py"), "args": [], "label": "Full-Stack × Gate Coverage Meta-Gate (every artefact named in the study's 13×6 matrix must exist)", "group": "P1 Roadmap", "report": "fullstack_gate_coverage_report.json",      "skip_if_fast": False, "severity": "blocker",    "parallel_safe": True},
    {"id": "rate-limit-adoption",          "script": "validate_rate_limit_adoption.py",          "args": [], "label": "Rate-Limit Adoption (every callAI fn calls checkAIRateLimit/checkUserRateLimit/checkRouteRateLimit)",                "group": "P1 Roadmap", "report": "rate_limit_adoption_report.json",          "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "llm-cache-adoption",           "script": "validate_llm_cache_adoption.py",           "args": [], "label": "LLM Cache Adoption (count of fns using cached() from _shared/cache.ts; floor ratchet)",                              "group": "P1 Roadmap", "report": "llm_cache_adoption_report.json",           "skip_if_fast": False, "severity": "warn",       "parallel_safe": True},
    {"id": "structured-log-adoption",      "script": "validate_structured_log_adoption.py",      "args": [], "label": "Structured Log Adoption (count of fns importing + calling log.* from _shared/logger.ts; floor ratchet)",            "group": "P1 Roadmap", "report": "structured_log_adoption_report.json",      "skip_if_fast": False, "severity": "warn",       "parallel_safe": True},
    {"id": "edge-error-capture",           "script": "validate_edge_error_capture.py",           "args": [], "label": "Edge Error-Capture Adoption (Arc T/T2 keystone: every edge fn routes through serveObserved so unhandled throws aggregate to wh_traces via trackError; L1 wrapper-integrity + L2 forward-only adoption floor; live fault-inject-proven)", "group": "P1 Roadmap", "report": "edge_error_capture_report.json",          "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "observability-fault-walk",     "script": os.path.join("tools", "observability_fault_walk.py"), "args": [], "label": "Observability Fault-Inject Walk (Arc T/T2 LIVE proof: injects an unhandled throw via the auth-gated chaos hook -> asserts a wh_traces error row lands with the same trace_id + a non-leaky 500 envelope + anon cannot inject; SKIPs cleanly if local Supabase is down)", "group": "P1 Roadmap", "report": "observability_fault_walk_report.json", "skip_if_fast": True,  "severity": "regression", "parallel_safe": False},
    {"id": "slo-rollup",                   "script": "validate_slo_rollup.py",                   "args": [], "label": "SLO Error-Budget Rollup Gate (Arc T/T3: v_wh_traces_slo view + slo_error_budget() RPC exist AND compute correctly - per-route error counts excl. 401/403/429 policy rejections, windowed 28d/6h/1h, burn = error_rate / 1% SLO budget; proven by a seeded rolled-back self-test; SKIPs if local DB down)", "group": "P1 Roadmap", "report": "slo_rollup_report.json", "skip_if_fast": True,  "severity": "regression", "parallel_safe": False},
    {"id": "grafana-slo-dashboard",        "script": "validate_grafana_slo_dashboard.py",        "args": [], "label": "Grafana SLO Provisioning Gate (Arc T/T5+T4: the repo-provisioned golden-signal dashboard workhive-slo-arct - 6 panels over wh_traces/v_wh_traces_slo on the supabase_local datasource - AND the alert routing (rule wh_slo_edge_errors + contact point + policy) exist, parse, and stay wired; static, no running Grafana needed)", "group": "P1 Roadmap", "report": "grafana_slo_dashboard_report.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "grafana-reader-reads",         "script": "validate_grafana_reader_reads.py",         "args": [], "label": "Grafana-Reader Read-Path Gate (Operator-Console->Grafana: LIVE-queries every dashboard-dependency table AS grafana_reader and fails if a read errors or is RLS-partially-blinded - catches the silent-blindness class that dark'd the SLO alert + founder-console observe tables; SKIPs if local DB down)", "group": "P1 Roadmap", "report": "grafana_reader_reads_report.json", "skip_if_fast": True,  "severity": "regression", "parallel_safe": False},
    {"id": "reproducible-build-pin",       "script": "validate_reproducible_build_pin.py",       "args": [], "label": "Reproducible Build Pin (L1 .tool-versions + L2 package-lock + L3 engines.node agreement)",                        "group": "P1 Roadmap", "report": "reproducible_build_pin_report.json",       "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "live-page-journeys",           "script": "validate_live_page_journeys.py",           "args": [], "label": "Arc K Live-Page Journeys Ratchet (live-as-a-user JTBDs never regress non-live + deterministic floor never grows; reads live_page_journeys_results.json vs baseline)", "group": "Arc K", "report": "live_page_journeys_check_report.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "arc-v-effortless",             "script": "validate_arc_v_effort.py",                "args": [], "label": "Arc V EFFORTLESS 3-Lens Ratchet (E: total click-hops CEILING - any new friction fails + excess-click debt never grows; L: cognitive-load floor never grows - Miller >7-choice/>40 walls/competing CTAs; F: Doherty flow floor never grows - slow-and-silent actions + dead-ends; reads arc_v_results.json vs baseline)", "group": "Arc V", "report": "arc_v_effort_check_report.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "arc-v-capstone",               "script": "validate_arc_v_capstone.py",              "args": [], "label": "Arc V EFFORTLESS Family-Capstone Ratchet (cross-page JOBS stay effortless: continuity never breaks - no hop bounces to sign-in / loses hive context; cumulative hop-cost never exceeds ideal; reads arc_v_capstone_results.json vs baseline)", "group": "Arc V", "report": "arc_v_capstone_check_report.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "arc-w-visual",                 "script": "validate_arc_w_visual.py",                "args": [], "label": "Arc W VISUAL UI/UX 9-Lens Ratchet (D depth/H focal/W whitespace/G grouping/C consistency/V dashboard/T color-type/M-S motion-state/I icon - every per-lens violation floor is a forward-only CEILING so visual quality can't rot; + M/S control-state CSS-rule floor :active/:focus-visible can't drop; reads arc_w_results.json vs baseline)", "group": "Arc W", "report": "arc_w_visual_check_report.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "arc-y-intuition",              "script": "validate_arc_y_intuition.py",             "args": [], "label": "Arc Y INTUITION GRADIENT Ratchet (per-page 5-lens novice floor never drops: L1 jargon-without-gloss can't grow / L3 first-paint overwhelm ceiling / L4 displayed-value-vs-DB-truth can't go silent / L5 in-app BACK can't disappear / L6 dead-links+unlabeled can't grow; 3-persona gradient measured by intuition_gradient_harness.mjs; reads intuition_gradient_report.json vs intuition_gradient_baseline.json)", "group": "Arc Y", "report": "arc_y_intuition_report.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "fb2-browser-ci-persona",       "script": "validate_browser_ci_persona.py",          "args": [], "label": "FB2 Browser-CI Multi-Persona Live Floor Ratchet (every page walked HEADLESS as field-tech/supervisor/new-worker/admin = role x viewport x hive; the persona-delta live floor - per-persona runtime/security/serious-a11y breakage a single-identity sweep can't see - never falls + every persona's sign-in holds; reads browser_ci_persona_board.json vs baseline; full re-drive = node tools/browser_ci_persona_walk.mjs --accept)", "group": "Forward-Build", "report": "browser_ci_persona_check_report.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "fb4-grounding-eval",           "script": os.path.join("tools", "fb4_grounding_eval.py"), "args": ["--accept"], "label": "FB4 Live-LLM Grounding/Fabrication Eval (invokes the served LLM edge fns with DIVERSE ASKER PERSONAS - earnest/edge-case/adversarial-injection/Tagalog - and grades answer-named asset-tags subset-of the hive DB truth = no fabrication; adversarial must not leak a secret; Tagalog must still get a grounded answer; free-tier $0 single invokes; forward-only pass ratchet vs fb4_grounding_baseline.json)", "group": "Forward-Build", "report": "fb4_grounding_results.json", "skip_if_fast": True, "severity": "regression", "parallel_safe": False},
    {"id": "mine-rls-policies",            "script": os.path.join("tools", "mine_rls_policies.py"), "args": [], "label": "RLS Policy Substrate Miner (L-1.5: USING(true) / WITH CHECK(true) / missing TO clause)",                     "group": "P1 Roadmap", "report": "rls_policy_mining_report.json",            "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    {"id": "mine-cache-name-drift",        "script": os.path.join("tools", "mine_cache_name_drift.py"), "args": [], "label": "Cache-Name Drift Miner (L-1: SHELL_FILEs committed after sw.js — bump CACHE_NAME warning)",            "group": "P1 Roadmap", "report": "cache_name_drift_report.json",             "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    # `report` corrected from `rls_policy_mining_report.json` to this gate's OWN artifact. It only READS the
    # mining report (validate_rls_strict.py:39 FAILs if that file is absent and tells you to run the miner
    # first) and writes `rls_strict_baseline.json` itself. Declaring the producer's file made two gates claim
    # one artifact and described the data flow backwards — caught by the registry check added below in main().
    {"id": "rls-strict",                   "script": "validate_rls_strict.py",                   "args": [], "label": "RLS Strict Baseline (L0 ratchet over mine_rls_policies: USING(true) + WITH CHECK(true) frozen at baseline)",         "group": "P1 Roadmap", "report": "rls_strict_baseline.json",                 "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "envelope-return-shape",        "script": "validate_envelope_return_shape.py",        "args": [], "label": "Envelope Return-Shape Adoption (true adoption: fns that actually call ok(ctx, ...); floor ratchet)",                 "group": "P1 Roadmap", "report": "envelope_return_shape_report.json",        "skip_if_fast": False, "severity": "warn",       "parallel_safe": True},
    {"id": "mine-capacity-signals",        "script": os.path.join("tools", "mine_capacity_signals.py"), "args": [], "label": "Capacity-Signals Miner (LB G-1.5: realtime channel/subscribe/teardown + unbounded select shape)",          "group": "Maturity P1", "report": "capacity_signals_report.json",            "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    {"id": "connection-surface-discovery", "script": "validate_connection_surface_discovery.py", "args": [], "label": "Connection-Surface Discovery (LB G-1: every subscribing surface registered + budgeted)",                    "group": "Maturity P1", "report": "connection_surface_discovery_report.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "connection-pool-saturation",   "script": "validate_connection_pool_saturation.py",   "args": [], "label": "Connection-Pool Saturation Ratchet (LB GH: leak surfaces frozen at 0 + surface count + alarm declared)",   "group": "Maturity P1", "report": "connection_pool_saturation_report.json",   "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "load-resilience",              "script": "validate_load_resilience.py",              "args": [], "label": "Load-Resilience Sentinel (LB GS: load_probe + LOAD-SLO + DEGRADED-MODE + 429/503 graceful degrade)",       "group": "Maturity P1", "report": "load_resilience_report.json",              "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "mine-health-surface",          "script": os.path.join("tools", "mine_health_surface.py"), "args": [], "label": "Health-Surface Miner (AV G-1.5: /health coverage shape across all edge fns)",                            "group": "Maturity P1", "report": "health_surface_report.json",               "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    {"id": "health-surface-discovery",     "script": "validate_health_surface_discovery.py",     "args": [], "label": "Health-Surface Discovery (AV G-1: count of fns without /health frozen at baseline — new health-less fn FAILs)", "group": "Maturity P1", "report": "health_surface_discovery_report.json",     "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "game-day-readiness",           "script": "validate_game_day_readiness.py",           "args": [], "label": "Game-Day Readiness (AV GH: game_day + verify_backups + RTO/RPO + rollback runbook + SLO all present)",       "group": "Maturity P1", "report": "game_day_readiness_report.json",           "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "mine-cache-signals",           "script": os.path.join("tools", "mine_cache_signals.py"), "args": [], "label": "Cache-Signals Miner (CA G-1.5: CDN _headers + LLM cached() adopters + SW shell precache shape)",                "group": "Maturity P2", "report": "cache_signals_report.json",                "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    {"id": "mine-rate-limit-signals",      "script": os.path.join("tools", "mine_rate_limit_signals.py"), "args": [], "label": "Rate-Limit-Signals Miner (RL G-1.5: per-fn rate-limit primitives + verifiedHiveId bucketing-key shape)",  "group": "Maturity P2", "report": "rate_limit_signals_report.json",          "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    {"id": "cache-hit-rate",               "script": "validate_cache_hit_rate.py",               "args": [], "label": "Cache Efficiency Ratchet (CA GH: CDN Cache-Control rules present + LLM cached() adopter floor)",                     "group": "Maturity P2", "report": "cache_hit_rate_report.json",               "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "rate-limit-fairness",          "script": "validate_rate_limit_fairness.py",          "args": [], "label": "Rate-Limit Fairness Sentinel (RL GS: no fn buckets on a spoofable client hive_id; latent ratchet; keystone fair)", "group": "Maturity P2", "report": "rate_limit_fairness_report.json",          "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "mine-deploy-signals",          "script": os.path.join("tools", "mine_deploy_signals.py"), "args": [], "label": "Deploy-Signals Miner (H G-1.5: edge fn registration/deploy coverage + rollback/pre-deploy presence)",          "group": "Maturity P3", "report": "deploy_signals_report.json",               "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    {"id": "mine-ci-signals",              "script": os.path.join("tools", "mine_ci_signals.py"), "args": [], "label": "CI-Signals Miner (CI G-1.5: workflow count/triggers + gate-running + .tool-versions pin)",                     "group": "Maturity P3", "report": "ci_signals_report.json",                   "skip_if_fast": False, "severity": "info",       "parallel_safe": True},
    {"id": "deploy-safety",                "script": "validate_deploy_safety.py",                "args": [], "label": "Deploy-Safety Sentinel (H GS: rollback runbook + pre-deploy gate + undeployed-fn ratchet)",                  "group": "Maturity P3", "report": "deploy_safety_report.json",                "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "ci-gate-sentinel",             "script": "validate_ci_gate_sentinel.py",             "args": [], "label": "CI-Gate Sentinel (CI GS: local ci_gate + a workflow runs the gate + reproducible pin + wired trigger)",     "group": "Maturity P3", "report": "ci_gate_sentinel_report.json",             "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "log-surface-discovery",        "script": "validate_log_surface_discovery.py",        "args": [], "label": "Log-Surface Discovery (L G-1: count of fns logging raw console.* without logger.ts frozen at baseline)",     "group": "Maturity P3", "report": "log_surface_discovery_report.json",        "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "log-correlation",              "script": "validate_log_correlation_sentinel.py",     "args": [], "label": "Log-Correlation Sentinel (L GS: structured logger + trace_id correlation + JSON + trace-store aggregation)",  "group": "Maturity P3", "report": "log_correlation_report.json",              "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "openapi-sync",                 "script": "validate_openapi_sync.py",                 "args": [], "label": "OpenAPI Sync (A capability: openapi.json covers every edge fn in ALL_FUNCTIONS, no ghost routes; re-run tools/gen_openapi.py on drift)", "group": "Maturity P4", "report": "openapi_sync_report.json",                 "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "sast-scan",                    "script": os.path.join("tools", "sast_scan.py"), "args": [], "label": "SAST Posture (S capability: every OWASP Top-10 category has an automated scanner; aggregates the 12 security validators)", "group": "Maturity P4", "report": "sast_report.json",                          "skip_if_fast": True,  "severity": "regression", "parallel_safe": True},
    {"id": "layer-depth",                  "script": os.path.join("tools", "measure_layer_depth.py"), "args": [], "label": "Layer sub-discipline COVERAGE (A7.4 §14.5: 99-item rubric checklist across 13 layers; forward-only ratchet — a layer losing validator/tool evidence FAILs. Measures presence-of-mechanism = upper bound on true-scope depth, NOT depth)", "group": "Maturity P4", "report": "layer_depth.json",        "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "gateway-bypass",               "script": os.path.join("tools", "validate_gateway_bypass.py"), "args": [], "label": "Gateway-axis MEASURED (G2 §14.6: derives each layer's PEP-chokepoint grade from REAL bypass reports — gateway_coverage/tenancy/policy-hive-binding/canonical-sources/kpi-canonical; forward-only on bypass count. 7/13 measured; data-gateway bypass = G1 target → 0)", "group": "Maturity P4", "report": "gateway_bypass.json",  "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "gateway-gate-depth",           "script": os.path.join("tools", "measure_gateway_gate.py"), "args": [], "label": "HONEST per-layer depth (§14.6: Gateway PEP × Gate ratchet × Prod-real, 13 layers; forward-only composite ratchet. Stricter than the 13x6 matrix + coverage — requires a PREVENTION chokepoint + prod-real, not detection/local-substitute. Overall 64.1%; Gateway axis 7.5/13 = the frontier, now 7 grades instrument-backed via gateway-bypass)", "group": "Maturity P4", "report": "gateway_gate_depth.json", "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {"id": "memento-catalog-citations",    "script": os.path.join("tools", "memento_catalog_citation_validator.py"), "args": [], "label": "Memento Pattern-Catalog Citation Rot (reference_pattern_catalog.md citations all resolve on disk or via the index)", "group": "Platform",   "report": None,                                          "skip_if_fast": False, "severity": "regression", "parallel_safe": True},
    {
        "id":      "visual_defect_confidence",
        "script":  "tools/validate_visual_defect_confidence.py",
        "args":    [],
        "label":   "AI Self-Improvement: Visual Defect Confidence",
        "group":   "AI Validation",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        "id":      "perf-scale",
        "script":  "validate_perf_scale.py",
        "args":    [],
        "label":   "Arc L Performance & Scale ratchet (forward-only: S/E/R/B pass-counts >= locked baseline; floors S90/E85/R85/B95)",
        "group":   "Arc L",
        "report":  None,
        "skip_if_fast": False,
        "severity": "regression",
        "parallel_safe": True,
    },
]

PYTHON_API_URL  = "https://engineering-calc-api.onrender.com/calculate"
SUPABASE_URL    = "https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/engineering-calc-agent"


# ── Run one validator ─────────────────────────────────────────────────────────
VALIDATOR_TIMEOUT_SECONDS = 1200  # per-validator hard cap; hung child gets SIGTERM
# 2026-05-24: bumped 300 -> 600 -> 1200. Phantom capture + phantom column
# auditors do O(captures x blobs) and O(columns x blobs) cross-products,
# which grow superlinearly with the codebase. Under gate concurrency they
# slow markedly: phantom_captures hit 347.9s (was 300+ killed), phantom_columns
# hit 600.1s (was killed at 600s ceiling). Standalone each finishes in 4-5 min.
# Bumping the cap to 1200s gives 2x headroom for future growth without losing
# the hung-child safety net. If a validator legitimately needs longer, that's
# the signal to refactor it (index by tail-N bytes / parallelize tables).


def run_validator(v):
    if not os.path.exists(v["script"]):
        return {"status": "ERROR", "reason": f"Script not found: {v['script']}", "output": ""}

    cmd = [PYTHON, v["script"]] + v["args"]
    t0  = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=VALIDATOR_TIMEOUT_SECONDS,
        )
        elapsed = round(time.time() - t0, 1)
        stdout  = (result.stdout or "") + (result.stderr or "")
        status  = "PASS" if result.returncode == 0 else "FAIL"
        return {"status": status, "output": stdout, "elapsed": elapsed}
    except subprocess.TimeoutExpired as ex:
        # Child has been killed by subprocess.run. Capture whatever it
        # wrote before the timeout so we can see where it hung.
        elapsed = round(time.time() - t0, 1)
        partial = (ex.stdout or "") + (ex.stderr or "")
        return {
            "status":  "FAIL",
            "reason":  f"hung; killed after {VALIDATOR_TIMEOUT_SECONDS}s",
            "output":  partial + f"\n[TIMEOUT — killed after {VALIDATOR_TIMEOUT_SECONDS}s]",
            "elapsed": elapsed,
        }
    except Exception as ex:
        return {"status": "ERROR", "reason": str(ex), "output": "", "elapsed": 0}


# ── Readiness Gate ─────────────────────────────────────────────────────────────
def check_git_clean():
    try:
        r = subprocess.run(
            ["git", "status", "--short"],
            capture_output=True, text=True
        )
        lines = [l for l in r.stdout.strip().splitlines()
                 if not l.startswith("??")]  # ignore untracked
        return len(lines) == 0, lines[:5]
    except Exception as ex:
        return None, [str(ex)]


def check_api(url, payload, label):
    try:
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200, f"HTTP {r.status}"
    except Exception as ex:
        return False, str(ex)[:80]


def run_readiness_gate():
    gate = {}

    # Git clean
    clean, dirty = check_git_clean()
    if clean is None:
        gate["git"] = {"status": "WARN", "detail": "git not available"}
    elif clean:
        gate["git"] = {"status": "PASS", "detail": "working tree clean"}
    else:
        gate["git"] = {"status": "WARN", "detail": f"{len(dirty)} uncommitted file(s)", "files": dirty}

    if not FAST:
        # Python API live
        ok, detail = check_api(
            PYTHON_API_URL,
            {"calc_type": "Pump Sizing (TDH)", "inputs": {"flow_rate": 10, "static_head": 20}},
            "Python API"
        )
        gate["python_api"] = {"status": "PASS" if ok else "FAIL", "detail": detail}

        # Supabase edge function live
        try:
            req = urllib.request.Request(
                SUPABASE_URL, method="OPTIONS",
                headers={"Origin": "https://workhiveph.com",
                         "Access-Control-Request-Method": "POST"}
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                ok2 = r.status == 200
        except Exception as ex:
            ok2 = False
            detail = str(ex)[:80]
        gate["supabase"] = {"status": "PASS" if ok2 else "WARN", "detail": "OPTIONS 200" if ok2 else detail}
    else:
        gate["python_api"] = {"status": "SKIP", "detail": "--fast mode"}
        gate["supabase"]   = {"status": "SKIP", "detail": "--fast mode"}

    return gate


# ── Baseline comparison ───────────────────────────────────────────────────────
def load_baseline():
    if not os.path.exists(BASELINE_FILE):
        return None
    try:
        with open(BASELINE_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def save_baseline(results, gate):
    baseline = {
        "timestamp":  datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "validators": {v["id"]: r["status"] for v, r in results},
        "readiness":  {k: v["status"] for k, v in gate.items()},
    }
    with open(BASELINE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)


def detect_regressions(results, baseline):
    if not baseline:
        return []
    regressions = []
    for v, r in results:
        prev = baseline.get("validators", {}).get(v["id"])
        curr = r["status"]
        if prev in ("PASS",) and curr == "FAIL":
            regressions.append({
                "id": v["id"], "label": v["label"],
                "was": prev, "now": curr,
            })
    return regressions


# ── Print helpers ─────────────────────────────────────────────────────────────
def status_icon(s):
    return {
        "PASS":  green("PASS"),
        "FAIL":  red("FAIL"),
        "WARN":  yellow("WARN"),
        "SKIP":  cyan("SKIP"),
        "ERROR": red("ERR "),
    }.get(s, s)


def divider(char="=", width=72):
    print(char * width)


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    start_time = time.time()
    now_str    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    divider()
    print(bold("  WorkHive Platform Guardian"))
    print(f"  {now_str}  |  {'FAST mode (skip live API)' if FAST else 'Full mode'}  |  Python {sys.version.split()[0]}")
    divider()

    # THE REGISTRY CHECKS ITSELF FIRST. Nothing asserted that a gate `id` appears once, and three had been
    # registered TWICE (`memory-integrity`, `companion-page-coverage`, `companion-source-coverage`): each ran
    # its script twice every suite for no extra assertion, the gate count was overstated by three, and the
    # duplicate `memory-integrity` label falsely claimed RLS/index/retention coverage that no check performs.
    # An id is the key that results, baselines and ratchets are stored under, so two gates sharing one can
    # overwrite each other's floor — the failure would show up as a ratchet that mysteriously stopped holding.
    # Printed and fatal, because a registry that cannot be trusted makes every number below it unreliable.
    _seen, _dupes = set(), []
    for _v in VALIDATORS:
        _id = _v.get("id")
        (_dupes.append(_id) if _id in _seen else _seen.add(_id))
    if _dupes:
        print(red(f"\n  REGISTRY ERROR — duplicate gate id(s): {', '.join(sorted(set(_dupes)))}"))
        print("  An id is the key results/baselines/ratchets are stored under; two entries sharing one can")
        print("  silently overwrite each other. Give each gate a unique id, or delete the redundant entry.")
        return 1

    # Two more properties in the SAME class as the duplicate id, both cheap and both previously unchecked.
    #
    # A script that does not resolve currently fails only WHEN THE GATE RUNS, which in --fast mode a
    # skip_if_fast gate never does: a typo'd path could sit green for weeks. Checked up front instead.
    #
    # A `report` filename shared by two gates means the second overwrites the first's artifact. The one
    # instance found was a MISLABEL rather than a clash — `rls-strict` declared the report that
    # `mine-rls-policies` produces, because it READS that file and writes its own baseline. Same lesson as
    # the id collision: the field means "the artifact this gate emits", and a consumer claiming a producer's
    # output makes the registry describe a data flow that does not exist.
    _bad_script = [(v.get("id"), v.get("script")) for v in VALIDATORS
                   if v.get("script") and not os.path.exists(v["script"])]
    if _bad_script:
        print(red(f"\n  REGISTRY ERROR — {len(_bad_script)} gate(s) point at a script that does not exist:"))
        for _i, _s in _bad_script[:6]:
            print(f"    {_i} -> {_s}")
        print("  A missing script only fails when the gate RUNS, and a skip_if_fast gate never runs in")
        print("  --fast mode — so this would sit green until a full run happened to reach it.")
        return 1

    _rep = {}
    for _v in VALIDATORS:
        if _v.get("report"):
            _rep.setdefault(_v["report"], []).append(_v.get("id"))
    _rep_dupes = {k: ids for k, ids in _rep.items() if len(ids) > 1}
    if _rep_dupes:
        print(red("\n  REGISTRY ERROR — a report artifact is claimed by more than one gate:"))
        for _k, _ids in sorted(_rep_dupes.items()):
            print(f"    {_k} <- {', '.join(_ids)}")
        print("  Whichever gate runs second overwrites the first's artifact. If one gate only READS the")
        print("  file, it should not declare it as its report — that field is what the gate EMITS.")
        return 1

    # A declared `report` that the gate never writes is a FICTIONAL pointer. It reads as "this gate leaves an
    # artifact you can inspect", and following it finds nothing — which is how the `rls-strict` entry misled me
    # into thinking it produced the RLS mining report when it only READS it. Measured rather than assumed: 25
    # of the 394 gates that declare a report have a script containing no report-writing code at all, and most
    # of those files do not exist on disk. That is pre-existing metadata debt, not a regression, so it is a
    # FORWARD-ONLY ceiling: the count is printed every run and only a RISE fails. Cleaning it up lowers the
    # ceiling; nothing forces 25 fixes today to land one new gate.
    _FICTIONAL_REPORT_CEILING = 25
    _fiction = []
    for _v in VALIDATORS:
        _rep, _scr = _v.get("report"), _v.get("script")
        if not _rep or not _scr or not os.path.exists(_scr):
            continue
        try:
            _src = open(_scr, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if os.path.basename(_rep) not in _src:
            _fiction.append(f"{_v.get('id')}->{os.path.basename(_rep)}")
    if len(_fiction) > _FICTIONAL_REPORT_CEILING:
        print(red(f"\n  REGISTRY ERROR — {len(_fiction)} gates declare a `report` their script never writes "
                  f"(ceiling {_FICTIONAL_REPORT_CEILING}). New offenders:"))
        for _f in _fiction[_FICTIONAL_REPORT_CEILING:]:
            print(f"    {_f}")
        print("  A report nobody writes is a pointer to nothing. Either write the artifact or drop the field.")
        return 1
    print(f"  {len(VALIDATORS)} gates registered · ids unique · scripts resolve · reports unclaimed twice · "
          f"{len(_fiction)}/{_FICTIONAL_REPORT_CEILING} unwritten report declarations (forward-only)")

    baseline = load_baseline()
    if baseline:
        base_time = baseline.get("timestamp", "?")[:16].replace("T", " ")
        print(f"\n  Baseline loaded from {base_time}")
    else:
        print("\n  No baseline found — this run will create one if all pass.")

    # ── GATE ONLY MODE ────────────────────────────────────────────────────────
    if GATE:
        print("\n" + cyan("  READINESS GATE ONLY") + "\n")
        gate = run_readiness_gate()
        for key, v in gate.items():
            print(f"  {status_icon(v['status'])}  {key:20s}  {v['detail']}")
        divider()
        all_ok = all(v["status"] in ("PASS", "WARN", "SKIP") for v in gate.values())
        print(f"\n  {'READY' if all_ok else 'BLOCKED'}\n")
        return 0 if all_ok else 3

    # ── LOOP 1: RUN ALL VALIDATORS ────────────────────────────────────────────
    results    = []
    group_seen = set()

    for v in VALIDATORS:
        if FAST and v.get("skip_if_fast"):
            results.append((v, {"status": "SKIP", "output": "--fast", "elapsed": 0}))
            continue

        if v["group"] not in group_seen:
            group_seen.add(v["group"])
            print(f"\n  {cyan(v['group'].upper())}")
            print("  " + "-" * 68)

        print(f"  {'RUN ':4s}  {v['label']:52s}", end="", flush=True)
        t0 = time.time()
        r  = run_validator(v)
        elapsed = r.get("elapsed", round(time.time() - t0, 1))
        print(f"  {status_icon(r['status'])}  {elapsed:4.1f}s")
        results.append((v, r))

    # ── LOOP 0: REGRESSION DETECTION ─────────────────────────────────────────
    regressions = detect_regressions(results, baseline)

    # ── LOOP 3: READINESS GATE ────────────────────────────────────────────────
    print(f"\n  {cyan('READINESS GATE')}")
    print("  " + "-" * 68)
    gate = run_readiness_gate()
    for key, v in gate.items():
        label = {"git": "Git working tree", "python_api": "Python API (Render)", "supabase": "Supabase edge function"}
        print(f"  {status_icon(v['status'])}  {label.get(key, key):38s}  {v['detail']}")

    # ── LOOP 4: IMPROVEMENT BACKLOG SUMMARY ───────────────────────────────────
    try:
        import json as _json
        if os.path.exists("improvement_backlog.json"):
            with open("improvement_backlog.json", encoding="utf-8") as _f:
                _bl = _json.load(_f)
            _high  = sum(1 for i in _bl if i.get("priority") == "HIGH"   and i.get("score", 0) >= 30)
            _eb    = sum(1 for i in _bl if i.get("business_value") == "enterprise_blocker" and i.get("score", 0) >= 30)
            if _high > 0:
                print(f"  {yellow('WARN')}  {'Improvement backlog':38s}  {_high} HIGH item(s)  {_eb} enterprise blocker(s) — run python improve.py")
    except Exception:
        pass

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    pass_count = sum(1 for _, r in results if r["status"] == "PASS")
    fail_count = sum(1 for _, r in results if r["status"] == "FAIL")
    skip_count = sum(1 for _, r in results if r["status"] == "SKIP")
    warn_count = sum(1 for _, r in results if r["status"] == "WARN")
    total_time = round(time.time() - start_time, 1)

    gate_blocked = any(v["status"] == "FAIL" for v in gate.values())

    print(f"\n  {'FAILURES' if fail_count else 'ALL PASS'}")
    print("  " + "-" * 68)
    for v, r in results:
        if r["status"] == "FAIL":
            print(f"  {red('FAIL')}  {v['label']}")
            # Show first few lines of output
            for line in r["output"].strip().splitlines():
                if "FAIL" in line or "CRITICAL" in line or "missing" in line.lower():
                    print(f"         {line.strip()[:70]}")
                    break

    if regressions:
        print(f"\n  {red('REGRESSIONS DETECTED')} (was PASS, now FAIL):")
        for reg in regressions:
            print(f"  {red('REG')}  {reg['label']}")

    divider()
    status_line = (
        red("BLOCKED — fix failures before deploying")
        if fail_count or regressions
        else yellow("READY (review WARNs)")
        if warn_count or gate_blocked
        else green("READY — safe to deploy")
    )
    print(f"\n  {bold(status_line)}")
    print(f"  {pass_count} PASS  {fail_count} FAIL  {warn_count} WARN  {skip_count} SKIP  |  {total_time}s total\n")

    # ── WRITE platform_health.json ────────────────────────────────────────────
    # Preserve improvement_backlog from previous improve.py run
    # (run_platform_checks.py rewrites health but must not wipe the backlog)
    preserved_backlog = None
    if os.path.exists(HEALTH_FILE):
        try:
            with open(HEALTH_FILE, encoding="utf-8") as _hf:
                _prev = json.load(_hf)
            preserved_backlog = _prev.get("improvement_backlog")
        except Exception:
            pass
    # Also read directly from improvement_backlog.json if health doesn't have it
    if not preserved_backlog and os.path.exists("improvement_backlog.json"):
        try:
            with open("improvement_backlog.json", encoding="utf-8") as _bf:
                _bl = json.load(_bf)
            _h  = sum(1 for i in _bl if i.get("priority") == "HIGH"   and i.get("score", 0) >= 30)
            _m  = sum(1 for i in _bl if i.get("priority") == "MEDIUM" and i.get("score", 0) >= 20)
            _lo = sum(1 for i in _bl if i.get("priority") == "LOW")
            _eb = sum(1 for i in _bl if i.get("business_value") == "enterprise_blocker" and i.get("score", 0) >= 30)
            _lu = _bl[-1].get("checked_at", "") if _bl else ""
            preserved_backlog = {
                "total": len(_bl), "high": _h, "medium": _m, "low": _lo,
                "enterprise_blockers": _eb, "last_updated": _lu,
            }
        except Exception:
            pass

    health = {
        "timestamp":    datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode":         "fast" if FAST else "full",
        "overall":      "FAIL" if (fail_count or regressions) else "WARN" if warn_count else "PASS",
        "summary":      {"pass": pass_count, "fail": fail_count, "warn": warn_count, "skip": skip_count},
        "duration_s":   total_time,
        "validators":   [
            {
                "id":      v["id"],
                "label":   v["label"],
                "group":   v["group"],
                "status":  r["status"],
                "elapsed": r.get("elapsed", 0),
                "report":  v.get("report"),   # optional — runtime-discovered validators (calc-suite auto-discovery) omit it
            }
            for v, r in results
        ],
        "regressions":  regressions,
        "readiness":    gate,
        "baseline_ref": baseline.get("timestamp", None) if baseline else None,
    }
    if preserved_backlog:
        health["improvement_backlog"] = preserved_backlog

    with open(HEALTH_FILE, "w") as f:
        json.dump(health, f, indent=2)
    print(f"  Saved {HEALTH_FILE}")

    # Save baseline only when everything passes
    if fail_count == 0 and not regressions:
        save_baseline(results, gate)
        print(f"  Saved {BASELINE_FILE} (new clean baseline)\n")

    # ── EXIT CODE ─────────────────────────────────────────────────────────────
    # ── AUTO-FIX (optional) ───────────────────────────────────────────────────
    if AUTOFIX and fail_count:
        print(f"\n  {cyan('AUTO-FIX')}\n  {'—' * 68}")
        af_result = subprocess.run(
            [PYTHON, "autofix.py"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace"
        )
        af_out = (af_result.stdout or "") + (af_result.stderr or "")
        for line in af_out.strip().splitlines():
            if any(w in line for w in ["FIXED", "SKIP", "ERROR", "fixed", "error"]):
                print(f"  {line.strip()[:70]}")
        af_fixed = sum(1 for l in af_out.splitlines() if "FIXED" in l)
        if af_fixed:
            print(f"\n  {af_fixed} auto-fix(es) applied — re-run to verify:")
            print(f"  python run_platform_checks.py --fast\n")

    if regressions:
        return 2
    if fail_count:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
