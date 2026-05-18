"""
ML Layer Validator -- WorkHive Platform
========================================
Confirms the Stage 1 ML pipeline is correctly wired so that missing
registrations, wrong feature lists, or un-ignored artifacts are caught
before they cause silent failures in production.

  Layer 1: Feature engineering
    1. All 11 FEATURE_COLS present in feature_engineering.py
    2. FEATURE_COLS exported at module level (accessible by trainer)

  Layer 2: Trainer + API
    3. /ml/train endpoint in main.py
    4. /ml/predict endpoint in main.py
    5. /ml/status endpoint in main.py
    6. MLTrainRequest model in main.py
    7. MLPredictRequest model in main.py
    8. artifacts/ directory exists

  Layer 3: Artifact hygiene
    9. *.pkl in .gitignore (model artifacts never committed)
    10. .gitkeep in artifacts/ (empty dir tracked in git)

  Layer 4: Edge function registration
    11. batch-risk-scoring in validate_edge_contracts.py ALL_FUNCTIONS
    12. trigger-ml-retrain in validate_edge_contracts.py ALL_FUNCTIONS
    13. asset_risk_scores in validate_schema.py CORE_TABLES

  Layer 5: UI registration
    14. predictive.html in validate_schema.py LIVE_PAGES
    15. predictive in validate_assistant.py LIVE_TOOL_PAGES
    16. predictive in nav-hub.js TOOLS
    17. predictive context entry in companion-launcher.js

Usage:  python validate_ml.py
Output: ml_report.json
"""
import re, json, sys, os

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from validator_utils import read_file, format_result

FEATURE_COLS = [
    "days_since_last_fault", "fault_count_30d", "fault_count_90d",
    "fault_freq_trend", "mtbf_days", "days_until_mtbf",
    "avg_downtime_hours", "repeat_fault_count", "pm_overdue_days",
    "parts_used_30d", "total_fault_count",
]

CHECKS = {
    "feature_cols_complete":         "L1  All 11 FEATURE_COLS in feature_engineering.py",
    "feature_cols_exported":         "L1  FEATURE_COLS exported at module level",
    "ml_train_endpoint":             "L2  /ml/train endpoint in main.py",
    "ml_predict_endpoint":           "L2  /ml/predict endpoint in main.py",
    "ml_status_endpoint":            "L2  /ml/status endpoint in main.py",
    "ml_train_request_model":        "L2  MLTrainRequest model in main.py",
    "ml_predict_request_model":      "L2  MLPredictRequest model in main.py",
    "artifacts_dir_exists":          "L2  python-api/ml/artifacts/ directory exists",
    "pkl_in_gitignore":              "L3  *.pkl in .gitignore (artifacts not committed)",
    "gitkeep_in_artifacts":          "L3  .gitkeep in artifacts/ directory",
    "batch_risk_in_contracts":       "L4  batch-risk-scoring in validate_edge_contracts.py",
    "retrain_in_contracts":          "L4  trigger-ml-retrain in validate_edge_contracts.py",
    "asset_risk_in_schema_tables":   "L4  asset_risk_scores in validate_schema.py CORE_TABLES",
    "predictive_in_schema_pages":    "L5  predictive.html in validate_schema.py LIVE_PAGES",
    "predictive_in_assistant_tools": "L5  predictive in validate_assistant.py LIVE_TOOL_PAGES",
    "predictive_in_nav_hub":         "L5  predictive in nav-hub.js TOOLS",
    "predictive_in_floating_ai":     "L5  predictive context entry in companion-launcher.js",
}


