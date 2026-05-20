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
    },
    {
        "id":      "tester-coverage",
        "script":  "validate_tester_coverage.py",
        "args":    [],
        "label":   "Tester Coverage Validator (every live tool page is in PUBLIC_PAGES + 4 flow PAGES lists)",
        "group":   "Platform",
        "report":  "tester_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "schema-coverage",
        "script":  "validate_schema_coverage.py",
        "args":    [],
        "label":   "Schema Coverage Validator (auto-derived from migrations, table+column existence)",
        "group":   "Platform",
        "report":  "schema_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "reset-coverage",
        "script":  "validate_reset_coverage.py",
        "args":    [],
        "label":   "Reset Coverage Validator (every migration table is in reset.py)",
        "group":   "Platform",
        "report":  "reset_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "edge-config",
        "script":  "validate_edge_config.py",
        "args":    [],
        "label":   "Edge Function Config Validator (config.toml coverage)",
        "group":   "Platform",
        "report":  "edge_config_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "cross-page",
        "script":  "validate_cross_page.py",
        "args":    [],
        "label":   "Cross-Page Flow Validator",
        "group":   "Platform",
        "report":  "cross_page_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "dom-refs",
        "script":  "validate_dom_refs.py",
        "args":    [],
        "label":   "DOM Reference Integrity Validator (bare getElementById on missing elements)",
        "group":   "Platform",
        "report":  "dom_refs_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "asset-brain",
        "script":  "validate_asset_brain.py",
        "args":    [],
        "label":   "Asset Brain Foundation Validator (schema, RLS, realtime publication)",
        "group":   "Platform",
        "report":  "asset_brain_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "canonical-sources",
        "script":  "validate_canonical_sources.py",
        "args":    [],
        "label":   "Canonical Sources Registry Validator (truth-scattering fix foundation + L2 drift detection)",
        "group":   "Platform",
        "report":  "canonical_sources_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "kpi-chip-coverage",
        "script":  "validate_kpi_chip_coverage.py",
        "args":    [],
        "label":   "KPI Chip Coverage Validator (pages reading v_*_truth must render renderSourceChip)",
        "group":   "Platform",
        "report":  "kpi_chip_coverage_report.json",
        "skip_if_fast": False,
    },
    {
        "id":      "calm-canonical-audit",
        "script":  "tools/audit_calm_dashboard_canonical.py",
        "args":    [],
        "label":   "Calm Dashboard Canonical-Wiring Audit (per-tile classify: canonical/drift/gap/allowed)",
        "group":   "Platform",
        "report":  "calm_canonical_audit_report.json",
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
        # fallback in Rosa's voice command UI.
        "id":      "legacy-worker-decommission",
        "script":  "validate_legacy_worker_decommission.py",
        "args":    [],
        "label":   "Legacy Worker Decommission Validator (no production JS calls workhive-assistant.workers.dev)",
        "group":   "Platform",
        "report":  None,
        "skip_if_fast": False,
    },
    {
        # 2026-05-19 Hardening Loop for the Rosa-offline incident (f5a8d99):
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
        "label":   "Service-Role Key Exposure (4-layer: service_role identifier + JWT in client + secret env + anon-key inventory)",
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
    {
        "id":      "memory-integrity",
        "script":  "validate_memory_integrity.py",
        "args":    [],
        "label":   "Agent Memory Integrity (4-layer: schema + RLS + index + retention)",
        "group":   "Platform",
        "report":  "memory_integrity_report.json",
        "skip_if_fast": False,
    },
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
        "id":      "admin-gates",
        "script":  "validate_admin_gates.py",
        "args":    [],
        "label":   "Admin Gate Enforcement (founder-console, marketplace-admin, platform-health must verify admin)",
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
        "label":   "AI Prompt Regression Validator",
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
]

PYTHON_API_URL  = "https://engineering-calc-api.onrender.com/calculate"
SUPABASE_URL    = "https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/engineering-calc-agent"


# ── Run one validator ─────────────────────────────────────────────────────────
VALIDATOR_TIMEOUT_SECONDS = 300  # per-validator hard cap; hung child gets SIGTERM


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
                "report":  v["report"],
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
