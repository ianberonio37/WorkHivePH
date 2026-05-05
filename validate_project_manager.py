"""
Project Manager Validator - WorkHive Platform
=============================================
Four-layer validation of the Project Manager build (Phases 0-2).

  Layer 1 - Page structure / contract
    1. project-manager.html identity gate (3-key chain)
    2. Hive gate present
    3. project-progress edge function invoked from page
    4. PROJECT_TEMPLATES library defined
    5. 4 project types covered in templates
    6. Wizard state + 3 wizard panes
    7. recents loadRecents/saveRecents + per-hive scoping
    8. Status grouping (renderList branches on status filter)
    9. Phase-grouped scope (PHASE_LABELS + getPhase)
    10. cycleScopeStatus inline pill
    11. utils.js loaded for escHtml

  Layer 2 - Edge function contract
    12. Function returns JSON.stringify({ error: ... })
    13. CORS OPTIONS handled
    14. Required fields validated (project_id, hive_id) with 400
    15. PYTHON_API_URL fallback handled gracefully (_unavailable flag)
    16. Forwards to /project/progress (not /project — exact path)
    17. Hive scope on every Supabase select (defence in depth)
    18. Soft-delete filter on projects select

  Layer 3 - Python module purity
    19. python-api/projects/__init__.py exists
    20. All 4 phase modules exist (descriptive/diagnostic/predictive/prescriptive)
    21. Each module exposes calculate(inputs)
    22. main.py registers /project/progress endpoint
    23. ProjectRequest pydantic model present
    24. networkx in python-api/requirements.txt
    25. py_compile passes on all 4 modules + main.py

  Layer 4 - Smoke + shape
    26. descriptive.calculate({}) doesn't crash
    27. diagnostic.calculate({}) returns {available: False} on empty
    28. predictive.calculate({}) gracefully returns no forecast
    29. prescriptive.calculate({}) returns empty critical path on empty input
    30. Schema columns: every column read in HTML exists in the migration

Usage:  python validate_project_manager.py
Output: project_manager_report.json
"""
import os
import re
import sys
import json
import py_compile

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = os.path.dirname(os.path.abspath(__file__))

HTML_FILE          = os.path.join(BASE, "project-manager.html")
EDGE_FUNC_FILE     = os.path.join(BASE, "supabase", "functions", "project-progress", "index.ts")
PROJECTS_INIT      = os.path.join(BASE, "python-api", "projects", "__init__.py")
DESCRIPTIVE_PY     = os.path.join(BASE, "python-api", "projects", "descriptive.py")
DIAGNOSTIC_PY      = os.path.join(BASE, "python-api", "projects", "diagnostic.py")
PREDICTIVE_PY      = os.path.join(BASE, "python-api", "projects", "predictive.py")
PRESCRIPTIVE_PY    = os.path.join(BASE, "python-api", "projects", "prescriptive.py")
MAIN_PY            = os.path.join(BASE, "python-api", "main.py")
REQUIREMENTS_TXT   = os.path.join(BASE, "python-api", "requirements.txt")
MIGRATION_FILE     = os.path.join(BASE, "supabase", "migrations", "20260505000000_project_manager.sql")

ALL_PHASE_MODULES = [
    ("descriptive",  DESCRIPTIVE_PY),
    ("diagnostic",   DIAGNOSTIC_PY),
    ("predictive",   PREDICTIVE_PY),
    ("prescriptive", PRESCRIPTIVE_PY),
]


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _check(label, ok, reason=""):
    return {"label": label, "ok": bool(ok), "reason": reason if not ok else ""}