def run():
    issues  = []
    results = {}

    # ── Feature engineering ───────────────────────────────────────────────────
    fe_content = read_file(os.path.join("python-api", "ml", "feature_engineering.py"))

    missing_cols = [c for c in FEATURE_COLS if fe_content and f'"{c}"' not in fe_content and f"'{c}'" not in fe_content]
    if missing_cols:
        issues.append({"check": "feature_cols_complete", "reason": f"Missing FEATURE_COLS: {missing_cols}"})
    results["feature_cols_complete"] = len(missing_cols) == 0

    results["feature_cols_exported"] = bool(fe_content and "FEATURE_COLS" in fe_content and "=" in fe_content)
    if not results["feature_cols_exported"]:
        issues.append({"check": "feature_cols_exported", "reason": "FEATURE_COLS not found as module-level assignment in feature_engineering.py"})

    # ── main.py endpoints ─────────────────────────────────────────────────────
    main_content = read_file(os.path.join("python-api", "main.py"))

    for check, pattern in [
        ("ml_train_endpoint",        r'"/ml/train"'),
        ("ml_predict_endpoint",      r'"/ml/predict"'),
        ("ml_status_endpoint",       r'"/ml/status"'),
        ("ml_train_request_model",   r"MLTrainRequest"),
        ("ml_predict_request_model", r"MLPredictRequest"),
    ]:
        found = bool(main_content and re.search(pattern, main_content))
        results[check] = found
        if not found:
            issues.append({"check": check, "reason": f"Pattern '{pattern}' not found in python-api/main.py"})

    # ── Artifacts directory ───────────────────────────────────────────────────
    artifacts_dir = os.path.join("python-api", "ml", "artifacts")
    results["artifacts_dir_exists"] = os.path.isdir(artifacts_dir)
    if not results["artifacts_dir_exists"]:
        issues.append({"check": "artifacts_dir_exists", "reason": f"Directory {artifacts_dir} does not exist"})

    # ── .gitignore ────────────────────────────────────────────────────────────
    gitignore = read_file(".gitignore")
    results["pkl_in_gitignore"] = bool(gitignore and "*.pkl" in gitignore)
    if not results["pkl_in_gitignore"]:
        issues.append({"check": "pkl_in_gitignore", "reason": "*.pkl not in .gitignore — model artifacts may be committed accidentally"})

    results["gitkeep_in_artifacts"] = os.path.isfile(os.path.join(artifacts_dir, ".gitkeep"))
    if not results["gitkeep_in_artifacts"]:
        issues.append({"check": "gitkeep_in_artifacts", "reason": f"{artifacts_dir}/.gitkeep not found — empty dir may not be tracked in git"})

    # ── Edge contract validator ───────────────────────────────────────────────
    contracts = read_file("validate_edge_contracts.py")

    results["batch_risk_in_contracts"] = bool(contracts and "batch-risk-scoring" in contracts)
    if not results["batch_risk_in_contracts"]:
        issues.append({"check": "batch_risk_in_contracts", "reason": "'batch-risk-scoring' not in validate_edge_contracts.py ALL_FUNCTIONS"})

    results["retrain_in_contracts"] = bool(contracts and "trigger-ml-retrain" in contracts)
    if not results["retrain_in_contracts"]:
        issues.append({"check": "retrain_in_contracts", "reason": "'trigger-ml-retrain' not in validate_edge_contracts.py ALL_FUNCTIONS"})

    # ── Schema validator ──────────────────────────────────────────────────────
    schema = read_file("validate_schema.py")

    results["asset_risk_in_schema_tables"] = bool(schema and "asset_risk_scores" in schema)
    if not results["asset_risk_in_schema_tables"]:
        issues.append({"check": "asset_risk_in_schema_tables", "reason": "'asset_risk_scores' not in validate_schema.py CORE_TABLES"})

    results["predictive_in_schema_pages"] = bool(schema and "predictive.html" in schema)
    if not results["predictive_in_schema_pages"]:
        issues.append({"check": "predictive_in_schema_pages", "reason": "'predictive.html' not in validate_schema.py LIVE_PAGES"})

    # ── Assistant validator ───────────────────────────────────────────────────
    assistant_v = read_file("validate_assistant.py")
    results["predictive_in_assistant_tools"] = bool(assistant_v and '"predictive"' in assistant_v)
    if not results["predictive_in_assistant_tools"]:
        issues.append({"check": "predictive_in_assistant_tools", "reason": "'predictive' not in validate_assistant.py LIVE_TOOL_PAGES"})

    # ── nav-hub.js ────────────────────────────────────────────────────────────
    nav = read_file("nav-hub.js")
    results["predictive_in_nav_hub"] = bool(nav and "predictive.html" in nav)
    if not results["predictive_in_nav_hub"]:
        issues.append({"check": "predictive_in_nav_hub", "reason": "'predictive.html' not in nav-hub.js TOOLS array"})

    # ── companion-launcher.js ────────────────────────────────────────────────────────
    fai = read_file("companion-launcher.js")
    results["predictive_in_floating_ai"] = bool(fai and "path.includes('predictive')" in fai)
    if not results["predictive_in_floating_ai"]:
        issues.append({"check": "predictive_in_floating_ai", "reason": "path.includes('predictive') context entry missing in companion-launcher.js"})

    # ── Summary ───────────────────────────────────────────────────────────────
    passed = sum(1 for v in results.values() if v)
    total  = len(results)
    fail_count = len(issues)

    with open("ml_report.json", "w", encoding="utf-8") as f:
        json.dump({"validator": "validate_ml", "total": total, "passed": passed,
                   "failed": fail_count, "issues": issues}, f, indent=2)

    label = "PASS" if fail_count == 0 else "FAIL"
    print(f"\nML Validator: {label}  ({passed}/{total} checks)")
    print(f"  {len(FEATURE_COLS)} feature columns, {total} registration checks\n")

    n_pass, n_skip, n_fail = format_result(list(CHECKS.keys()), CHECKS, issues)

    if fail_count == 0:
        print("  All ML layer checks passed.")

    return fail_count


if __name__ == "__main__":
    sys.exit(run())
