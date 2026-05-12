"""
Tier C contract regression validator
====================================
Runs each canonical_agent_contracts schema against synthetic good + bad
fixtures and confirms the JSON Schema correctly accepts/rejects each.

This is the CI tripwire that catches schema drift: if someone edits a
schema in canonical_agent_contracts (or registers a new contract) the
fixture suite re-runs against every contract_id and FAILs if a known-good
fixture is now rejected, or a known-bad fixture now passes.

The fixtures mirror real production output shapes:
  - analytics_action_plan_v1: { summary, this_week[], watch_list[] }
  - next_failure_forecast_v1: { predictions[], high_risk, medium_risk, total_tracked }
  - parts_stockout_v1: { stockout_risk[], at_risk_count, period_days }
  - health_score_v1: per-row v_risk_truth-shaped object
  - anomaly_baseline_v1: { baselines[], anomalies[], anomaly_count, machines_tracked }
  - parts_spike_v1: { spikes[], note? }
  - priority_ranking_v1: { ranking[], p1_count, p2_count, top_priority }

Layer 1: every registered contract has a fixture (no contract goes untested)
Layer 2: every good fixture validates
Layer 3: every bad fixture is rejected

Usage:  python validate_tier_c_contracts.py
Output: tier_c_contracts_report.json
"""
from __future__ import annotations

import json
import os
import re
import sys
import glob

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

try:
    from jsonschema import Draft7Validator
    JSONSCHEMA_AVAILABLE = True
except ImportError:
    JSONSCHEMA_AVAILABLE = False

from validator_utils import format_result, read_file


# Fixtures: contract_id → (good_example, bad_example, why_bad)
FIXTURES = {
    "analytics_action_plan_v1": (
        {"summary": "Focus on high-risk assets.",
         "this_week": ["Perform urgent PM on HPU-001"],
         "watch_list": ["HPU-001 - critical risk"]},
        {"summary": "No this_week field present"},
        "missing required this_week and watch_list — would be silently rendered as empty arrays today",
    ),
    "next_failure_forecast_v1": (
        {"predictions": [
            {"machine": "PMP-001", "predicted_next": "2026-06-01", "risk": "HIGH"}
         ], "high_risk": 1, "medium_risk": 0, "total_tracked": 1},
        {"predictions": [
            {"machine": "PMP-001", "risk": "EMERGENCY"}  # invalid enum
         ]},
        "risk enum must be HIGH/MEDIUM/LOW; EMERGENCY would slip through and break dashboard tier coloring",
    ),
    "parts_stockout_v1": (
        {"stockout_risk": [
            {"part_name": "Bearing 6203", "qty_on_hand": 2, "days_until_stockout": 14, "urgency": "CRITICAL"}
         ], "at_risk_count": 1, "period_days": 90},
        {"reorder": []},  # wrong key (the OLD schema)
        "uses 'reorder' instead of 'stockout_risk' — was the original wrong schema before realign",
    ),
    "health_score_v1": (
        {"asset_name": "PMP-001", "risk_score": 0.75, "risk_level": "high",
         "health_score": 25, "mtbf_days": 18, "days_until_failure": 5},
        {"asset_name": 123},  # wrong type
        "asset_name must be string; numeric ID would fail join lookup downstream",
    ),
    "anomaly_baseline_v1": (
        {"baselines": [{"machine": "PMP-001", "mean": 50, "stddev": 5}],
         "anomalies": [{"machine": "PMP-001", "value": 78, "deviation_sigma": 5.6, "quality_flag": "ANOMALY"}],
         "anomaly_count": 1, "machines_tracked": 1},
        {"baselines": [], "anomalies": [{"value": 78}]},  # missing machine
        "anomaly without machine name — dashboard can't show 'which machine is anomalous'",
    ),
    "parts_spike_v1": (
        {"spikes": [{"part_name": "Oil filter", "current_rate": 8.0, "previous_rate": 2.0, "spike_factor": 4.0}]},
        {"spikes": [{"current_rate": 8.0}]},  # missing part_name
        "spike row without part_name — can't reorder what you can't identify",
    ),
    "priority_ranking_v1": (
        {"ranking": [{"machine": "PMP-001", "priority": "P1", "priority_score": 0.92}],
         "p1_count": 1, "p2_count": 0, "top_priority": "PMP-001"},
        {"ranking": [{"machine": "PMP-001", "priority": "URGENT"}]},  # invalid enum
        "priority must be P1/P2/P3/P4; freeform string breaks dashboard sort/filter",
    ),
}