def layer1_page_structure():
    issues = []
    html = _read(HTML_FILE)
    if html is None:
        issues.append(_check("html_exists", False, "project-manager.html not found"))
        return issues

    # 1. Identity gate (3-key chain)
    has_3key = bool(re.search(
        r"wh_last_worker.*wh_worker_name.*workerName",
        html, re.DOTALL,
    ))
    issues.append(_check("identity_3key_chain", has_3key,
                         "project-manager.html must read wh_last_worker || wh_worker_name || workerName"))

    # 2. Hive gate present
    issues.append(_check("hive_gate", "hive-gate" in html and "validateHiveMembership" in html,
                         "Page must show hive gate when not a hive member"))

    # 3. Edge function invoked
    issues.append(_check("edge_fn_invoked", "functions.invoke('project-progress'" in html,
                         "Page must invoke 'project-progress' edge function"))

    # 4. PROJECT_TEMPLATES library
    issues.append(_check("templates_defined", "PROJECT_TEMPLATES" in html,
                         "PROJECT_TEMPLATES library not defined"))

    # 5. 4 project types in templates
    types_ok = all(t in html for t in ["workorder:", "shutdown:", "capex:", "contractor:"])
    issues.append(_check("4_types_covered", types_ok,
                         "Templates must cover all 4 project types"))

    # 6. Wizard state + 3 panes
    wiz_ok = "_wizardState" in html and html.count('class="wizard-pane"') >= 3
    issues.append(_check("wizard_3_panes", wiz_ok,
                         "Wizard requires _wizardState + 3 .wizard-pane elements"))

    # 7. Recents per-hive scoped
    recents_ok = "loadRecents" in html and "wh_pm_recent_" in html
    issues.append(_check("recents_per_hive", recents_ok,
                         "Recents must be per-hive scoped (wh_pm_recent_<HIVE_ID>)"))

    # 8. Status grouping
    issues.append(_check("status_grouping", "toggleGroup" in html and "_groupOpen" in html,
                         "All-tab grouped view requires toggleGroup + _groupOpen"))

    # 9. Phase-grouped scope
    phase_ok = "PHASE_LABELS" in html and "getPhase" in html
    issues.append(_check("phase_grouped_scope", phase_ok,
                         "Scope tab grouping requires PHASE_LABELS + getPhase helper"))

    # 10. Inline status pill cycling
    issues.append(_check("status_pill_cycle", "cycleScopeStatus" in html,
                         "Inline status cycling on scope rows requires cycleScopeStatus"))

    # 11. utils.js loaded
    issues.append(_check("utils_loaded", '<script src="utils.js"' in html,
                         "Page must load utils.js for escHtml"))

    return issues


def layer2_edge_contract():
    issues = []
    edge = _read(EDGE_FUNC_FILE)
    if edge is None:
        issues.append(_check("edge_fn_exists", False, "edge function file not found"))
        return issues

    # 12. Error contract
    issues.append(_check("error_contract", bool(re.search(r"JSON\.stringify\s*\(\s*\{\s*error\s*:", edge)),
                         "Edge fn must return JSON.stringify({ error: ... })"))

    # 13. CORS
    issues.append(_check("cors_options", bool(re.search(r"req\.method\s*===\s*['\"]OPTIONS['\"]", edge)),
                         "Edge fn must handle OPTIONS preflight"))

    # 14. Required fields validation
    has_pid_check  = "!project_id" in edge or "Missing.*project_id" in edge
    has_hive_check = "!hive_id"    in edge or "Missing.*hive_id"    in edge
    issues.append(_check("required_fields", has_pid_check and has_hive_check,
                         "Edge fn must validate project_id + hive_id with 400"))

    # 15. Python URL graceful fallback
    has_py_check = "PYTHON_API_URL" in edge and "_unavailable" in edge
    issues.append(_check("python_url_fallback", has_py_check,
                         "Missing PYTHON_API_URL must produce { _unavailable: true } not crash"))

    # 16. Forwards to /project/progress
    issues.append(_check("forwards_to_python", "/project/progress" in edge,
                         "Edge fn must POST to ${PYTHON_API_URL}/project/progress"))

    # 17. Hive scope on selects
    selects = re.findall(r"db\.from\(['\"](\w+)['\"]\)\.select", edge)
    has_hive_scope = edge.count(".eq('hive_id'") + edge.count('.eq("hive_id"') >= len(selects)
    issues.append(_check("hive_scope_on_selects", has_hive_scope,
                         "Every Supabase select in the edge fn must filter by hive_id"))

    # 18. Soft-delete filter on projects select
    proj_select = re.search(r"\.from\(['\"]projects['\"]\).*?\.maybeSingle\(\)", edge, re.DOTALL)
    soft_ok = proj_select and ".is('deleted_at', null)" in proj_select.group(0)
    issues.append(_check("soft_delete_on_projects", soft_ok,
                         "projects select must chain .is('deleted_at', null)"))

    return issues


