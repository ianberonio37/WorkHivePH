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
]

PYTHON_API_URL  = "https://engineering-calc-api.onrender.com/calculate"
SUPABASE_URL    = "https://hzyvnjtisfgbksicrouu.supabase.co/functions/v1/engineering-calc-agent"


# ── Run one validator ─────────────────────────────────────────────────────────
def run_validator(v):
    if not os.path.exists(v["script"]):
        return {"status": "ERROR", "reason": f"Script not found: {v['script']}", "output": ""}

    cmd = [PYTHON, v["script"]] + v["args"]
    t0  = time.time()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        elapsed = round(time.time() - t0, 1)
        stdout  = (result.stdout or "") + (result.stderr or "")
        status  = "PASS" if result.returncode == 0 else "FAIL"
        return {"status": status, "output": stdout, "elapsed": elapsed}
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
