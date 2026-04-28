"""
Analytics Engine Validator — WorkHive Platform
===============================================
Four-layer validation of the Stage 3 Analytics Engine:

  Layer 1 — Pattern checks (structural rules)
    1.  WORKER_NAME auth gate         — redirect to sign-in if unauthenticated
    2.  HIVE_ID sent in fetch body    — tenant isolation requirement
    3.  escHtml on error output       — XSS protection in error rendering
    4.  PHASE_BANNERS completeness    — all 4 phases defined for UI labels
    5.  Double-submit guard           — _loading flag prevents parallel requests
    6.  analytics-orchestrator ref    — correct edge function endpoint
    7.  All 4 render functions        — renderDescriptive/Diagnostic/Predictive/Prescriptive
    8.  Toast on error                — user-visible error feedback
    9.  All 4 phases in edge function — phase === "descriptive|..." handled
    10. Logbook hive_id scope         — tenant isolation on logbook queries
    11. Inventory hive_id scope       — tenant isolation on inventory queries
    12. Groq fallback chain           — 2+ models for resilience
    13. GROQ_API_KEY null guard       — graceful degradation when key missing
    14. PYTHON_API_URL null guard     — structured error when Python API unconfigured
    15. AbortSignal.timeout           — prevents hanging on cold-start
    16. Missing phase returns 400     — input validation
    17. All 4 analytics modules exist — descriptive / diagnostic / predictive / prescriptive
    18. calculate() entry in each     — correct function signature
    19. All 8 SMRP/ISO metrics        — calc_mtbf through calc_repeat_failures
    20. Availability formula correct  — MTBF / (MTBF + MTTR)
    21. All 4 phases routed in main   — /analytics endpoint handles all phases
    22. HTTP 404 for unknown phase    — graceful rejection in main.py

  Layer 2 — Syntax checks
    23. Python syntax clean           — py_compile on all 5 analytics .py files

  Layer 3 — Smoke tests (actually runs the code)
    24. Smoke: descriptive.calculate({})   — runs without crash on empty input
    25. Smoke: diagnostic.calculate({})    — runs without crash on empty input
    26. Smoke: predictive.calculate({})    — runs without crash on empty input
    27. Smoke: prescriptive.calculate({})  — runs without crash on empty input

  Layer 4 — Output shape + consistency
    28. Shape: descriptive result     — all 8 metric keys + sub-keys present
    29. Period default consistency     — period_days=90 consistent across HTML/edge/Python

Usage:  python validate_analytics.py
Output: analytics_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import (
    read_file, compile_check, smoke_test, check_shape,
    extract_js_object_keys, format_result
)

BASE            = os.path.dirname(os.path.abspath(__file__))
PYTHON_API_DIR  = os.path.join(BASE, "python-api")

HTML_FILE       = "analytics.html"
EDGE_FUNC_FILE  = os.path.join("supabase", "functions", "analytics-orchestrator", "index.ts")
DESCRIPTIVE_PY  = os.path.join("python-api", "analytics", "descriptive.py")
DIAGNOSTIC_PY   = os.path.join("python-api", "analytics", "diagnostic.py")
PREDICTIVE_PY   = os.path.join("python-api", "analytics", "predictive.py")
PRESCRIPTIVE_PY = os.path.join("python-api", "analytics", "prescriptive.py")
MAIN_PY         = os.path.join("python-api", "main.py")

ALL_PHASES = ["descriptive", "diagnostic", "predictive", "prescriptive"]

DESCRIPTIVE_FUNCTIONS = [
    "calc_mtbf", "calc_mttr", "calc_availability", "calc_pm_compliance",
    "calc_failure_frequency", "calc_downtime_pareto",
    "calc_parts_consumption", "calc_repeat_failures",
]

# Minimal empty inputs for each phase (tests graceful empty-data handling)
SMOKE_INPUTS = {
    "descriptive": {
        "logbook_entries": [], "pm_completions": [],
        "pm_scope_items": [], "inv_transactions": [], "period_days": 90,
    },
    "diagnostic": {
        "logbook_entries": [], "pm_completions": [], "pm_scope_items": [],
        "inv_transactions": [], "skill_badges": [],
        "engineering_calcs": [], "period_days": 90,
    },
    "predictive": {
        "logbook_entries": [], "pm_completions": [], "pm_scope_items": [],
        "inv_transactions": [], "inventory_items": [], "period_days": 90,
    },
    "prescriptive": {
        "logbook_entries": [], "pm_completions": [], "pm_scope_items": [],
        "inv_transactions": [], "inventory_items": [], "skill_badges": [],
        "pm_assets": [], "period_days": 90,
    },
}

# Expected output shape for descriptive phase (includes new OEE key)
DESCRIPTIVE_SHAPE = {
    "phase":             [],
    "standard":          [],
    "period_days":       [],
    "mtbf":              ["mtbf_by_asset", "unit", "standard"],
    "mttr":              ["mttr_by_asset", "unit", "standard"],
    "availability":      ["availability_by_asset", "unit", "standard"],
    "oee":               ["oee_by_asset", "standard"],
    "pm_compliance":     ["compliance_by_asset", "standard"],
    "failure_frequency": ["failure_frequency", "period_days", "standard"],
    "downtime_pareto":   ["pareto"],
    "parts_consumption": ["consumption", "period_days", "standard"],
    "repeat_failures":   ["repeats", "standard"],
}

# New logbook fields that must be fetched in the edge function SELECT
NEW_LOGBOOK_FIELDS = ["failure_consequence", "readings_json", "production_output"]

# New render functions added for the new analytics features
NEW_RENDER_FUNCTIONS = ["renderOEE", "renderRCMConsequence", "renderAnomalyBaseline"]


# ── Layer 1: Pattern checks (HTML frontend) ───────────────────────────────────

def check_html_auth_gate(html, page):
    if not html:
        return [{"check": "auth_gate", "page": page, "reason": f"{page} not found"}]
    if "window.location.href = 'index.html?signin=1'" not in html and \
       'window.location.href = "index.html?signin=1"' not in html:
        return [{"check": "auth_gate", "page": page,
                 "reason": "WORKER_NAME auth gate missing — unauthenticated users will not be redirected"}]
    return []


def check_html_hive_id_in_fetch(html, page):
    if not html:
        return []
    if not re.search(r"hive_id\s*:\s*HIVE_ID", html):
        return [{"check": "hive_id_in_fetch", "page": page,
                 "reason": "hive_id: HIVE_ID not found in fetch body — analytics results will not be tenant-scoped"}]
    return []


def check_html_esc_html_on_error(html, page):
    if not html:
        return []
    if "escHtml(err.message)" not in html and "escHtml(err" not in html:
        return [{"check": "esc_html_error", "page": page,
                 "reason": "escHtml not applied to error message in catch block — XSS risk"}]
    return []


def check_html_phase_banners(html, page):
    if not html:
        return []
    issues = []
    for phase in ALL_PHASES:
        if f"'{phase}'" not in html and f'"{phase}"' not in html:
            issues.append({"check": "phase_banners", "page": page, "phase": phase,
                           "reason": f"Phase '{phase}' not found in analytics.html"})
    return issues


def check_html_double_submit_guard(html, page):
    if not html:
        return []
    if "if (_loading)" not in html and "if(_loading)" not in html:
        return [{"check": "double_submit_guard", "page": page,
                 "reason": "_loading guard missing — user can trigger multiple concurrent requests"}]
    return []


def check_html_orchestrator_ref(html, page):
    if not html:
        return []
    if "analytics-orchestrator" not in html:
        return [{"check": "orchestrator_endpoint", "page": page,
                 "reason": "analytics-orchestrator not referenced — fetch may point to wrong edge function"}]
    return []


def check_html_render_functions(html, page):
    if not html:
        return []
    issues = []
    for fn in ["renderDescriptive", "renderDiagnostic", "renderPredictive", "renderPrescriptive"]:
        if fn not in html:
            issues.append({"check": "render_functions", "page": page, "function": fn,
                           "reason": f"{fn}() not found — that phase's results will not display"})
    return issues


def check_html_new_render_functions(html, page):
    """New render functions for OEE, RCM consequence, and anomaly baseline."""
    if not html:
        return []
    issues = []
    for fn in NEW_RENDER_FUNCTIONS:
        if fn not in html:
            issues.append({"check": "new_render_functions", "page": page, "function": fn,
                           "reason": f"{fn}() not found in analytics.html — new analytics output will not be displayed"})
    return issues


def check_edge_new_logbook_fields(ts, path):
    """Edge function logbook SELECT must include the new logbook fields."""
    if not ts:
        return []
    issues = []
    for field in NEW_LOGBOOK_FIELDS:
        if field not in ts:
            issues.append({"check": "edge_new_logbook_fields", "page": path, "field": field,
                           "reason": f"Edge function logbook SELECT missing '{field}' — analytics can't use this new logbook data"})
    return issues


def check_html_toast_on_error(html, page):
    if not html:
        return []
    catch_m = re.search(r"catch\s*\(err\)", html)
    if not catch_m:
        return [{"check": "toast_on_error", "page": page,
                 "reason": "No catch(err) block found — errors may be silently swallowed"}]
    window = html[catch_m.start():catch_m.start() + 600]
    if "showToast" not in window:
        return [{"check": "toast_on_error", "page": page,
                 "reason": "showToast not called in error catch — users will not see feedback"}]
    return []


# ── Layer 1: Pattern checks (edge function) ───────────────────────────────────

def check_edge_all_phases(ts, path):
    if not ts:
        return [{"check": "edge_phases", "page": path,
                 "reason": f"{path} not found — edge function cannot be validated"}]
    issues = []
    for phase in ALL_PHASES:
        if f'phase === "{phase}"' not in ts:
            issues.append({"check": "edge_phases", "page": path, "phase": phase,
                           "reason": f'Edge function does not handle phase === "{phase}"'})
    return issues


def check_edge_hive_id_scoping(ts, path):
    if not ts:
        return []
    issues = []
    for table, var in [("logbook", "logbookQ"), ("inventory_transactions", "txnQ"), ("pm_assets", "assetsQ")]:
        if not re.search(rf'{re.escape(var)}\.eq\("hive_id"', ts):
            issues.append({"check": "edge_hive_id_scoping", "page": path, "table": table,
                           "reason": f'{var} missing .eq("hive_id", hiveId) — data leaks across tenants'})
    return issues


def check_edge_groq_fallback(ts, path):
    if not ts:
        return []
    models = re.findall(r'"(llama[^"]+|meta-llama[^"]+|mixtral[^"]+)"', ts)
    if len(models) < 2:
        return [{"check": "groq_fallback", "page": path, "found_models": models,
                 "reason": "Groq fallback chain has fewer than 2 models — no fallback on rate limit"}]
    return []


def check_edge_groq_null_guard(ts, path):
    if not ts:
        return []
    if "if (!GROQ_KEY)" not in ts and "if(!GROQ_KEY)" not in ts:
        return [{"check": "groq_null_guard", "page": path,
                 "reason": "GROQ_API_KEY not null-checked — prescriptive phase throws instead of degrading gracefully"}]
    return []


def check_edge_python_url_null_guard(ts, path):
    if not ts:
        return []
    if "if (!PYTHON_URL)" not in ts and "if(!PYTHON_URL)" not in ts:
        return [{"check": "python_url_null_guard", "page": path,
                 "reason": "PYTHON_API_URL not null-checked — analytics throws instead of structured error"}]
    return []


def check_edge_abort_timeout(ts, path):
    if not ts:
        return []
    if "AbortSignal.timeout" not in ts:
        return [{"check": "abort_timeout", "page": path,
                 "reason": "AbortSignal.timeout not used — request will hang on Python API cold start"}]
    return []


def check_edge_phase_validation(ts, path):
    if not ts:
        return []
    if "status: 400" not in ts and '"Missing required field' not in ts:
        return [{"check": "phase_validation", "page": path,
                 "reason": "Edge function does not return 400 for missing phase"}]
    return []


# ── Layer 1: Pattern checks (Python backend) ─────────────────────────────────

def check_python_modules_exist():
    issues = []
    for phase, fp in [("descriptive", DESCRIPTIVE_PY), ("diagnostic", DIAGNOSTIC_PY),
                      ("predictive", PREDICTIVE_PY), ("prescriptive", PRESCRIPTIVE_PY)]:
        if not os.path.exists(fp):
            issues.append({"check": "module_exists", "phase": phase, "page": fp,
                           "reason": f"analytics/{phase}.py not found"})
    return issues


def check_python_calculate_entry(phase, fp):
    content = read_file(fp)
    if not content:
        return []
    if not re.search(r"def calculate\s*\(", content):
        return [{"check": "calculate_entry", "phase": phase, "page": fp,
                 "reason": f"calculate() not found in {fp} — main.py router will fail to call it"}]
    return []


def check_descriptive_functions(content, path):
    if not content:
        return [{"check": "descriptive_functions", "page": path, "reason": f"{path} not found"}]
    issues = []
    for fn in DESCRIPTIVE_FUNCTIONS:
        if f"def {fn}" not in content:
            issues.append({"check": "descriptive_functions", "page": path, "function": fn,
                           "reason": f"{fn}() not defined — that SMRP/ISO metric will be missing"})
    return issues


def check_availability_formula(content, path):
    if not content:
        return []
    if re.search(r"mtbf\s*/\s*\(\s*mtbf\s*\+\s*mttr\s*\)", content, re.IGNORECASE):
        return []
    if re.search(r"mttr\s*/\s*\(\s*mttr\s*\+\s*mtbf\s*\)", content, re.IGNORECASE):
        return [{"check": "availability_formula", "page": path,
                 "reason": "Availability formula appears inverted — should be MTBF/(MTBF+MTTR)"}]
    if re.search(r"availability\s*=.{0,80}\*\s*100", content, re.DOTALL):
        return [{"check": "availability_formula", "page": path,
                 "reason": "Availability formula found but does not match MTBF/(MTBF+MTTR) — verify ISO 14224 §9.2"}]
    return [{"check": "availability_formula", "page": path,
             "reason": "Availability formula not found in calc_availability"}]


def check_main_py_phase_routing(content, path):
    if not content:
        return [{"check": "main_phase_routing", "page": path, "reason": f"{path} not found"}]
    issues = []
    for phase in ALL_PHASES:
        if f'phase == "{phase}"' not in content and f"phase == '{phase}'" not in content:
            issues.append({"check": "main_phase_routing", "phase": phase, "page": path,
                           "reason": f"main.py /analytics does not route phase='{phase}'"})
    return issues


def check_main_py_analytics_404(content, path):
    if not content:
        return []
    if "raise HTTPException" not in content:
        return [{"check": "main_analytics_404", "page": path,
                 "reason": "main.py /analytics does not raise HTTPException for unknown phases"}]
    return []


# ── Layer 2: Syntax checks ────────────────────────────────────────────────────

def check_py_syntax():
    files = [DESCRIPTIVE_PY, DIAGNOSTIC_PY, PREDICTIVE_PY, PRESCRIPTIVE_PY, MAIN_PY]
    issues = []
    for f in files:
        if not os.path.exists(f):
            continue
        err = compile_check(f)
        if err:
            issues.append({"check": "py_syntax", "page": f,
                           "reason": f"Syntax error in {os.path.basename(f)}: {err}"})
    return issues


# ── Layer 3: Smoke tests ──────────────────────────────────────────────────────

def check_smoke(phase, filepath):
    inputs = SMOKE_INPUTS[phase]
    result, err = smoke_test(filepath, "calculate", inputs, extra_sys_path=PYTHON_API_DIR)
    check_id = f"py_smoke_{phase}"
    if err is None:
        return [], result
    if err.startswith("SKIP:"):
        return [{"check": check_id, "page": filepath, "reason": err, "skip": True}], None
    return [{"check": check_id, "page": filepath, "reason": err}], None


# ── Layer 4: Output shape + consistency ───────────────────────────────────────

def check_descriptive_shape(result):
    if result is None:
        return [{"check": "py_shape_descriptive",
                 "reason": "Cannot check shape — smoke test was skipped or failed"}]
    issues = check_shape(result, DESCRIPTIVE_SHAPE, label="descriptive")
    return [{"check": "py_shape_descriptive", "reason": msg} for msg in issues]


def check_period_consistency(html, ts, desc_content):
    issues = []
    if html and not re.search(r"let\s+_period\s*=\s*90", html):
        issues.append({"check": "period_consistency", "layer": "HTML",
                       "reason": "HTML default _period is not 90 — may differ from backend default"})
    if ts and "|| 90" not in ts:
        issues.append({"check": "period_consistency", "layer": "edge_function",
                       "reason": "Edge function period_days fallback is not || 90"})
    if desc_content and '"period_days", 90' not in desc_content and "'period_days', 90" not in desc_content:
        issues.append({"check": "period_consistency", "layer": "python",
                       "reason": "Python descriptive.py default period_days is not 90"})
    return issues


# ── Runner ─────────────────────────────────────────────────────────────────────

def run_checks():
    html    = read_file(HTML_FILE)
    ts      = read_file(EDGE_FUNC_FILE)
    desc    = read_file(DESCRIPTIVE_PY)
    main_py = read_file(MAIN_PY)

    all_issues = []

    # Layer 1 — pattern checks
    all_issues += check_html_auth_gate(html, HTML_FILE)
    all_issues += check_html_hive_id_in_fetch(html, HTML_FILE)
    all_issues += check_html_esc_html_on_error(html, HTML_FILE)
    all_issues += check_html_phase_banners(html, HTML_FILE)
    all_issues += check_html_double_submit_guard(html, HTML_FILE)
    all_issues += check_html_orchestrator_ref(html, HTML_FILE)
    all_issues += check_html_render_functions(html, HTML_FILE)
    all_issues += check_html_toast_on_error(html, HTML_FILE)
    all_issues += check_html_new_render_functions(html, HTML_FILE)
    all_issues += check_edge_all_phases(ts, EDGE_FUNC_FILE)
    all_issues += check_edge_hive_id_scoping(ts, EDGE_FUNC_FILE)
    all_issues += check_edge_new_logbook_fields(ts, EDGE_FUNC_FILE)
    all_issues += check_edge_groq_fallback(ts, EDGE_FUNC_FILE)
    all_issues += check_edge_groq_null_guard(ts, EDGE_FUNC_FILE)
    all_issues += check_edge_python_url_null_guard(ts, EDGE_FUNC_FILE)
    all_issues += check_edge_abort_timeout(ts, EDGE_FUNC_FILE)
    all_issues += check_edge_phase_validation(ts, EDGE_FUNC_FILE)
    all_issues += check_python_modules_exist()
    for phase, fp in [("descriptive", DESCRIPTIVE_PY), ("diagnostic", DIAGNOSTIC_PY),
                      ("predictive", PREDICTIVE_PY), ("prescriptive", PRESCRIPTIVE_PY)]:
        if os.path.exists(fp):
            all_issues += check_python_calculate_entry(phase, fp)
    all_issues += check_descriptive_functions(desc, DESCRIPTIVE_PY)
    all_issues += check_availability_formula(desc, DESCRIPTIVE_PY)
    all_issues += check_main_py_phase_routing(main_py, MAIN_PY)
    all_issues += check_main_py_analytics_404(main_py, MAIN_PY)

    # Layer 2 — syntax
    all_issues += check_py_syntax()

    # Layer 3 — smoke tests
    desc_result = None
    for phase, fp in [("descriptive", DESCRIPTIVE_PY), ("diagnostic", DIAGNOSTIC_PY),
                      ("predictive", PREDICTIVE_PY), ("prescriptive", PRESCRIPTIVE_PY)]:
        if os.path.exists(fp):
            smoke_issues, result = check_smoke(phase, fp)
            all_issues += smoke_issues
            if phase == "descriptive" and result is not None:
                desc_result = result

    # Layer 4 — shape + consistency
    all_issues += check_descriptive_shape(desc_result)
    all_issues += check_period_consistency(html, ts, desc)

    return all_issues


# ── Main ──────────────────────────────────────────────────────────────────────

CHECK_NAMES = [
    # L1 — pattern
    "auth_gate", "hive_id_in_fetch", "esc_html_error", "phase_banners",
    "double_submit_guard", "orchestrator_endpoint", "render_functions", "toast_on_error",
    "new_render_functions",
    "edge_phases", "edge_hive_id_scoping", "edge_new_logbook_fields",
    "groq_fallback", "groq_null_guard",
    "python_url_null_guard", "abort_timeout", "phase_validation",
    "module_exists", "calculate_entry", "descriptive_functions",
    "availability_formula", "main_phase_routing", "main_analytics_404",
    # L2 — syntax
    "py_syntax",
    # L3 — smoke
    "py_smoke_descriptive", "py_smoke_diagnostic",
    "py_smoke_predictive", "py_smoke_prescriptive",
    # L4 — shape + consistency
    "py_shape_descriptive", "period_consistency",
]

CHECK_LABELS = {
    # L1
    "auth_gate":                "L1  Auth gate (WORKER_NAME redirect)",
    "hive_id_in_fetch":         "L1  HIVE_ID sent in fetch body",
    "esc_html_error":           "L1  escHtml on error output",
    "phase_banners":            "L1  PHASE_BANNERS completeness (4 phases)",
    "double_submit_guard":      "L1  Double-submit guard (_loading)",
    "orchestrator_endpoint":    "L1  analytics-orchestrator endpoint ref",
    "render_functions":         "L1  Render functions (all 4 phases)",
    "toast_on_error":           "L1  Toast feedback on error",
    "new_render_functions":     "L1  New render fns (OEE, RCM, Anomaly)",
    "edge_phases":              "L2  Edge fn: all 4 phases handled",
    "edge_hive_id_scoping":     "L2  Edge fn: hive_id scope on tables",
    "edge_new_logbook_fields":  "L2  Edge fn: new logbook fields in SELECT",
    "groq_fallback":            "L2  Groq fallback chain (2+ models)",
    "groq_null_guard":          "L2  GROQ_API_KEY null guard",
    "python_url_null_guard":    "L2  PYTHON_API_URL null guard",
    "abort_timeout":            "L2  AbortSignal.timeout on Python fetch",
    "phase_validation":         "L2  Phase missing returns 400",
    "module_exists":            "L3  All 4 analytics .py modules exist",
    "calculate_entry":          "L3  calculate() entry in each module",
    "descriptive_functions":    "L3  All 8 SMRP/ISO metrics in descriptive",
    "availability_formula":     "L3  Availability formula MTBF/(MTBF+MTTR)",
    "main_phase_routing":       "L3  main.py routes all 4 phases",
    "main_analytics_404":       "L3  main.py raises 404 for unknown phase",
    # L2 (syntax layer)
    "py_syntax":                "SYN Python syntax check (all .py files)",
    # L3 (smoke layer)
    "py_smoke_descriptive":     "RUN Smoke: descriptive.calculate({}) — empty data",
    "py_smoke_diagnostic":      "RUN Smoke: diagnostic.calculate({}) — empty data",
    "py_smoke_predictive":      "RUN Smoke: predictive.calculate({}) — empty data",
    "py_smoke_prescriptive":    "RUN Smoke: prescriptive.calculate({}) — empty data",
    # L4 (shape + consistency)
    "py_shape_descriptive":     "SHP Shape: descriptive — all 9 metric keys (incl. OEE)",
    "period_consistency":       "CON period_days=90 consistent across all layers",
}


def main():
    def bold(s): return f"\033[1m{s}\033[0m"
    print(bold("\nAnalytics Engine Validator (4-layer)"))
    print("=" * 55)

    issues = run_checks()
    n_pass, n_skip, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    total = len(CHECK_NAMES)
    if n_fail == 0 and n_skip == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    elif n_fail == 0:
        print(f"\033[93m\n  {n_pass} PASS  {n_skip} SKIP  0 FAIL — smoke tests skipped (install pandas/scipy to run locally)\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")

    report = {
        "validator":    "analytics",
        "total_checks": total,
        "passed":       n_pass,
        "skipped":      n_skip,
        "failed":       n_fail,
        "issues":       [i for i in issues if not i.get("skip")],
        "skips":        [i for i in issues if i.get("skip")],
    }
    with open("analytics_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