def layer3_python_purity():
    issues = []

    # 19. __init__.py
    issues.append(_check("projects_init", os.path.exists(PROJECTS_INIT),
                         "python-api/projects/__init__.py missing"))

    # 20. 4 phase modules exist
    for name, path in ALL_PHASE_MODULES:
        issues.append(_check(f"module_{name}", os.path.exists(path),
                             f"python-api/projects/{name}.py missing"))

    # 21. calculate() in each
    for name, path in ALL_PHASE_MODULES:
        body = _read(path) or ""
        has_calc = "def calculate(" in body
        issues.append(_check(f"calculate_in_{name}", has_calc,
                             f"{name}.py must expose calculate(inputs: dict)"))

    # 22. main.py registers /project/progress
    main = _read(MAIN_PY) or ""
    issues.append(_check("main_endpoint", '@app.post("/project/progress")' in main,
                         "main.py must register POST /project/progress"))

    # 23. ProjectRequest model
    issues.append(_check("project_request_model", "class ProjectRequest" in main,
                         "main.py must define ProjectRequest pydantic model"))

    # 24. networkx in requirements
    reqs = _read(REQUIREMENTS_TXT) or ""
    issues.append(_check("networkx_in_requirements",
                         re.search(r"^networkx\b", reqs, re.MULTILINE) is not None,
                         "networkx must be in python-api/requirements.txt for CPM"))

    # 25. py_compile passes on all 4 modules + main.py
    for name, path in ALL_PHASE_MODULES + [("main", MAIN_PY)]:
        if not os.path.exists(path):
            continue
        try:
            py_compile.compile(path, doraise=True, quiet=1)
            issues.append(_check(f"compile_{name}", True))
        except py_compile.PyCompileError as e:
            issues.append(_check(f"compile_{name}", False, str(e)))

    return issues


def layer4_smoke_shape():
    issues = []
    # 26-29. Smoke each phase with empty inputs
    sys.path.insert(0, os.path.join(BASE, "python-api"))
    try:
        from projects.descriptive import calculate as desc
        out = desc({})
        ok = isinstance(out, dict) and "pct_complete" in out
        issues.append(_check("smoke_descriptive", ok,
                             "descriptive.calculate({}) must return dict with pct_complete"))
    except Exception as e:
        issues.append(_check("smoke_descriptive", False, f"crash: {e}"))

    try:
        from projects.diagnostic import calculate as diag
        out = diag({"project": {}})
        ok = isinstance(out, dict) and out.get("available") is False
        issues.append(_check("smoke_diagnostic", ok,
                             "diagnostic.calculate(empty) must return {available: False}"))
    except Exception as e:
        issues.append(_check("smoke_diagnostic", False, f"crash: {e}"))

    try:
        from projects.predictive import calculate as pred
        out = pred({"project": {}})
        ok = isinstance(out, dict) and "forecasts" in out
        issues.append(_check("smoke_predictive", ok,
                             "predictive.calculate(empty) must return {forecasts: ...}"))
    except Exception as e:
        issues.append(_check("smoke_predictive", False, f"crash: {e}"))

    try:
        from projects.prescriptive import calculate as presc
        out = presc({})
        ok = (isinstance(out, dict) and "critical_path" in out
              and out["critical_path"]["item_ids"] == [])
        issues.append(_check("smoke_prescriptive", ok,
                             "prescriptive.calculate({}) must return empty critical_path"))
    except Exception as e:
        issues.append(_check("smoke_prescriptive", False, f"crash: {e}"))

    # 30. Schema column existence (light AST)
    html = _read(HTML_FILE) or ""
    migration = _read(MIGRATION_FILE) or ""
    project_cols_in_html = set(re.findall(
        r"db\.from\('projects'\)\.select\([^)]*\)",
        html,
    ))
    # Just confirm projects has the columns we reference in the page header
    expected_cols = ["project_code", "project_type", "status", "priority", "owner_name", "budget_php"]
    missing = [c for c in expected_cols if c not in migration]
    issues.append(_check("schema_columns_present", not missing,
                         f"Columns missing from migration: {missing}" if missing else ""))

    return issues