def load_registered_schemas() -> dict:
    """Parse canonical_agent_contracts INSERT + UPDATE blocks across all
    migrations and return the LATEST registered schema per contract_id."""
    schemas: dict[str, dict] = {}
    # First pass: INSERT VALUES tuples (contract_id, agent, version, json_schema, ...)
    INSERT_RE = re.compile(
        r"INSERT\s+INTO\s+(?:public\.)?canonical_agent_contracts[^;]*?VALUES\s*([\s\S]*?);",
        re.IGNORECASE,
    )
    # Each tuple opens with ('contract_id', 'agent', NUM, 'json_schema' or '...'::jsonb, ...)
    TUPLE_RE = re.compile(
        r"\(\s*'([a-z_][a-z0-9_]*)'\s*,\s*'[^']+'\s*,\s*\d+\s*,\s*'((?:[^'\\]|\\.|'')*)'::jsonb",
        re.DOTALL,
    )
    UPDATE_RE = re.compile(
        r"UPDATE\s+(?:public\.)?canonical_agent_contracts\s+SET\s+json_schema\s*=\s*'((?:[^'\\]|\\.|'')*)'::jsonb[\s\S]*?WHERE\s+contract_id\s*=\s*'([a-z_0-9]+)'",
        re.IGNORECASE,
    )
    for path in sorted(glob.glob(os.path.join("supabase", "migrations", "*.sql"))):
        sql = read_file(path) or ""
        if "canonical_agent_contracts" not in sql:
            continue
        for m in INSERT_RE.finditer(sql):
            block = m.group(1)
            for tup in TUPLE_RE.finditer(block):
                cid    = tup.group(1)
                schema = tup.group(2).replace("''", "'")  # SQL '' -> '
                try:
                    schemas[cid] = json.loads(schema)
                except json.JSONDecodeError:
                    pass
        # Apply any UPDATE statements (these override INSERT seed)
        for um in UPDATE_RE.finditer(sql):
            schema = um.group(1).replace("''", "'")
            cid    = um.group(2)
            try:
                schemas[cid] = json.loads(schema)
            except json.JSONDecodeError:
                pass
    return schemas


def main():
    print("\nTier C Contract Regression Validator")
    print("=" * 60)

    if not JSONSCHEMA_AVAILABLE:
        print("\033[93m  SKIP: jsonschema package not installed (pip install jsonschema)\033[0m")
        with open("tier_c_contracts_report.json", "w", encoding="utf-8") as f:
            json.dump({"validator": "tier_c_contracts", "skipped": "jsonschema not installed"}, f)
        sys.exit(0)

    schemas = load_registered_schemas()
    print(f"  {len(schemas)} contracts loaded from canonical_agent_contracts migrations")
    print(f"  {len(FIXTURES)} fixture pairs defined\n")

    CHECK_NAMES  = ["fixture_coverage", "good_accepted", "bad_rejected"]
    CHECK_LABELS = {
        "fixture_coverage": "L1  Every registered contract has a fixture pair",
        "good_accepted":    "L2  Every good fixture validates against its schema",
        "bad_rejected":     "L3  Every bad fixture is rejected by its schema",
    }
    issues: list[dict] = []
    failures = {"good_accepted": [], "bad_rejected": []}

    # L1: every registered contract must have a fixture
    missing_fixtures = [c for c in schemas if c not in FIXTURES]
    if missing_fixtures:
        issues.append({
            "check": "fixture_coverage", "skip": False,
            "reason": f"Registered contracts without fixtures: {missing_fixtures}. "
                      f"Add good + bad examples to FIXTURES in validate_tier_c_contracts.py.",
        })

    # L2 + L3: run each fixture pair through Draft7Validator
    for contract_id, (good, bad, why) in FIXTURES.items():
        schema = schemas.get(contract_id)
        if not schema:
            print(f"  \033[93mSKIP\033[0m {contract_id} — not registered yet")
            continue
        try:
            validator = Draft7Validator(schema)
        except Exception as e:
            issues.append({
                "check": "good_accepted", "skip": False,
                "reason": f"{contract_id} schema is itself malformed: {e}",
            })
            continue

        good_errors = list(validator.iter_errors(good))
        if good_errors:
            failures["good_accepted"].append({
                "contract_id": contract_id,
                "errors": [e.message for e in good_errors[:3]],
            })

        bad_errors = list(validator.iter_errors(bad))
        if not bad_errors:
            failures["bad_rejected"].append({
                "contract_id": contract_id,
                "expected_to_fail_because": why,
            })

    if failures["good_accepted"]:
        issues.append({
            "check": "good_accepted", "skip": False,
            "reason": f"{len(failures['good_accepted'])} good fixtures rejected — schema is too strict OR fixture is wrong: "
                      f"{json.dumps(failures['good_accepted'][:3])}",
        })
    if failures["bad_rejected"]:
        issues.append({
            "check": "bad_rejected", "skip": False,
            "reason": f"{len(failures['bad_rejected'])} bad fixtures NOT rejected — schema is too lenient (regression slipped through): "
                      f"{json.dumps(failures['bad_rejected'][:3])}",
        })

    n_pass, n_warn, n_fail = format_result(CHECK_NAMES, CHECK_LABELS, issues)

    total = len(CHECK_NAMES)
    if n_fail == 0:
        print(f"\033[92m\n  All {total} checks passed.\033[0m")
    else:
        print(f"\033[91m\n  {n_pass} PASS  {n_warn} WARN  {n_fail} FAIL\033[0m")

    report = {
        "validator":      "tier_c_contracts",
        "total_checks":   total,
        "passed":         n_pass,
        "warned":         n_warn,
        "failed":         n_fail,
        "n_registered":   len(schemas),
        "n_fixtures":     len(FIXTURES),
        "missing_fixtures": missing_fixtures,
        "failures":       failures,
        "issues":         [i for i in issues if not i.get("skip")],
    }
    with open("tier_c_contracts_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    sys.exit(1 if n_fail > 0 else 0)


if __name__ == "__main__":
    main()
