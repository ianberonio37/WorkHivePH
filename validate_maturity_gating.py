"""validate_maturity_gating.py — Phase 0.5 of STRATEGIC_ROADMAP.md.

Enforces the epistemic gating layer architecturally. The doctrine says:
"We never promise predictive analytics on insufficient data. We surface
the gap honestly instead of producing charts of garbage."

For that doctrine to actually bind in the codebase, every page that
renders predictive / sensor / benchmark output must:

  1. Load `maturity-gate.js` before its main script block
  2. Call `checkMaturityGate(db, HIVE_ID, requiredStair)` somewhere in
     its init path
  3. Wire `renderMaturityHonestEmpty(...)` as the gate-blocked branch

The validator scans the configured gated pages and reports any that skip
any of these three contract points.

Layers:
  L1  Every GATED_PAGES entry exists on disk
  L2  Every page loads `maturity-gate.js`
  L3  Every page calls `checkMaturityGate(`
  L4  Every page calls `renderMaturityHonestEmpty(`

Add a page to GATED_PAGES whenever a new surface ships predictive output
or peer benchmarks. The validator will then ratchet that page's contract.

Skills consulted:
  architect (contract validator pattern, baseline regression detection)
  predictive-analytics ("rules first, then ML" doctrine — never surface
    prediction on insufficient data)
  qa-tester (gated pages need a smoke test that the honest-empty path
    renders without crashing the page)
"""
from __future__ import annotations

import os
import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

ROOT = Path(__file__).parent

# Pages that surface output requiring a minimum maturity stair. Each entry is
# a tuple (filename, required_stair). When a new gated surface ships (e.g. the
# upcoming Anomaly Engine 2.0 at Stair 3+), add it here.
GATED_PAGES: list[tuple[str, int]] = [
    # predictive.html removed 2026-07-01 — page deleted; per-asset risk-360 merged into asset-hub.
    ("ph-intelligence.html", 3),
    # analytics.html — predictive + prescriptive phases are gated, but the
    # descriptive phase is fine at any stair. Banner-only gating planned in
    # Phase 0.3b; not yet enforced.
]

REQUIRED_SCRIPT_TAG = 'maturity-gate.js'
REQUIRED_GATE_CALL  = 'checkMaturityGate('
REQUIRED_RENDER_CALL = 'renderMaturityHonestEmpty('


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def check_pages_exist() -> list[dict]:
    issues: list[dict] = []
    for name, _stair in GATED_PAGES:
        p = ROOT / name
        if not p.exists():
            issues.append({
                "check": "pages_exist",
                "page":  name,
                "reason": f"GATED_PAGES references {name} but the file does not exist on disk. Remove from GATED_PAGES or restore the page.",
            })
    return issues


def check_script_tag_loaded() -> list[dict]:
    issues: list[dict] = []
    for name, stair in GATED_PAGES:
        p = ROOT / name
        if not p.exists():
            continue
        sql = _read(p)
        if REQUIRED_SCRIPT_TAG not in sql:
            issues.append({
                "check": "script_tag_loaded",
                "page":  name,
                "reason": (
                    f"{name} gates at Stair {stair} but does not load "
                    f"<script src=\"{REQUIRED_SCRIPT_TAG}\"></script>. "
                    f"Add it after utils.js so checkMaturityGate is available."
                ),
            })
    return issues


def check_gate_call() -> list[dict]:
    issues: list[dict] = []
    for name, stair in GATED_PAGES:
        p = ROOT / name
        if not p.exists():
            continue
        sql = _read(p)
        if REQUIRED_GATE_CALL not in sql:
            issues.append({
                "check": "gate_call_present",
                "page":  name,
                "reason": (
                    f"{name} loads maturity-gate.js but never calls "
                    f"{REQUIRED_GATE_CALL}. The page must check the hive's "
                    f"current stair against the required stair "
                    f"({stair}) in its init path."
                ),
            })
    return issues


def check_honest_empty_render() -> list[dict]:
    issues: list[dict] = []
    for name, _stair in GATED_PAGES:
        p = ROOT / name
        if not p.exists():
            continue
        sql = _read(p)
        if REQUIRED_GATE_CALL not in sql:
            continue  # already flagged by L3; skip cascade
        if REQUIRED_RENDER_CALL not in sql:
            issues.append({
                "check": "honest_empty_render",
                "page":  name,
                "reason": (
                    f"{name} calls {REQUIRED_GATE_CALL} but never invokes "
                    f"{REQUIRED_RENDER_CALL}. The gate-blocked branch must "
                    f"render the honest empty state, not silently pass."
                ),
            })
    return issues


def run() -> dict:
    issues: list[dict] = []
    issues.extend(check_pages_exist())
    issues.extend(check_script_tag_loaded())
    issues.extend(check_gate_call())
    issues.extend(check_honest_empty_render())

    layers = [
        {"layer": "L1", "label": "Every GATED_PAGES entry exists on disk"},
        {"layer": "L2", "label": "Every gated page loads maturity-gate.js"},
        {"layer": "L3", "label": "Every gated page calls checkMaturityGate("},
        {"layer": "L4", "label": "Every gated page calls renderMaturityHonestEmpty("},
    ]

    return {
        "validator":    "maturity_gating",
        "total_checks": len(layers),
        "passed":       len(layers) - (1 if issues else 0),
        "failed":       1 if issues else 0,
        "warned":       0,
        "layers":       layers,
        "gated_pages":  [{"page": n, "required_stair": s} for n, s in GATED_PAGES],
        "issues":       issues,
        "warnings":     [],
    }


def main() -> int:
    result = run()
    issues = result["issues"]
    print(f"\nMaturity Gating Validator ({len(result['layers'])}-layer)")
    print("=" * 60)
    for layer in result["layers"]:
        print(f"  [{layer['layer']}] {layer['label']}")
    print()
    for page in result["gated_pages"]:
        print(f"  GATED: {page['page']} (Stair {page['required_stair']}+)")
    print()
    if issues:
        print(f"  \033[91m{len(issues)} FAIL\033[0m")
        for i in issues:
            print(f"  [FAIL] [{i['check']}]  {i['page']}: {i['reason']}")
        return 1
    print(f"  \033[92mAll {len(result['layers'])} checks passed.\033[0m")
    return 0


if __name__ == "__main__":
    import json

    out = run()
    out_path = ROOT / "maturity_gating_report.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    sys.exit(main())