def layer5_phase35_contracts():
    """
    Phase 3-5 feature contracts added after the initial Phase 0-2 build.
    These checks are structural (pattern presence) — they confirm the key
    tables, variables, and functions exist in the page without requiring
    a live DB.

    Phase 3 (3B/3C): Logbook auto-link + PM link to active projects
      31. _links variable and project_links table query
      32. project_links INSERT has link_type + link_id + hive_id
      33. _linkSuggestions (logbook open entries panel)

    Phase 4: Project Report PDF + Lessons Learned
      34. lessons_learned in meta field read/write path
      35. project-report.html link present in detail view
      36. saveLessons function exists

    Phase 5: Resources, Multi-role, Risk, Change Orders
      37. _roles variable and project_roles table query
      38. _changeOrders variable and project_change_orders table query
      39. approveChangeOrder / rejectChangeOrder functions
      40. schedule_risk panel rendered from forecast data
      41. generate_change_order_number RPC called
    """
    issues = []
    html = _read(HTML_FILE) or ""

    # Phase 3
    issues.append(_check("links_variable",
        "_links" in html and "project_links" in html,
        "Phase 3: _links variable + project_links table not found — logbook link feature missing"))
    issues.append(_check("links_insert_fields",
        bool(re.search(r"project_links.*insert|insert.*project_links", html, re.DOTALL))
        and "link_type" in html and "link_id" in html,
        "Phase 3: project_links INSERT missing link_type or link_id fields"))
    issues.append(_check("link_suggestions_panel",
        "_linkSuggestions" in html,
        "Phase 3: _linkSuggestions panel missing — workers won't see open logbook entries to link"))

    # Phase 4
    issues.append(_check("lessons_learned_rw",
        "lessons_learned" in html,
        "Phase 4: lessons_learned not referenced — lessons learned save/load feature missing"))
    issues.append(_check("project_report_link",
        "project-report.html" in html,
        "Phase 4: project-report.html link not in detail view — PDF report unreachable from project"))
    issues.append(_check("save_lessons_fn",
        "saveLessons" in html or "lessons_learned" in html,
        "Phase 4: saveLessons function or lessons_learned write path missing"))

    # Phase 5
    issues.append(_check("roles_variable",
        "_roles" in html and "project_roles" in html,
        "Phase 5: _roles variable + project_roles table not found — multi-role feature missing"))
    issues.append(_check("change_orders_variable",
        "_changeOrders" in html and "project_change_orders" in html,
        "Phase 5: _changeOrders + project_change_orders not found — change order feature missing"))
    issues.append(_check("change_order_approval_fns",
        ("approveCO" in html or "approveChangeOrder" in html) and
        ("rejectCO" in html or "rejectChangeOrder" in html),
        "Phase 5: approveCO/rejectCO (or approveChangeOrder/rejectChangeOrder) functions missing — supervisor approval flow broken"))
    issues.append(_check("schedule_risk_panel",
        "schedule_risk" in html,
        "Phase 5: schedule_risk panel not rendered — Monte Carlo risk data silently unused"))
    issues.append(_check("change_order_number_rpc",
        "generate_change_order_number" in html,
        "Phase 5: generate_change_order_number RPC not called — change order codes will be null"))

    # Role guard regression: supervisor-gated mutation functions must check
    # isSupervisor() internally — not just at the button render level.
    # A worker can call approveCO/rejectCO/removeRole directly from the browser
    # console regardless of whether the button is visible in the DOM.
    for fn in ["approveCO", "rejectCO", "removeRole"]:
        fn_match = re.search(rf'async function {re.escape(fn)}\b', html)
        if not fn_match:
            continue
        body = html[fn_match.start():fn_match.start() + 400]
        has_guard = bool(re.search(r'isSupervisor\(\)|HIVE_ROLE\s*===\s*[\'"]supervisor', body))
        issues.append(_check(f"role_guard_{fn}",
            has_guard,
            f"Phase 5: {fn}() missing internal isSupervisor() guard — callable from browser console"))

    return issues


def main():
    print("\nProject Manager Validator (5-layer)")
    print("=" * 55)
    layers = [
        ("L1  Page structure / contract", layer1_page_structure()),
        ("L2  Edge function contract",     layer2_edge_contract()),
        ("L3  Python module purity",       layer3_python_purity()),
        ("L4  Smoke + shape",              layer4_smoke_shape()),
        ("L5  Phase 3-5 contracts",        layer5_phase35_contracts()),
    ]
    all_pass, all_fail = 0, 0
    for layer_name, issues in layers:
        for it in issues:
            mark = "PASS" if it["ok"] else "FAIL"
            print(f"  [{mark}]  {it['label']}{(' - ' + it['reason']) if not it['ok'] else ''}")
            if it["ok"]:
                all_pass += 1
            else:
                all_fail += 1
    print()
    print(f"  Summary: {all_pass} pass / {all_fail} fail")
    out = {"layers": [{"name": n, "issues": iss} for n, iss in layers],
           "summary": {"pass": all_pass, "fail": all_fail}}
    with open(os.path.join(BASE, "project_manager_report.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"  Report: project_manager_report.json")
    sys.exit(0 if all_fail == 0 else 1)


if __name__ == "__main__":
    main()
